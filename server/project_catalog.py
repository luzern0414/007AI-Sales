"""Authorized one-level project discovery; business input stays under docs."""
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter,HTTPException,Request
from sqlalchemy import select

from .auth import Auth
from .common import DB,data,record
from .db import Project,SourceLink,User

router=APIRouter(prefix='/api')


def root():
    path=Path(os.getenv('PROJECTS_ROOT','D:/Codes')).resolve()
    if not path.is_dir():raise HTTPException(503,'项目目录不可用')
    return path


def safe_directory(name):
    if not name or name in ('.','..') or Path(name).name!=name or any(c in name for c in '/\\:\x00'):
        raise HTTPException(422,'目录名称无效')
    base=root();candidate=base/name
    if candidate.is_symlink() or candidate.is_junction() or candidate.resolve().parent!=base:
        raise HTTPException(422,'目录不可用')
    return candidate


def configure_source():
    from .sources import roots
    mapping={k:str(v) for k,v in roots().items()}
    mapping['codes']=str(root())
    os.environ['DOCUMENT_SOURCES_JSON']=json.dumps(mapping,ensure_ascii=False)


def attach(db,p,directory,create=False):
    if db.scalar(select(Project.id).where(Project.directory_path==str(directory.resolve()),Project.id!=p.id)):
        raise HTTPException(409,'目录已绑定其他项目')
    if create:directory.mkdir(exist_ok=True)
    if not directory.is_dir():raise HTTPException(422,'目录不存在')
    docs=directory/'docs'
    if docs.is_symlink() or docs.is_junction():raise HTTPException(422,'文档目录不可用')
    docs.mkdir(exist_ok=True)
    from .docs_structure import scaffold
    scaffold(docs,p.name)
    p.directory_path=str(directory.resolve())
    configure_source()
    link=db.scalar(select(SourceLink).where(SourceLink.project_id==p.id,SourceLink.source_key=='codes'))
    if link is None:
        db.add(SourceLink(project_id=p.id,source_key='codes',subdirectory=directory.name+'/docs'))
    db.flush()


@router.get('/project-directories')
def directories(db:DB,user:Auth):
    if not user.is_admin:raise HTTPException(403,'仅管理员可管理本机目录')
    mapping={p.directory_path:p.id for p in db.scalars(select(Project).where(Project.directory_path.is_not(None)))}
    base=root()
    return {'root':str(base),'directories':[{'name':d.name,'path':str(d),'has_docs':(d/'docs').is_dir(),
        'bound_project_id':mapping.get(str(d.resolve()))} for d in sorted(base.iterdir())
        if re.match(r'^\d+.+',d.name) and d.is_dir() and not d.is_symlink() and not d.is_junction()]}


async def discover_for(app,db,user):
    if not user.is_admin:raise HTTPException(403,'仅管理员可导入本机项目')
    imported=existing=0;errors=[]
    from .sources import sync_link
    for directory in sorted(root().iterdir()):
        if not re.match(r'^\d+.+',directory.name) or not directory.is_dir() or directory.is_symlink() or directory.is_junction():continue
        p=db.scalar(select(Project).where(Project.directory_path==str(directory.resolve())))
        if p:
            if p.owner_id!=user.id:continue
            from .docs_structure import scaffold
            scaffold(directory/'docs',p.name)
            existing+=1
        else:
            p=Project(owner_id=user.id,name=directory.name)
            db.add(p);db.flush();attach(db,p,directory)
            record(db,p.id,user,'project','导入项目目录')
            imported+=1
        db.commit()
        link=db.scalar(select(SourceLink).where(SourceLink.project_id==p.id,SourceLink.source_key=='codes'))
        if link and link.enabled:
            try:await sync_link(SimpleNamespace(app=app),db,user,link)
            except HTTPException as e:
                db.rollback();errors.append({'project_id':p.id,'message':e.detail})
    for p in db.scalars(select(Project).where(Project.owner_id==user.id,Project.directory_path.is_not(None))):
        if Path(p.directory_path).is_dir():continue
        for link in db.scalars(select(SourceLink).where(SourceLink.project_id==p.id,SourceLink.source_key=='codes')):
            link.status='failed';link.last_error='项目目录已移除或改名，请重新绑定'
    db.commit()
    return {'imported':imported,'existing':existing,'errors':errors}


@router.post('/projects/discover')
async def discover(request:Request,db:DB,user:Auth):
    return await discover_for(request.app,db,user)


async def background_discovery(app):
    import asyncio
    import logging
    def run():
        with app.state.sessions() as db:
            # The first administrator owns automatic local imports; existing bindings remain authoritative.
            user=db.scalar(select(User).where(User.is_admin.is_(True)).order_by(User.id).limit(1))
            if user:asyncio.run(discover_for(app,db,user))
    while True:
        if os.getenv('PROJECTS_ROOT'):
            try:await asyncio.to_thread(run)
            except Exception:logging.getLogger(__name__).warning('Project discovery did not complete')
        await asyncio.sleep(300)
