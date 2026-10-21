import hashlib
import os
import secrets
import wave
from datetime import datetime,timezone
from typing import Literal
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Header, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select,or_,delete

from .auth import Auth, digest
from .common import DB, data, owned, record, check_version
from .db import Meeting, Project, MeetingProject, CaptureEpoch, AudioBlock, now

router = APIRouter(prefix='/api')


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)


class MeetingUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=200000)
    transcript: str | None = Field(default=None, max_length=1000000)


class Seal(BaseModel):
    token: str
    last_seq: int = Field(ge=-1)
    total_frames: int = Field(ge=0)


class Restore(BaseModel):
    last_seq:int=Field(ge=-1,le=43200)
    total_frames:int=Field(ge=0,le=691200000)


INTERRUPTIONS={'input_stalled':'录音输入停滞','device_ended':'麦克风断开','device_muted':'麦克风不可用','context_suspended':'录音被系统暂停','overflow':'录音处理积压','storage_failed':'本机录音保存失败','recovered':'恢复时发现录音未正常结束'}


class Interruption(BaseModel):
    model_config=ConfigDict(extra='forbid')
    token:str
    kind:Literal['input_stalled','device_ended','device_muted','context_suspended','overflow','storage_failed','recovered']
    detected_at:datetime


def meeting(db, mid, user):
    row = db.get(Meeting, mid)
    if row is None:
        raise HTTPException(404, '会议不存在')
    if row.owner_id:
        if row.owner_id!=user.id:raise HTTPException(404,'会议不存在')
    elif row.project_id:
        owned(db, Project, row.project_id, user)
    else:raise HTTPException(404,'会议不存在')
    return row


def meeting_data(db,row):
    ids=list(db.scalars(select(MeetingProject.project_id).where(MeetingProject.meeting_id==row.id)))
    if row.project_id and row.project_id not in ids:ids.insert(0,row.project_id)
    projects=list(db.scalars(select(Project).where(Project.id.in_(ids)))) if ids else []
    from .db import ImportedRecording,StoredFile
    from .recording_imports import active_recording
    imported=active_recording(db,row.id)
    recordings=[]
    for link in db.scalars(select(ImportedRecording).where(ImportedRecording.meeting_id==row.id).order_by(ImportedRecording.active.desc(),ImportedRecording.file_id)):
        f=db.get(StoredFile,link.file_id)
        recordings.append({'file_id':f.id,'name':f.name,'mime':f.mime,'source_modified_at':f.source_modified_at,'active':link.active,'transcript':link.transcript if not link.active else '', 'summary':link.summary if not link.active else ''})
    return dict(data(row),project_ids=ids,projects=[{'id':p.id,'name':p.name} for p in projects],
                occurred_at=imported.occurred_at if imported else row.created_at,
                recordings=recordings)


def epoch(db, eid, user):
    row = db.get(CaptureEpoch, eid)
    if row is None:
        raise HTTPException(404, '录音段不存在')
    meeting(db, row.meeting_id, user)
    return row


def blocks(db, eid):
    return db.scalars(select(AudioBlock).where(AudioBlock.epoch_id == eid).order_by(AudioBlock.seq)).all()


def epoch_manifest(db, e):
    items = blocks(db, e.id)
    next_seq, frames = 0, 0
    for b in items:
        if b.seq != next_seq or b.frame_start != frames:
            break
        next_seq += 1
        frames += b.frames
    known = {b.seq for b in items}
    max_seq = max(known, default=-1) if e.last_seq is None else e.last_seq
    missing = []
    start = None
    for seq in range(max_seq + 1):
        if seq not in known and start is None:
            start = seq
        elif seq in known and start is not None:
            missing.append([start, seq-1])
            start = None
    if start is not None:
        missing.append([start, max_seq])
    return {'id': e.id, 'sealed': e.sealed, 'mode': e.mode, 'created_at': e.created_at, 'contiguous_frames': frames, 'next_seq': next_seq, 'received_sequences': sorted(known), 'missing_ranges': missing, 'total_frames': e.total_frames, 'last_seq': e.last_seq,'interruption_kind':e.interruption_kind,'interruption_detected_at':e.interruption_detected_at}


