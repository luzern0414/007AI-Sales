import json
import httpx
from tests.test_platform import clients,create_project
from tests.test_recordings import new_meeting


def test_generation_is_atomic_and_citations_are_validated(clients,monkeypatch):
    a,_=clients
    for key,value in {'LLM_API_KEY':'isolated-test-key','LLM_BASE_URL':'https://model.test/v1','LLM_MODEL':'contract-test'}.items():monkeypatch.setenv(key,value)
    m=new_meeting(a,create_project(a))
    a.patch(f'/api/meetings/{m["id"]}',json={'version':1,'notes':'需要记录审批进度。权限待确认。'})
    docs=[{'kind':k,'title':k+'讨论稿','markdown':'# 讨论稿\n\n权限待确认。','source_ids':[m['id']]} for k in ['minutes','proposal','requirements','client_checklist']]
    def handler(request):
        body=json.loads(request.content)
        assert '二期' in body['messages'][0]['content']
        assert '审批进度' in body['messages'][1]['content']
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'documents':docs},ensure_ascii=False)}}]})
    a.app.state.llm_transport=httpx.MockTransport(handler)
    r=a.post(f'/api/meetings/{m["id"]}/generate',json={})
    assert r.status_code==201,r.text
    assert len(a.get(f'/api/projects/{m["project_id"]}/documents').json())==4
    docs[0]['source_ids']=['forged-source']
    assert a.post(f'/api/meetings/{m["id"]}/generate',json={}).status_code==502
    assert len(a.get(f'/api/projects/{m["project_id"]}/documents').json())==4


def test_no_unrequested_phases_from_model(clients,monkeypatch):
    a,_=clients
    for key,value in {'LLM_API_KEY':'test','LLM_BASE_URL':'https://model.test/v1','LLM_MODEL':'contract-test'}.items():monkeypatch.setenv(key,value)
    m=new_meeting(a,create_project(a))
    a.patch(f'/api/meetings/{m["id"]}',json={'version':1,'notes':'完整实现需求，没有另行分期安排。'})
    docs=[{'kind':k,'title':k,'markdown':'# 一期实施\n二期展望','source_ids':[m['id']]} for k in ['minutes','proposal','requirements','client_checklist']]
    a.app.state.llm_transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'documents':docs})}}]}))
    assert a.post(f'/api/meetings/{m["id"]}/generate',json={}).status_code==502


def test_generation_accepts_persisted_realtime_transcript(clients,monkeypatch):
    a,_=clients
    for key,value in {'LLM_API_KEY':'test','LLM_BASE_URL':'https://model.test/v1','LLM_MODEL':'contract-test'}.items():monkeypatch.setenv(key,value)
    m=new_meeting(a,create_project(a))
    from server.asr import persist_sentence
    persist_sentence(a.app,m['id'],'raw',{'begin_time':0,'end_time':1000,'sentence_end':True,'text':'请整理审批权限需求'})
    docs=[{'kind':k,'title':k,'markdown':'# 讨论稿\n\n审批权限待确认','source_ids':[m['id']]} for k in ['minutes','proposal','requirements','client_checklist']]
    def handler(request):
        assert '请整理审批权限需求' in json.loads(request.content)['messages'][1]['content']
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'documents':docs})}}]})
    a.app.state.llm_transport=httpx.MockTransport(handler)
    assert a.post(f'/api/meetings/{m["id"]}/generate',json={}).status_code==201


def test_generation_reads_complete_project_meeting_chain(clients,monkeypatch):
    a,_=clients
    for key,value in {'LLM_API_KEY':'test','LLM_BASE_URL':'https://model.test/v1','LLM_MODEL':'contract-test'}.items():monkeypatch.setenv(key,value)
    p=create_project(a);first=new_meeting(a,p);latest=new_meeting(a,p)
    a.patch(f'/api/meetings/{first["id"]}',json={'version':1,'notes':'首次洽谈确认权限必须隔离'})
    a.patch(f'/api/meetings/{latest["id"]}',json={'version':1,'notes':'本次确认审批规则待补齐'})
    docs=[{'kind':k,'title':k,'markdown':'# 讨论稿\n\n权限待确认','source_ids':[first['id'],latest['id']]} for k in ['minutes','proposal','requirements','client_checklist']]
    def handler(request):
        materials=json.loads(request.content)['messages'][1]['content']
        assert '首次洽谈确认权限必须隔离' in materials
        assert '本次确认审批规则待补齐' in materials
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'documents':docs})}}]})
    a.app.state.llm_transport=httpx.MockTransport(handler)
    assert a.post(f'/api/meetings/{latest["id"]}/generate',json={}).status_code==201


