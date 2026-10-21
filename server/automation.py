"""Durable context analysis with source coverage, evidence and recoverable jobs."""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, update, or_, delete,func,case

from .auth import Auth
from .common import DB, owned, data
from .db import AnalysisJob, ProjectProgress, Project, Meeting, MeetingProject, StoredFile, TranscriptSegment, SourceImport, User, uid, now
from .analysis_model import call_model, AnalysisError
from .recording_imports import active_recording

router=APIRouter(prefix='/api')


class AnalysisDeferred(Exception):
    pass


def hashed(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def original(db,m):
    segments=list(db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id==m.id).order_by(TranscriptSegment.created_at,TranscriptSegment.begin_ms)))
    return {'notes':m.notes,'transcript':m.transcript,'segments':[{'id':s.id,'text':s.text,'begin_ms':s.begin_ms,'end_ms':s.end_ms} for s in segments]}


def enqueue(db,kind,target,owner,fingerprint):
    row=db.scalar(select(AnalysisJob).where(AnalysisJob.kind==kind,AnalysisJob.target_id==target,AnalysisJob.fingerprint==fingerprint))
    if row is None:
        row=AnalysisJob(kind=kind,target_id=target,owner_id=owner,fingerprint=fingerprint)
        db.add(row);db.flush()
    return row


def enqueue_file(db,file):
    if file.mime.startswith('audio/'):return None
    if file.project_id and file.parse_status in ('ready','needs_ocr','pending_asr'):
        return enqueue(db,'file',file.id,file.owner_id,hashed([file.sha256,file.project_id]))


def enqueue_meeting(db,m,user):
    row=enqueue(db,'meeting',m.id,user.id,meeting_fingerprint(db,m,user.id))
    row.priority=20
    if row.status!='succeeded':m.analysis_status=row.status
    return row


def audio_text(app,file):
    import subprocess
    from .files import TYPES
    root=Path(__file__).resolve().parents[1]
    runtime=Path(os.getenv('FUNASR_BATCH_PYTHON',str(root/'.venv-asr/Scripts/python.exe')))
    if not runtime.is_file():raise AnalysisError('本地录音识别服务未配置')
    work=app.state.storage/('asr-'+file.id);work.mkdir(exist_ok=True)
    target=work/'转写原文.md'
    if not target.exists():
        try:
            run=subprocess.run([str(runtime),str(root/'scripts/transcribe_funasr.py'),str(app.state.storage/file.storage_key),'--work-dir',str(work),'--model-dir',str(root/'output/funasr/models'),'--device',os.getenv('FUNASR_BATCH_DEVICE','cpu'),'--output',str(target)],capture_output=True,timeout=1800,env={**os.environ,'PYTHONUTF8':'1'})
            if run.returncode or not target.is_file():
                result=work/'result.json'
                if result.is_file():
                    try:
                        items=json.loads(result.read_text(encoding='utf-8')).get('result',[])
                        if items and not any(item.get('text','').strip() for item in items):raise AnalysisError('未识别到语音，录音已保留')
                    except (ValueError,KeyError,TypeError):pass
                raise AnalysisError('录音识别失败，请检查本地服务')
        except (OSError,subprocess.TimeoutExpired):raise AnalysisError('录音识别中断，原音已保留') from None
    return target.read_text(encoding='utf-8')


def ensure_recording_text(app,job,token):
    """Recover a meeting from its verified audio if streaming yielded no words."""
    from types import SimpleNamespace
    from .recordings import build_wav
    with app.state.sessions() as db:
        m=db.get(Meeting,job.target_id)
        raw=original(db,m)
        imported=active_recording(db,m.id)
        if raw['transcript'].strip() or (not imported and (raw['notes'].strip() or raw['segments'])):return
        if imported:
            f=db.get(StoredFile,imported.file_id)
            source=SimpleNamespace(id=f.id,storage_key=f.storage_key)
        else:
            try:path=build_wav(db,m,app.state.storage)
            except HTTPException:raise AnalysisError('尚无会议正文，录音已保留') from None
            source=SimpleNamespace(id=job.target_id,storage_key=path.name)
    text=audio_text(app,source)
    with app.state.sessions() as db:
        lease=db.get(AnalysisJob,job.id)
        if lease.lease_token!=token or lease.lease_expires_at<=now():raise AnalysisError('分析任务已被接管')
        m=db.get(Meeting,job.target_id);raw=original(db,m)
        current=active_recording(db,m.id)
        if imported and (not current or current.file_id!=source.id):raise AnalysisError('录音版本已更新，请重新整理')
        if not raw['transcript'].strip() and (current or not raw['notes'].strip() and not raw['segments']):m.transcript=text
        lease.status='superseded';lease.lease_token=None;lease.lease_expires_at=None
        enqueue_meeting(db,m,db.get(User,job.owner_id));db.commit()
    raise AnalysisDeferred()