@router.get('/meetings')
def list_meetings(db: DB, user: Auth):
    query = select(Meeting).outerjoin(Project).where(or_(Meeting.owner_id==user.id,Meeting.owner_id.is_(None)&(Project.owner_id==user.id))).order_by(Meeting.updated_at.desc()).limit(100)
    return [meeting_data(db,m) for m in db.scalars(query)]


@router.post('/meetings/start',status_code=201)
def start(db:DB,user:Auth):
    from zoneinfo import ZoneInfo
    title='录音记录 '+datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%m月%d日 %H:%M')
    row=Meeting(owner_id=user.id,project_id=None,title=title)
    db.add(row);db.flush()
    return meeting_data(db,row)


@router.post('/projects/{project_id}/meetings', status_code=201)
def create(project_id: str, body: MeetingCreate, db: DB, user: Auth):
    owned(db, Project, project_id, user)
    row = Meeting(project_id=project_id, owner_id=user.id,title=body.title,title_locked=True)
    db.add(row)
    db.flush()
    db.add(MeetingProject(meeting_id=row.id,project_id=project_id,source='original'))
    record(db, project_id, user, 'meeting', '创建会议：' + row.title, source_id=row.id)
    return meeting_data(db,row)


@router.get('/meetings/{meeting_id}')
def detail(meeting_id: str, db: DB, user: Auth):
    return meeting_data(db,meeting(db, meeting_id, user))


@router.patch('/meetings/{meeting_id}')
def update(meeting_id: str, body: MeetingUpdate, db: DB, user: Auth):
    m = meeting(db, meeting_id, user)
    check_version(m, body.version)
    for key, value in body.model_dump(exclude_unset=True, exclude={'version'}).items():
        if value is None:
            raise HTTPException(422, '字段不能为空')
        if key=='title':
            value=value.strip()
            if not value:raise HTTPException(422,'会议名称不能为空')
        setattr(m, key, value)
        if key=='title':m.title_locked=True
    m.updated_at = now()
    if m.project_id:record(db, m.project_id, user, 'meeting', '更新会议记录：' + m.title, source_id=m.id)
    db.flush()
    if m.status=='finished' and any(k in body.model_fields_set for k in ('notes','transcript')):
        from .automation import enqueue_meeting
        enqueue_meeting(db,m,user)
    return meeting_data(db,m)


