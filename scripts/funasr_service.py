"""Loopback-only FunASR service. Start via `python -m scripts.funasr_service`."""
import argparse
import asyncio
from contextlib import suppress
import json
import logging
from pathlib import Path
import time

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from .funasr_session import RecognitionSession
from .funasr_device import resolve_device


class RecognitionService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.busy = False

    async def handle(self, socket):
        if self.busy:
            await socket.send(json.dumps({'error':'service_busy'}))
            await socket.close(code=1013)
            return
        self.busy = True
        running = None
        try:
            config = json.loads(await asyncio.wait_for(socket.recv(),10))
            if (not isinstance(config,dict) or config.get('mode')!='2pass'
                or config.get('audio_fs')!=16000 or config.get('wav_format')!='pcm'
                or config.get('chunk_size')!=[5,10,5]):
                raise ValueError('unsupported configuration')
            session = self.session_factory()
            window, count = time.monotonic(), 0
            while True:
                message = await asyncio.wait_for(socket.recv(),60)
                final = False
                acknowledge = False
                if isinstance(message,str):
                    stop = json.loads(message)
                    if not isinstance(stop,dict) or stop.get('is_speaking') is not False:
                        raise ValueError('invalid stop')
                    final = True
                    acknowledge = stop.get('is_end') is True
                    pcm = b''
                else:
                    pcm = message
                    if not pcm or len(pcm)>6400 or len(pcm)%2:
                        raise ValueError('invalid audio frame')
                    if time.monotonic()-window>1:
                        window,count=time.monotonic(),0
                    count += len(pcm)
                    if count>64000:
                        raise ValueError('audio rate exceeded')
                running = asyncio.create_task(asyncio.to_thread(session.feed,pcm,final))
                events = await asyncio.shield(running)
                for event in events:
                    await socket.send(json.dumps(event,ensure_ascii=False))
                if final:
                    if acknowledge:
                        await socket.send(json.dumps({'mode':'2pass','is_end':True,'is_final':True}))
                    return
        except ConnectionClosed:
            pass
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Client errors never contain audio, recognized text or traceback paths.
            import torch
            error_code = 'recognition_failed'
            if isinstance(error, torch.cuda.OutOfMemoryError):
                error_code = 'gpu_out_of_memory'
                logging.error('CUDA GPU memory insufficient; close other GPU workloads or restart with --device cpu')
                torch.cuda.empty_cache()
            logging.exception('Local recognition failed')
            with suppress(ConnectionClosed):
                await socket.send(json.dumps({'error':error_code}))
        finally:
            # A cancelled coroutine must not release the model while its
            # inference thread is still using shared model weights.
            if running:
                with suppress(Exception):
                    await running
            self.busy = False


class Models:
    def __init__(self, directory, threads, device='cpu'):
        import torch
        from funasr import AutoModel
        torch.set_num_threads(threads)
        self.device = resolve_device(device, torch)
        self.models = {}
        try:
            for alias in ('paraformer-zh','paraformer-zh-streaming','fsmn-vad','ct-punc'):
                path=(directory/alias).resolve(strict=True)
                model=AutoModel(model=str(path),device=self.device,ncpu=threads,
                                disable_update=True,disable_pbar=True,
                                max_single_segment_time=20000)
                actual=str(next(model.model.parameters()).device)
                if actual != self.device:
                    raise RuntimeError(f'{alias}: requested {self.device}, actual {actual}')
                self.models[alias]=model
        except torch.cuda.OutOfMemoryError as error:
            raise RuntimeError('CUDA GPU memory insufficient. Close other GPU workloads or restart with --device cpu') from error

    def session(self):
        return RecognitionSession(Inference(self.models))


class Inference:
    def __init__(self, models):
        self.models=models
        self.vad_cache={}
        self.stream_cache={}
        self.vad_total=0
        self.vad_origin=0
        self.vad_active=False
        self.vad_last_end=0
        self.vad_tail=bytearray()
        self.vad_pending=bytearray()

    @staticmethod
    def samples(pcm):
        import numpy as np
        return np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768

    def vad(self, pcm, final):
        events=[]
        # FSMN retains waveform/scores indefinitely during silence. Rotate only
        # between utterances, replaying unconfirmed context on the same time axis.
        if not self.vad_active and self.vad_total-self.vad_origin>=10*32000:
            origin=max(self.vad_total-32000,self.vad_last_end)
            replay=bytes(self.vad_tail[-(self.vad_total-origin):]) if origin<self.vad_total else b''
            self.vad_cache={}
            self.vad_pending.clear()
            self.vad_origin=origin
            if replay:
                events.extend(self._vad(replay,False))
        self.vad_total+=len(pcm)
        self.vad_tail.extend(pcm)
        del self.vad_tail[:-32000]
        events.extend(self._vad(pcm,final))
        return events

    def _vad(self, pcm, final):
        # FunASR 1.2.9 stores a processed prefix instead of the short remainder
        # for non-final inputs. Keep remainders here and send whole 200ms frames.
        self.vad_pending.extend(pcm)
        events=[]
        while len(self.vad_pending)>=6400:
            frame=bytes(self.vad_pending[:6400])
            del self.vad_pending[:6400]
            events.extend(self._vad_frame(frame,False))
        if final:
            events.extend(self._vad_frame(bytes(self.vad_pending),True))
            self.vad_pending.clear()
        return events

    def _vad_frame(self, pcm, final):
        result=self.models['fsmn-vad'].generate(input=self.samples(pcm),cache=self.vad_cache,
                                               is_final=final,chunk_size=200,
                                               max_single_segment_time=20000,disable_pbar=True)
        events=[]
        for begin,end in result[0].get('value',[]) if result else []:
            if begin==end:
                continue
            begin=begin+self.vad_origin/32 if begin>=0 else begin
            end=end+self.vad_origin/32 if end>=0 else end
            if begin>=0:
                self.vad_active=True
            if end>=0:
                self.vad_active=False
                self.vad_last_end=max(self.vad_last_end,int(end*32))
            events.append([begin,end])
        return events

    def streaming(self, pcm, final):
        if not pcm and not self.stream_cache:
            return ''
        result=self.models['paraformer-zh-streaming'].generate(
            input=self.samples(pcm),cache=self.stream_cache,is_final=final,
            chunk_size=[5,10,5],encoder_chunk_look_back=4,decoder_chunk_look_back=1,
            disable_pbar=True)
        return result[0].get('text','') if result else ''

    def reset_stream(self):
        self.stream_cache={}

    def offline(self, pcm):
        result=self.models['paraformer-zh'].generate(input=self.samples(pcm),disable_pbar=True)
        text=result[0].get('text','') if result else ''
        if text:
            result=self.models['ct-punc'].generate(input=text,disable_pbar=True)
            text=result[0].get('text','') if result else ''
        return text


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-dir',type=Path,default=Path('output/funasr/models'))
    parser.add_argument('--port',type=int,default=10096)
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--device',choices=('cpu','cuda:0','auto'),default='cpu')
    args=parser.parse_args()
    models=Models(args.model_dir,args.threads,args.device)
    service=RecognitionService(models.session)
    async with serve(service.handle,'127.0.0.1',args.port,max_size=6400,max_queue=16,
                     open_timeout=10,close_timeout=2,compression=None):
        print(f'FUNASR_READY ws://127.0.0.1:{args.port} device={models.device} threads={args.threads}',flush=True)
        await asyncio.get_running_loop().create_future()


if __name__=='__main__':
    asyncio.run(main())
