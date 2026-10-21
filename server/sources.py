import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone,timedelta

from fastapi import APIRouter,HTTPException,Request,UploadFile
from pydantic import BaseModel,Field
from sqlalchemy import select,update,or_

from .auth import Auth
from .common import DB,owned,data,record
from .db import SourceLink,SourceImport,Project,User,StoredFile,now,uid
from .files import store

router=APIRouter(prefix='/api')
EXTENSIONS={'.md','.txt','.pdf','.docx','.xlsx','.html','.htm','.pptx','.drawio','.png','.jpg','.jpeg','.m4a','.mp3','.wav','.ogg','.webm'}
EXCLUDED={'node_modules','venv','.venv','__pycache__','site-packages','vendor','runtime','bin','lib','libs','dist','build'}

def business_file(relative):
    if any(part.startswith('.') or part.lower() in EXCLUDED for part in relative.parts):return False
    parts=[part.lower() for part in relative.parts]
    if any(parts[index:index+2]==['projects','assets'] for index in range(len(parts)-1)):return False
    if relative.name=='项目进展.md':return False
    stem=relative.stem.lower()
    if stem.startswith(('license','licence','third_party','third-party','copying','notice')):return False
    return relative.suffix.lower() in EXTENSIONS


def link_data(link):
    return data(link,('sync_token','sync_expires_at'))


def idle():
    return or_(SourceLink.sync_token.is_(None),SourceLink.sync_expires_at<now())


def roots():
    try:
        mapping=json.loads(os.getenv('DOCUMENT_SOURCES_JSON','{}'))
        return {str(k):Path(v).resolve() for k,v in mapping.items() if isinstance(v,str)}
    except (ValueError,AttributeError):return {}


def folder(key,subdirectory):
    root=roots().get(key)
    if root is None:raise HTTPException(422,'文档来源未配置')
    candidate=(root/subdirectory).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_dir():
        raise HTTPException(422,'文档目录无效')
    return candidate


class LinkCreate(BaseModel):
    source_key:str=Field(min_length=1,max_length=160)
    subdirectory:str=Field(default='',max_length=240)


@router.get('/document-sources')
def available(user:Auth):
    return [{'key':k} for k in roots()]


@router.get('/projects/{project_id}/sources')
def links(project_id:str,db:DB,user:Auth):
    owned(db,Project,project_id,user)
    return [link_data(row) for row in db.scalars(select(SourceLink).where(SourceLink.project_id==project_id))]


@router.post('/projects/{project_id}/sources',status_code=201)
def create(project_id:str,body:LinkCreate,db:DB,user:Auth):
    project=owned(db,Project,project_id,user)
    if body.source_key=='codes' and not user.is_admin:
        expected=(Path(project.directory_path)/'docs').resolve() if project.directory_path else None
        if expected is None or folder(body.source_key,body.subdirectory)!=expected:raise HTTPException(403,'无权连接该目录')
    folder(body.source_key,body.subdirectory)
    row=SourceLink(project_id=project_id,**body.model_dump())
    db.add(row);db.flush()
    record(db,project_id,user,'source','连接项目文档',detail=body.source_key,source_id=row.id)
    return link_data(row)


