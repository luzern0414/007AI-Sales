from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text, Integer, Boolean, UniqueConstraint, Index, text, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy import create_engine


def uid():
    return uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class LoginSession(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[str] = mapped_column(String(40))


class Initialization(Base):
    __tablename__='initialization'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    created_at: Mapped[str]=mapped_column(String(40),default=now)


class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(160))
    customer: Mapped[str] = mapped_column(String(160), default='')
    stage: Mapped[str] = mapped_column(String(30), default='negotiation')
    status: Mapped[str] = mapped_column(String(30), default='active')
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    directory_path: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    __mapper_args__ = {'version_id_col': version}


class WorkflowNode(Base):
    __tablename__ = 'workflow_nodes'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), primary_key=True)
    key: Mapped[str] = mapped_column(String(30), primary_key=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    occurred_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default='')
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    __mapper_args__ = {'version_id_col': version}


class ProjectAnalysis(Base):
    __tablename__ = 'project_analysis'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), primary_key=True)
    background: Mapped[str] = mapped_column(Text, default='')
    instructions: Mapped[str] = mapped_column(Text, default='')
    summary: Mapped[str] = mapped_column(Text, default='')
    next_step: Mapped[str] = mapped_column(Text, default='')
    risks_json: Mapped[str] = mapped_column(Text, default='[]')
    insight_json: Mapped[str] = mapped_column(Text, default='{}')
    status: Mapped[str] = mapped_column(String(30), default='pending')
    input_hash: Mapped[str] = mapped_column(String(64), default='')
    analyzed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class ImportedRecording(Base):
    __tablename__ = 'imported_recordings'
    __table_args__ = (Index('uq_recording_active_meeting', 'meeting_id', unique=True, sqlite_where=text('active = 1'), postgresql_where=text('active = true')),)
    file_id: Mapped[str] = mapped_column(ForeignKey('files.id'), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey('meetings.id'))
    occurred_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    transcript: Mapped[str] = mapped_column(Text, default='')
    summary: Mapped[str] = mapped_column(Text, default='')


class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    title: Mapped[str] = mapped_column(String(240))
    assignee: Mapped[str] = mapped_column(String(100), default='')
    status: Mapped[str] = mapped_column(String(20), default='todo')
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    __mapper_args__ = {'version_id_col': version}


class ProjectEvent(Base):
    __tablename__ = 'project_events'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(500))
    detail: Mapped[str] = mapped_column(Text, default='')
    occurred_at: Mapped[str] = mapped_column(String(40), default=now)
    recorded_at: Mapped[str] = mapped_column(String(40), default=now)
    source_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Product(Base):
    __tablename__ = 'products'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text, default='')
    internal_notes: Mapped[str] = mapped_column(Text, default='')
    demo_url: Mapped[str] = mapped_column(Text, default='')
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    __mapper_args__ = {'version_id_col': version}


class StoredFile(Base):
    __tablename__ = 'files'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id'), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey('products.id'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(80))
    previous_version_id: Mapped[str | None] = mapped_column(ForeignKey('files.id'),nullable=True)
    file_version: Mapped[int] = mapped_column(Integer,default=1)
    parse_status: Mapped[str] = mapped_column(String(30), default='archived')
    extracted_text: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    source_modified_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_time_basis: Mapped[str] = mapped_column(String(30), default='uploaded')
    origin: Mapped[str] = mapped_column(String(20), default='unknown')


class DevelopmentDay(Base):
    __tablename__='development_days'
    project_id: Mapped[str]=mapped_column(ForeignKey('projects.id'),primary_key=True)
    day: Mapped[str]=mapped_column(String(10),primary_key=True)
    inventory_json: Mapped[str]=mapped_column(Text,default='{}')
    result_json: Mapped[str]=mapped_column(Text,default='{}')
    recorded_at: Mapped[str]=mapped_column(String(40),default=now)


class Meeting(Base):
    __tablename__ = 'meetings'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id'), index=True, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    notes: Mapped[str] = mapped_column(Text, default='')
    transcript: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(20), default='draft')
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    analysis_status: Mapped[str] = mapped_column(String(30), default='pending')
    ai_summary: Mapped[str] = mapped_column(Text, default='')
    title_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    classification_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    __mapper_args__ = {'version_id_col': version}


