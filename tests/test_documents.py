import io
from tests.test_platform import clients, create_project
from tests.test_recordings import new_meeting


def test_minutes_export_uses_same_revision_and_escapes_html(clients):
    a, _ = clients
    m = new_meeting(a, create_project(a))
    a.patch(f'/api/meetings/{m["id"]}', json={'version':1,'notes':'范围：审批流程\n<script>alert(1)</script>','transcript':'甲方：请先确认权限。'})
    url=f'/api/meetings/{m["id"]}'
    md=a.get(url+'/minutes.md')
    assert md.status_code == 200
    assert '审批流程' in md.text and '讨论稿' in md.text
    assert md.headers['x-document-revision'] == '2'
    page=a.get(url+'/minutes.html')
    assert page.status_code == 200
    assert '&lt;script&gt;' in page.text and '<script>' not in page.text
    assert page.headers['x-document-revision'] == '2'


def test_unconfigured_ai_is_not_faked(clients, monkeypatch):
    monkeypatch.delenv('LLM_API_KEY',raising=False)
    a,_=clients
    m=new_meeting(a,create_project(a))
    assert a.get('/api/integrations/status').json()['llm']['configured'] is False
    r=a.post(f'/api/meetings/{m["id"]}/generate',json={})
    assert r.status_code == 503
    assert a.get(f'/api/projects/{m["project_id"]}/documents').json() == []


def test_source_file_extraction_and_search(clients):
    a,_=clients
    p=create_project(a)
    a.post(f'/api/projects/{p["id"]}/files',files={'file':('requirements.md','需求：审批权限需要隔离'.encode(),'text/markdown')})
    r=a.get(f'/api/projects/{p["id"]}/search',params={'q':'审批'})
    assert r.status_code == 200 and len(r.json())==1
    assert '审批权限' in r.json()[0]['snippet']


def test_export_revision_tracks_final_transcripts(clients):
    a,_=clients
    m=new_meeting(a,create_project(a))
    from server.asr import persist_sentence
    persist_sentence(a.app,m['id'],'revision',{'begin_time':0,'end_time':1000,'sentence_end':True,'text':'现场确认需提供权限清单'})
    for ext in ('md','html'):
        r=a.get(f'/api/meetings/{m["id"]}/minutes.{ext}')
        assert r.headers['x-document-revision']=='1.asr1'
        assert '现场确认需提供权限清单' in r.text
