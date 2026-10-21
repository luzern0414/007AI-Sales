from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select,or_,func

from .auth import Auth
from .common import DB, data, owned, check_version, record,describe_changes
from .db import Project, Task, ProjectEvent, StoredFile, TaskDependency, Issue, Milestone, Meeting, MeetingProject, now

router = APIRouter(prefix='/api')
Stage = Literal['negotiation', 'requirements', 'proposal', 'preparation', 'implementation', 'testing', 'acceptance', 'maintenance']
TaskStatus = Literal['todo', 'doing', 'blocked', 'review', 'done', 'cancelled']


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str | None = Field(default=None,min_length=1, max_length=160)
    customer: str = Field(default='', max_length=160)
    due_date: date | None = None

    directory_name: str | None = Field(default=None,max_length=160)
    create_directory: bool = False


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    customer: str | None = Field(default=None, max_length=160)
    stage: Stage | None = None
    status: Literal['active', 'paused', 'delivered', 'archived', 'cancelled'] | None = None
    due_date: date | None = None
    reason: str = Field(default='', max_length=2000)


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    title: str = Field(min_length=1, max_length=240)
    assignee: str = Field(default='', max_length=100)
    due_date: date | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    assignee: str | None = Field(default=None, max_length=100)
    due_date: date | None = None
    status: TaskStatus | None = None
    evidence: str | None = Field(default=None, max_length=10000)


class EventCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    title: str = Field(min_length=1, max_length=500)
    detail: str = Field(default='', max_length=20000)
    kind: Literal['progress', 'issue', 'decision', 'change', 'note'] = 'progress'
    occurred_at: datetime | None = None


def updates(body, omit=('version',)):
    result = body.model_dump(exclude_unset=True, mode='json')
    return {k: v for k, v in result.items() if k not in omit}


def project_tasks(db, project_id):
    return db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.created_at.desc(), Task.id.desc())).all()


def progress(tasks):
    valid = [t for t in tasks if t.status != 'cancelled']
    return round(100 * sum(t.status == 'done' and bool(t.evidence) for t in valid) / len(valid)) if valid else None


def material_counts(db, pid):
    """Current originals by provider plus linked meetings, for dense list rows."""
    from .db import StoredFile, SourceImport, Meeting, MeetingProject
    from sqlalchemy import or_
    rows = list(db.execute(select(StoredFile.id, StoredFile.origin, StoredFile.mime, StoredFile.previous_version_id, StoredFile.created_at, StoredFile.source_modified_at).where(StoredFile.project_id == pid)))
    replaced = {r.previous_version_id for r in rows if r.previous_version_id}
    missing = set(db.scalars(select(SourceImport.file_id).where(SourceImport.missing.is_(True), SourceImport.file_id.in_([r.id for r in rows])))) if rows else set()
    current = [r for r in rows if r.id not in replaced | missing and not r.mime.startswith('audio/')]
    meetings = db.scalar(select(func.count()).select_from(Meeting).where(or_(Meeting.project_id == pid, Meeting.id.in_(select(MeetingProject.meeting_id).where(MeetingProject.project_id == pid))))) or 0
    times = [r.source_modified_at or r.created_at for r in current]
    return {'files': len(current), 'client': sum(r.origin == 'client' for r in current), 'ours': sum(r.origin == 'ours' for r in current),
            'meetings': meetings, 'latest': max(times) if times else None}


@router.get('/projects')
def list_projects(db: DB, user: Auth):
    from .workflow import flow,analysis_data
    return [dict(data(p), workflow=flow(db,p), analysis=analysis_data(db,p.id), counts=material_counts(db,p.id), progress=progress(project_tasks(db, p.id))) for p in db.scalars(select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc(), Project.id.desc()))]


@router.post('/projects', status_code=201)
def create_project(body: ProjectCreate, db: DB, user: Auth):
    if not body.name:
        if not body.directory_name:raise HTTPException(422,'请填写项目名称')
        body.name=body.directory_name
    project = Project(owner_id=user.id, **body.model_dump(mode='json',exclude={'directory_name','create_directory'}))
    db.add(project)
    db.flush()
    if body.directory_name:
        if not user.is_admin:raise HTTPException(403,'仅管理员可管理本机目录')
        from .project_catalog import safe_directory,attach
        attach(db,project,safe_directory(body.directory_name),body.create_directory)
    record(db, project.id, user, 'project', '创建项目')
    return data(project)


@router.get('/projects/{project_id}')
def project_detail(project_id: str, db: DB, user: Auth):
    from .recordings import meeting_data
    p = owned(db, Project, project_id, user)
    tasks = project_tasks(db, p.id)
    events = db.scalars(select(ProjectEvent).where(ProjectEvent.project_id == p.id).order_by(ProjectEvent.occurred_at.desc(), ProjectEvent.recorded_at.desc(), ProjectEvent.id.desc())).all()
    files = db.scalars(select(StoredFile).where(StoredFile.project_id == p.id, ~StoredFile.mime.like('audio/%')).order_by(StoredFile.created_at.desc(), StoredFile.id.desc())).all()
    dependencies=db.execute(select(TaskDependency.task_id,TaskDependency.depends_on_id).join(Task,Task.id==TaskDependency.task_id).where(Task.project_id==p.id)).all()
    return {'project': dict(data(p), progress=progress(tasks)), 'tasks': [dict(data(t),depends_on=[parent for child,parent in dependencies if child==t.id]) for t in tasks], 'events': [data(e) for e in events], 'files': [data(f, ('storage_key', 'extracted_text')) for f in files], 'issues':[data(i) for i in db.scalars(select(Issue).where(Issue.project_id==p.id).order_by(Issue.created_at.desc()))], 'milestones':[data(i) for i in db.scalars(select(Milestone).where(Milestone.project_id==p.id).order_by(Milestone.due_date))], 'meetings':[meeting_data(db,i) for i in db.scalars(select(Meeting).where(or_(Meeting.project_id==p.id,Meeting.id.in_(select(MeetingProject.meeting_id).where(MeetingProject.project_id==p.id)))).order_by(Meeting.created_at.desc()))]}


