from tests.test_platform import clients,create_project
from tests.test_recordings import new_meeting
from server.db import GeneratedDocument


def test_document_revision_preserves_old_evidence_and_rejects_stale_edit(clients):
    a,b=clients;p=create_project(a);m=new_meeting(a,p)
    with a.app.state.sessions() as db:
        row=GeneratedDocument(project_id=p['id'],meeting_id=m['id'],kind='proposal',title='审批实施方案',markdown='# 审批实施方案\n\n## 一、范围\n\n权限待确认',source_snapshot='[{"evidence":"original"}]',source_revision=1)
        db.add(row);db.commit();did=row.id
    url=f'/api/documents/{did}/revisions'
    body={'title':'审批实施方案','markdown':'# 审批实施方案\n\n## 一、范围\n\n甲方角色清单仍待提供','reason':'依据本次会议校订措辞'}
    assert b.post(url,json=body).status_code==401
    assert a.post(url,json={**body,'reason':''}).status_code==422
    r=a.post(url,json=body)
    assert r.status_code==201,r.text
    revised=r.json()
    assert revised['document_version']==2 and revised['previous_version_id']==did
    assert a.get(f'/api/documents/{did}/download').text.endswith('权限待确认')
    assert '甲方角色清单' in a.get(f'/api/documents/{revised["id"]}/download').text
    assert a.post(url,json=body).status_code==409
    assert 'source_snapshot' not in revised
    with a.app.state.sessions() as db:
        assert db.get(GeneratedDocument,revised['id']).source_snapshot=='[{"evidence":"original"}]'
    events=a.get(f'/api/projects/{p["id"]}').json()['events']
    assert any(e['kind']=='document' and '校订措辞' in e['detail'] for e in events)