async def sync_content(request,db,user,link):
    if not link.enabled:raise HTTPException(409,'文档连接已断开')
    project=owned(db,Project,link.project_id,user)
    directory=folder(link.source_key,link.subdirectory)
    checked,total,updates=0,0,0
    membership_changed=False
    seen=set();files=[];total_bytes=0
    for scanned,file in enumerate(directory.rglob('*'),1):
        if scanned>10000:raise HTTPException(413,'目录内容过多，请选择子目录')
        relative=file.relative_to(directory)
        if not business_file(relative):continue
        if file.is_symlink() or file.is_junction() or not file.is_file():continue
        if not file.resolve().is_relative_to(directory):raise HTTPException(422,'文档路径越界')
        from .docs_structure import managed_file
        if managed_file(file):continue
        files.append(file);total_bytes+=file.stat().st_size
        if len(files)>1000 or total_bytes>1024*1024*1024:raise HTTPException(413,'单次同步最多1000份文档、1GB')
    for file in sorted(files,key=lambda f:(f.stat().st_mtime,f.as_posix())):
        relative=file.relative_to(directory).as_posix()
        if len(relative)>240:raise HTTPException(422,'文档路径过长')
        seen.add(relative)
        payload=file.read_bytes()
        value=hashlib.sha256(payload).hexdigest()
        prior=db.get(SourceImport,(link.id,relative))
        if prior is None or prior.sha256!=value:
            import io
            name='['+link.source_key+'] '+relative.replace('/',' · ')
            if len(name)>255:raise HTTPException(422,'文档名称过长')
            result=await store(UploadFile(file=io.BytesIO(payload),filename=name),request,db,user,project=project,source_import=link.source_key=='codes')
            stored=db.get(StoredFile,result['id'])
            stored.source_modified_at=datetime.fromtimestamp(file.stat().st_mtime,timezone.utc).isoformat(timespec='microseconds')
            stored.source_time_basis='file_modified'
            if stored.parse_status=='pending_asr':
                transcript=file.with_name(file.stem+'-FunASR转写稿.md')
                if transcript.is_file() and not transcript.is_symlink() and transcript.stat().st_size<=4*1024*1024:
                    try:
                        original_text=transcript.read_text(encoding='utf-8-sig')
                        if original_text.strip() and len(original_text)<=1000000:
                            stored.extracted_text=original_text;stored.parse_status='ready'
                    except UnicodeError:pass
            if stored.mime.startswith('audio/'):
                from .recording_imports import import_audio
                import_audio(db,stored,user)
            if prior:
                prior.sha256,prior.file_id,prior.missing=value,result['id'],False
            else:db.add(SourceImport(link_id=link.id,relative_path=relative,sha256=value,file_id=result['id']))
            # Release SQLite writes between documents so recording blocks can commit.
            # Each checkpoint is fenced by the current source lease.
            guarded=db.execute(update(SourceLink).where(SourceLink.id==link.id,SourceLink.sync_token==link.sync_token,SourceLink.sync_expires_at>now()).values(sync_expires_at=(datetime.now(timezone.utc)+timedelta(seconds=660)).isoformat(timespec='microseconds'))).rowcount
            if not guarded:raise HTTPException(409,'同步授权已更新，请重新同步')
            db.commit()
            updates+=1
        elif prior.missing:prior.missing=False;membership_changed=True
        if file.suffix.lower() in ('.md','.txt'):
            text=payload.decode('utf-8-sig',errors='replace')
            tasks=re.findall(r'^\s*[-*]\s+\[([ xX])\]',text,re.M)
            total+=len(tasks);checked+=sum(x.lower()=='x' for x in tasks)
    missing=0
    for prior in db.scalars(select(SourceImport).where(SourceImport.link_id==link.id)):
        if prior.relative_path not in seen:
            missing+=1
            if not prior.missing:
                record(db,project.id,user,'source','来源文件已移除',detail=prior.relative_path,source_id=prior.file_id)
                prior.missing=True
                membership_changed=True
    if membership_changed:
        from .automation import enqueue_meeting
        from .db import Meeting
        for m in db.scalars(select(Meeting).where(Meeting.owner_id==user.id,Meeting.status=='finished')):enqueue_meeting(db,m,user)
    link.status='stale' if missing else 'synced';link.last_error='来源有已移除文件' if missing else '';link.last_synced_at=now()
    link.summary=json.dumps({'document_checked':checked,'document_total':total,'files':len(files),'missing':missing},ensure_ascii=False)
    if updates:record(db,project.id,user,'source','同步项目文档',detail=f'{updates} 份文件有更新',source_id=link.id)
    db.flush()
    return {'updated_files':updates,'link':link_data(link)}


