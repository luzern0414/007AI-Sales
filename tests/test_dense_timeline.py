from tests.test_platform import clients,create_project


def test_recording_filename_preserves_date_precision():
    from server.recording_imports import filename_time
    assert filename_time('2026-10-13 14-30 客户沟通.m4a')=='2026-10-13T06:30:00.000000+00:00'
    assert filename_time('20261013-客户沟通.m4a')=='2026-10-13'
    assert filename_time('20261013-143000-客户沟通.m4a')=='2026-10-13T06:30:00.000000+00:00'
    assert filename_time('20261013143000客户沟通.m4a')=='2026-10-13T06:30:00.000000+00:00'
    assert filename_time('客户沟通1013.m4a') is None
    assert filename_time('2026-02-30-会议.m4a') is None
    assert filename_time('2026年9月3日 客户沟通.m4a')=='2026-09-03'
    assert filename_time('[codes] Project · docs · 2026-09-01 archive · 2026-10-13 14-30 meeting.m4a')=='2026-10-13T06:30:00.000000+00:00'


def test_grouped_timeline_merges_formats_and_meeting_assets(clients):
    a,_=clients;p=create_project(a)
    from server.db import StoredFile,Meeting,MeetingProject,ImportedRecording,User
    with a.app.state.sessions() as db:
        owner=db.query(User).first();at='2026-10-13T06:30:00+00:00'
        for name,mime in [('项目方案.docx','application/docx'),('项目方案.pdf','application/pdf'),('客户沟通-会议纪要.md','text/markdown'),('数据库设计.md','text/markdown')]:
            db.add(StoredFile(project_id=p['id'],owner_id=owner.id,name=name,mime=mime,size=20,sha256='a'*64,storage_key=name,parse_status='ready',extracted_text='说明接口设计与验收范围。',source_modified_at=at))
        m=Meeting(project_id=p['id'],owner_id=owner.id,title='客户沟通',status='finished',transcript='需确认接口。');db.add(m);db.flush()
        audio=StoredFile(project_id=p['id'],owner_id=owner.id,name='客户沟通.m4a',mime='audio/mp4',size=10,sha256='b'*64,storage_key='audio');db.add(audio);db.flush()
        db.add(ImportedRecording(file_id=audio.id,meeting_id=m.id,occurred_at=at));db.add(MeetingProject(meeting_id=m.id,project_id=p['id']));db.commit()
    response=a.get('/api/projects/'+p['id']+'/activity');assert response.status_code==200,response.text
    rows=response.json()['items']
    proposal=next(r for r in rows if r['title']=='项目方案')
    assert len(proposal['attachments'])==2
    meeting=next(r for r in rows if r['meeting_ids'])
    assert len(meeting['attachments'])==2
    assert not any('数据库设计' in str(r['attachments']) for r in rows)
    assert any(r['kind']=='development' for r in rows)


def test_file_preview_and_origin_are_owned_and_persistent(clients):
    from server.files import infer_origin
    assert infer_origin('客户确认流程.md')=='unknown'
    assert infer_origin('客户资料收集清单.md')=='unknown'
    a,b=clients;p=create_project(a)
    f=a.post('/api/projects/'+p['id']+'/files',files={'file':('客户确认.md','# 范围\n\n**审批**与权限。'.encode(),'text/markdown')}).json()
    url='/api/files/'+f['id']
    assert a.get(url+'/preview').json()['markdown'].startswith('# 范围')
    assert b.get(url+'/preview').status_code==401
    assert a.patch(url+'/origin',json={'origin':'client'}).status_code==200
    assert a.get(url+'/preview').json()['origin']=='client'
    assert a.patch(url+'/origin',json={'origin':'bad'}).status_code==422