def meeting_fingerprint(db,m,owner):
    linked=set(db.scalars(select(MeetingProject.project_id).where(MeetingProject.meeting_id==m.id)))
    if m.project_id:linked.add(m.project_id)
    ids=sorted(linked) if m.classification_locked else []
    background=list(db.execute(select(ProjectProgress.source_id,ProjectProgress.input_hash).where(ProjectProgress.project_id.in_(linked),ProjectProgress.source_type=='file').order_by(ProjectProgress.source_id,ProjectProgress.input_hash))) if linked else []
    source_state=[list(x) for x in db.execute(select(SourceImport.file_id,SourceImport.missing).join(StoredFile,StoredFile.id==SourceImport.file_id).where(StoredFile.project_id.in_(linked)).order_by(SourceImport.file_id))] if linked else []
    recording=active_recording(db,m.id)
    f=db.get(StoredFile,recording.file_id) if recording else None
    return hashed([original(db,m),ids,m.classification_locked,[list(x) for x in background],source_state,[f.id,f.sha256,recording.occurred_at] if f else None])


def chunks(text,size=6000):
    return [text[i:i+size] for i in range(0,len(text),size)]


def clean(result,key,limit):
    value=result.get(key,'')
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise AnalysisError('AI返回内容不完整，请重试')
    return value.strip()


def summary_result(result):
    from .project_analysis import concise
    return {key:concise(clean(result,key,700 if key=='summary' else 400)) for key in ('summary','previous','current','next')}


def project_context(db,pid):
    from .workflow import analysis_data,flow
    p=db.get(Project,pid)
    return {'workflow':flow(db,p),'analysis':analysis_data(db,pid)}


def checkpoint(app,jid,token,state):
    with app.state.sessions() as db:
        changed=db.execute(update(AnalysisJob).where(AnalysisJob.id==jid,AnalysisJob.lease_token==token,AnalysisJob.status=='running',AnalysisJob.lease_expires_at>now()).values(result_json=json.dumps(state,ensure_ascii=False),lease_expires_at=(datetime.now(timezone.utc)+timedelta(minutes=4)).isoformat(timespec='microseconds'),updated_at=now())).rowcount
        db.commit()
        if not changed:raise AnalysisError('分析任务已被接管')


def context(db,pid,at=None,exclude=None):
    query=select(ProjectProgress).where(ProjectProgress.project_id==pid)
    if at:query=query.where(ProjectProgress.occurred_at<=at)
    if exclude:query=query.where(ProjectProgress.source_id!=exclude)
    rows=list(db.scalars(query.order_by(ProjectProgress.recorded_at,ProjectProgress.id)))
    # A revised source contributes its latest analysis once, without feeding itself back.
    latest={}
    versions=select(StoredFile.previous_version_id).where(StoredFile.project_id==pid,StoredFile.previous_version_id.is_not(None))
    if at:versions=versions.where(func.coalesce(StoredFile.source_modified_at,StoredFile.created_at)<=at)
    replaced=set(db.scalars(versions))
    missing=set(db.scalars(select(SourceImport.file_id).where(SourceImport.missing.is_(True))))
    for r in rows:
        if r.source_type=='meeting' and not db.scalar(select(Meeting.id).where(Meeting.id==r.source_id,or_(Meeting.project_id==pid,Meeting.id.in_(select(MeetingProject.meeting_id).where(MeetingProject.project_id==pid))))):continue
        if r.source_id not in replaced|missing:latest[r.source_id]=r
    rows=sorted(latest.values(),key=lambda r:(r.occurred_at,r.recorded_at))
    return [{'source_id':r.source_id,'source':r.source_name,'time':r.occurred_at,'time_basis':r.time_basis,'summary':r.summary,'next':r.next} for r in rows]


