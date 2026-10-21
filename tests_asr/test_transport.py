import asyncio
import json

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from scripts.funasr_service import RecognitionService


class Session:
    def feed(self, pcm, final=False):
        if final:
            return [{'mode': '2pass-offline', 'text': '测试尾句。', 'is_final': False}]
        return []


def test_transport_rejects_competing_session_and_acknowledges_after_tail():
    async def scenario():
        service = RecognitionService(lambda: Session())
        async with serve(service.handle, '127.0.0.1', 0) as server:
            url = f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            async with connect(url, proxy=None) as first:
                await first.send(json.dumps({'mode':'2pass','audio_fs':16000,'wav_format':'pcm','chunk_size':[5,10,5]}))
                async with connect(url, proxy=None) as second:
                    assert json.loads(await second.recv())['error'] == 'service_busy'
                await first.send(bytes(6400))
                await first.send(json.dumps({'is_speaking':False,'is_end':True}))
                assert json.loads(await first.recv())['text'] == '测试尾句。'
                assert json.loads(await first.recv()) == {'mode':'2pass','is_end':True,'is_final':True}
    asyncio.run(scenario())


def test_bad_configuration_and_inference_error_never_get_success_ack():
    class Broken:
        def feed(self, pcm, final=False):
            raise RuntimeError('secret internal model path')
    async def scenario():
        service = RecognitionService(lambda: Broken())
        async with serve(service.handle, '127.0.0.1', 0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            async with connect(url,proxy=None) as socket:
                await socket.send(json.dumps({'mode':'2pass','audio_fs':48000}))
                assert json.loads(await socket.recv()) == {'error':'recognition_failed'}
            async with connect(url,proxy=None) as socket:
                await socket.send(json.dumps({'mode':'2pass','audio_fs':16000,'wav_format':'pcm','chunk_size':[5,10,5]}))
                await socket.send(json.dumps({'is_speaking':False,'is_end':True}))
                assert json.loads(await socket.recv()) == {'error':'recognition_failed'}
    asyncio.run(scenario())


def test_gpu_out_of_memory_is_distinct_and_never_acknowledged():
    import torch

    class Exhausted:
        def feed(self, pcm, final=False):
            raise torch.cuda.OutOfMemoryError('private allocation details')

    async def scenario():
        service=RecognitionService(lambda: Exhausted())
        async with serve(service.handle,'127.0.0.1',0) as server:
            url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            async with connect(url,proxy=None) as socket:
                await socket.send(json.dumps({'mode':'2pass','audio_fs':16000,'wav_format':'pcm','chunk_size':[5,10,5]}))
                await socket.send(json.dumps({'is_speaking':False,'is_end':True}))
                assert json.loads(await socket.recv()) == {'error':'gpu_out_of_memory'}
        assert service.busy is False

    asyncio.run(scenario())