class MeetingProject(Base):
    __tablename__='meeting_projects'
    meeting_id: Mapped[str] = mapped_column(ForeignKey('meetings.id'), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), primary_key=True)
    evidence: Mapped[str] = mapped_column(Text, default='')
    source: Mapped[str] = mapped_column(String(20), default='automatic')


class NameEntry(Base):
    __tablename__='name_entries'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id'), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(160))
    aliases_json: Mapped[str] = mapped_column(Text, default='[]')
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class AnalysisJob(Base):
    __tablename__='analysis_jobs'
    __table_args__=(UniqueConstraint('kind','target_id','fingerprint'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(300), default='')
    result_json: Mapped[str] = mapped_column(Text, default='{}')
    lease_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lease_expires_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class ProjectProgress(Base):
    __tablename__='project_progress'
    __table_args__=(UniqueConstraint('project_id','input_hash'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), index=True)
    source_type: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str] = mapped_column(String(32))
    source_name: Mapped[str] = mapped_column(String(500))
    input_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(Text)
    previous: Mapped[str] = mapped_column(Text, default='')
    current: Mapped[str] = mapped_column(Text, default='')
    next: Mapped[str] = mapped_column(Text, default='')
    evidence_json: Mapped[str] = mapped_column(Text, default='[]')
    time_basis: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[str] = mapped_column(String(40))
    recorded_at: Mapped[str] = mapped_column(String(40), default=now)