def compact_context(app,items):
    # Every earlier summary participates; reduce in bounded groups instead of dropping older context.
    passes=0
    while len(json.dumps(items,ensure_ascii=False))>36000:
        passes+=1
        if passes>6:raise AnalysisError('项目上下文过长，请分范围整理')
        reduced=[]
        groups=chunks(json.dumps(items,ensure_ascii=False),20000)
        for group in groups:
            r=call_model(app,'context_reduce',{'context':group},'压缩项目上下文为JSON {summary}，保留关键变化、未决问题、来源ID与建议的性质。summary是最多1500字的紧凑字符串，不能照抄全文。')
            reduced.append({'summary':clean(r,'summary',6500)})
        items=reduced
    return items


def write_progress(app,pid):
    from .project_analysis import concise
    with app.state.sessions() as db:
        if db.bind.dialect.name=='sqlite':db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        else:db.execute(select(Project).where(Project.id==pid).with_for_update())
        p=db.get(Project,pid)
        if not p or not p.directory_path:return
        from .project_catalog import root
        directory=Path(p.directory_path)
        if not directory.is_dir() or directory.is_symlink() or directory.is_junction() or directory.resolve().parent!=root():raise AnalysisError('项目目录不可用')
        docs=directory/'docs'
        if docs.is_symlink() or docs.is_junction():raise AnalysisError('项目文档目录不可用')
        docs.mkdir(exist_ok=True)
        rows=visible_progress(db,pid)
        active=[r for r in rows if source_state(db,r)=='current']
        latest=active[-1] if active else None
        text='# '+p.name+' · 项目进展\n\n## 概览\n\n'+(latest.summary if latest else '暂无已确认进展。')+'\n\n## 进展记录\n'
        for row in rows:
            basis={'file_modified':'文件修改时间','filename':'文件名日期','uploaded':'上传时间','recorded':'录音记录时间'}.get(row.time_basis,row.time_basis)
            label={'missing':'（来源已移除）','superseded':'（历史版本）'}.get(source_state(db,row),'')
            from zoneinfo import ZoneInfo
            try:when=row.occurred_at if len(row.occurred_at)==10 else datetime.fromisoformat(row.occurred_at).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')
            except ValueError:when=row.occurred_at
            text+='\n### '+when+' · '+row.title.replace('\n',' ')+label+'\n\n'+concise(row.summary)+'\n\n来源：'+row.source_name.replace('\n',' ')+'；'+basis+'；记录ID：'+row.id+'\n'
        if latest:text+='\n## 后续建议\n\n'+latest.next+'\n'
        path=docs/'项目进展.md';temporary=docs/('.项目进展-'+uid()+'.tmp')
        try:
            with temporary.open('w',encoding='utf-8',newline='\n') as stream:
                stream.write(text);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path)
        finally:temporary.unlink(missing_ok=True)


def project_queue(db,pid):
    """Latest job state per file, meeting and the project itself, so readers see how complete the AI view is."""
    files=select(StoredFile.id).where(StoredFile.project_id==pid)
    meetings=select(Meeting.id).where(or_(Meeting.project_id==pid,Meeting.id.in_(select(MeetingProject.meeting_id).where(MeetingProject.project_id==pid))))
    rows=db.execute(select(AnalysisJob.kind,AnalysisJob.target_id,AnalysisJob.status).where(or_(
        (AnalysisJob.kind=='file')&AnalysisJob.target_id.in_(files),(AnalysisJob.kind=='meeting')&AnalysisJob.target_id.in_(meetings),
        (AnalysisJob.kind=='project')&(AnalysisJob.target_id==pid))).order_by(AnalysisJob.updated_at,AnalysisJob.id)).all()
    latest={}
    for kind,target,status in rows:
        if status!='superseded':latest[(kind,target)]=status
    count=lambda *s:sum(1 for (k,_),v in latest.items() if v in s and k!='project')
    project=next((v for (k,_),v in latest.items() if k=='project'),None)
    return {'pending':count('pending'),'running':count('running'),'failed':count('failed'),'done':count('succeeded'),'project':project}