def test_development_snapshot_baseline_and_changes_are_idempotent(clients,tmp_path):
    a,_=clients;p=create_project(a)
    folder=tmp_path/'001Code';folder.mkdir();(folder/'app.py').write_text('print(1)',encoding='utf-8')
    (folder/'.env').write_text('SECRET=never-read',encoding='utf-8')
    vendor=folder/'Third_Party';vendor.mkdir();(vendor/'dependency.py').write_text('vendor = True')
    from server.development import scan_project
    from server.db import Project
    with a.app.state.sessions() as db:
        row=db.get(Project,p['id']);row.directory_path=str(folder);db.commit()
    first=scan_project(a.app,p['id'],day='2026-10-14')
    assert first['baseline'] and first['changed']==0
    from server.development import inventory
    assert set(inventory(folder))=={'app.py'}
    (folder/'app.py').write_text('print(2)',encoding='utf-8')
    second=scan_project(a.app,p['id'],day='2026-10-15')
    assert second['changed']==1 and 'SECRET' not in str(second)
    again=scan_project(a.app,p['id'],day='2026-10-15')
    assert again==second


def test_concurrent_development_scan_returns_one_daily_snapshot(clients,tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from server import development
    from server.db import Project,DevelopmentDay
    a,_=clients;p=create_project(a)
    folder=tmp_path/'001Code';folder.mkdir();(folder/'app.py').write_text('print(1)')
    with a.app.state.sessions() as db:
        db.get(Project,p['id']).directory_path=str(folder);db.commit()
    original=development.inventory;barrier=Barrier(2)
    def synchronized(directory):
        result=original(directory);barrier.wait(timeout=10);return result
    monkeypatch.setattr(development,'inventory',synchronized)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:development.scan_project(a.app,p['id'],day='2026-10-15'),range(2)))
    assert results[0]==results[1]
    with a.app.state.sessions() as db:
        assert db.query(DevelopmentDay).filter_by(project_id=p['id']).count()==1


def test_grouping_preserves_directory_scope_and_merges_cross_day_formats(clients):
    a,_=clients;p=create_project(a)
    from server.db import StoredFile,Meeting,ImportedRecording,User
    with a.app.state.sessions() as db:
        owner=db.query(User).first()
        def file(name,mime,at):
            f=StoredFile(project_id=p['id'],owner_id=owner.id,name=name,mime=mime,size=20,sha256='a'*64,storage_key=name,parse_status='ready',extracted_text='# 方案\n**审批权限**',source_modified_at=at)
            db.add(f);db.flush();return f
        file('[codes] 甲范围 · 方案.docx','application/docx','2026-10-12T06:30:00+00:00')
        file('[codes] 甲范围 · 方案.pdf','application/pdf','2026-10-13T06:30:00+00:00')
        m=Meeting(project_id=p['id'],owner_id=owner.id,title='客户沟通',status='finished');db.add(m);db.flush()
        audio=file('[codes] 甲范围 · 客户沟通.m4a','audio/mp4','2026-10-12T06:30:00+00:00')
        db.add(ImportedRecording(file_id=audio.id,meeting_id=m.id,occurred_at='2026-10-12'))
        file('[codes] 乙范围 · 客户沟通-会议纪要.md','text/markdown','2026-10-13T06:30:00+00:00');db.commit()
    rows=a.get('/api/projects/'+p['id']+'/activity').json()['items']
    proposal=next(r for r in rows if r['title']=='方案')
    assert len(proposal['attachments'])==2 and proposal['time'].startswith('2026-10-13')
    assert not any(c in proposal['summary'] for c in '#*')
    assert len(next(r for r in rows if r['meeting_ids'])['attachments'])==1
    assert any(r['title']=='客户沟通-会议纪要' for r in rows)


def test_git_log_covers_interval_since_previous_snapshot(clients,tmp_path,monkeypatch):
    from server import development
    from server.db import Project,DevelopmentDay
    from types import SimpleNamespace
    a,_=clients;p=create_project(a);folder=tmp_path/'001Code';folder.mkdir();(folder/'.git').mkdir()
    commands=[]
    def fake_run(args,**kwargs):commands.append(args);return SimpleNamespace(returncode=0,stdout='abc123 修复审批\n')
    monkeypatch.setattr(development.subprocess,'run',fake_run)
    with a.app.state.sessions() as db:
        db.get(Project,p['id']).directory_path=str(folder)
        db.add(DevelopmentDay(project_id=p['id'],day='2026-10-14',recorded_at='2026-10-14T01:00:00+00:00'));db.commit()
    result=development.scan_project(a.app,p['id'],day='2026-10-15')
    assert '--since=2026-10-14T01:00:00+00:00' in commands[0]
    assert result['commits']==['abc123 修复审批'] and '期间' in result['summary']


