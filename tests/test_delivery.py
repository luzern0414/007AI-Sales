from tests.test_platform import clients,create_project


def test_dependencies_reject_cycles_and_block_premature_completion(clients):
    a,_=clients
    p=create_project(a)
    url=f'/api/projects/{p["id"]}/tasks'
    first=a.post(url,json={'title':'Requirements'}).json()
    second=a.post(url,json={'title':'Implementation'}).json()
    assert a.post(f'/api/tasks/{second["id"]}/dependencies',json={'depends_on_id':first['id']}).status_code==201
    assert a.post(f'/api/tasks/{first["id"]}/dependencies',json={'depends_on_id':second['id']}).status_code==409
    assert a.patch(f'/api/tasks/{second["id"]}',json={'version':1,'status':'done','evidence':'test'}).status_code==409
    assert a.patch(f'/api/tasks/{first["id"]}',json={'version':1,'status':'done','evidence':'approved requirements'}).status_code==200
    assert a.patch(f'/api/tasks/{second["id"]}',json={'version':1,'status':'done','evidence':'verified build'}).status_code==200


def test_issue_lifecycle_and_delivery_gate(clients):
    a,_=clients
    p=create_project(a)
    url=f'/api/projects/{p["id"]}/issues'
    r=a.post(url,json={'title':'Missing customer permission','severity':'blocking'})
    assert r.status_code==201,r.text
    issue=r.json()
    assert a.patch(f'/api/projects/{p["id"]}',json={'version':1,'status':'delivered','reason':'attempt'}).status_code==409
    assert a.patch(f'/api/issues/{issue["id"]}',json={'version':1,'status':'closed'}).status_code==422
    assert a.patch(f'/api/issues/{issue["id"]}',json={'version':1,'status':'closed','resolution':'Approved permission record'}).status_code==200
    assert a.patch(f'/api/projects/{p["id"]}',json={'version':1,'status':'delivered','reason':'Signed acceptance record'}).status_code==200
    events=a.get(f'/api/projects/{p["id"]}').json()['events']
    assert sum(e['kind']=='issue' for e in events)==2


def test_milestone_and_reminders_are_deterministic(clients):
    a,_=clients
    p=create_project(a)
    r=a.post(f'/api/projects/{p["id"]}/milestones',json={'title':'Customer acceptance','due_date':'2020-01-01'})
    assert r.status_code==201,r.text
    dash=a.get('/api/dashboard').json()
    assert any(x['kind']=='milestone_overdue' for x in dash['risks'])
    assert a.get('/api/dashboard').json()['risks']==dash['risks']


def test_completed_tasks_keep_dependency_completion_consistent(clients):
    a,_=clients
    p=create_project(a)
    url=f'/api/projects/{p["id"]}/tasks'
    parent=a.post(url,json={'title':'需求确认'}).json()
    child=a.post(url,json={'title':'交付验收'}).json()
    assert a.patch(f'/api/tasks/{child["id"]}',json={'version':1,'status':'done','evidence':'验收单'}).status_code==200
    assert a.post(f'/api/tasks/{child["id"]}/dependencies',json={'depends_on_id':parent['id']}).status_code==409
    assert a.patch(f'/api/tasks/{parent["id"]}',json={'version':1,'status':'done','evidence':'需求确认单'}).status_code==200
    assert a.post(f'/api/tasks/{child["id"]}/dependencies',json={'depends_on_id':parent['id']}).status_code==201
    assert a.patch(f'/api/tasks/{parent["id"]}',json={'version':2,'status':'doing'}).status_code==409
    detail=a.get(f'/api/projects/{p["id"]}').json()
    assert all(t['status']=='done' for t in detail['tasks'])
