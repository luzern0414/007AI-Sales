import hashlib
import json
import subprocess
import sys
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select

from .auth import Auth
from .common import DB, data, owned, record
from .db import Project, Product, StoredFile, uid


def infer_origin(name):
    if any(x in name for x in ('客户提供','甲方提供')):return 'client'
    if any(x in name for x in ('我方提供','乙方提供','我方方案','我方报价')):return 'ours'
    return 'unknown'

router = APIRouter(prefix='/api')
LIMIT = 100 * 1024 * 1024
TYPES = {'.pdf': 'application/pdf', '.txt': 'text/plain', '.md': 'text/markdown', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.webm': 'audio/webm', '.zip': 'application/zip'}

TYPES.update({'.html':'text/html','.htm':'text/html','.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation','.drawio':'application/xml'})


async def store(file: UploadFile, request, db, user, project=None, product=None, source_import=False):
    name = Path((file.filename or '').replace('\\', '/')).name
    ext = Path(name).suffix.lower()
    if ext not in TYPES or len(name) > 255:
        raise HTTPException(422, '不支持此文件格式')
    key = uid() + ext
    path = request.app.state.storage / key
    size, digest = 0, hashlib.sha256()
    # Open before the cleanup scope so a key collision never removes another upload's file.
    try: output = path.open('xb')
    except FileExistsError:
        await file.close(); raise HTTPException(409, '存储冲突，请重试') from None
    try:
        with output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > LIMIT:
                    raise HTTPException(413, '文件超过100MB')
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if size == 0:
            raise HTTPException(422, '文件为空')
        with path.open('rb') as stream:
            header = stream.read(16)
        invalid_header=ext=='.pdf' and b'%PDF-' not in header
        invalid_header=invalid_header or (ext in ('.xlsx','.docx','.pptx','.zip') and not header.startswith(b'PK'))
        if invalid_header and not source_import:
            raise HTTPException(422, 'PDF文件无效')
        text, status = '', 'archived'
        if ext in ('.wav','.mp3','.m4a','.ogg','.webm'):status='pending_asr'
        if ext in ('.md','.txt','.pdf','.docx','.xlsx','.html','.htm','.pptx','.drawio','.png','.jpg','.jpeg'):
            try:
                process=await run_in_threadpool(subprocess.run,[sys.executable,'-m','server.parse_file',str(path)],capture_output=True,text=True,encoding='utf-8',timeout=90,cwd=Path(__file__).resolve().parents[1])
                parsed=json.loads(process.stdout)
                text,status=parsed['text'],parsed['status']
            except (OSError,subprocess.TimeoutExpired,ValueError,KeyError):
                status = 'failed'
        if invalid_header:text,status='','failed'
        if ext in ('.html','.htm') and (status!='ready' or not text.strip()) and not source_import:
            raise HTTPException(422,'网页文件没有可读取的正文')
        prior=db.scalar(select(StoredFile).where(StoredFile.project_id==(project.id if project else None),StoredFile.product_id==(product.id if product else None),StoredFile.name==name,StoredFile.owner_id==user.id).order_by(StoredFile.created_at.desc(),StoredFile.id.desc()))
        row = StoredFile(owner_id=user.id, project_id=project.id if project else None, product_id=product.id if product else None, name=name, mime=TYPES[ext], size=size, sha256=digest.hexdigest(), storage_key=key, extracted_text=text, parse_status=status,previous_version_id=prior.id if prior else None,file_version=prior.file_version+1 if prior else 1,origin=prior.origin if prior and prior.origin!='unknown' else infer_origin(name))
        db.add(row)
        db.flush()
        if project:
            from .automation import enqueue_file
            enqueue_file(db,row)
            if row.mime.startswith('audio/') and not source_import:
                from .recording_imports import import_audio
                import_audio(db,row,user)
            record(db, project.id, user, 'file', '上传文件：' + name, source_id=row.id)
            from .project_analysis import enqueue_project
            enqueue_project(db,project)
        if product:
            product.published = False
        return data(row, ('storage_key', 'extracted_text'))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.post('/projects/{project_id}/files', status_code=201)
async def upload_project(project_id: str, file: UploadFile, request: Request, db: DB, user: Auth):
    project = owned(db, Project, project_id, user)
    return await store(file, request, db, user, project=project)


@router.post('/products/{product_id}/files', status_code=201)
async def upload_product(product_id: str, file: UploadFile, request: Request, db: DB, user: Auth):
    product = owned(db, Product, product_id, user)
    if Path(file.filename or '').suffix.lower() not in ('.pdf','.docx','.pptx','.md','.txt'):
        raise HTTPException(422, '请选择产品资料文档')
    return await store(file, request, db, user, product=product)


@router.get('/files/{file_id}/download')
def download(file_id: str, request: Request, db: DB, user: Auth):
    row = db.get(StoredFile, file_id)
    if row is None or row.owner_id != user.id:
        raise HTTPException(404, '文件不存在')
    path = request.app.state.storage / row.storage_key
    if not path.is_file():
        raise HTTPException(410, '文件暂不可用')
    return FileResponse(path, filename=row.name, media_type=row.mime, headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})


def owned_file(db,file_id,user):
    row=db.get(StoredFile,file_id)
    if row is None or row.owner_id!=user.id:raise HTTPException(404,'文件不存在')
    return row


@router.get('/files/{file_id}/preview')
def preview(file_id:str,db:DB,user:Auth):
    row=owned_file(db,file_id,user)
    return {'id':row.id,'name':row.name,'mime':row.mime,'origin':row.origin,'status':row.parse_status,'markdown':row.extracted_text,'size':row.size}


from pydantic import BaseModel
from typing import Literal
class OriginUpdate(BaseModel):
    origin:Literal['unknown','client','ours']


@router.patch('/files/{file_id}/origin')
def update_origin(file_id:str,body:OriginUpdate,db:DB,user:Auth):
    row=owned_file(db,file_id,user);row.origin=body.origin
    if row.project_id:
        record(db,row.project_id,user,'file','确认资料来源',source_id=row.id,detail=body.origin)
        from .project_analysis import enqueue_project
        enqueue_project(db,db.get(Project,row.project_id),urgent=True)
    return {'id':row.id,'origin':row.origin}