def test_imported_audio_does_not_block_generation_and_uses_actual_time(clients,monkeypatch):
    a,_=clients;p=create_project(a)
    for key,value in {'LLM_API_KEY':'test','LLM_BASE_URL':'https://model.test/v1','LLM_MODEL':'contract-test'}.items():monkeypatch.setenv(key,value)
    a.post(f'/api/projects/{p["id"]}/files',files={'file':('现场.m4a',b'audio','audio/mp4')})
    m=a.get(f'/api/projects/{p["id"]}').json()['meetings'][0]
    a.patch(f'/api/meetings/{m["id"]}',json={'version':m['version'],'transcript':'客户要求按部门隔离审批权限。'})
    a.patch(f'/api/meetings/{m["id"]}/classification',json={'project_ids':[p['id']],'occurred_at':'2026-10-10T10:00:00+08:00'})
    docs=[{'kind':k,'title':k,'markdown':'# 讨论稿\n\n权限待确认','source_ids':[m['id']]} for k in ['minutes','proposal','requirements','client_checklist']]
    def handler(request):
        materials=json.loads(json.loads(request.content)['messages'][1]['content'])
        source=next(s for s in materials['sources'] if s['id']==m['id'])
        assert source['occurred_at'].startswith('2026-10-10T02:00')
        assert not any(s['kind']=='file' for s in materials['sources'])
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'documents':docs})}}]})
    a.app.state.llm_transport=httpx.MockTransport(handler)
    r=a.post(f'/api/meetings/{m["id"]}/generate',json={})
    assert r.status_code==201,r.text


def test_generation_request_replay_does_not_call_model_twice(clients,monkeypatch):
    a,_=clients
    for key,value in {'LLM_API_KEY':'test','LLM_BASE_URL':'https://model.test/v1','LLM_MODEL':'contract-test'}.items():monkeypatch.setenv(key,value)
    m=new_meeting(a,create_project(a))
    a.patch(f'/api/meetings/{m["id"]}',json={'version':1,'notes':'确认审批范围'})
    docs=[{'kind':k,'title':k,'markdown':'# 讨论稿\n\n权限待确认','source_ids':[m['id']]} for k in ['minutes','proposal','requirements','client_checklist']]
    calls=[]
    def handler(request):
        calls.append(1)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'documents':docs})}}]})
    a.app.state.llm_transport=httpx.MockTransport(handler)
    url=f'/api/meetings/{m["id"]}/generate'
    first=a.post(url,json={'request_id':'replay-request-01'})
    assert first.status_code==201,first.text
    replay=a.post(url,json={'request_id':'replay-request-01'})
    assert replay.status_code==201,replay.text
    assert [d['id'] for d in replay.json()]==[d['id'] for d in first.json()]
    assert len(calls)==1
    jobs=a.get(f'/api/meetings/{m["id"]}/generations').json()
    assert len(jobs)==1 and jobs[0]['status']=='succeeded'
    assert len(jobs[0]['document_ids'])==4


def test_failed_request_is_persisted_without_automatic_model_retry(clients,monkeypatch):
    a,b=clients
    for key,value in {'LLM_API_KEY':'test','LLM_BASE_URL':'https://model.test/v1','LLM_MODEL':'contract-test'}.items():monkeypatch.setenv(key,value)
    m=new_meeting(a,create_project(a));a.patch(f'/api/meetings/{m["id"]}',json={'version':1,'notes':'需要权限清单'})
    calls=[]
    def handler(request):calls.append(1);return httpx.Response(429,json={'error':'rate limited'})
    a.app.state.llm_transport=httpx.MockTransport(handler)
    url=f'/api/meetings/{m["id"]}/generate'
    for _ in range(2):assert a.post(url,json={'request_id':'failed-request-01'}).status_code==502
    assert len(calls)==1
    jobs=a.get(f'/api/meetings/{m["id"]}/generations').json()
    assert jobs[0]['status']=='failed' and jobs[0]['document_ids']==[]
    assert b.get(f'/api/meetings/{m["id"]}/generations').status_code==401
