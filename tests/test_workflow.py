import json
from tests.test_platform import clients, create_project


def test_nodes_require_actual_time_evidence_and_signed_delivery(clients):
    a, b = clients
    p = create_project(a)
    url = '/api/projects/' + p['id'] + '/workflow'
    r = a.get(url)
    assert r.status_code == 200
    workflow = r.json()
    assert len(workflow['nodes']) == 8 and workflow['confirmed'] == 0
    assert b.get(url).status_code == 401
    body = {'version': 0, 'confirmed': True, 'occurred_at': '2026-10-12T09:00:00+08:00', 'evidence': '客户邮件确认方案已经收到'}
    assert a.put(url + '/proposal', json={**body, 'evidence': ''}).status_code == 422
    assert a.put(url + '/proposal', json={**body, 'due_date': '2026-12-01'}).status_code == 409
    assert a.put(url + '/proposal', json={**body, 'occurred_at': '2026-10-12T09:00:00'}).status_code == 422
    r = a.put(url + '/proposal', json=body)
    assert r.status_code == 200, r.text
    assert r.json()['confirmed'] == 1
    assert r.json()['current'] == 'contract'
    assert not r.json()['nodes'][0]['confirmed']
    assert a.put(url + '/proposal', json=body).status_code == 409
    node = r.json()['nodes'][2]
    assert a.put(url + '/proposal', json={'version': node['version'], 'confirmed': False, 'evidence': '客户要求重新修订方案'}).status_code == 200
    assert a.get(url).json()['confirmed'] == 0


def test_analysis_covers_originals_background_and_nodes_without_risks(clients):
    a, _ = clients
    p = create_project(a)
    base = '/api/projects/' + p['id']
    a.post(base + '/files', files={'file': ('技术.md', '客户接口未开放，尚不能联调。'.encode(), 'text/markdown')})
    calls = []
    def model(purpose, payload):
        calls.append((purpose, payload))
        if purpose == 'project_chunk':
            source = payload['source']
            return {'summary': '接口尚未开放。', 'risks': [{'category': 'technical', 'title': '接口联调受阻', 'detail': '建议确认接口开放时间', 'quote': '客户接口未开放', 'source_id': source['id']}]}
        if purpose == 'project_review':
            return {'summary': '已收到技术资料，接口开放时间待确认。', 'next': '确认接口开放时间。'}
        if purpose == 'file_chunk': return {'summary': '接口尚未开放', 'terms': []}
        return {'summary': '技术资料说明接口尚未开放。', 'previous': '暂无记录', 'current': '收到资料', 'next': '确认接口'}
    a.app.state.analysis_model = model
    r = a.post(base + '/analyze', json={'background': '客户使用自研ERP', 'instructions': '重点核实接口风险'})
    assert r.status_code == 202, r.text
    from server.automation import drain_jobs
    drain_jobs(a.app, limit=1)
    review = a.get(base + '/workflow').json()['analysis']
    assert review['status'] == 'ready', review
    # Risk assessment is not part of the agent's output any more.
    assert review['risks'] == []
    assert 'risks' not in next(c for c in calls if c[0] == 'project_review')[1]
    assert any('客户接口未开放' in json.dumps(payload, ensure_ascii=False) for purpose, payload in calls if purpose == 'project_chunk')
    final = next(payload for purpose, payload in calls if purpose == 'project_review')
    assert final['background'] == '客户使用自研ERP' and final['instructions'] == '重点核实接口风险'
    assert len(final['workflow']['nodes']) == 8
    entries=a.get(base+'/overview').json()['entries']
    assert any(e['summary']=='接口尚未开放。' for e in entries)


