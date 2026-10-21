import json
import os
from pathlib import Path

from tests.test_platform import clients, create_project


def test_recording_starts_without_project_or_title_and_keeps_owner(clients):
    a,b=clients
    r=a.post('/api/meetings/start',json={})
    assert r.status_code==201,r.text
    m=r.json()
    assert m['project_id'] is None and m['title'] and m['project_ids']==[]
    assert a.get('/api/meetings').json()[0]['id']==m['id']
    assert b.get('/api/meetings/'+m['id']).status_code==401
    assert a.post('/api/meetings/'+m['id']+'/epochs',json={}).status_code==200


def test_directories_import_docs_only_and_preserve_source_time(clients,tmp_path,monkeypatch):
    a,_=clients
    root=tmp_path/'projects';root.mkdir()
    docs=root/'001Customer'/'docs';docs.mkdir(parents=True)
    (root/'001Customer'/'code.py').write_text('not project knowledge')
    file=docs/'需求.md';file.write_text('客户需要费用审批',encoding='utf-8')
    os.utime(file,(1700000000,1700000000))
    (root/'002New').mkdir();(root/'not-a-project').mkdir()
    monkeypatch.setenv('PROJECTS_ROOT',str(root))
    monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'codes':str(root)}))
    r=a.post('/api/projects/discover',json={})
    assert r.status_code==200,r.text
    assert r.json()['imported']==2
    assert a.post('/api/projects/discover',json={}).json()['imported']==0
    p=next(x for x in a.get('/api/projects').json() if x['name']=='001Customer')
    files=a.get('/api/projects/'+p['id']).json()['files']
    assert len(files)==1 and files[0]['source_modified_at'].startswith('2023-11-14')
    assert files[0]['source_time_basis']=='file_modified'
    assert a.get('/api/projects/'+p['id']+'/overview').status_code==200


def test_directory_creation_rejects_escape_and_existing_foreign_binding(clients,tmp_path,monkeypatch):
    a,_=clients
    monkeypatch.setenv('PROJECTS_ROOT',str(tmp_path))
    assert a.post('/api/projects',json={'name':'Bad','directory_name':'../escape','create_directory':True}).status_code==422
    r=a.post('/api/projects',json={'name':'客户项目','directory_name':'013Customer','create_directory':True})
    assert r.status_code==201,r.text
    assert (tmp_path/'013Customer'/'docs').is_dir()
    assert a.post('/api/projects',json={'name':'Duplicate','directory_name':'013Customer','create_directory':True}).status_code==409


def test_retired_name_feature_is_not_available(clients):
    a,_=clients
    assert a.get('/api/lexicon').status_code==404
    assert a.post('/api/lexicon',json={}).status_code in (404,405)


def test_multi_project_classification_can_be_changed_after_recording(clients):
    a,_=clients
    first=create_project(a,name='项目甲');second=create_project(a,name='项目乙')
    m=a.post('/api/meetings/start',json={}).json()
    r=a.patch('/api/meetings/'+m['id']+'/classification',json={'title':'方案联席会','project_ids':[first['id'],second['id']]})
    assert r.status_code==200,r.text
    assert set(r.json()['project_ids'])=={first['id'],second['id']}
    for p in (first,second):
        assert a.get('/api/projects/'+p['id']).json()['meetings'][0]['id']==m['id']


def test_file_analysis_is_idempotent_and_writes_readable_progress(clients,tmp_path,monkeypatch):
    a,_=clients
    root=tmp_path/'catalog';docs=root/'001Proof'/'docs';docs.mkdir(parents=True)
    (docs/'客户需求.md').write_text('客户需要发票核验，尚未确认上线日期。',encoding='utf-8')
    monkeypatch.setenv('PROJECTS_ROOT',str(root));monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'codes':str(root)}))
    a.post('/api/projects/discover',json={})
    calls=[]
    def model(purpose,payload):
        calls.append((purpose,payload))
        if purpose=='file_chunk':return {'summary':'客户提出发票核验需求，上线日期未确认。','terms':[]}
        return {'summary':'已收到发票核验需求；上线日期待确认，建议下一步核对规则。','previous':'尚无已确认进展。','current':'收到发票核验需求。','next':'建议确认核验规则及上线日期。'}
    a.app.state.analysis_model=model
    from server.automation import drain_jobs
    drain_jobs(a.app,limit=20)
    p=a.get('/api/projects').json()[0]
    overview=a.get('/api/projects/'+p['id']+'/overview').json()
    assert '发票核验' in overview['summary'] and overview['entries']
    output=docs/'项目进展.md';text=output.read_text(encoding='utf-8')
    assert '发票核验' in text and '客户需求.md' in text
    count=len(calls)
    a.post('/api/projects/discover',json={});drain_jobs(a.app,limit=20)
    assert len(calls)==count
    assert output.read_text(encoding='utf-8')==text


