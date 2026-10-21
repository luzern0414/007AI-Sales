"""Real HTTP/DB tests, isolated from the local working database."""
import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def clients(tmp_path):
    assert importlib.util.find_spec('server') is not None, 'Platform API is not implemented'
    from server.app import create_app
    app = create_app(database_url=f'sqlite:///{tmp_path / "test.db"}', storage_dir=tmp_path / 'files', testing=True)
    with TestClient(app) as a, TestClient(app) as b:
        assert a.post('/api/auth/setup', json={'username': 'owner', 'password': 'StrongPass!2026'}).status_code == 201
        assert a.post('/api/auth/login', json={'username': 'owner', 'password': 'StrongPass!2026'}).status_code == 200
        yield a, b


def create_project(a, **kwargs):
    r = a.post('/api/projects', json={'name': 'Delivery verification', 'customer': 'Isolated test', **kwargs})
    assert r.status_code == 201, r.text
    return r.json()


def test_setup_once_and_requires_auth(clients):
    a, b = clients
    assert b.get('/api/projects').status_code == 401
    assert b.post('/api/auth/setup', json={'username': 'other', 'password': 'StrongPass!2026'}).status_code == 409
    assert a.get('/api/auth/me').json()['username'] == 'owner'
    assert a.post('/api/auth/logout').status_code == 204
    assert a.get('/api/projects').status_code == 401


def test_project_persists_and_version_conflict(clients):
    a, _ = clients
    p = create_project(a)
    assert a.get('/api/projects').json()[0]['id'] == p['id']
    url = f'/api/projects/{p["id"]}'
    r = a.patch(url, json={'version': 1, 'name': 'Revised'})
    assert r.status_code == 200 and r.json()['version'] == 2
    assert a.patch(url, json={'version': 1, 'name': 'Lost edit'}).status_code == 409
    assert a.get(url).json()['project']['name'] == 'Revised'
    assert len(a.get(url).json()['events']) == 2


def test_other_user_cannot_read_or_write(clients):
    a, b = clients
    p = create_project(a)
    assert a.post('/api/users', json={'username': 'second', 'password': 'SecondPass!2026'}).status_code == 201
    assert b.post('/api/auth/login', json={'username': 'second', 'password': 'SecondPass!2026'}).status_code == 200
    assert b.get('/api/projects').json() == []
    assert b.get(f'/api/projects/{p["id"]}').status_code == 404
    assert b.post(f'/api/projects/{p["id"]}/tasks', json={'title': 'Forbidden'}).status_code == 404
    assert b.post('/api/users', json={'username': 'third', 'password': 'ThirdPass!2026'}).status_code == 403


def test_task_progress_requires_completion_evidence(clients):
    a, _ = clients
    p = create_project(a)
    assert a.get('/api/dashboard').json()['projects'][0]['progress'] is None
    url = f'/api/projects/{p["id"]}/tasks'
    r = a.post(url, json={'title': 'Verify persistence', 'due_date': str(date.today() - timedelta(days=1))})
    assert r.status_code == 201
    t = r.json()
    dash = a.get('/api/dashboard').json()
    assert dash['overdue'] == 1 and dash['projects'][0]['progress'] == 0
    task_url = f'/api/tasks/{t["id"]}'
    assert a.patch(task_url, json={'version': 1, 'status': 'done'}).status_code == 422
    assert a.patch(task_url, json={'version': 1, 'status': 'done', 'evidence': 'Signed test record #1'}).status_code == 200
    dash = a.get('/api/dashboard').json()
    assert dash['overdue'] == 0 and dash['projects'][0]['progress'] == 100
    assert a.get(f'/api/projects/{p["id"]}').json()['tasks'][0]['evidence'] == 'Signed test record #1'


def test_event_order_and_date_validation(clients):
    a, _ = clients
    p = create_project(a)
    url = f'/api/projects/{p["id"]}/events'
    assert a.post(url, json={'title': 'Earlier', 'kind': 'progress', 'occurred_at': '2020-01-01T09:00:00+08:00'}).status_code == 201
    assert a.post(url, json={'title': 'Later', 'kind': 'issue', 'occurred_at': '2021-01-01T09:00:00+08:00'}).status_code == 201
    e = a.get(f'/api/projects/{p["id"]}').json()['events']
    assert next(i for i, x in enumerate(e) if x['title'] == 'Later') < next(i for i, x in enumerate(e) if x['title'] == 'Earlier')
    assert a.post(url, json={'title': 'Invalid', 'occurred_at': 'not-a-date'}).status_code == 422
    assert a.post(f'/api/projects/{p["id"]}/tasks', json={'title': 'Invalid', 'due_date': 'tomorrow'}).status_code == 422


def test_file_integrity_download_and_isolation(clients):
    a, b = clients
    p = create_project(a)
    content = '会议原始记录：范围待确认'.encode()
    url = f'/api/projects/{p["id"]}/files'
    r = a.post(url, files={'file': ('meeting.md', content, 'text/markdown')})
    assert r.status_code == 201, r.text
    f = r.json()
    assert f['size'] == len(content) and len(f['sha256']) == 64
    assert a.get(f'/api/files/{f["id"]}/download').content == content
    assert b.get(f'/api/files/{f["id"]}/download').status_code == 401
    assert a.get(f'/api/projects/{p["id"]}').json()['files'][0]['id'] == f['id']
    assert a.post(url, files={'file': ('payload.html', b'<script>bad()</script>', 'text/html')}).status_code == 422
    assert a.post(url, files={'file': ('fake.pdf', b'not a PDF', 'application/pdf')}).status_code == 422


def test_product_published_view_is_allowlisted(clients):
    a, _ = clients
    r = a.post('/api/products', json={'name': 'Verified product', 'summary': 'Approved overview', 'internal_notes': 'Private cost', 'demo_url': 'https://demo.example.com'})
    assert r.status_code == 201, r.text
    p = r.json()
    assert a.get('/api/showcase').json() == []
    assert a.post(f'/api/products/{p["id"]}/publish', json={'version': 1, 'approved': False}).status_code == 422
    assert a.post(f'/api/products/{p["id"]}/publish', json={'version': 1, 'approved': True}).status_code == 200
    public = a.get('/api/showcase').json()[0]
    assert public['name'] == 'Verified product'
    assert 'internal_notes' not in public and 'owner_id' not in public
    assert a.post('/api/products', json={'name': 'Unsafe', 'demo_url': 'javascript:alert(1)'}).status_code == 422
    assert a.post('/api/products', json={'name': 'Private URL', 'demo_url': 'https://127.0.0.1/'}).status_code == 422


def test_write_is_committed_before_response_starts(tmp_path):
    from server.app import create_app
    from server.db import User
    from sqlalchemy import select
    app = create_app(database_url=f'sqlite:///{tmp_path / "commit.db"}', storage_dir=tmp_path / 'files', testing=True)
    observed = []

    @app.middleware('http')
    async def inspect_commit(request, call_next):
        response = await call_next(request)
        if request.url.path == '/api/auth/setup':
            with app.state.sessions() as other:
                observed.append(other.scalar(select(User.id)) is not None)
        return response

    with TestClient(app) as client:
        assert client.post('/api/auth/setup', json={'username': 'admin', 'password': 'StrongPass!2026'}).status_code == 201
        assert observed == [True], 'Successful response must not race its transaction commit'