def test_audio_is_only_in_meetings_with_unknown_occurrence(clients):
    a, _ = clients
    p = create_project(a)
    r = a.post('/api/projects/' + p['id'] + '/files', files={'file': ('客户会议.m4a', b'audio-test', 'audio/mp4')})
    assert r.status_code == 201, r.text
    detail = a.get('/api/projects/' + p['id']).json()
    assert detail['files'] == []
    assert len(detail['meetings']) == 1
    m = a.get('/api/meetings/' + detail['meetings'][0]['id']).json()
    assert m['recordings'][0]['file_id'] == r.json()['id']
    assert m['occurred_at'] is None


def test_docs_scaffold_preserves_originals_and_excludes_generated_files(tmp_path):
    from server.docs_structure import scaffold, managed_file
    docs = tmp_path / 'docs'; docs.mkdir()
    (docs / 'README.md').write_text('客户原始导航', encoding='utf-8')
    scaffold(docs, '测试项目')
    assert (docs / 'README.md').read_text(encoding='utf-8') == '客户原始导航'
    assert {p.name for p in docs.iterdir() if p.is_dir()} == {'01-商务与需求', '02-产品与开发', '03-测试与交付'}
    assert not any(p.is_dir() for stage in docs.iterdir() if stage.is_dir() for p in stage.iterdir())
    assert not any('sales-agent:placeholder' in p.read_text(encoding='utf-8') for p in docs.rglob('*.md'))
    placeholder = docs / '01-商务与需求/立项确认.md'
    placeholder.write_text('# 立项确认\n\n客户已书面确认范围', encoding='utf-8')
    scaffold(docs, '测试项目')
    assert not managed_file(placeholder)
    assert '客户已书面确认' in placeholder.read_text(encoding='utf-8')


def test_confirmation_triggers_analysis_and_preserves_audit(clients):
    a, _ = clients
    p = create_project(a)
    calls = []
    def model(purpose, payload):
        calls.append(payload)
        return {'summary': '方案已按客户邮件提交。', 'next': '跟进合同确认。', 'risks': []}
    a.app.state.analysis_model = model
    url = '/api/projects/' + p['id']
    body = {'version': 0, 'confirmed': True, 'occurred_at': '2026-10-12T09:00:00+08:00', 'evidence': '客户邮件确认方案已收到'}
    assert a.put(url + '/workflow/proposal', json=body).status_code == 200
    from server.automation import drain_jobs
    drain_jobs(a.app, limit=5)
    result = a.get(url + '/workflow').json()
    assert result['analysis']['status'] == 'ready'
    assert calls[-1]['workflow']['nodes'][2]['confirmed'] is True
    assert calls[-1]['workflow']['nodes'][2]['occurred_at'].startswith('2026-10-12T01:00')
    assert a.put(url + '/workflow/contract', json={**body, 'due_date': '2026-12-01'}).status_code == 200
    assert a.get(url + '/workflow').json()['due_date'] == '2026-12-01'
    assert a.put(url + '/workflow/contract', json={'version': 1, 'confirmed': False, 'evidence': '签约证据有误'}).status_code == 200
    assert a.get(url + '/workflow').json()['due_date'] is None
    events = a.get(url).json()['events']
    assert len([e for e in events if e['kind'] == 'workflow']) == 3


def test_model_risks_are_never_surfaced(clients):
    a, _ = clients
    p = create_project(a)
    a.post('/api/projects/' + p['id'] + '/files', files={'file': ('资料.md', '接口仍在评估。'.encode(), 'text/markdown')})
    def model(purpose, payload):
        if purpose == 'project_chunk':
            return {'summary': '接口待评估。', 'risks': [{'category': 'technical', 'title': '虚构', 'detail': '虚构', 'quote': '客户明确表示项目失败', 'source_id': payload['source']['id']}]}
        if purpose == 'project_review':
            return {'summary': '接口待评估。', 'next': '确认接口范围。', 'risks': [{'category': 'technical', 'title': '虚构', 'quote': '不存在的证据', 'source_id': 'foreign'}]}
        if purpose == 'file_chunk': return {'summary': '接口待评估。', 'terms': []}
        return {'summary': '接口待评估。', 'previous': '无', 'current': '接口待评估', 'next': '核实'}
    a.app.state.analysis_model = model
    a.post('/api/projects/' + p['id'] + '/analyze', json={})
    from server.automation import drain_jobs
    drain_jobs(a.app, limit=10)
    assert a.get('/api/projects/' + p['id'] + '/workflow').json()['analysis']['risks'] == []


