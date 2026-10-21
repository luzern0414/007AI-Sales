"""Human-authoritative lifecycle, analysis requests and immutable confirmation history."""
import json
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select

from .auth import Auth
from .common import DB, owned, record, check_version, data
from .db import Project, WorkflowNode, ProjectAnalysis, ProjectEvent, now

router = APIRouter(prefix='/api')
NODES = [('negotiation', '客户洽谈'), ('requirements', '需求确认'), ('proposal', '方案提交'),
         ('contract', '合同签订'), ('development', '开发启动'), ('delivery', '项目交付'),
         ('acceptance', '验收通过'), ('maintenance', '维护移交')]
# Cumulative share of the whole delivery when each node completes; development carries the most work.
WEIGHTS = {'negotiation': 5, 'requirements': 15, 'proposal': 28, 'contract': 38, 'development': 70,
           'delivery': 85, 'acceptance': 95, 'maintenance': 100}


def insight_of(db, pid):
    row = db.get(ProjectAnalysis, pid)
    try: return json.loads(row.insight_json or '{}') if row else {}
    except ValueError: return {}


def insight_view(db, pid):
    from .agent import feedback_state
    insight = insight_of(db, pid)
    state = feedback_state(db, pid)
    insight['actions'] = [{**a, 'state': state.get(a.get('id'), {}).get('verdict')} for a in insight.get('actions', [])]
    return insight


def progress_view(nodes, insight):
    """Confirmed milestones set the floor; the AI stage judgement refines progress inside the current stage."""
    keys = [k for k, _ in NODES]
    furthest = max((i for i, n in enumerate(nodes) if n['confirmed']), default=-1)
    confirmed = WEIGHTS[keys[furthest]] if furthest >= 0 else 0
    stage = insight.get('stage') if insight.get('stage') in keys else None
    if stage and keys.index(stage) <= furthest: stage = None
    percent, basis = confirmed, 'confirmed'
    if stage:
        # Sum each node's share: done counts fully, the current stage by its progress, other started work by half.
        judged = {n.get('key'): n.get('status') for n in insight.get('nodes', []) if isinstance(n, dict)}
        within = max(0, min(100, int(insight.get('stage_progress') or 0))) / 100
        total, previous = 0.0, 0
        for i, key in enumerate(keys):
            share = WEIGHTS[key] - previous; previous = WEIGHTS[key]
            done = i <= furthest or judged.get(key) == 'done'
            total += share * (1 if done else within if key == stage else .5 if judged.get(key) == 'doing' else 0)
        estimate = round(total)
        if estimate > percent: percent, basis = estimate, 'ai'
    elif furthest + 1 < len(keys):
        stage = keys[furthest + 1]
    return {'percent': percent, 'confirmed_percent': confirmed, 'basis': basis, 'stage': stage,
            'stage_title': dict(NODES).get(stage, '已完成'), 'stage_progress': insight.get('stage_progress') if basis == 'ai' else None,
            'weights': WEIGHTS}


def flow(db, p):
    rows = {r.key: r for r in db.scalars(select(WorkflowNode).where(WorkflowNode.project_id == p.id))}
    nodes = [dict(key=key, title=title, confirmed=bool(rows.get(key) and rows[key].confirmed),
                  occurred_at=rows[key].occurred_at if key in rows else None,
                  evidence=rows[key].evidence if key in rows else '',
                  version=rows[key].version if key in rows else 0,
                  actor_id=rows[key].actor_id if key in rows else None) for key, title in NODES]
    confirmed = sum(n['confirmed'] for n in nodes)
    furthest = max((index for index,n in enumerate(nodes) if n['confirmed']), default=-1)
    current = nodes[furthest+1]['key'] if furthest+1 < len(nodes) else None
    insight = insight_of(db, p.id)
    suggested = {a.get('key'): a for a in insight.get('nodes', []) if isinstance(a, dict)}
    for n in nodes:
        a = suggested.get(n['key'])
        n['weight'] = WEIGHTS[n['key']]
        n['ai'] = {'status': a.get('status'), 'evidence': a.get('evidence', '')} if a and not n['confirmed'] else None
    return {'nodes': nodes, 'confirmed': confirmed, 'total': len(nodes), 'current': current, 'progress': progress_view(nodes, insight),
            'due_date': p.due_date if rows.get('contract') and rows['contract'].confirmed else None}


def analysis_data(db, pid):
    row = db.get(ProjectAnalysis, pid)
    if row:
        from .db import AnalysisJob,DevelopmentDay
        job=db.scalar(select(AnalysisJob).where(AnalysisJob.kind=='project',AnalysisJob.target_id==pid,AnalysisJob.fingerprint==row.input_hash))
        unread=json.loads(job.result_json).get('review',{}).get('unread_sources',[]) if job else []
        latest=db.scalar(select(DevelopmentDay).where(DevelopmentDay.project_id==pid).order_by(DevelopmentDay.day.desc()).limit(1))
        from .automation import project_queue
        return dict(data(row, ('risks_json','insight_json')), risks=json.loads(row.risks_json),insight=insight_view(db,pid),unread_sources=unread,development=json.loads(latest.result_json) if latest else None,queue=project_queue(db,pid))
    from .automation import project_queue
    return {'status': 'pending', 'background': '', 'instructions': '', 'summary': '', 'next_step': '', 'risks': [], 'insight': {}, 'analyzed_at': None,'unread_sources':[],'queue':project_queue(db,pid)}


