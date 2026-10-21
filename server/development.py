"""Daily local code evidence, isolated from customer-facing document events."""
import asyncio,hashlib,json,os,subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from fastapi import APIRouter,HTTPException,Request
from .auth import Auth
from .common import DB,owned
from .db import Project,DevelopmentDay,now

router=APIRouter(prefix='/api')
EXCLUDED={'docs','node_modules','data','output','.git','.venv','.venv-asr','.venv-asr-gpu','dist','build','vendor','third_party','third-party','external','target','result','__pycache__','.next','.cache','assets'}
EXTENSIONS={'.py','.ts','.tsx','.js','.jsx','.mjs','.vue','.go','.rs','.java','.cs','.sql','.css','.scss','.html','.prisma','.toml'}


def inventory(directory):
    result={}
    for root,dirs,files in os.walk(directory,followlinks=False):
        dirs[:]=[d for d in dirs if not d.startswith('.') and d.casefold() not in EXCLUDED and not (Path(root)/d).is_symlink() and not (Path(root)/d).is_junction()]
        for name in files:
            path=Path(root)/name
            if path.suffix.lower() not in EXTENSIONS or name.startswith('.') or any(x in name.casefold() for x in ('secret','apikey','credential','private-key')):continue
            if path.is_symlink() or path.stat().st_size>2*1024*1024:continue
            if len(result)>=20000:raise ValueError('代码目录超过扫描容量')
            result[path.relative_to(directory).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def scan_project(app,pid,day=None):
    day=day or datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    with app.state.sessions() as db:
        existing=db.get(DevelopmentDay,(pid,day))
        if existing:return json.loads(existing.result_json)
        p=db.get(Project,pid)
        if not p or not p.directory_path:return None
        directory=Path(p.directory_path)
        if not directory.is_dir() or directory.is_symlink() or directory.is_junction():return None
        from .project_catalog import root
        if not app.state.testing and directory.resolve().parent!=root():raise ValueError('项目代码目录越界')
        current=inventory(directory)
        previous=db.scalar(select(DevelopmentDay).where(DevelopmentDay.project_id==pid,DevelopmentDay.day<day).order_by(DevelopmentDay.day.desc()).limit(1))
        old=json.loads(previous.inventory_json) if previous else {}
        added=len(current.keys()-old.keys()) if previous else 0
        deleted=len(old.keys()-current.keys()) if previous else 0
        modified=sum(old[k]!=current[k] for k in current.keys()&old.keys()) if previous else 0
        commits=[]
        captured=now()
        if (directory/'.git').exists():
            try:
                start=previous.recorded_at if previous else day+'T00:00:00+08:00'
                run=subprocess.run(['git','-C',str(directory),'log','--since='+start,'--until='+captured,'--format=%h %s','-40'],capture_output=True,text=True,encoding='utf-8',timeout=15)
                if run.returncode==0:commits=run.stdout.splitlines()
            except (OSError,subprocess.TimeoutExpired):pass
        changed=added+deleted+modified
        summary=('建立代码基线，共'+str(len(current))+'份代码文件。') if not previous and not commits else f'距上次快照新增{added}、修改{modified}、删除{deleted}份代码'+(f'，期间记录{len(commits)}条提交'+('（最多40条）' if len(commits)==40 else '')+'。' if commits else '。')
        if previous and not changed and not commits:summary='距上次代码快照未发现变化。'
        result={'day':day,'baseline':previous is None,'changed':changed,'added':added,'modified':modified,'deleted':deleted,'commits':commits,'summary':summary}
        saved=db.execute(insert(DevelopmentDay).values(project_id=pid,day=day,recorded_at=captured,inventory_json=json.dumps(current),result_json=json.dumps(result,ensure_ascii=False)).on_conflict_do_nothing(index_elements=['project_id','day']))
        if not saved.rowcount:
            db.rollback()
            return json.loads(db.get(DevelopmentDay,(pid,day)).result_json)
        from .project_analysis import enqueue_project
        enqueue_project(db,p)
        db.commit()
        return result


@router.post('/projects/{pid}/development/scan')
async def scan(pid:str,request:Request,db:DB,user:Auth):
    owned(db,Project,pid,user)
    try:result=await asyncio.to_thread(scan_project,request.app,pid)
    except ValueError:raise HTTPException(422,'项目代码目录超过扫描容量或不可访问') from None
    if result is None:raise HTTPException(409,'请先绑定有效项目目录')
    return result


async def background_daily(app):
    import logging
    while True:
        def run():
            with app.state.sessions() as db:ids=list(db.scalars(select(Project.id).where(Project.directory_path.is_not(None))))
            for pid in ids:
                try:scan_project(app,pid)
                except Exception:logging.getLogger(__name__).warning('Daily development scan failed for project %s',pid)
        await asyncio.to_thread(run)
        await asyncio.sleep(3600)