class CaptureEpoch(Base):
    __tablename__ = 'capture_epochs'
    __table_args__=(Index('uq_meeting_open_epoch','meeting_id',unique=True,sqlite_where=text('sealed = 0'),postgresql_where=text('sealed = false')),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    meeting_id: Mapped[str] = mapped_column(ForeignKey('meetings.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20), default='capture')
    sealed: Mapped[bool] = mapped_column(Boolean, default=False)
    total_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    restore_max_seq: Mapped[int | None] = mapped_column(Integer,nullable=True)
    restore_total_frames: Mapped[int | None] = mapped_column(Integer,nullable=True)
    interruption_kind: Mapped[str|None]=mapped_column(String(40),nullable=True)
    interruption_detected_at: Mapped[str|None]=mapped_column(String(40),nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class AudioBlock(Base):
    __tablename__ = 'audio_blocks'
    __table_args__ = (UniqueConstraint('epoch_id', 'seq'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    epoch_id: Mapped[str] = mapped_column(ForeignKey('capture_epochs.id'), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    frame_start: Mapped[int] = mapped_column(Integer)
    frames: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(100))


class GeneratedDocument(Base):
    __tablename__='generated_documents'
    __table_args__=(UniqueConstraint('root_id','document_version'),)
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    project_id: Mapped[str]=mapped_column(ForeignKey('projects.id'),index=True)
    meeting_id: Mapped[str]=mapped_column(ForeignKey('meetings.id'))
    kind: Mapped[str]=mapped_column(String(30))
    title: Mapped[str]=mapped_column(String(240))
    markdown: Mapped[str]=mapped_column(Text)
    source_snapshot: Mapped[str]=mapped_column(Text)
    source_revision: Mapped[int]=mapped_column(Integer)
    root_id: Mapped[str]=mapped_column(String(32),default=uid)
    document_version: Mapped[int]=mapped_column(Integer,default=1)
    previous_version_id: Mapped[str|None]=mapped_column(ForeignKey('generated_documents.id'),nullable=True)
    revision_reason: Mapped[str]=mapped_column(Text,default='')
    created_at: Mapped[str]=mapped_column(String(40),default=now)


class GenerationJob(Base):
    __tablename__='generation_jobs'
    __table_args__=(UniqueConstraint('meeting_id','request_id'),Index('uq_running_generation','meeting_id',unique=True,sqlite_where=text("status = 'running'"),postgresql_where=text("status = 'running'")))
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    meeting_id: Mapped[str]=mapped_column(ForeignKey('meetings.id'),index=True)
    request_id: Mapped[str]=mapped_column(String(100))
    input_hash: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(30),default='running')
    document_ids: Mapped[str]=mapped_column(Text,default='[]')
    error: Mapped[str]=mapped_column(String(500),default='')
    error_status: Mapped[int]=mapped_column(Integer,default=502)
    created_at: Mapped[str]=mapped_column(String(40),default=now)
    finished_at: Mapped[str|None]=mapped_column(String(40),nullable=True)


class TaskDependency(Base):
    __tablename__='task_dependencies'
    task_id: Mapped[str]=mapped_column(ForeignKey('tasks.id'),primary_key=True)
    depends_on_id: Mapped[str]=mapped_column(ForeignKey('tasks.id'),primary_key=True)


class Issue(Base):
    __tablename__='issues'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    project_id: Mapped[str]=mapped_column(ForeignKey('projects.id'),index=True)
    title: Mapped[str]=mapped_column(String(240))
    detail: Mapped[str]=mapped_column(Text,default='')
    severity: Mapped[str]=mapped_column(String(20),default='normal')
    status: Mapped[str]=mapped_column(String(20),default='open')
    assignee: Mapped[str]=mapped_column(String(100),default='')
    due_date: Mapped[str|None]=mapped_column(String(10),nullable=True)
    resolution: Mapped[str]=mapped_column(Text,default='')
    version: Mapped[int]=mapped_column(Integer,default=1)
    created_at: Mapped[str]=mapped_column(String(40),default=now)
    __mapper_args__={'version_id_col':version}


class Milestone(Base):
    __tablename__='milestones'
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    project_id: Mapped[str]=mapped_column(ForeignKey('projects.id'),index=True)
    title: Mapped[str]=mapped_column(String(240))
    due_date: Mapped[str]=mapped_column(String(10))
    status: Mapped[str]=mapped_column(String(20),default='pending')
    evidence: Mapped[str]=mapped_column(Text,default='')
    version: Mapped[int]=mapped_column(Integer,default=1)
    __mapper_args__={'version_id_col':version}


class TranscriptSegment(Base):
    __tablename__='transcript_segments'
    __table_args__=(UniqueConstraint('meeting_id','run_id','begin_ms'),)
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    meeting_id: Mapped[str]=mapped_column(ForeignKey('meetings.id'),index=True)
    run_id: Mapped[str]=mapped_column(String(32))
    begin_ms: Mapped[int | None]=mapped_column(Integer,nullable=True)
    end_ms: Mapped[int | None]=mapped_column(Integer,nullable=True)
    text: Mapped[str]=mapped_column(Text)
    created_at: Mapped[str]=mapped_column(String(40),default=now)


class SourceLink(Base):
    __tablename__='source_links'
    __table_args__=(UniqueConstraint('project_id','source_key','subdirectory'),)
    id: Mapped[str]=mapped_column(String(32),primary_key=True,default=uid)
    project_id: Mapped[str]=mapped_column(ForeignKey('projects.id'),index=True)
    source_key: Mapped[str]=mapped_column(String(160))
    subdirectory: Mapped[str]=mapped_column(String(240),default='')
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)
    status: Mapped[str]=mapped_column(String(30),default='pending')
    last_synced_at: Mapped[str|None]=mapped_column(String(40),nullable=True)
    last_error: Mapped[str]=mapped_column(String(500),default='')
    summary: Mapped[str]=mapped_column(Text,default='')
    sync_token: Mapped[str|None]=mapped_column(String(32),nullable=True)
    sync_expires_at: Mapped[str|None]=mapped_column(String(40),nullable=True)


class SourceImport(Base):
    __tablename__='source_imports'
    link_id: Mapped[str]=mapped_column(ForeignKey('source_links.id'),primary_key=True)
    relative_path: Mapped[str]=mapped_column(String(500),primary_key=True)
    sha256: Mapped[str]=mapped_column(String(64))
    file_id: Mapped[str]=mapped_column(ForeignKey('files.id'))
    missing: Mapped[bool]=mapped_column(Boolean,default=False)


def connect(url):
    kwargs = {'connect_args': {'check_same_thread': False, 'timeout': 30}} if url.startswith('sqlite') else {}
    engine = create_engine(url, **kwargs)
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def pragmas(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA journal_mode=WAL')
    return engine, sessionmaker(engine, expire_on_commit=False)


def session(request):
    with request.app.state.sessions() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