@router.patch('/projects/{project_id}')
def update_project(project_id: str, body: ProjectUpdate, db: DB, user: Auth):
    p = owned(db, Project, project_id, user)
    check_version(p, body.version)
    values = updates(body, ('version', 'reason'))
    if any(v is None for k, v in values.items() if k != 'due_date'):
        raise HTTPException(422, '字段不能为空')
    if values.get('status') in ('delivered', 'archived'):
        if db.scalar(select(Issue.id).where(Issue.project_id==p.id,Issue.severity=='blocking',Issue.status!='closed')):
            raise HTTPException(409,'请先关闭阻断问题')
        if db.scalar(select(Milestone.id).where(Milestone.project_id==p.id,Milestone.status!='completed')):
            raise HTTPException(409,'请先完成项目里程碑')
        if not body.reason or any(t.status not in ('done', 'cancelled') for t in project_tasks(db, p.id)):
            raise HTTPException(422, '请完成任务并填写验收依据')
    before = {k: getattr(p, k) for k in values}
    for key, value in values.items():
        setattr(p, key, value)
    p.updated_at = now()
    record(db, p.id, user, 'change', '更新项目', detail=describe_changes(before,values,body.reason))
    db.flush()
    from .project_analysis import enqueue_project
    enqueue_project(db,p)
    return data(p)


@router.post('/projects/{project_id}/tasks', status_code=201)
def create_task(project_id: str, body: TaskCreate, db: DB, user: Auth):
    p = owned(db, Project, project_id, user)
    t = Task(project_id=p.id, **body.model_dump(mode='json'))
    db.add(t)
    db.flush()
    record(db, p.id, user, 'task', '新增任务：' + t.title, source_id=t.id)
    return data(t)


@router.patch('/tasks/{task_id}')
def update_task(task_id: str, body: TaskUpdate, db: DB, user: Auth):
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, '任务不存在')
    owned(db, Project, t.project_id, user)
    check_version(t, body.version)
    values = updates(body)
    if any(v is None for k, v in values.items() if k != 'due_date'):
        raise HTTPException(422, '字段不能为空')
    if values.get('status', t.status) == 'done' and not values.get('evidence', t.evidence).strip():
        raise HTTPException(422, '请填写完成依据')
    if values.get('status')=='done':
        parents=db.scalars(select(Task).join(TaskDependency,Task.id==TaskDependency.depends_on_id).where(TaskDependency.task_id==t.id)).all()
        if any(parent.status!='done' for parent in parents):raise HTTPException(409,'请先完成前置任务')
    if t.status=='done' and values.get('status',t.status)!='done':
        completed_child=db.scalar(select(Task.id).join(TaskDependency,Task.id==TaskDependency.task_id).where(TaskDependency.depends_on_id==t.id,Task.status=='done').limit(1))
        if completed_child:raise HTTPException(409,'请先重新打开后续已完成任务')
    before = {k: getattr(t, k) for k in values}
    for k, v in values.items():
        setattr(t, k, v)
    record(db, t.project_id, user, 'task', '更新任务：' + t.title, detail=describe_changes(before,values), source_id=t.id)
    db.flush()
    return data(t)


@router.post('/projects/{project_id}/events', status_code=201)
def add_event(project_id: str, body: EventCreate, db: DB, user: Auth):
    owned(db, Project, project_id, user)
    when = body.occurred_at
    if when is not None and when.tzinfo is None:
        raise HTTPException(422, '请选择含时区的发生时间')
    kwargs = {'detail': body.detail}
    if when:
        kwargs['occurred_at'] = when.astimezone(timezone.utc).isoformat(timespec='microseconds')
    return data(record(db, project_id, user, body.kind, body.title, **kwargs))


@router.get('/dashboard')
def dashboard(db: DB, user: Auth):
    projects = db.scalars(select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc())).all()
    rows, project_rows,risks = [], [],[]
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    for p in projects:
        tasks = project_tasks(db, p.id)
        from .delivery import risks_for
        risks.extend(risks_for(db,p,tasks,today))
        from .workflow import flow,analysis_data
        project_rows.append(dict(data(p), workflow=flow(db,p), analysis=analysis_data(db,p.id), counts=material_counts(db,p.id), progress=progress(tasks)))
        for t in tasks:
            if t.status not in ('done', 'cancelled'):
                rows.append(dict(data(t), project_name=p.name, overdue=bool(t.due_date and t.due_date < today)))
    rows.sort(key=lambda t: (not t['overdue'], t['due_date'] or '9999', t['id']))
    from .source_summary import document_progress
    return {'projects': project_rows, 'tasks': rows, 'overdue': sum(t['overdue'] for t in rows), 'blocked': sum(t['status'] == 'blocked' for t in rows), 'risks':risks,'document_progress':document_progress(db,user),'updated_at': now()}