def test_meeting_reads_all_original_text_and_updates_each_evidenced_project(clients):
    a,_=clients
    first=create_project(a,name='餐饮项目');second=create_project(a,name='健身项目')
    m=a.post('/api/meetings/start',json={}).json()
    raw='餐饮项目要核对收银。'+'原文内容。'*3000+'健身项目先核对会员规则。'
    a.patch('/api/meetings/'+m['id'],json={'version':m['version'],'transcript':raw})
    seen=[]
    def model(purpose,payload):
        seen.append((purpose,payload))
        if purpose=='meeting_chunk':
            items=[]
            for p,quote in [(first,'餐饮项目要核对收银。'),(second,'健身项目先核对会员规则。')]:
                if quote in payload['original']:items.append({'project_id':p['id'],'quotes':[quote],'summary':quote})
            items.append({'project_id':'foreign-project','quotes':['原文内容。'],'summary':'不得关联'})
            return {'summary':'本片保留核对要求。','facts':[],'projects':items}
        if purpose=='meeting_summary':return {'title':'客户需求核对会','markdown':'本次核对收银与会员规则。后续建议核实资料。'}
        return {'summary':'此前尚待确认，本次提出规则核对，建议继续核实。','previous':'此前待确认。','current':'提出规则核对。','next':'建议核实资料。'}
    a.app.state.analysis_model=model
    assert a.post('/api/meetings/'+m['id']+'/finish').status_code==200
    from server.automation import drain_jobs
    drain_jobs(a.app)
    result=a.get('/api/meetings/'+m['id']).json()
    assert result['transcript']==raw and result['title']=='客户需求核对会'
    assert set(result['project_ids'])=={first['id'],second['id']}
    original=''.join(payload['original'] for purpose,payload in seen if purpose=='meeting_chunk')
    assert raw in original
    final=next(payload for purpose,payload in seen if purpose=='meeting_summary')
    assert raw in final['original_transcript']
    for p in (first,second):assert len(a.get('/api/projects/'+p['id']+'/overview').json()['entries'])==1
    assert a.get('/api/meetings/'+m['id']+'/minutes.md').status_code==200


def test_unsupported_project_quote_stays_unclassified_and_manual_title_is_kept(clients):
    a,_=clients;p=create_project(a)
    m=a.post('/api/meetings/start',json={}).json()
    a.patch('/api/meetings/'+m['id'],json={'version':m['version'],'title':'我指定的名称','transcript':'只讨论通用安排。'})
    def model(purpose,payload):
        if purpose=='meeting_chunk':return {'summary':'讨论安排。','projects':[{'project_id':p['id'],'quotes':['原文中不存在的项目名'],'summary':'伪造关联'}]}
        return {'title':'自动名称','markdown':'讨论通用安排，归属待确认。'}
    a.app.state.analysis_model=model
    a.post('/api/meetings/'+m['id']+'/finish')
    from server.automation import drain_jobs
    drain_jobs(a.app)
    result=a.get('/api/meetings/'+m['id']).json()
    assert result['project_ids']==[] and result['analysis_status']=='unclassified'
    assert result['title']=='我指定的名称'


def test_failed_analysis_retries_without_duplicate_progress(clients):
    a,_=clients;p=create_project(a)
    f=a.post('/api/projects/'+p['id']+'/files',files={'file':('需求.md','需要核实审批规则。'.encode(),'text/markdown')}).json()
    def fail(*args):raise RuntimeError('provider unavailable')
    a.app.state.analysis_model=fail
    from server.automation import drain_jobs
    drain_jobs(a.app)
    job=next(j for j in a.get('/api/analysis-jobs').json() if j['kind']=='file')
    assert job['status']=='failed' and 'provider' not in job['error']
    def success(purpose,payload):
        if purpose=='file_chunk':return {'summary':'审批规则待核实。'}
        return {'summary':'收到规则核实需求，建议确认审批口径。','previous':'此前待确认。','current':'收到需求。','next':'建议确认审批口径。'}
    a.app.state.analysis_model=success
    assert a.post('/api/analysis-jobs/'+job['id']+'/retry').status_code==200
    drain_jobs(a.app)
    assert next(j for j in a.get('/api/analysis-jobs').json() if j['id']==job['id'])['status']=='succeeded'
    assert len(a.get('/api/projects/'+p['id']+'/overview').json()['entries'])==1