def test_long_originals_are_covered_to_last_character(clients):
    a, _ = clients
    p = create_project(a)
    text = '讨论接口范围。' * 2200 + '最终约束：测试数据必须脱敏。'
    a.post('/api/projects/' + p['id'] + '/files', files={'file': ('长资料.md', text.encode(), 'text/markdown')})
    seen = []
    def model(purpose, payload):
        if purpose == 'project_chunk':
            seen.append(payload['original'])
            return {'summary': '接口范围与测试约束。', 'risks': []}
        if purpose == 'project_review': return {'summary': '已收到接口及测试约束。', 'next': '核对数据脱敏。', 'risks': []}
        if purpose == 'file_chunk': return {'summary': '接口范围与测试约束。', 'terms': []}
        return {'summary': '接口范围与测试约束。', 'previous': '无', 'current': '已收到资料', 'next': '核实'}
    a.app.state.analysis_model = model
    a.post('/api/projects/' + p['id'] + '/analyze', json={})
    from server.automation import drain_jobs
    drain_jobs(a.app, limit=10)
    assert ''.join(seen) == text


def test_audio_migration_is_idempotent_after_new_version(clients):
    a, _ = clients
    p = create_project(a)
    for payload in (b'audio-one', b'audio-two'):
        assert a.post('/api/projects/' + p['id'] + '/files', files={'file': ('现场.m4a', payload, 'audio/mp4')}).status_code == 201
    from server.recording_imports import migrate_audio
    migrate_audio(a.app); migrate_audio(a.app)
    result = a.get('/api/projects/' + p['id']).json()
    assert len(result['meetings']) == 1 and not result['files']
    m = result['meetings'][0]
    assert a.patch('/api/meetings/' + m['id'] + '/classification', json={'project_ids': [p['id']], 'occurred_at': '2026-10-10T10:00:00+08:00'}).status_code == 200
    assert a.get('/api/meetings/' + m['id']).json()['occurred_at'].startswith('2026-10-10T02:00')


def test_legacy_audio_progress_becomes_meeting_progress(clients):
    a,_=clients;p=create_project(a)
    from server.db import StoredFile,ProjectProgress,User
    with a.app.state.sessions() as db:
        owner=db.query(User).first()
        f=StoredFile(owner_id=owner.id,project_id=p['id'],name='旧会议.m4a',mime='audio/mp4',size=12,sha256='a'*64,storage_key='legacy.m4a',parse_status='ready',extracted_text='会议讨论接口。')
        db.add(f);db.flush()
        db.add(ProjectProgress(project_id=p['id'],source_type='file',source_id=f.id,source_name=f.name,input_hash='b'*64,title=f.name,summary='会议讨论接口。',time_basis='file_modified',occurred_at='2026-10-01T00:00:00+00:00'))
        db.commit()
    from server.recording_imports import migrate_audio
    migrate_audio(a.app)
    e=a.get('/api/projects/'+p['id']+'/overview').json()['entries'][0]
    assert e['source_type']=='meeting' and e['time_basis']=='imported_at'


def test_scaffold_does_not_follow_symlink(tmp_path):
    from server.docs_structure import scaffold
    import pytest
    docs = tmp_path / 'docs'; docs.mkdir()
    outside = tmp_path / 'outside'; outside.mkdir()
    try: (docs / '01-商务与需求').symlink_to(outside, target_is_directory=True)
    except OSError: pytest.skip('系统未开放符号链接')
    with pytest.raises(ValueError): scaffold(docs, 'test')
    assert not list(outside.iterdir())


