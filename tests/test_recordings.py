import hashlib
import struct

from tests.test_platform import clients, create_project


def new_meeting(a, p):
    r = a.post(f'/api/projects/{p["id"]}/meetings', json={'title': 'Meeting audio test'})
    assert r.status_code == 201, r.text
    return r.json()


def test_audio_out_of_order_retry_and_seal(clients):
    a, b = clients
    p = create_project(a)
    m = new_meeting(a, p)
    epoch = a.post(f'/api/meetings/{m["id"]}/epochs', json={}).json()
    payload = struct.pack('<16000h', *([0] * 16000))
    headers = {'Content-Type': 'application/octet-stream', 'X-Audio-Hash': hashlib.sha256(payload).hexdigest(), 'X-Frame-Start': '16000', 'X-Capture-Token': epoch['token']}
    url = f'/api/epochs/{epoch["id"]}/blocks/'
    assert a.put(url+'1', content=payload, headers=headers).status_code == 200
    manifest = a.get(f'/api/meetings/{m["id"]}/manifest').json()
    assert manifest['epochs'][0]['contiguous_frames'] == 0
    assert manifest['epochs'][0]['missing_ranges'] == [[0, 0]]
    headers['X-Frame-Start'] = '0'
    assert a.put(url+'0', content=payload, headers=headers).status_code == 200
    assert a.put(url+'0', content=payload, headers=headers).status_code == 200
    changed = struct.pack('<16000h', *([1] * 16000))
    headers['X-Audio-Hash'] = hashlib.sha256(changed).hexdigest()
    assert a.put(url+'0', content=changed, headers=headers).status_code == 409
    assert b.get(f'/api/meetings/{m["id"]}/manifest').status_code == 401
    manifest = a.get(f'/api/meetings/{m["id"]}/manifest').json()
    assert manifest['epochs'][0]['contiguous_frames'] == 32000
    r = a.post(f'/api/epochs/{epoch["id"]}/seal', json={'token': epoch['token'], 'last_seq': 1, 'total_frames': 32000})
    assert r.status_code == 200, r.text
    assert a.post(f'/api/meetings/{m["id"]}/finish', json={}).status_code == 200
    wav = a.get(f'/api/meetings/{m["id"]}/audio')
    assert wav.status_code == 200 and wav.content[:4] == b'RIFF'
    assert len(wav.content) == 64044


def test_recovery_token_fences_old_capture_and_missing_blocks(clients):
    a, _ = clients
    m = new_meeting(a, create_project(a))
    url = f'/api/meetings/{m["id"]}'
    first = a.post(url+'/epochs', json={}).json()
    assert a.post(url+'/finish', json={}).status_code == 409
    assert a.post(url+'/epochs', json={}).status_code == 409
    restored = a.post(f'/api/epochs/{first["id"]}/restore', json={'last_seq':0,'total_frames':16000}).json()
    payload = bytes(32000)
    headers = {'Content-Type': 'application/octet-stream', 'X-Audio-Hash': hashlib.sha256(payload).hexdigest(), 'X-Frame-Start': '0', 'X-Capture-Token': first['token']}
    assert a.put(f'/api/epochs/{first["id"]}/blocks/0', content=payload, headers=headers).status_code == 409
    headers['X-Capture-Token'] = restored['token']
    assert a.put(f'/api/epochs/{first["id"]}/blocks/0', content=payload, headers=headers).status_code == 200
    headers['X-Frame-Start']='16000'
    assert a.put(f'/api/epochs/{first["id"]}/blocks/1',content=payload,headers=headers).status_code==409
    assert a.post(f'/api/epochs/{first["id"]}/seal', json={'token': restored['token'], 'last_seq': 1, 'total_frames': 32000}).status_code == 409
    assert a.post(f'/api/epochs/{first["id"]}/seal', json={'token': restored['token'], 'last_seq': 0, 'total_frames': 16000}).status_code == 200
    second = a.post(url+'/epochs', json={}).json()
    assert second['id'] != first['id']


def test_meeting_notes_revision_and_access(clients):
    a, b = clients
    m = new_meeting(a, create_project(a))
    url = f'/api/meetings/{m["id"]}'
    assert a.patch(url, json={'version': 1, 'notes': 'Customer asked for an approval workflow'}).status_code == 200
    assert a.patch(url, json={'version': 1, 'notes': 'lost edit'}).status_code == 409
    assert a.get(url).json()['notes'].endswith('workflow')
    assert b.get(url).status_code == 401


def test_interruption_is_token_fenced_preserved_and_exported(clients):
    a,b=clients
    m=new_meeting(a,create_project(a));e=a.post(f'/api/meetings/{m["id"]}/epochs',json={}).json()
    url=f'/api/epochs/{e["id"]}/interruption'
    body={'token':e['token'],'kind':'input_stalled','detected_at':'2026-10-15T03:00:00Z'}
    assert b.post(url,json=body).status_code==401
    assert a.post(url,json={**body,'token':'obsolete'}).status_code==409
    assert a.post(url,json=body).status_code==200
    assert a.post(url,json=body).status_code==200
    row=a.get(f'/api/meetings/{m["id"]}/manifest').json()['epochs'][0]
    assert row['interruption_kind']=='input_stalled'
    assert row['interruption_detected_at'].startswith('2026-10-15T03:00:00')
    assert a.post(f'/api/epochs/{e["id"]}/seal',json={'token':e['token'],'last_seq':-1,'total_frames':0}).status_code==200
    assert '录音输入停滞' in a.get(f'/api/meetings/{m["id"]}/minutes.md').text
    events=a.get(f'/api/projects/{m["project_id"]}').json()['events']
    assert len([x for x in events if x['title']=='会议录音中断'])==1