def test_project_context_excludes_self_future_and_replaced_source(clients):
    from server.db import ProjectProgress,StoredFile
    from server.automation import context
    a,_=clients;p=create_project(a)
    with a.app.state.sessions() as db:
        for sid,when in [('past','2020-01-01'),('self','2021-01-01'),('future','2022-01-01')]:
            db.add(ProjectProgress(project_id=p['id'],source_type='file',source_id=sid,source_name=sid,input_hash=sid,title=sid,summary=sid,time_basis='recorded',occurred_at=when))
        db.commit()
        result=context(db,p['id'],'2021-01-01','self')
        assert [x['source_id'] for x in result]==['past']


def test_corrupt_catalog_file_does_not_block_other_documents(clients,tmp_path,monkeypatch):
    a,_=clients;docs=tmp_path/'001Customer'/'docs';docs.mkdir(parents=True)
    (docs/'坏文件.pdf').write_bytes(b'not a pdf')
    (docs/'需求.md').write_text('客户需要核实权限。',encoding='utf-8')
    monkeypatch.setenv('PROJECTS_ROOT',str(tmp_path));monkeypatch.setenv('DOCUMENT_SOURCES_JSON',json.dumps({'codes':str(tmp_path)}))
    result=a.post('/api/projects/discover').json()
    assert result['errors']==[]
    p=a.get('/api/projects').json()[0]
    files=a.get('/api/projects/'+p['id']).json()['files']
    assert {f['parse_status'] for f in files}=={'ready','failed'}


def test_reclassified_meeting_leaves_old_project_overview_and_persistent_file(clients,tmp_path,monkeypatch):
    from server.db import ProjectProgress
    from server.automation import write_progress
    a,_=clients;monkeypatch.setenv('PROJECTS_ROOT',str(tmp_path))
    first=a.post('/api/projects',json={'name':'甲','directory_name':'001A','create_directory':True}).json()
    second=create_project(a,name='乙')
    m=a.post('/api/projects/'+first['id']+'/meetings',json={'title':'客户会议'}).json()
    with a.app.state.sessions() as db:
        db.add(ProjectProgress(project_id=first['id'],source_type='meeting',source_id=m['id'],source_name=m['title'],input_hash='proof',title='客户会议',summary='旧项目内容',time_basis='recorded',occurred_at='2020-01-01'));db.commit()
    write_progress(a.app,first['id'])
    assert '旧项目内容' in (tmp_path/'001A/docs/项目进展.md').read_text(encoding='utf-8')
    assert a.patch('/api/meetings/'+m['id']+'/classification',json={'project_ids':[second['id']]}).status_code==200
    assert a.get('/api/projects/'+first['id']+'/overview').json()['entries']==[]
    assert '旧项目内容' not in (tmp_path/'001A/docs/项目进展.md').read_text(encoding='utf-8')


def test_historical_context_uses_version_that_existed_at_the_time(clients):
    from server.db import ProjectProgress,StoredFile
    from server.automation import context
    a,_=clients;p=create_project(a)
    with a.app.state.sessions() as db:
        owner=a.get('/api/auth/me').json()['id']
        old=StoredFile(owner_id=owner,project_id=p['id'],name='规则.md',mime='text/markdown',size=1,sha256='a'*64,storage_key='old',created_at='2020-01-01');db.add(old);db.flush()
        new=StoredFile(owner_id=owner,project_id=p['id'],name='规则.md',mime='text/markdown',size=1,sha256='b'*64,storage_key='new',previous_version_id=old.id,created_at='2022-01-01');db.add(new);db.flush()
        for f,when in [(old,'2020-01-01'),(new,'2022-01-01')]:
            db.add(ProjectProgress(project_id=p['id'],source_type='file',source_id=f.id,source_name=f.name,input_hash=f.id,title=f.name,summary=f.id,time_basis='uploaded',occurred_at=when))
        db.commit()
        assert [x['source_id'] for x in context(db,p['id'],'2021-01-01')]==[old.id]
        assert [x['source_id'] for x in context(db,p['id'])]==[new.id]


def test_streaming_tail_after_finish_enqueues_new_analysis(clients):
    from server.asr import persist_untimed
    a,_=clients;m=a.post('/api/meetings/start',json={}).json()
    a.post('/api/meetings/'+m['id']+'/finish')
    before=len(a.get('/api/analysis-jobs').json())
    persist_untimed(a.app,m['id'],'最后补充一项权限要求。')
    assert len(a.get('/api/analysis-jobs').json())==before+1
    assert a.get('/api/meetings/'+m['id']+'/transcripts').json()[0]['text']=='最后补充一项权限要求。'


def test_original_transcript_whitespace_is_preserved(clients):
    a,_=clients;m=a.post('/api/meetings/start',json={}).json()
    original='\n  原始识别内容。\n\n'
    r=a.patch('/api/meetings/'+m['id'],json={'version':m['version'],'transcript':original})
    assert r.json()['transcript']==original