def test_grouped_meeting_export_keeps_original_and_attachments_together(tmp_path):
    from server.docs_structure import export_meeting
    from types import SimpleNamespace
    docs = tmp_path / 'docs'
    meeting = SimpleNamespace(id='abcdefgh123', title='客户需求沟通', ai_summary='确认了接口范围。', notes='')
    relative = export_meeting(docs, meeting, '2026-10-19T09:00:00+08:00',
                              {'transcript': '原文：客户需要接口。', 'segments': [{'begin_ms': 20, 'text': '保留分段原文'}]},
                              '01-商务与需求')
    path = docs / relative
    assert path.parent == docs / '01-商务与需求/客户资料'
    content = path.read_text(encoding='utf-8')
    assert all(text in content for text in ['确认了接口范围', '原文：客户需要接口', '保留分段原文', '/audio', '/minutes.pdf'])
    path.write_text('人工补充会议内容', encoding='utf-8')
    export_meeting(docs, meeting, None, {'transcript': '后续原文', 'segments': []}, '01-商务与需求')
    # Unknown dates use a separate stable prefix; an existing manual target is never overwritten.
    export_meeting(docs, meeting, '2026-10-19T09:00:00+08:00', {'transcript': '新版', 'segments': []}, '01-商务与需求')
    assert path.read_text(encoding='utf-8') == '人工补充会议内容'


def test_user_analysis_does_not_wait_behind_background_file_jobs(clients):
    a, _ = clients
    p = create_project(a)
    a.post('/api/projects/' + p['id'] + '/files', files={'file': ('需求.md', '接口尚需核实。'.encode(), 'text/markdown')})
    calls=[]
    def model(purpose,payload):
        calls.append(purpose)
        if purpose=='project_chunk':return {'summary':'接口待核实。','risks':[]}
        return {'summary':'接口条件待核实。','next':'确认接口条件。','risks':[]}
    a.app.state.analysis_model=model
    a.post('/api/projects/'+p['id']+'/analyze',json={})
    from server.automation import drain_jobs
    drain_jobs(a.app,limit=1)
    assert calls==['project_chunk','project_review','project_review','project_reflect','timeline_digest']
    assert a.get('/api/projects/'+p['id']+'/workflow').json()['analysis']['status']=='ready'


def test_analysis_does_not_reingest_its_own_generated_timeline(clients):
    a,_=clients;p=create_project(a)
    a.post('/api/projects/'+p['id']+'/files',files={'file':('资料.md','接口待核实。'.encode(),'text/markdown')})
    def model(purpose,payload):
        if purpose=='project_chunk':return {'summary':'资料列出接口约束。','risks':[]}
        return {'summary':'已收到接口资料。','next':'核实接口。','risks':[]}
    a.app.state.analysis_model=model
    a.post('/api/projects/'+p['id']+'/analyze',json={})
    from server.automation import drain_jobs
    drain_jobs(a.app,limit=1)
    from server.db import Project,AnalysisJob
    from server.project_analysis import enqueue_project
    with a.app.state.sessions() as db:
        before=db.query(AnalysisJob).filter_by(kind='project',status='succeeded').one()
        repeat=enqueue_project(db,db.get(Project,p['id']))
        assert repeat.id==before.id and repeat.status=='succeeded'


