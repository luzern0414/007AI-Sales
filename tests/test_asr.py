import os
from tests.test_platform import clients,create_project
from tests.test_recordings import new_meeting


def test_unconfigured_stream_is_explicit_and_does_not_stop_archive(clients,monkeypatch):
    monkeypatch.setenv('REALTIME_ASR_PROVIDER','dashscope')
    monkeypatch.delenv('DASHSCOPE_API_KEY',raising=False)
    a,_=clients
    m=new_meeting(a,create_project(a))
    with a.websocket_connect(f'/api/meetings/{m["id"]}/transcribe') as ws:
        event=ws.receive_json()
        assert event['type']=='unavailable'
    assert a.post(f'/api/meetings/{m["id"]}/epochs',json={}).status_code==200


def test_stream_result_contract_persists_final_only(clients,monkeypatch):
    a,_=clients
    m=new_meeting(a,create_project(a))
    from server.asr import persist_sentence
    app=a.app
    persist_sentence(app,m['id'],'run1',{'begin_time':0,'end_time':None,'sentence_end':False,'text':'在识别'})
    persist_sentence(app,m['id'],'run1',{'begin_time':0,'end_time':1000,'sentence_end':True,'text':'确认需求'})
    persist_sentence(app,m['id'],'run1',{'begin_time':0,'end_time':1000,'sentence_end':True,'text':'确认需求'})
    rows=a.get(f'/api/meetings/{m["id"]}/transcripts').json()
    assert len(rows)==1 and rows[0]['text']=='确认需求'
    assert a.get(f'/api/meetings/{m["id"]}').json()['transcript']==''