def visible_progress(db,pid):
    rows=list(db.scalars(select(ProjectProgress).where(ProjectProgress.project_id==pid).order_by(ProjectProgress.recorded_at,ProjectProgress.id)))
    meeting_ids=set(db.scalars(select(Meeting.id).where(or_(Meeting.project_id==pid,Meeting.id.in_(select(MeetingProject.meeting_id).where(MeetingProject.project_id==pid))))))
    latest={}
    for r in rows:
        if r.source_type=='meeting' and r.source_id not in meeting_ids:continue
        latest[(r.source_type,r.source_id)]=r
    return sorted(latest.values(),key=lambda r:(r.occurred_at,r.recorded_at,r.id))


def source_state(db,row):
    if row.source_type!='file':return 'current'
    if db.scalar(select(SourceImport.file_id).where(SourceImport.file_id==row.source_id,SourceImport.missing.is_(True))):return 'missing'
    if db.scalar(select(StoredFile.id).where(StoredFile.previous_version_id==row.source_id).limit(1)):return 'superseded'
    return 'current'


def add_progress(db,job,pid,source_type,source_name,title,result,evidence,occurred_at,time_basis):
    fingerprint=hashed([job.kind,job.target_id,job.fingerprint])
    row=db.scalar(select(ProjectProgress).where(ProjectProgress.project_id==pid,ProjectProgress.input_hash==fingerprint))
    if row is None:
        row=ProjectProgress(project_id=pid,source_type=source_type,source_id=job.target_id,source_name=source_name,input_hash=fingerprint,title=title[:240],evidence_json=json.dumps(evidence,ensure_ascii=False),occurred_at=occurred_at,time_basis=time_basis,**result)
        db.add(row)
    return row


def file_work(app,job,token,state):
    with app.state.sessions() as db:
        f=db.get(StoredFile,job.target_id);p=db.get(Project,f.project_id)
        payload={'name':f.name,'project':p.name,'project_context':project_context(db,p.id)}
        from .recording_imports import business_time
        text=f.extracted_text;at,basis=business_time(f)
        prior=context(db,p.id,at,job.target_id)
        pid=p.id;source_name=f.name
        if f.parse_status=='needs_ocr':
            from .vision import extract_image
            text=extract_image(app,app.state.storage/f.storage_key,f.mime)
            f.extracted_text=text;f.parse_status='ready';db.commit()
        elif f.parse_status=='pending_asr':
            # The caller renews a longer lease for bounded local offline inference.
            db.expunge(f)
            text=audio_text(app,f)
            f=db.merge(f);f.extracted_text=text;f.parse_status='ready';db.commit()
    if not text.strip():raise AnalysisError('文件尚无可分析正文')
    parts=state.setdefault('chunks',[])
    chunk_size=state.setdefault('chunk_size',14000 if parts else 6000)
    all_chunks=chunks(text,chunk_size)
    for index,part in enumerate(all_chunks):
        if index<len(parts):continue
        r=call_model(app,'file_chunk',{**payload,'part':index+1,'parts':len(all_chunks),'original':part},'通读本片原文。返回 {summary,terms:[]}，summary是字符串，最多1000个汉字，以三段简短文字概括核心需求、决定、限制、日期及其性质、原文定位；不要罗列全部条目，terms固定空数组。不得将方案描述判为已实现。')
        parts.append({'part':index+1,'summary':clean(r,'summary',4000)})
        checkpoint(app,job.id,token,state)
    if 'final' not in state:
        state['final']=summary_result(call_model(app,'file_summary',{**payload,'previous_context':compact_context(app,prior),'source_chunks':compact_context(app,parts),'time_basis':basis},'返回{summary,previous,current,next}。summary只用一句不超过80字说明本文件的用途、展示的核心内容或新增事实，不复述其他文件，不以此前、本次、下一步开头，不列点；previous/current/next各一句承接上下文。文件能力描述不等于实际开发进度；时间来自文件排序。'))
        checkpoint(app,job.id,token,state)
    return [(pid,source_name,source_name,state['final'],{'file_id':job.target_id,'chunks':len(parts)},at,basis)]