def test_replaced_audio_preserves_old_text_and_retranscribes_new_bytes(clients,monkeypatch):
    a,_=clients;p=create_project(a);url='/api/projects/'+p['id']
    first=a.post(url+'/files',files={'file':('现场.m4a',b'first-audio','audio/mp4')}).json()
    m=a.get(url).json()['meetings'][0]
    from server.db import Meeting,User,StoredFile,ImportedRecording
    from server.automation import meeting_fingerprint,drain_jobs
    with a.app.state.sessions() as db:
        row=db.get(Meeting,m['id']);row.transcript='旧录音：接口未开放。';row.ai_summary='旧版纪要'
        old_hash=meeting_fingerprint(db,row,row.owner_id);db.commit()
    second=a.post(url+'/files',files={'file':('现场.m4a',b'second-audio','audio/mp4')}).json()
    current=a.get('/api/meetings/'+m['id']).json()
    assert current['transcript']=='' and current['ai_summary']==''
    assert len(current['recordings'])==2
    previous=next(r for r in current['recordings'] if r['file_id']==first['id'])
    assert previous['transcript']=='旧录音：接口未开放。' and previous['summary']=='旧版纪要'
    assert a.get('/api/meetings/'+m['id']+'/audio',params={'recording_id':first['id']}).content==b'first-audio'
    assert a.get('/api/meetings/'+m['id']+'/audio').content==b'second-audio'
    with a.app.state.sessions() as db:
        row=db.get(Meeting,m['id'])
        assert meeting_fingerprint(db,row,row.owner_id)!=old_hash
    seen=[]
    monkeypatch.setattr('server.automation.audio_text',lambda app,file:seen.append(file.id) or '新录音：接口已经开放。')
    drain_jobs(a.app,limit=1)
    assert seen==[second['id']]
    assert a.get('/api/meetings/'+m['id']).json()['transcript']=='新录音：接口已经开放。'


def test_file_search_excludes_audio_with_transcription(clients):
    a,_=clients;p=create_project(a);url='/api/projects/'+p['id']
    f=a.post(url+'/files',files={'file':('会议.m4a',b'audio','audio/mp4')}).json()
    from server.db import StoredFile
    with a.app.state.sessions() as db:
        row=db.get(StoredFile,f['id']);row.extracted_text='接口仍未开放';row.parse_status='ready';db.commit()
    assert a.get(url+'/search',params={'q':'接口'}).json()==[]


def test_issue_resolution_changes_analysis_context_and_fingerprint(clients):
    a,_=clients;p=create_project(a)
    from server.db import Project,Issue
    from server.project_analysis import material,fingerprint
    with a.app.state.sessions() as db:
        row=Issue(project_id=p['id'],title='接口未开放',status='resolved',resolution='等待开放',assignee='负责人',due_date='2026-10-20')
        db.add(row);db.flush();project=db.get(Project,p['id']);before=fingerprint(db,project)
        row.resolution='接口已获批，明日开放';db.flush()
        assert fingerprint(db,project)!=before
        issue=material(db,project)['issues'][0]
        assert issue['resolution']==row.resolution and issue['assignee']=='负责人' and issue['due_date']=='2026-10-20'


def test_corrected_meeting_date_replaces_import_time_in_overview(clients):
    a,_=clients;p=create_project(a);base='/api/projects/'+p['id']
    a.post(base+'/files',files={'file':('现场.wav',b'audio','audio/wav')})
    m=a.get(base).json()['meetings'][0]
    a.patch('/api/meetings/'+m['id'],json={'version':m['version'],'transcript':'接口日期待确认。'})
    def model(purpose,payload):
        if purpose=='meeting_chunk':return {'summary':'讨论接口日期。','facts':[],'projects':[]}
        if purpose=='meeting_summary':return {'title':'接口讨论','markdown':'接口日期待确认。'}
        return {'summary':'会议明确接口日期待确认。','previous':'无','current':'讨论接口','next':'确认日期','risks':[]}
    a.app.state.analysis_model=model
    from server.automation import drain_jobs
    drain_jobs(a.app,10)
    assert a.patch('/api/meetings/'+m['id']+'/classification',json={'project_ids':[p['id']],'occurred_at':'2026-10-10T10:00:00+08:00'}).status_code==200
    drain_jobs(a.app,10)
    entry=next(e for e in a.get(base+'/overview').json()['entries'] if e['source_type']=='meeting')
    assert entry['occurred_at'].startswith('2026-10-10T02:00') and entry['time_basis']=='recorded'
