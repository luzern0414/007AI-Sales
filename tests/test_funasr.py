"""Real local WebSocket transport; isolated upstream, never a recognition benchmark."""
import json
import threading
from contextlib import contextmanager

from websockets.sync.server import serve

from tests.test_platform import clients, create_project
from tests.test_recordings import new_meeting


@contextmanager
def local_asr(handler):
    with serve(handler, '127.0.0.1', 0) as upstream:
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        try:
            yield f'ws://127.0.0.1:{upstream.socket.getsockname()[1]}'
        finally:
            upstream.shutdown()
            thread.join(timeout=5)


def test_local_funasr_stream_corrects_partial_and_persists_only_final(clients, monkeypatch):
    received = []

    def provider(socket):
        config = json.loads(socket.recv())
        received.append(config)
        received.append(socket.recv())
        socket.send(json.dumps({'mode': '2pass-online', 'text': '客户要', 'is_final': True}))
        socket.send(json.dumps({'mode': '2pass-online', 'text': '对账'}))
        socket.send(json.dumps({'mode': '2pass-offline', 'text': '客户需要对账。', 'is_final': False}))
        stop = json.loads(socket.recv())
        received.append(stop)
        socket.send(json.dumps({'mode': '2pass-offline', 'text': '下周确认。', 'is_final': True}))
        # Official runtime sends an end acknowledgement only when requested.
        if stop.get('is_end'):
            socket.send(json.dumps({'mode': '2pass', 'is_end': True, 'is_final': True}))

    a, _ = clients
    m = new_meeting(a, create_project(a))
    monkeypatch.setenv('REALTIME_ASR_PROVIDER', 'funasr')
    monkeypatch.delenv('DASHSCOPE_API_KEY', raising=False)
    with local_asr(provider) as url:
        monkeypatch.setenv('FUNASR_WS_URL', url)
        assert a.get('/api/integrations/status').json()['realtime_asr']['configured'] is True
        with a.websocket_connect(f'/api/meetings/{m["id"]}/transcribe') as ws:
            assert ws.receive_json()['type'] == 'ready'
            ws.send_bytes(b'\x00\x00' * 1600)
            events = [ws.receive_json() for _ in range(3)]
            assert [x['text'] for x in events] == ['客户要', '客户要对账', '客户需要对账。']
            assert [x['final'] for x in events] == [False, False, True]
            ws.send_text('stop')
            assert ws.receive_json()['text'] == '下周确认。'
            assert ws.receive_json()['type'] == 'complete'
    assert received[0]['mode'] == '2pass'
    assert received[0]['audio_fs'] == 16000
    assert received[1] == b'\x00\x00' * 1600
    assert received[2] == {'is_speaking': False, 'is_end': True}
    rows = a.get(f'/api/meetings/{m["id"]}/transcripts').json()
    assert [x['text'] for x in rows] == ['客户需要对账。', '下周确认。']
    assert all(x['begin_ms'] is None and x['end_ms'] is None for x in rows)
    assert a.post(f'/api/meetings/{m["id"]}/epochs', json={}).status_code == 200


def test_local_asr_failure_is_explicit_and_archive_remains_available(clients, monkeypatch):
    def provider(socket):
        socket.recv()
        socket.send('{invalid-json')

    a, _ = clients
    m = new_meeting(a, create_project(a))
    monkeypatch.setenv('REALTIME_ASR_PROVIDER', 'funasr')
    with local_asr(provider) as url:
        monkeypatch.setenv('FUNASR_WS_URL', url)
        with a.websocket_connect(f'/api/meetings/{m["id"]}/transcribe') as ws:
            assert ws.receive_json()['type'] == 'ready'
            assert ws.receive_json()['type'] == 'error'
    assert a.get(f'/api/meetings/{m["id"]}/transcripts').json() == []
    assert a.post(f'/api/meetings/{m["id"]}/epochs', json={}).status_code == 200


def test_unselected_or_invalid_provider_does_not_fall_back_to_paid_service(clients, monkeypatch):
    a, _ = clients
    m = new_meeting(a, create_project(a))
    monkeypatch.setenv('REALTIME_ASR_PROVIDER', 'funasr')
    monkeypatch.delenv('FUNASR_WS_URL', raising=False)
    for key in ('DASHSCOPE_API_KEY', 'DASHSCOPE_WS_URL', 'DASHSCOPE_ASR_MODEL'):
        monkeypatch.setenv(key, 'configured-but-not-selected')
    assert a.get('/api/integrations/status').json()['realtime_asr']['configured'] is False
    with a.websocket_connect(f'/api/meetings/{m["id"]}/transcribe') as ws:
        assert ws.receive_json()['type'] == 'unavailable'