def meeting_work(app,job,token,state):
    with app.state.sessions() as db:
        m=db.get(Meeting,job.target_id);raw=original(db,m)
        if not any((raw['notes'].strip(),raw['transcript'].strip(),raw['segments'])):raise AnalysisError('尚无会议转写，录音已保留')
        projects=list(db.scalars(select(Project).where(Project.owner_id==job.owner_id)))
        candidates=[{'id':p.id,'name':p.name,'customer':p.customer,'background':context(db,p.id)[-8:]} for p in projects]
        project_background={p.id:project_context(db,p.id) for p in projects}
        manual=list(db.scalars(select(MeetingProject.project_id).where(MeetingProject.meeting_id==m.id))) if m.classification_locked else None
        imported=active_recording(db,m.id)
        locked=m.title_locked;title=m.title;at=imported.occurred_at if imported and imported.occurred_at else m.created_at
        time_basis='imported_at' if imported and not imported.occurred_at else 'recorded'
        contexts={p.id:context(db,p.id,at,m.id) for p in projects}
    original_text='会议记录\n'+raw['notes']+'\n转写原文\n'+raw['transcript']+'\n实时转写原文\n'+'\n'.join('['+s['id']+' '+str(s['begin_ms'])+'–'+str(s['end_ms'])+'ms] '+s['text'] for s in raw['segments'])
    parts=state.setdefault('chunks',[])
    chunk_size=state.setdefault('chunk_size',14000 if parts else 6000)
    for index,part in enumerate(chunks(original_text,chunk_size)):
        if index<len(parts):continue
        r=call_model(app,'meeting_chunk',{'original':part,'part':index+1,'projects':candidates,'project_background':project_background},'通读原文并识别项目。只返回紧凑JSON {summary,facts:[{quote,meaning}],projects:[{project_id,quotes:[],summary}]}。summary最多600汉字，保留原文时间/片段编号。facts最多8条，每条quote不超过100字逐字原文，meaning不超过80字；覆盖本片核心事实及未决事项。每个项目最多3条quotes、summary最多100字。仅明确涉及的候选项目，不能仅凭财务、系统、客户等通用词关联。允许多项目、无项目。quotes必须逐字出现在本片原文中。不得长篇复述。')
        found=[]
        for item in r.get('projects',[]):
            if not isinstance(item,dict) or item.get('project_id') not in contexts:continue
            quotes=[q for q in item.get('quotes',[]) if isinstance(q,str) and len(q.strip())>=2 and q in part]
            if quotes:found.append({'project_id':item['project_id'],'quotes':quotes,'summary':clean(item,'summary',4000)})
        facts=[f for f in r.get('facts',[]) if isinstance(f,dict) and isinstance(f.get('quote'),str) and f['quote'] and f['quote'] in part]
        parts.append({'part':index+1,'char_start':index*chunk_size,'char_end':index*chunk_size+len(part),'summary':clean(r,'summary',4000),'facts':facts,'projects':found});checkpoint(app,job.id,token,state)
    ids=manual if manual is not None else sorted({p['project_id'] for part in parts for p in part['projects']})
    if 'meeting' not in state:
        state['meeting']=call_model(app,'meeting_summary',{'original_transcript':original_text if len(original_text)<=70000 else None,'full_transcript_coverage':parts,'background':compact_context(app,[{'project_id':pid,'context':contexts[pid]} for pid in ids]),'project_background':project_background},'返回{title,markdown}，中文会议名不超过60字；markdown为有背景承接的会议纪要，含上次进展、本次讨论与明确决定、未决事项、后续建议，引用原文片段和资料来源。原文超过单次上下文时每片已通读，并提供逐字事实证据与字符位置。不得遗漏跨项目内容，不猜参会人和日期，建议不能写成承诺。')
        clean(state['meeting'],'title',240);clean(state['meeting'],'markdown',30000);checkpoint(app,job.id,token,state)
    output=[];summaries=state.setdefault('project_summaries',{})
    for pid in ids:
        evidence=[p for part in parts for p in part['projects'] if p['project_id']==pid]
        if pid not in summaries:
            summaries[pid]=summary_result(call_model(app,'meeting_project',{'project_id':pid,'full_transcript_coverage':parts,'project_evidence':evidence,'previous_context':compact_context(app,contexts[pid]),'manual_link':manual is not None},'返回{summary,previous,current,next}，summary一句60至100字，其他各一句。只总结本项目。说明上次做了什么、本次新增什么、建议后续做什么；无本项目内容明确说明，不能把其他项目需求混入。'))
            checkpoint(app,job.id,token,state)
        output.append((pid,title,state['meeting']['title'],summaries[pid],evidence,at,time_basis))
    state['project_ids']=ids
    return output