class Classification(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    project_ids:list[str]=Field(default_factory=list,max_length=30)
    title:str|None=Field(default=None,min_length=1,max_length=240)
    occurred_at:datetime|None=None


@router.patch('/meetings/{meeting_id}/classification')
def classify(meeting_id:str,body:Classification,request:Request,db:DB,user:Auth):
    m=meeting(db,meeting_id,user)
    if 'occurred_at' in body.model_fields_set:
        from .recording_imports import active_recording
        imported=active_recording(db,m.id)
        if imported is None:raise HTTPException(409,'现场录音时间无需修改')
        if body.occurred_at and (body.occurred_at.tzinfo is None or body.occurred_at>datetime.now(timezone.utc)):raise HTTPException(422,'请填写有效的实际会议时间')
        imported.occurred_at=body.occurred_at.astimezone(timezone.utc).isoformat(timespec='microseconds') if body.occurred_at else None
    previous=set(db.scalars(select(MeetingProject.project_id).where(MeetingProject.meeting_id==m.id)))
    if m.project_id:previous.add(m.project_id)
    ids=list(dict.fromkeys(body.project_ids))
    for pid in ids:owned(db,Project,pid,user)
    db.execute(delete(MeetingProject).where(MeetingProject.meeting_id==m.id))
    for pid in ids:db.add(MeetingProject(meeting_id=m.id,project_id=pid,source='manual'))
    m.project_id=ids[0] if ids else None;m.classification_locked=True
    if body.title:m.title=body.title;m.title_locked=True
    m.updated_at=now();db.flush()
    if m.status=='finished':
        from .automation import enqueue_meeting
        enqueue_meeting(db,m,user)
    for pid in previous-set(ids):record(db,pid,user,'change','会议移出项目：'+m.title,source_id=m.id)
    from .project_analysis import enqueue_project
    for pid in previous|set(ids):enqueue_project(db,db.get(Project,pid))
    db.commit()
    from .automation import write_progress
    for pid in previous-set(ids):write_progress(request.app,pid)
    return meeting_data(db,m)


@router.post('/meetings/{meeting_id}/epochs')
def start_epoch(meeting_id: str, db: DB, user: Auth):
    m = meeting(db, meeting_id, user)
    if m.status == 'finished':
        raise HTTPException(409, '会议已结束')
    pending = db.scalar(select(CaptureEpoch).where(CaptureEpoch.meeting_id == m.id, CaptureEpoch.sealed.is_(False)))
    if pending:
        raise HTTPException(409, '请先恢复并保存上一段录音')
    token = secrets.token_urlsafe(32)
    row = CaptureEpoch(meeting_id=m.id, token_hash=digest(token))
    m.status, m.updated_at = 'recording', now()
    db.add(row)
    db.flush()
    return {'id': row.id, 'token': token}


@router.post('/epochs/{epoch_id}/restore')
def restore(epoch_id: str, body:Restore, db: DB, user: Auth):
    e = epoch(db, epoch_id, user)
    if e.sealed:
        raise HTTPException(409, '录音段已封存')
    token = secrets.token_urlsafe(32)
    e.token_hash, e.mode = digest(token), 'restore'
    prior=blocks(db,e.id)
    if any(b.seq>body.last_seq or b.frame_start+b.frames>body.total_frames for b in prior):
        raise HTTPException(409,'恢复范围少于云端已有录音')
    e.restore_max_seq,e.restore_total_frames=body.last_seq,body.total_frames
    return {'id': e.id, 'token': token}


@router.put('/epochs/{epoch_id}/blocks/{seq}')
async def upload(epoch_id: str, seq: int, request: Request, db: DB, user: Auth, x_audio_hash: str = Header(), x_frame_start: int = Header(), x_capture_token: str = Header()):
    e = epoch(db, epoch_id, user)
    if seq < 0 or seq > 43200 or x_frame_start < 0 or x_frame_start > 16000*43200:
        raise HTTPException(422, '录音块范围无效')
    if not secrets.compare_digest(e.token_hash, digest(x_capture_token)):
        raise HTTPException(409, '录音授权已更新，请恢复录音')
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 64000:
            raise HTTPException(413, '录音块过大')
    value = hashlib.sha256(payload).hexdigest()
    if not payload or len(payload) % 2 or not secrets.compare_digest(value, x_audio_hash):
        raise HTTPException(422, '录音块校验失败')
    old = db.scalar(select(AudioBlock).where(AudioBlock.epoch_id == e.id, AudioBlock.seq == seq))
    if old:
        if old.sha256 != value or old.frame_start != x_frame_start:
            raise HTTPException(409, '录音块内容冲突')
        return epoch_manifest(db, e)
    if e.sealed:
        raise HTTPException(409, '录音段已封存')
    if e.mode=='restore' and (seq>e.restore_max_seq or x_frame_start+len(payload)//2>e.restore_total_frames):
        raise HTTPException(409,'超出录音恢复范围')
    key = f'audio-{e.id}-{seq}-{value[:16]}.pcm'
    path = request.app.state.storage / key
    with path.open('wb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    db.add(AudioBlock(epoch_id=e.id, seq=seq, frame_start=x_frame_start, frames=len(payload)//2, sha256=value, storage_key=key))
    db.flush()
    return epoch_manifest(db, e)


@router.post('/epochs/{epoch_id}/seal')
def seal(epoch_id: str, body: Seal, db: DB, user: Auth):
    e = epoch(db, epoch_id, user)
    if not secrets.compare_digest(e.token_hash, digest(body.token)):
        raise HTTPException(409, '录音授权已更新')
    manifest = epoch_manifest(db, e)
    if manifest['next_seq'] != body.last_seq+1 or manifest['contiguous_frames'] != body.total_frames or len(manifest['received_sequences']) != body.last_seq+1:
        raise HTTPException(409, '录音尚未完整上传')
    e.sealed, e.total_frames, e.last_seq = True, body.total_frames, body.last_seq
    return epoch_manifest(db, e)


@router.post('/epochs/{epoch_id}/interruption')
def interruption(epoch_id:str,body:Interruption,db:DB,user:Auth):
    e=epoch(db,epoch_id,user)
    if not secrets.compare_digest(e.token_hash,digest(body.token)):raise HTTPException(409,'录音授权已更新')
    if body.detected_at.tzinfo is None:raise HTTPException(422,'中断时间需要时区')
    if not e.interruption_kind:
        e.interruption_kind=body.kind
        e.interruption_detected_at=body.detected_at.astimezone(timezone.utc).isoformat(timespec='microseconds')
        m=meeting(db,e.meeting_id,user)
        if m.project_id:record(db,m.project_id,user,'meeting','会议录音中断',detail=INTERRUPTIONS[body.kind]+'；时间为设备检测时间，未录制区间不能还原',source_id=m.id)
        db.flush()
    return epoch_manifest(db,e)


@router.get('/meetings/{meeting_id}/manifest')
def manifest(meeting_id: str, db: DB, user: Auth):
    m = meeting(db, meeting_id, user)
    rows = db.scalars(select(CaptureEpoch).where(CaptureEpoch.meeting_id == m.id).order_by(CaptureEpoch.created_at)).all()
    return {'meeting_id': m.id, 'status': m.status, 'epochs': [epoch_manifest(db, e) for e in rows]}


@router.post('/meetings/{meeting_id}/finish')
def finish(meeting_id: str, db: DB, user: Auth):
    m = meeting(db, meeting_id, user)
    if db.scalar(select(CaptureEpoch.id).where(CaptureEpoch.meeting_id == m.id, CaptureEpoch.sealed.is_(False))):
        raise HTTPException(409, '录音仍有待保存内容')
    if m.status != 'finished':
        m.status, m.updated_at = 'finished', now()
        if m.project_id:record(db, m.project_id, user, 'meeting', '结束会议：' + m.title, source_id=m.id)
    db.flush()
    from .automation import enqueue_meeting
    enqueue_meeting(db,m,user)
    return meeting_data(db,m)


def build_wav(db, m, storage):
    epochs = db.scalars(select(CaptureEpoch).where(CaptureEpoch.meeting_id == m.id).order_by(CaptureEpoch.created_at)).all()
    if not epochs or any(not e.sealed for e in epochs):
        raise HTTPException(409, '请先完整保存录音')
    path = storage / f'meeting-{m.id}.wav'
    temporary = storage / (path.name + '.' + secrets.token_hex(5) + '.tmp')
    try:
        with wave.open(str(temporary), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            for e in epochs:
                for block in blocks(db, e.id):
                    payload = (storage / block.storage_key).read_bytes()
                    if hashlib.sha256(payload).hexdigest() != block.sha256:
                        raise HTTPException(409, '录音完整性检查失败')
                    output.writeframesraw(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


@router.get('/meetings/{meeting_id}/audio')
def audio(meeting_id: str, request: Request, db: DB, user: Auth, recording_id: str | None = None):
    m = meeting(db, meeting_id, user)
    from .db import ImportedRecording, StoredFile
    from .recording_imports import active_recording
    imported=db.get(ImportedRecording,recording_id) if recording_id else active_recording(db,m.id)
    if recording_id and (not imported or imported.meeting_id!=m.id):raise HTTPException(404,'录音版本不存在')
    if imported:
        f=db.get(StoredFile,imported.file_id)
        path=request.app.state.storage/f.storage_key
        if not path.is_file():raise HTTPException(410,'录音暂不可用')
        return FileResponse(path,filename=f.name,media_type=f.mime)
    path = build_wav(db, m, request.app.state.storage)
    return FileResponse(path, filename=m.title+'.wav', media_type='audio/wav')


@router.delete('/meetings/{meeting_id}',status_code=204)
def remove(meeting_id: str, request: Request, db: DB, user: Auth):
    """Delete a recording and everything derived from it; directory originals stay on disk but leave the project."""
    from .db import TranscriptSegment, GeneratedDocument, GenerationJob, ImportedRecording, StoredFile, AnalysisJob, ProjectProgress
    from .activity import key_name, source_scope
    m = meeting(db, meeting_id, user)
    if m.status == 'recording' or db.scalar(select(CaptureEpoch.id).where(CaptureEpoch.meeting_id == m.id, CaptureEpoch.sealed.is_(False))):
        raise HTTPException(409, '请先停止录音')
    linked = set(db.scalars(select(MeetingProject.project_id).where(MeetingProject.meeting_id == m.id)))
    if m.project_id: linked.add(m.project_id)
    storage = request.app.state.storage
    for e in db.scalars(select(CaptureEpoch).where(CaptureEpoch.meeting_id == m.id)).all():
        for b in db.scalars(select(AudioBlock).where(AudioBlock.epoch_id == e.id)).all():
            (storage / b.storage_key).unlink(missing_ok=True)
        db.execute(delete(AudioBlock).where(AudioBlock.epoch_id == e.id))
    db.execute(delete(CaptureEpoch).where(CaptureEpoch.meeting_id == m.id))
    db.execute(delete(TranscriptSegment).where(TranscriptSegment.meeting_id == m.id))
    db.execute(delete(GenerationJob).where(GenerationJob.meeting_id == m.id))
    documents = list(db.scalars(select(GeneratedDocument).where(GeneratedDocument.meeting_id == m.id)))
    for d in documents: d.previous_version_id = None
    db.flush()
    for d in documents: db.delete(d)
    for link in db.scalars(select(ImportedRecording).where(ImportedRecording.meeting_id == m.id)).all():
        audio_file = db.get(StoredFile, link.file_id)
        db.delete(link)
        if audio_file and audio_file.project_id:
            # Its transcript companion belongs to the same recording.
            for f in db.scalars(select(StoredFile).where(StoredFile.project_id == audio_file.project_id)).all():
                if f.id == audio_file.id or (source_scope(f.name) == source_scope(audio_file.name) and key_name(f.name) == key_name(audio_file.name) and '转写' in f.name):
                    f.project_id = None
    db.execute(delete(AnalysisJob).where(AnalysisJob.kind == 'meeting', AnalysisJob.target_id == m.id))
    db.execute(delete(ProjectProgress).where(ProjectProgress.source_type == 'meeting', ProjectProgress.source_id == m.id))
    db.execute(delete(MeetingProject).where(MeetingProject.meeting_id == m.id))
    (storage / f'meeting-{m.id}.wav').unlink(missing_ok=True)
    title = m.title
    db.delete(m)
    db.flush()
    from .project_analysis import enqueue_project
    for pid in linked:
        p = db.get(Project, pid)
        if not p: continue
        record(db, pid, user, 'meeting', '删除录音：' + title)
        enqueue_project(db, p, urgent=True)
    return Response(status_code=204)
