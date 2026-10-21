"""Manager-facing agent turns: act on AI suggestions, and ask the project agent questions.

Every turn is stored as a project event; the next project review reads them back as memory,
so adopted and dismissed suggestions steer how the agent reasons and advises.
"""
import json
from typing import Literal

from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .auth import Auth
from .common import DB, owned, record
from .db import Project, ProjectEvent, ProjectAnalysis, Task, Issue
from .analysis_model import call_model, stream_model, AnalysisError

router = APIRouter(prefix='/api')

TONE = ('语气像资深项目总监：直接、干脆、敢下判断，必要时尖锐指出问题和失职；不寒暄、不客套、不复述问题、不写“根据资料”“希望对你有帮助”之类的话。')
ASK_RULES = ('你是这个项目的AI参谋，回答项目经理的问题。' + TONE + '先在thinking中按步骤推理（2至4步，每步不超过40字），'
             '再给出answer。返回JSON {"thinking":["..."],"answer":"markdown，不超过250字，第一句就是结论，其余用短列点","basis":["引用的资料或会议名称，最多4个"],'
             '"follow_ups":["经理可能接着问的问题，最多3个，每个不超过20字"]}。只依据输入的项目资料、AI判断、任务和历史问答作答；'
             '资料没有的写待确认并说明需要补充什么，不编造日期、金额、负责人和完成状态；建议不能写成已发生的事实。')