def test_project_list_contains_current_summary(clients):
    from server.db import ProjectAnalysis
    a,_=clients;p=create_project(a)
    with a.app.state.sessions() as db:
        db.add(ProjectAnalysis(project_id=p['id'],summary='已提交方案，等待客户确认。'));db.commit()
    row=next(r for r in a.get('/api/projects').json() if r['id']==p['id'])
    assert row['analysis']['summary']=='已提交方案，等待客户确认。'


def test_oversized_code_scan_reports_actionable_error(clients,tmp_path,monkeypatch):
    from server import development
    from server.db import Project
    a,_=clients;p=create_project(a);folder=tmp_path/'001Code';folder.mkdir()
    with a.app.state.sessions() as db:
        db.get(Project,p['id']).directory_path=str(folder);db.commit()
    def oversized(directory):raise ValueError('capacity')
    monkeypatch.setattr(development,'inventory',oversized)
    response=a.post('/api/projects/'+p['id']+'/development/scan')
    assert response.status_code==422 and '扫描容量' in response.json()['detail']


def test_same_day_directory_batches_and_contextual_digests(clients):
    a,_=clients;p=create_project(a)
    from server.db import StoredFile,User,ProjectProgress
    with a.app.state.sessions() as db:
        owner=db.query(User).first();at='2026-10-14T06:30:00+00:00'
        for name in ['汇报V3_主线.png','汇报V3_总体架构.png','汇报V3_月报示意.png']:
            f=StoredFile(project_id=p['id'],owner_id=owner.id,name='[codes] 甲 · docs · '+name,mime='image/png',size=20,sha256='c'*64,storage_key=name,parse_status='ready',extracted_text='示意图',source_modified_at=at,origin='ours')
            db.add(f);db.flush()
            db.add(ProjectProgress(project_id=p['id'],source_type='file',source_id=f.id,source_name=f.name,input_hash=f.id,title=f.name,summary='此前甲资料均未见决定、负责人。',time_basis='file_modified',occurred_at=at))
        db.commit()
    rows=a.get('/api/projects/'+p['id']+'/activity').json()['items']
    group=next(r for r in rows if r['kind']=='batch')
    assert len(group['attachments'])==3 and '汇报V3' in group['summary'] and '我方' in group['summary']
    assert not any('未见决定' in r['summary'] or r['summary'].startswith('此前') for r in rows)
    calls=[]
    def model(purpose,payload):
        calls.append((purpose,payload))
        if purpose=='project_chunk':return {'summary':'汇报配图。','risks':[]}
        if purpose=='project_review':return {'summary':'为甲方建设运营平台，已提交汇报配图。','next':'确认汇报安排。','risk_ids':[]}
        if purpose=='timeline_digest':return {'items':[{'key':e['key'],'headline':'提交汇报V3配图','detail':'包含主线、总体架构与月报示意。'} for e in payload['entries']]}
        return {'summary':'汇报配图。'}
    a.app.state.analysis_model=model
    a.post('/api/projects/'+p['id']+'/analyze',json={})
    from server.automation import drain_jobs
    drain_jobs(a.app,limit=5,project_id=p['id'])
    digest=next(payload for purpose,payload in calls if purpose=='timeline_digest')
    assert digest['project']['summary'].startswith('为甲方') and digest['entries'][0]['files']
    rows=a.get('/api/projects/'+p['id']+'/activity').json()['items']
    assert next(r for r in rows if r['kind']=='batch')['summary']=='提交汇报V3配图'
    queue=a.get('/api/projects/'+p['id']+'/workflow').json()['analysis']['queue']
    assert queue['project']=='succeeded'
