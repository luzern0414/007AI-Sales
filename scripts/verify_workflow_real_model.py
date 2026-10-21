"""Real configured provider, isolated database, complete original meeting plus background."""
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from server.app import create_app
from server.db import Base,User,Project,StoredFile,Meeting,MeetingProject,ProjectAnalysis,AnalysisJob
from server.project_analysis import enqueue_project
from server.automation import drain_jobs
from sqlalchemy import select,inspect

target=Path('output/workflow-real-model');target.mkdir(parents=True,exist_ok=True)
app=create_app('sqlite:///'+(target/'verification.db').resolve().as_posix(),target/'files',testing=True)
Base.metadata.create_all(app.state.sessions.kw['bind'])
engine=app.state.sessions.kw['bind']
if 'priority' not in {c['name'] for c in inspect(engine).get_columns('analysis_jobs')}:
    with engine.begin() as connection:connection.exec_driver_sql('ALTER TABLE analysis_jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0')
source=Path('D:/Codes/011KeChuang/docs/00_原始资料')
with app.state.sessions() as db:
    p=db.scalar(select(Project))
    if not p:
        user=User(username='isolated-real-model',password_hash='disabled',is_admin=False);db.add(user);db.flush()
        p=Project(owner_id=user.id,name='科创项目 · 真实模型隔离验证',customer='深湾科创中心');db.add(p);db.flush()
        for name in ['简介.txt','深圳科创项目内部会-会议纪要.md']:
            text=(source/name).read_text(encoding='utf-8-sig')
            db.add(StoredFile(owner_id=user.id,project_id=p.id,name=name,mime='text/markdown',size=len(text.encode()),sha256=hashlib.sha256(text.encode()).hexdigest(),storage_key='verification-only',extracted_text=text,parse_status='ready'))
        transcript=(source/'深圳科创项目内部会-FunASR转写稿.md').read_text(encoding='utf-8-sig')
        m=Meeting(project_id=p.id,owner_id=user.id,title='深圳科创项目内部会 · 原文验证',transcript=transcript,status='finished',classification_locked=True);db.add(m);db.flush()
        db.add(MeetingProject(meeting_id=m.id,project_id=p.id,source='manual'))
        db.add(ProjectAnalysis(project_id=p.id,background='项目背景以所附简介、会议纪要和完整转写为准。该隔离验证不向业务目录写入结果。',instructions='简洁概述实际进展，核实时间、技术、合同及需求风险；未知时间及节点待确认，不推断已签约。'))
        db.flush();enqueue_project(db,p);db.commit()
    pid=p.id
    enqueue_project(db,p)
    for job in db.scalars(select(AnalysisJob).where(AnalysisJob.kind=='project',AnalysisJob.target_id==pid,AnalysisJob.status=='failed',AnalysisJob.attempts<3)):
        job.status='pending'
    db.commit()
started=time.time()
drain_jobs(app,limit=3,project_id=pid)
with app.state.sessions() as db:
    row=db.get(ProjectAnalysis,pid)
    jobs=list(db.scalars(select(AnalysisJob).where(AnalysisJob.kind=='project',AnalysisJob.target_id==pid)))
    report={'status':row.status,'elapsed_seconds':round(time.time()-started,2),'summary':row.summary,'next':row.next_step,'risks':json.loads(row.risks_json),'jobs':[{'status':j.status,'error':j.error,'covered_chunks':len(json.loads(j.result_json).get('coverage',[]))} for j in jobs]}
    (target/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':row.status,'covered_chunks':[r['covered_chunks'] for r in report['jobs']],'elapsed_seconds':report['elapsed_seconds']},ensure_ascii=False))