class Feedback(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    action_id: str = Field(min_length=1, max_length=40)
    verdict: Literal['adopt', 'dismiss']
    note: str = Field(default='', max_length=500)


class Ask(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=500)


def feedback_state(db, pid):
    state = {}
    for e in db.scalars(select(ProjectEvent).where(ProjectEvent.project_id == pid, ProjectEvent.kind == 'ai_feedback').order_by(ProjectEvent.recorded_at)):
        try: item = json.loads(e.detail)
        except ValueError: continue
        state[item.get('action_id')] = {'verdict': item.get('verdict'), 'task_id': item.get('task_id'), 'at': e.recorded_at}
    return state


@router.post('/projects/{pid}/insight/actions')
def act(pid: str, body: Feedback, db: DB, user: Auth):
    p = owned(db, Project, pid, user)
    from .workflow import insight_of
    action = next((a for a in insight_of(db, p.id).get('actions', []) if a.get('id') == body.action_id), None)
    if not action: raise HTTPException(409, '建议已更新，请刷新后重试')
    if body.action_id in feedback_state(db, p.id): raise HTTPException(409, '该建议已处理')
    task_id = None
    if body.verdict == 'adopt':
        task = Task(project_id=p.id, title=action['title'][:240])
        db.add(task); db.flush(); task_id = task.id
    record(db, p.id, user, 'ai_feedback', ('采纳AI建议：' if body.verdict == 'adopt' else '忽略AI建议：') + action['title'],
           detail=json.dumps({'action_id': body.action_id, 'verdict': body.verdict, 'title': action['title'], 'why': action.get('why', ''),
                              'note': body.note, 'task_id': task_id}, ensure_ascii=False))
    from .project_analysis import enqueue_project
    enqueue_project(db, p)
    return {'action_id': body.action_id, 'verdict': body.verdict, 'task_id': task_id}


def ask_context(db, p):
    from .automation import context
    from .workflow import flow, analysis_data
    from .activity import latest_digests
    review = analysis_data(db, p.id)
    lifecycle = flow(db, p)
    digests = latest_digests(db, p.id)
    sources = context(db, p.id)[-60:]
    history = []
    for e in db.scalars(select(ProjectEvent).where(ProjectEvent.project_id == p.id, ProjectEvent.kind == 'ai_ask').order_by(ProjectEvent.recorded_at.desc()).limit(4)):
        try: item = json.loads(e.detail)
        except ValueError: continue
        history.append({'question': item.get('question'), 'answer': (item.get('answer') or '')[:300]})
    return {'project': {'name': p.name, 'customer': p.customer, 'due_date': p.due_date},
            'summary': review.get('summary'), 'next_step': review.get('next_step'), 'insight': review.get('insight', {}),
            'lifecycle': [{'title': n['title'], 'confirmed': n['confirmed'], 'occurred_at': n['occurred_at'], 'evidence': n['evidence']} for n in lifecycle['nodes']],
            'progress': lifecycle['progress'],
            'timeline': [v.get('headline') for v in digests.values()][:40],
            'sources': [{'source': s['source'], 'time': s['time'], 'summary': s['summary']} for s in sources],
            'tasks': [{'title': t.title, 'status': t.status, 'due_date': t.due_date} for t in db.scalars(select(Task).where(Task.project_id == p.id).limit(40))],
            'issues': [{'title': i.title, 'status': i.status} for i in db.scalars(select(Issue).where(Issue.project_id == p.id).limit(30))],
            'previous_questions': list(reversed(history))}


def ask_view(e):
    try: item = json.loads(e.detail)
    except ValueError: item = {}
    return {'id': e.id, 'question': item.get('question', e.title), 'answer': item.get('answer', ''), 'thinking': item.get('thinking', []),
            'basis': item.get('basis', []), 'follow_ups': item.get('follow_ups', []), 'at': e.recorded_at}


@router.get('/projects/{pid}/asks')
def asks(pid: str, db: DB, user: Auth):
    p = owned(db, Project, pid, user)
    rows = db.scalars(select(ProjectEvent).where(ProjectEvent.project_id == p.id, ProjectEvent.kind == 'ai_ask').order_by(ProjectEvent.recorded_at.desc()).limit(20))
    return [ask_view(e) for e in rows]


@router.post('/projects/{pid}/ask', status_code=201)
def ask(pid: str, body: Ask, request: Request, db: DB, user: Auth):
    p = owned(db, Project, pid, user)
    payload = {'question': body.question, **ask_context(db, p)}
    db.rollback()  # Release the read transaction while the model thinks.
    try:
        result = call_model(request.app, 'project_ask', payload, ASK_RULES)
    except AnalysisError as exc:
        raise HTTPException(503, str(exc)) from None
    answer = result.get('answer')
    if not isinstance(answer, str) or not answer.strip(): raise HTTPException(503, 'AI回答不完整，请重试')
    strings = lambda v, n, size: [x.strip()[:size] for x in v if isinstance(x, str) and x.strip()][:n] if isinstance(v, list) else []
    p = owned(db, Project, pid, user)
    event = record(db, p.id, user, 'ai_ask', body.question[:500], detail=json.dumps({
        'question': body.question, 'answer': answer.strip()[:4000], 'thinking': strings(result.get('thinking'), 4, 120),
        'basis': strings(result.get('basis'), 4, 120), 'follow_ups': strings(result.get('follow_ups'), 3, 40)}, ensure_ascii=False))
    # A question tells the agent what the manager cares about; the next review takes it into account.
    from .project_analysis import enqueue_project
    enqueue_project(db, p)
    return ask_view(event)


FOLLOW_MARK = '<<<追问>>>'
STREAM_RULES = ('你是这个项目的AI参谋，回答项目经理的问题。' + TONE +
                '直接输出Markdown正文，不要JSON、不要代码块、不要标题。第一行用一句加粗的话给出结论；'
                '随后最多5个短列点（每点不超过30字），写依据、卡点或下一步动作，动作要具体到人、事、产出。总长不超过220字。'
                '只依据输入的项目资料、AI判断、任务和历史问答；资料没有的直说“缺：xxx”，不编造日期、金额、负责人和完成状态，建议不能写成已发生的事实。'
                '正文结束后另起一行输出' + FOLLOW_MARK + '，再逐行给出2至3个经理可能追问的问题（每个不超过16字，不加序号）。')


def split_answer(text):
    answer, _, tail = text.partition(FOLLOW_MARK)
    follow = [line.strip(' -*·0123456789.、') for line in tail.splitlines()]
    return answer.strip(), [f[:40] for f in follow if f][:3]


def sse(event, data):
    return 'event: ' + event + '\ndata: ' + json.dumps(data, ensure_ascii=False) + '\n\n'


@router.post('/projects/{pid}/ask/stream')
def ask_stream(pid: str, body: Ask, request: Request, db: DB, user: Auth):
    """Server-sent events: `delta` text chunks, then `done` with the stored turn, or `error`."""
    p = owned(db, Project, pid, user)
    payload = {'question': body.question, **ask_context(db, p)}
    project_id, actor = p.id, SimpleNamespace(id=user.id)
    db.rollback()  # The stream outlives this request's transaction.
    app = request.app

    def events():
        text = ''
        try:
            for delta in stream_model(app, 'project_ask', payload, STREAM_RULES):
                text += delta
                yield sse('delta', {'t': delta})
        except AnalysisError as exc:
            yield sse('error', {'message': str(exc)}); return
        answer, follow = split_answer(text)
        if not answer:
            yield sse('error', {'message': 'AI回答不完整，请重试'}); return
        with app.state.sessions() as session:
            event = record(session, project_id, actor, 'ai_ask', body.question[:500], detail=json.dumps(
                {'question': body.question, 'answer': answer[:4000], 'thinking': [], 'basis': [], 'follow_ups': follow}, ensure_ascii=False))
            from .project_analysis import enqueue_project
            enqueue_project(session, session.get(Project, project_id))
            session.commit()
            view = ask_view(event)
        yield sse('done', view)

    return StreamingResponse(events(), media_type='text/event-stream', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
