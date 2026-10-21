from datetime import date
from typing import Literal

from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select

from .auth import Auth
from .common import DB,owned,check_version,record,data,describe_changes
from .db import Project,Task,TaskDependency,Issue,Milestone

router=APIRouter(prefix='/api')


class DependencyCreate(BaseModel):
    depends_on_id:str


class IssueCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title:str=Field(min_length=1,max_length=240)
    detail:str=Field(default='',max_length=20000)
    severity:Literal['normal','high','blocking']='normal'
    assignee:str=Field(default='',max_length=100)
    due_date:date|None=None


class IssueUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    version:int=Field(ge=1)
    status:Literal['open','working','resolved','closed']
    resolution:str=Field(default='',max_length=20000)


class MilestoneCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title:str=Field(min_length=1,max_length=240)
    due_date:date


class MilestoneUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    version:int=Field(ge=1)
    status:Literal['pending','completed']
    evidence:str=Field(default='',max_length=10000)
    due_date:date|None=None
    reason:str=Field(default='',max_length=2000)


@router.post('/tasks/{task_id}/dependencies',status_code=201)
def dependency(task_id:str,body:DependencyCreate,db:DB,user:Auth):
    task=db.get(Task,task_id)
    predecessor=db.get(Task,body.depends_on_id)
    if task is None or predecessor is None:
        raise HTTPException(404,'任务不存在')
    owned(db,Project,task.project_id,user)
    if task.project_id!=predecessor.project_id:
        raise HTTPException(422,'请选择同项目任务')
    if task.status=='done' and predecessor.status!='done':
        raise HTTPException(409,'已完成任务只能关联已完成的前置任务')
    edges=db.execute(select(TaskDependency.task_id,TaskDependency.depends_on_id).join(Task,Task.id==TaskDependency.task_id).where(Task.project_id==task.project_id)).all()
    graph={}
    for child,parent in edges:
        graph.setdefault(child,[]).append(parent)
    visited=set();queue=[predecessor.id]
    while queue:
        current=queue.pop()
        if current==task.id:
            raise HTTPException(409,'任务依赖形成循环')
        if current not in visited:
            visited.add(current);queue.extend(graph.get(current,[]))
    if (task.id,predecessor.id) in edges:
        raise HTTPException(409,'依赖已存在')
    db.add(TaskDependency(task_id=task.id,depends_on_id=predecessor.id))
    record(db,task.project_id,user,'task','关联任务依赖',detail=task.title+' ← '+predecessor.title,source_id=task.id)
    return {'task_id':task.id,'depends_on_id':predecessor.id}


@router.delete('/tasks/{task_id}/dependencies/{depends_on_id}',status_code=204)
def remove_dependency(task_id:str,depends_on_id:str,db:DB,user:Auth):
    task=db.get(Task,task_id)
    if not task:raise HTTPException(404,'任务不存在')
    owned(db,Project,task.project_id,user)
    row=db.get(TaskDependency,(task_id,depends_on_id))
    if not row:raise HTTPException(404,'依赖不存在')
    db.delete(row)
    record(db,task.project_id,user,'task','移除任务依赖',source_id=task.id)


@router.post('/projects/{project_id}/issues',status_code=201)
def create_issue(project_id:str,body:IssueCreate,db:DB,user:Auth):
    owned(db,Project,project_id,user)
    row=Issue(project_id=project_id,**body.model_dump(mode='json'))
    db.add(row);db.flush()
    record(db,project_id,user,'issue','新增问题：'+row.title,detail=row.detail,source_id=row.id)
    from .project_analysis import enqueue_project
    enqueue_project(db,db.get(Project,project_id))
    return data(row)


@router.patch('/issues/{issue_id}')
def update_issue(issue_id:str,body:IssueUpdate,db:DB,user:Auth):
    row=db.get(Issue,issue_id)
    if row is None:raise HTTPException(404,'问题不存在')
    owned(db,Project,row.project_id,user);check_version(row,body.version)
    if body.status in ('resolved','closed') and not body.resolution:
        raise HTTPException(422,'请填写处理结果')
    before=row.status
    row.status,row.resolution=body.status,body.resolution
    record(db,row.project_id,user,'issue','更新问题：'+row.title,detail=describe_changes({'status':before},{'status':body.status},body.resolution),source_id=row.id)
    db.flush()
    from .project_analysis import enqueue_project
    enqueue_project(db,db.get(Project,row.project_id))
    return data(row)


@router.post('/projects/{project_id}/milestones',status_code=201)
def create_milestone(project_id:str,body:MilestoneCreate,db:DB,user:Auth):
    owned(db,Project,project_id,user)
    row=Milestone(project_id=project_id,**body.model_dump(mode='json'))
    db.add(row);db.flush()
    record(db,project_id,user,'milestone','新增里程碑：'+row.title,detail=row.due_date,source_id=row.id)
    return data(row)


@router.patch('/milestones/{milestone_id}')
def update_milestone(milestone_id:str,body:MilestoneUpdate,db:DB,user:Auth):
    row=db.get(Milestone,milestone_id)
    if row is None:raise HTTPException(404,'里程碑不存在')
    owned(db,Project,row.project_id,user);check_version(row,body.version)
    if body.status=='completed' and not body.evidence:raise HTTPException(422,'请填写完成依据')
    if body.due_date and body.due_date.isoformat()!=row.due_date:
        if not body.reason:raise HTTPException(422,'请填写日期变更依据')
        row.due_date=body.due_date.isoformat()
    row.status,row.evidence=body.status,body.evidence
    record(db,row.project_id,user,'milestone','更新里程碑：'+row.title,detail=body.reason+'\n'+body.evidence,source_id=row.id)
    db.flush();return data(row)


def risks_for(db,p,tasks,today):
    from datetime import timedelta
    soon=(date.fromisoformat(today)+timedelta(days=3)).isoformat()
    result=[]
    def add(kind,source,title,due=None):
        result.append({'id':kind+':'+source,'kind':kind,'project_id':p.id,'project_name':p.name,'source_id':source,'title':title,'due_date':due})
    for t in tasks:
        if t.status in ('done','cancelled'):continue
        if t.status=='blocked':add('task_blocked',t.id,t.title,t.due_date)
        if t.due_date and t.due_date<today:add('task_overdue',t.id,t.title,t.due_date)
        elif t.due_date and t.due_date<=soon:add('task_due',t.id,t.title,t.due_date)
    for issue in db.scalars(select(Issue).where(Issue.project_id==p.id,Issue.status!='closed')):
        if issue.severity=='blocking':add('blocking_issue',issue.id,issue.title,issue.due_date)
    for milestone in db.scalars(select(Milestone).where(Milestone.project_id==p.id,Milestone.status!='completed')):
        if milestone.due_date<today:add('milestone_overdue',milestone.id,milestone.title,milestone.due_date)
        elif milestone.due_date<=soon:add('milestone_due',milestone.id,milestone.title,milestone.due_date)
    if p.status=='active' and p.due_date and p.due_date<today:add('project_overdue',p.id,p.name,p.due_date)
    return result