async def sync_link(request,db,user,link):
    owned(db,Project,link.project_id,user)
    if not link.enabled:raise HTTPException(409,'文档连接已断开')
    link_id=link.id
    token=uid()
    expires=(datetime.now(timezone.utc)+timedelta(seconds=660)).isoformat(timespec='microseconds')
    with request.app.state.sessions() as claim:
        changed=claim.execute(update(SourceLink).where(SourceLink.id==link_id,SourceLink.enabled.is_(True),idle()).values(sync_token=token,sync_expires_at=expires)).rowcount
        claim.commit()
    if not changed:raise HTTPException(409,'文档正在同步，请稍后重试')
    succeeded=False
    try:
        db.refresh(link)
        result=await asyncio.wait_for(sync_content(request,db,user,link),600)
        guarded=db.execute(update(SourceLink).where(SourceLink.id==link_id,SourceLink.sync_token==token,SourceLink.sync_expires_at>now()).values(sync_token=None,sync_expires_at=None)).rowcount
        if not guarded:raise HTTPException(409,'同步已过期，请重新同步')
        db.commit()
        from .automation import write_progress
        write_progress(request.app,link.project_id)
        from .project_analysis import enqueue_project
        from .docs_structure import export_state
        enqueue_project(db,db.get(Project,link.project_id));db.commit()
        export_state(request.app,link.project_id)
        succeeded=True
        return result
    except asyncio.TimeoutError:
        db.rollback()
        raise HTTPException(504,'同步超时，请缩小目录后重试')
    except BaseException:
        db.rollback()
        raise
    finally:
        if not succeeded:
            with request.app.state.sessions() as claim:
                claim.execute(update(SourceLink).where(SourceLink.id==link_id,SourceLink.sync_token==token).values(sync_token=None,sync_expires_at=None,status='failed',last_error='同步失败，请检查来源后重试'))
                claim.commit()


@router.post('/sources/{link_id}/sync')
async def sync(link_id:str,request:Request,db:DB,user:Auth):
    link=db.get(SourceLink,link_id)
    if link is None:raise HTTPException(404,'文档连接不存在')
    owned(db,Project,link.project_id,user)
    return await sync_link(request,db,user,link)


@router.delete('/sources/{link_id}',status_code=204)
def disable(link_id:str,db:DB,user:Auth):
    link=db.get(SourceLink,link_id)
    if link is None:raise HTTPException(404,'文档连接不存在')
    owned(db,Project,link.project_id,user)
    changed=db.execute(update(SourceLink).where(SourceLink.id==link.id,idle()).values(enabled=False,status='disabled')).rowcount
    if not changed:raise HTTPException(409,'文档正在同步，请稍后断开')
    record(db,link.project_id,user,'source','断开文档连接',source_id=link.id)


@router.post('/sources/{link_id}/reconnect')
def reconnect(link_id:str,db:DB,user:Auth):
    link=db.get(SourceLink,link_id)
    if link is None:raise HTTPException(404,'文档连接不存在')
    owned(db,Project,link.project_id,user)
    folder(link.source_key,link.subdirectory)
    changed=db.execute(update(SourceLink).where(SourceLink.id==link.id,idle()).values(enabled=True,status='pending',last_error='')).rowcount
    if not changed:raise HTTPException(409,'文档正在同步，请稍后重试')
    record(db,link.project_id,user,'source','重新连接项目文档',detail=link.source_key,source_id=link.id)
    db.flush();db.refresh(link)
    return link_data(link)


def synchronize_all(app):
    with app.state.sessions() as db:
        ids=list(db.scalars(select(SourceLink.id).where(SourceLink.enabled.is_(True))))
    for link_id in ids:
        try:
            with app.state.sessions() as db:
                link=db.get(SourceLink,link_id)
                project=db.get(Project,link.project_id)
                user=db.get(User,project.owner_id)
                asyncio.run(sync_link(SimpleNamespace(app=app),db,user,link))
                db.commit()
        except Exception:
            # A failed owner releases its own claim. Busy/disabled workers never
            # override another worker's committed result or connection status.
            import logging
            logging.getLogger(__name__).warning('Document sync did not complete: %s',link_id)


async def background_sync(app):
    while True:
        await asyncio.sleep(60)
        await asyncio.to_thread(synchronize_all,app)
