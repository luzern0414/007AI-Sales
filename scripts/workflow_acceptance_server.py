"""Isolated UI acceptance fixture. Never connects to the normal platform database."""
import asyncio
import io
import os
import sys
import wave
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[1] / 'output/playwright/workflow'
ROOT.mkdir(parents=True, exist_ok=True)
os.environ['ALLOWED_ORIGINS'] = 'http://127.0.0.1:18767'
os.environ['PROJECTS_ROOT'] = str(ROOT / 'projects')
(ROOT / 'projects').mkdir(exist_ok=True)
from server.app import create_app
from server.automation import drain_jobs
from fastapi.testclient import TestClient

database=ROOT/'acceptance.db'
if database.exists():
    import sqlite3
    from alembic import command
    from alembic.config import Config
    with sqlite3.connect(database) as db:
        columns={r[1] for r in db.execute('PRAGMA table_info(analysis_jobs)')}
        if columns and 'priority' not in columns:db.execute('ALTER TABLE analysis_jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0')
        versioned=bool(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone())
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    config.attributes['database_url']='sqlite:///'+database.as_posix()
    if not versioned:command.stamp(config,'f932ab63d510')
    command.upgrade(config,'head')

app = create_app('sqlite:///' + (ROOT / 'acceptance.db').as_posix(), ROOT / 'files', testing=True)


def model(purpose, payload):
    if purpose == 'project_chunk':
        return {'summary': '验收资料说明接口联调条件与交付约束。', 'risks': [{'category': 'technical', 'title': '接口开放时间待确认', 'detail': '确认接口开放日期后安排联调。', 'quote': '客户接口尚未开放', 'source_id': payload['source']['id']}]}
    if purpose == 'project_review':
        confirmed = payload['workflow']['confirmed']
        return {'summary': f'验收环境：已确认{confirmed}个流程节点；资料明确了接口联调条件，接口开放日期仍待核实。', 'next': '确认接口开放日期并跟进下一节点。', 'risks': payload['risks'][:3]}
    if purpose == 'file_chunk': return {'summary': '验收资料明确接口联调约束。', 'terms': []}
    if purpose == 'meeting_chunk': return {'summary': '验收会议讨论联调条件。', 'facts': [], 'projects': []}
    if purpose == 'meeting_summary': return {'title': '验收会议 · 接口对接', 'markdown': '本次确认接口开放日期需继续跟进。'}
    if purpose == 'context_reduce': return {'summary': '验收环境资料与接口约束。'}
    return {'summary': '验收资料说明接口联调条件与交付约束。', 'previous': '已收到客户背景。', 'current': '本次明确接口联调条件。', 'next': '确认接口开放日期。'}


app.state.analysis_model = model
with TestClient(app) as client:
    if not client.get('/api/auth/status').json().get('initialized'):
        client.post('/api/auth/setup', json={'username': 'workflow-ui', 'password': 'WorkflowUI!2026'})
    else: client.post('/api/auth/login', json={'username': 'workflow-ui', 'password': 'WorkflowUI!2026'})
    assert client.post('/api/auth/login', json={'username': 'workflow-ui', 'password': 'WorkflowUI!2026'}).status_code == 200
    # Initialize only once; repeated launches preserve UI actions for refresh verification.
    if not client.get('/api/projects').json():
        p = client.post('/api/projects', json={'name': '验收环境 · 客户协同平台', 'customer': '验收客户', 'directory_name': '001Acceptance', 'create_directory': True}).json()
        base = '/api/projects/' + p['id']
        for name, text in [('客户需求.md', '验收环境资料。客户接口尚未开放，需确认联调时间。'), ('项目方案.md', '验收环境方案。说明客户协同流程、权限设计及交付清单。')]:
            client.post(base + '/files', files={'file': (name, text.encode(), 'text/markdown')})
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000); out.writeframes(b'\x00\x00' * 8000)
        client.post(base + '/files', files={'file': ('验收会议.wav', buffer.getvalue(), 'audio/wav')})
        m = client.get(base).json()['meetings'][0]
        client.patch('/api/meetings/' + m['id'], json={'version': m['version'], 'transcript': '验收环境转写：客户接口尚未开放，下次确认联调日期。'})
        client.post(base + '/analyze', json={'background': '验收环境：客户采用自研系统，先确认接口条件。', 'instructions': '核实接口与交付风险。'})
        drain_jobs(app, 20)

original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(application):
    async with original_lifespan(application):
        async def worker():
            while True:
                await asyncio.to_thread(drain_jobs, app, 1)
                await asyncio.sleep(1)
        task = asyncio.create_task(worker())
        try: yield
        finally:
            task.cancel()
            from contextlib import suppress
            with suppress(asyncio.CancelledError): await task


app.router.lifespan_context = lifespan
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=18767)