def confirmation_history(db,pid):
    rows=db.scalars(select(ProjectEvent).where(ProjectEvent.project_id==pid,ProjectEvent.kind=='workflow').order_by(ProjectEvent.recorded_at.desc(),ProjectEvent.id.desc()).limit(200))
    result=[]
    for row in rows:
        try:after=json.loads(row.detail)['after']
        except (ValueError,KeyError,TypeError):continue
        result.append({'id':row.id,'key':after['key'],'title':row.title,'confirmed':after['confirmed'],'occurred_at':after['occurred_at'],
                       'recorded_at':row.recorded_at,'evidence':after['evidence'],'actor_id':row.actor_id})
    return result


@router.get('/projects/{project_id}/workflow')
def get_workflow(project_id: str, db: DB, user: Auth):
    p = owned(db, Project, project_id, user)
    return {**flow(db, p), 'analysis': analysis_data(db, p.id),'history':confirmation_history(db,p.id)}


class NodeUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=0)
    confirmed: bool
    occurred_at: datetime | None = None
    evidence: str = Field(min_length=1, max_length=4000)
    due_date: date | None = None


@router.put('/projects/{project_id}/workflow/{key}')
def confirm(project_id: str, key: str, body: NodeUpdate, request: Request, db: DB, user: Auth):
    p = owned(db, Project, project_id, user)
    if key not in dict(NODES): raise HTTPException(404, '节点不存在')
    row = db.get(WorkflowNode, (p.id, key))
    if (row.version if row else 0) != body.version: raise HTTPException(409, '节点已更新，请刷新后重试')
    if body.confirmed and (body.occurred_at is None or body.occurred_at.tzinfo is None):
        raise HTTPException(422, '请填写实际发生时间')
    if body.occurred_at and (body.occurred_at.tzinfo is None or body.occurred_at > datetime.now(timezone.utc)):
        raise HTTPException(422, '实际时间不能晚于现在')
    contract = db.get(WorkflowNode, (p.id, 'contract'))
    if body.due_date and (key not in [n[0] for n in NODES[3:]] or not ((key == 'contract' and body.confirmed) or (contract and contract.confirmed))):
        raise HTTPException(409, '签约后才能设置计划交付')
    if not body.confirmed and key == 'contract': p.due_date = None
    if body.due_date: p.due_date = body.due_date.isoformat()
    before = data(row) if row else None
    if row is None:
        row = WorkflowNode(project_id=p.id, key=key, actor_id=user.id)
        db.add(row)
    row.confirmed = body.confirmed
    row.occurred_at = body.occurred_at.astimezone(timezone.utc).isoformat(timespec='microseconds') if body.confirmed else None
    row.evidence, row.actor_id, row.updated_at = body.evidence, user.id, now()
    p.updated_at = now()
    db.flush()
    record(db, p.id, user, 'workflow', ('确认：' if body.confirmed else '撤回：') + dict(NODES)[key],
           detail=json.dumps({'before': before, 'after': data(row), 'due_date': p.due_date}, ensure_ascii=False),
           occurred_at=row.occurred_at or now())
    from .project_analysis import enqueue_project
    enqueue_project(db, p, urgent=True)
    db.commit()
    from .docs_structure import export_state
    export_state(request.app, p.id)
    return {**flow(db, p), 'analysis': analysis_data(db, p.id)}


class AnalyzeBody(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    background: str = Field(default='', max_length=30000)
    instructions: str = Field(default='', max_length=10000)
    expected_hash: str | None = None


@router.post('/projects/{project_id}/analyze', status_code=202)
def analyze(project_id: str, body: AnalyzeBody, db: DB, user: Auth):
    p = owned(db, Project, project_id, user)
    row = db.get(ProjectAnalysis, p.id)
    if row is None:
        row = ProjectAnalysis(project_id=p.id); db.add(row); db.flush()
    if body.expected_hash is not None and row.input_hash != body.expected_hash:
        raise HTTPException(409, '背景已更新，请刷新后重试')
    row.background, row.instructions, row.updated_at = body.background, body.instructions, now()
    record(db, p.id, user, 'analysis', '重新分析项目', detail=json.dumps({'background': body.background, 'instructions': body.instructions}, ensure_ascii=False))
    from .project_analysis import enqueue_project
    job = enqueue_project(db, p, force=True, urgent=True)
    return {'id': job.id, 'status': job.status}