def process_job(app,jid,token):
    with app.state.sessions() as db:
        job=db.get(AnalysisJob,jid);db.expunge(job)
    state=json.loads(job.result_json)
    try:
        if job.kind=='meeting':ensure_recording_text(app,job,token)
        if job.kind=='project':
            from .project_analysis import project_work,fingerprint,enqueue_project
            from .db import ProjectAnalysis
            result=project_work(app,job,token,state)
            with app.state.sessions() as db:
                row=db.get(AnalysisJob,jid)
                if row.lease_token!=token or row.lease_expires_at<=now():raise AnalysisError('分析任务已被接管')
                p=db.get(Project,job.target_id)
                if fingerprint(db,p)!=job.fingerprint:
                    row.status='superseded';row.lease_token=None;row.lease_expires_at=None
                    enqueue_project(db,p);db.commit();return
                review=db.get(ProjectAnalysis,p.id)
                review.summary=result['summary'];review.next_step=result['next_step'];review.risks_json=json.dumps(result['risks'],ensure_ascii=False)
                review.status='ready';review.analyzed_at=now()
                review.insight_json=json.dumps({**result.get('insight',{}),'analyzed_at':review.analyzed_at},ensure_ascii=False)
                from .project_analysis import save_source_summaries
                save_source_summaries(db,job,state)
                row.result_json=json.dumps(state,ensure_ascii=False)
                row.status='succeeded';row.error='';row.lease_token=None;row.lease_expires_at=None;row.updated_at=now();db.commit()
            from .docs_structure import export_state
            write_progress(app,job.target_id)
            export_state(app,job.target_id)
            return
        output=file_work(app,job,token,state) if job.kind=='file' else meeting_work(app,job,token,state)
        with app.state.sessions() as db:
            row=db.get(AnalysisJob,jid)
            if row.lease_token!=token or row.lease_expires_at<=now():raise AnalysisError('分析任务已被接管')
            if job.kind=='meeting':
                m=db.get(Meeting,job.target_id)
                current=meeting_fingerprint(db,m,job.owner_id)
                if current!=job.fingerprint:raise AnalysisError('会议内容已更新，请重新整理')
                if not m.title_locked:m.title=state['meeting']['title']
                m.ai_summary=state['meeting']['markdown'];m.analysis_status='ready' if state['project_ids'] else 'unclassified'
                if not m.classification_locked:
                    db.execute(delete(MeetingProject).where(MeetingProject.meeting_id==m.id))
                    for pid in state['project_ids']:db.add(MeetingProject(meeting_id=m.id,project_id=pid,evidence=json.dumps([e for part in state['chunks'] for e in part['projects'] if e['project_id']==pid],ensure_ascii=False)))
                    m.project_id=next(iter(state['project_ids']),None)
            for pid,name,title,result,evidence,at,basis in output:
                add_progress(db,job,pid,job.kind,name,title,result,evidence,at,basis)
            db.flush()
            project_ids={item[0] for item in output}
            if job.kind=='file' and not db.scalar(select(AnalysisJob.id).where(AnalysisJob.kind=='file',AnalysisJob.target_id.in_(select(StoredFile.id).where(StoredFile.project_id.in_(project_ids))),AnalysisJob.status=='pending',AnalysisJob.id!=jid).limit(1)):
                for m in db.scalars(select(Meeting).where(Meeting.owner_id==job.owner_id,Meeting.status=='finished',or_(Meeting.project_id.in_(project_ids),Meeting.id.in_(select(MeetingProject.meeting_id).where(MeetingProject.project_id.in_(project_ids)))))):
                    enqueue_meeting(db,m,db.get(User,job.owner_id))
            from .project_analysis import enqueue_project
            for pid in project_ids:
                waiting=db.scalar(select(AnalysisJob.id).where(AnalysisJob.kind=='file',AnalysisJob.status.in_(['pending','running']),AnalysisJob.id!=jid,AnalysisJob.target_id.in_(select(StoredFile.id).where(StoredFile.project_id==pid))).limit(1))
                enqueue_project(db,db.get(Project,pid),urgent=not waiting)
            row.result_json=json.dumps(state,ensure_ascii=False);db.commit()
        from .docs_structure import export_state
        for pid in {item[0] for item in output}:
            write_progress(app,pid);export_state(app,pid)
        with app.state.sessions() as db:
            db.execute(update(AnalysisJob).where(AnalysisJob.id==jid,AnalysisJob.lease_token==token).values(status='succeeded',error='',lease_token=None,lease_expires_at=None,updated_at=now()));db.commit()
    except AnalysisDeferred:
        return
    except Exception as exc:
        if not isinstance(exc,AnalysisError):
            import traceback,logging
            frames='; '.join(f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}' for frame in traceback.extract_tb(exc.__traceback__))
            logging.getLogger(__name__).error('Analysis processing exception %s: %s',type(exc).__name__,frames)
        message=str(exc) if isinstance(exc,AnalysisError) else '资料整理失败，请重试'
        with app.state.sessions() as db:
            changed=db.execute(update(AnalysisJob).where(AnalysisJob.id==jid,AnalysisJob.lease_token==token).values(status='failed',error=message[:300],lease_token=None,lease_expires_at=None,updated_at=now())).rowcount
            if changed and job.kind=='meeting':
                m=db.get(Meeting,job.target_id)
                if m and meeting_fingerprint(db,m,job.owner_id)==job.fingerprint:m.analysis_status='failed'
            if changed and job.kind=='project':
                from .db import ProjectAnalysis
                review=db.get(ProjectAnalysis,job.target_id)
                if review and review.input_hash==job.fingerprint:review.status='failed'
            db.commit()
        import logging
        logging.getLogger(__name__).warning('Analysis job %s failed: %s',jid,message)


