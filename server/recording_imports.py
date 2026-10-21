"""Idempotent audio-to-meeting association; original files and bytes stay intact."""
from pathlib import Path
from sqlalchemy import select
from .db import ImportedRecording, StoredFile, Meeting, MeetingProject, AnalysisJob,ProjectProgress


def filename_time(name):
    """Only explicit calendar dates; date-only names never acquire a fake time."""
    import re
    from datetime import datetime,timezone,timedelta
    if name.startswith('[') and ' · ' in name:name=name.rsplit(' · ',1)[-1]
    name=re.sub(r'(20\d{2})[-年_.](\d{1,2})[-月_.](\d{1,2})日?',lambda m:f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}',Path(name.replace('\\','/')).stem)
    match=re.search(r'(?<!\d)(20\d{2})[-年_.]?(\d{2})[-月_.]?(\d{2})日?(?:[ T_\-]+(\d{2})[:时_\-]?(\d{2})(?:[:分_\-]?(\d{2}))?|(?=\d{6}(?!\d))(\d{2})(\d{2})(\d{2}))?(?!\d)',name)
    if not match:return None
    y,mo,d,h,mi,s,h2,mi2,s2=match.groups()
    h,mi,s=h or h2,mi or mi2,s or s2
    try:
        local=datetime(int(y),int(mo),int(d),int(h or 0),int(mi or 0),int(s or 0),tzinfo=timezone(timedelta(hours=8)))
        if local>datetime.now(timezone.utc):return None
        return local.astimezone(timezone.utc).isoformat(timespec='microseconds') if h else local.date().isoformat()
    except ValueError:return None


def business_time(f):
    """A date written in the file or folder name is when the work happened; file mtime is only a fallback."""
    parts=f.name.rsplit(' · ',3) if f.name.startswith('[') else [f.name]
    for part in reversed(parts):
        value=filename_time(part.split('] ',1)[-1])
        if value:return value,'filename'
    return f.source_modified_at or f.created_at,f.source_time_basis


def active_recording(db, meeting_id):
    return db.scalar(select(ImportedRecording).where(ImportedRecording.meeting_id == meeting_id, ImportedRecording.active.is_(True)))


def import_audio(db, file, user):
    if not file.project_id or not file.mime.startswith('audio/'): return None
    link = db.get(ImportedRecording, file.id)
    if link is None:
        # Changed versions of the same recording remain a single meeting.
        prior = db.get(ImportedRecording, file.previous_version_id) if file.previous_version_id else None
        if prior:
            m = db.get(Meeting, prior.meeting_id)
            current = active_recording(db, m.id)
            if current:
                current.transcript, current.summary = m.transcript, m.ai_summary
                current.active = False
            db.flush()
            link = ImportedRecording(file_id=file.id, meeting_id=m.id, occurred_at=filename_time(file.name) or prior.occurred_at)
            db.add(link)
            m.transcript, m.ai_summary, m.analysis_status = '', '', 'pending'
            for job in db.scalars(select(AnalysisJob).where(AnalysisJob.kind=='meeting',AnalysisJob.target_id==m.id,AnalysisJob.status.in_(['pending','running','failed']))):
                job.status='superseded';job.lease_token=None;job.lease_expires_at=None
        else:
            m = Meeting(project_id=file.project_id, owner_id=file.owner_id, title=Path(file.name).stem[:240],
                        status='finished', classification_locked=True, title_locked=False)
            db.add(m); db.flush()
            db.add(MeetingProject(meeting_id=m.id, project_id=file.project_id, source='recording'))
            link = ImportedRecording(file_id=file.id, meeting_id=m.id, occurred_at=filename_time(file.name))
            db.add(link)
    else: m = db.get(Meeting, link.meeting_id)
    if link.active is not False and file.extracted_text.strip() and not m.transcript.strip(): m.transcript = file.extracted_text
    db.flush()
    from .automation import enqueue_meeting
    enqueue_meeting(db, m, user)
    for job in db.scalars(select(AnalysisJob).where(AnalysisJob.kind == 'file', AnalysisJob.target_id == file.id, AnalysisJob.status.in_(['pending', 'failed']))):
        job.status = 'superseded'
    return m


def migrate_audio(app):
    from .db import User
    with app.state.sessions() as db:
        replaced=set(db.scalars(select(StoredFile.previous_version_id).where(StoredFile.previous_version_id.is_not(None))))
        for f in db.scalars(select(StoredFile).where(StoredFile.project_id.is_not(None), StoredFile.mime.like('audio/%')).order_by(StoredFile.created_at, StoredFile.id)):
            for job in db.scalars(select(AnalysisJob).where(AnalysisJob.kind=='file',AnalysisJob.target_id==f.id,AnalysisJob.status.in_(['pending','running','failed']))):
                job.status='superseded';job.lease_token=None;job.lease_expires_at=None
            if f.id in replaced:continue
            if db.get(ImportedRecording, f.id) is None:
                import_audio(db, f, db.get(User, f.owner_id))
            link=db.get(ImportedRecording,f.id)
            if not link.occurred_at:
                link.occurred_at=filename_time(f.name)
                if link.occurred_at:
                    from .automation import enqueue_meeting
                    enqueue_meeting(db,db.get(Meeting,link.meeting_id),db.get(User,f.owner_id))
            for progress in db.scalars(select(ProjectProgress).where(ProjectProgress.source_type=='file',ProjectProgress.source_id==f.id)):
                progress.source_type='meeting';progress.source_id=link.meeting_id
                progress.time_basis='recorded' if link.occurred_at else 'imported_at'
                progress.occurred_at=link.occurred_at or db.get(Meeting,link.meeting_id).created_at
        db.commit()
