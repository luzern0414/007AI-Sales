import json
from tests.test_platform import clients,create_project


def test_authorized_folder_sync_tracks_changes_and_rejects_escape(clients,tmp_path,monkeypatch):
    a,b=clients
    source=tmp_path/'authorized';source.mkdir()
    (source/'progress.md').write_text('# 进度\n- [x] 需求确认\n- [ ] 测试',encoding='utf-8')
    monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'delivery-docs':str(source)}))
    p=create_project(a)
    assert a.get('/api/document-sources').json()==[{'key':'delivery-docs'}]
    url=f'/api/projects/{p["id"]}/sources'
    assert a.post(url,json={'source_key':'delivery-docs','subdirectory':'../'}).status_code==422
    r=a.post(url,json={'source_key':'delivery-docs','subdirectory':''})
    assert r.status_code==201,r.text
    link=r.json()
    sync=f'/api/sources/{link["id"]}/sync'
    assert a.post(sync,json={}).status_code==200
    dashboard=a.get('/api/dashboard').json()
    doc=dashboard['document_progress'][0]
    assert (doc['checked'],doc['total'],doc['progress'])==(1,2,50)
    assert doc['source_key']=='delivery-docs' and doc['project_id']==p['id']
    assert dashboard['projects'][0]['progress'] is None
    first=a.get(f'/api/projects/{p["id"]}').json()['files']
    assert len(first)==1 and first[0]['parse_status']=='ready'
    assert a.post(sync,json={}).json()['updated_files']==0
    (source/'progress.md').write_text('# 进度\n- [x] 测试通过',encoding='utf-8')
    assert a.post(sync,json={}).json()['updated_files']==1
    files=a.get(f'/api/projects/{p["id"]}').json()['files']
    assert len(files)==2 and files[0]['previous_version_id']==first[0]['id']
    assert a.get('/api/dashboard').json()['document_progress'][0]['progress']==100
    assert b.post(sync,json={}).status_code==401


def test_disabled_connection_cannot_sync_manually(clients,tmp_path,monkeypatch):
    a,_=clients
    source=tmp_path/'authorized';source.mkdir()
    monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'docs':str(source)}))
    p=create_project(a)
    link=a.post(f'/api/projects/{p["id"]}/sources',json={'source_key':'docs'}).json()
    assert a.delete(f'/api/sources/{link["id"]}').status_code==204
    assert a.post(f'/api/sources/{link["id"]}/sync',json={}).status_code==409
    assert a.get('/api/integrations/status').json()['document_sync']['configured'] is True
    assert a.get('/api/dashboard').json()['document_progress']==[]
    assert a.post(f'/api/sources/{link["id"]}/reconnect',json={}).status_code==200
    assert a.post(f'/api/sources/{link["id"]}/sync',json={}).status_code==200


def test_overlapping_sync_and_disable_cannot_duplicate_or_override_inflight_sync(clients,tmp_path,monkeypatch):
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from server import sources
    a,_=clients
    root=tmp_path/'docs';root.mkdir()
    (root/'progress.md').write_text('- [x] 核对',encoding='utf-8')
    monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'docs':str(root)}))
    p=create_project(a)
    link=a.post(f'/api/projects/{p["id"]}/sources',json={'source_key':'docs'}).json()
    entered,release=threading.Event(),threading.Event()
    original=sources.store
    async def paused(*args,**kwargs):
        entered.set()
        assert await asyncio.to_thread(release.wait,8)
        return await original(*args,**kwargs)
    monkeypatch.setattr(sources,'store',paused)
    url=f'/api/sources/{link["id"]}'
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(a.post,url+'/sync',json={})
        try:
            assert entered.wait(4)
            assert a.post(url+'/sync',json={}).status_code==409
            assert a.delete(url).status_code==409
            sources.synchronize_all(a.app)
        finally:
            release.set()
        result=pending.result(timeout=10)
    assert result.status_code==200,result.text
    assert len(a.get(f'/api/projects/{p["id"]}').json()['files'])==1
    assert a.get(f'/api/projects/{p["id"]}/sources').json()[0]['status']=='synced'
    assert a.post(url+'/sync',json={}).json()['updated_files']==0


def test_failed_sync_releases_claim_and_can_be_retried(clients,tmp_path,monkeypatch):
    from server.db import SourceLink
    a,_=clients
    root=tmp_path/'docs';root.mkdir()
    (root/'bad.pdf').write_bytes(b'not a pdf')
    monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'docs':str(root)}))
    p=create_project(a)
    link=a.post(f'/api/projects/{p["id"]}/sources',json={'source_key':'docs'}).json()
    assert 'sync_token' not in link
    url=f'/api/sources/{link["id"]}/sync'
    assert a.post(url,json={}).status_code==422
    with a.app.state.sessions() as db:
        row=db.get(SourceLink,link['id'])
        assert row.sync_token is None and row.status=='failed'
    (root/'bad.pdf').unlink()
    (root/'progress.md').write_text('- [ ] 核对',encoding='utf-8')
    assert a.post(url,json={}).status_code==200


def test_expired_claim_can_be_recovered_without_stealing_live_claim(clients,tmp_path,monkeypatch):
    from server.db import SourceLink
    a,_=clients
    root=tmp_path/'docs';root.mkdir()
    monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'docs':str(root)}))
    p=create_project(a)
    link=a.post(f'/api/projects/{p["id"]}/sources',json={'source_key':'docs'}).json()
    with a.app.state.sessions() as db:
        row=db.get(SourceLink,link['id']);row.sync_token='expired';row.sync_expires_at='2000-01-01T00:00:00.000000+00:00';db.commit()
    assert a.post(f'/api/sources/{link["id"]}/sync',json={}).status_code==200
    with a.app.state.sessions() as db:
        assert db.get(SourceLink,link['id']).sync_token is None


def test_worker_with_replaced_claim_cannot_commit_or_release_new_owner(clients,tmp_path,monkeypatch):
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from server import sources
    from server.db import SourceLink
    a,_=clients
    root=tmp_path/'docs';root.mkdir()
    (root/'progress.md').write_text('- [x] 核对',encoding='utf-8')
    monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'docs':str(root)}))
    p=create_project(a)
    link=a.post(f'/api/projects/{p["id"]}/sources',json={'source_key':'docs'}).json()
    entered,release=threading.Event(),threading.Event()
    original=sources.store
    async def paused(*args,**kwargs):
        entered.set()
        assert await asyncio.to_thread(release.wait,8)
        return await original(*args,**kwargs)
    monkeypatch.setattr(sources,'store',paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(a.post,f'/api/sources/{link["id"]}/sync',json={})
        try:
            assert entered.wait(4)
            with a.app.state.sessions() as db:
                row=db.get(SourceLink,link['id']);row.sync_token='replacement-owner';db.commit()
        finally:release.set()
        result=pending.result(timeout=10)
    assert result.status_code==409,result.text
    assert a.get(f'/api/projects/{p["id"]}').json()['files']==[]
    with a.app.state.sessions() as db:
        assert db.get(SourceLink,link['id']).sync_token=='replacement-owner'