def drain_jobs(app,limit=20,project_id=None):
    completed=0
    for _ in range(limit):
        with app.state.sessions() as db:
            retry_before=(datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat(timespec='microseconds')
            eligible=or_(AnalysisJob.status=='pending',(AnalysisJob.status=='running')&(AnalysisJob.lease_expires_at<now()),(AnalysisJob.status=='failed')&(AnalysisJob.attempts<3)&AnalysisJob.error.like('AI%')&(AnalysisJob.updated_at<retry_before))
            query=select(AnalysisJob).where(eligible)
            if project_id:query=query.where(or_((AnalysisJob.kind=='file') & AnalysisJob.target_id.in_(select(StoredFile.id).where(StoredFile.project_id==project_id)), (AnalysisJob.kind=='project') & (AnalysisJob.target_id==project_id)))
            job=db.scalar(query.order_by(AnalysisJob.priority.desc(),case((AnalysisJob.kind=='meeting',0),else_=1),AnalysisJob.created_at,AnalysisJob.id).limit(1))
            if not job:break
            if job.kind=='meeting':
                m=db.get(Meeting,job.target_id)
                if meeting_fingerprint(db,m,job.owner_id)!=job.fingerprint:
                    job.status='superseded';enqueue_meeting(db,m,db.get(User,job.owner_id));db.commit();continue
            if job.kind=='project':
                from .project_analysis import fingerprint,enqueue_project
                p=db.get(Project,job.target_id)
                if fingerprint(db,p)!=job.fingerprint:
                    job.status='superseded';enqueue_project(db,p,urgent=job.priority>0);db.commit();continue
            token=uid();jid=job.id
            target=db.get(StoredFile,job.target_id) if job.kind=='file' else None
            lease_minutes=35 if (target and target.parse_status=='pending_asr') or job.kind=='meeting' else 4
            changed=db.execute(update(AnalysisJob).where(AnalysisJob.id==jid,eligible).values(status='running',lease_token=token,lease_expires_at=(datetime.now(timezone.utc)+timedelta(minutes=lease_minutes)).isoformat(timespec='microseconds'),attempts=AnalysisJob.attempts+1,updated_at=now())).rowcount
            db.commit()
        if not changed:continue
        process_job(app,jid,token);completed+=1
    return completed


@router.get('/projects/{project_id}/overview')
def overview(project_id:str,db:DB,user:Auth):
    p=owned(db,Project,project_id,user)
    rows=list(reversed(visible_progress(db,p.id)))
    ids=list(db.scalars(select(StoredFile.id).where(StoredFile.project_id==p.id)))+list(db.scalars(select(MeetingProject.meeting_id).where(MeetingProject.project_id==p.id)))
    jobs=list(db.scalars(select(AnalysisJob).where(AnalysisJob.target_id.in_(ids)))) if ids else []
    from .db import ProjectAnalysis
    review=db.get(ProjectAnalysis,p.id)
    jobs+=list(db.scalars(select(AnalysisJob).where(AnalysisJob.kind=='project',AnalysisJob.target_id==p.id,AnalysisJob.fingerprint==(review.input_hash if review else ''))))
    latest_jobs={}
    for job in sorted(jobs,key=lambda j:(j.created_at,j.id)):
        latest_jobs[(job.kind,job.target_id)]=job
    jobs=list(latest_jobs.values())
    status='running' if any(j.status=='running' for j in jobs) else 'pending' if any(j.status=='pending' for j in jobs) else 'failed' if any(j.status=='failed' for j in jobs) else 'ready'
    states={r.id:source_state(db,r) for r in rows}
    latest=next((r for r in rows if states[r.id]=='current'),None)
    from .project_analysis import concise
    return {**{key:concise(getattr(latest,key,'')) if latest else '' for key in ('summary','previous','current','next')},'analysis_status':status,'directory':p.directory_path,'failed_jobs':[{'id':j.id,'error':j.error} for j in jobs if j.status=='failed'],'entries':[dict(data(r,('evidence_json',)),summary=concise(r.summary),source_status=states[r.id],evidence=json.loads(r.evidence_json)) for r in rows]}


@router.get('/analysis-jobs')
def jobs(db:DB,user:Auth):
    return [data(j,('result_json','lease_token','lease_expires_at')) for j in db.scalars(select(AnalysisJob).where(AnalysisJob.owner_id==user.id).order_by(AnalysisJob.created_at.desc()).limit(500))]


@router.post('/analysis-jobs/{job_id}/retry')
def retry(job_id:str,db:DB,user:Auth):
    row=db.get(AnalysisJob,job_id)
    if not row or row.owner_id!=user.id:raise HTTPException(404,'整理任务不存在')
    if row.status=='running':raise HTTPException(409,'正在整理')
    row.status='pending';row.error='';row.updated_at=now()
    if row.kind=='project':
        from .db import ProjectAnalysis
        review=db.get(ProjectAnalysis,row.target_id)
        if review:review.status='pending'
    if row.kind=='meeting':
        m=db.get(Meeting,row.target_id)
        if m:m.analysis_status='pending'
    return {'status':'pending'}


async def analysis_worker(app):
    while True:
        done=await asyncio.to_thread(drain_jobs,app,1) if os.getenv('LLM_API_KEY') else 0
        await asyncio.sleep(0.5 if done else 3)


def refresh_reviews(app):
    """Daily re-think: a new day (or new manager signal) changes the fingerprint, so each project is reviewed again."""
    from .project_analysis import enqueue_project,fingerprint
    from .db import ProjectAnalysis
    with app.state.sessions() as db:
        for p in db.scalars(select(Project).where(Project.status.in_(['active','paused'])|Project.status.is_(None))):
            row=db.get(ProjectAnalysis,p.id)
            if not row or row.input_hash!=fingerprint(db,p):enqueue_project(db,p)
        db.commit()


async def review_scheduler(app):
    while True:
        try:await asyncio.to_thread(refresh_reviews,app)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning('Review refresh skipped: %s',type(exc).__name__)
        await asyncio.sleep(1800)


async def background_analysis(app):
    # Model calls are network-bound; a few leased workers drain backlogs without reordering evidence.
    workers=max(1,min(6,int(os.getenv('ANALYSIS_WORKERS','3'))))
    await asyncio.gather(review_scheduler(app),*(analysis_worker(app) for _ in range(workers)))
