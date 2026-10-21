"""Bounded relay to an operator-configured private FunASR 2pass service."""
import asyncio
import json
import os
import time
from contextlib import suppress
from urllib.parse import urlsplit

from fastapi import WebSocketDisconnect
from websockets.asyncio.client import connect

from .db import uid


def service_url():
    value=os.getenv('FUNASR_WS_URL','').strip()
    try:
        parsed=urlsplit(value)
        if parsed.scheme not in ('ws','wss') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            return None
        parsed.port
    except ValueError:
        return None
    return value


async def relay(ws,meeting_id,persist):
    run_id=uid()
    tasks=[]
    stopped=asyncio.Event()
    try:
        # No browser-controlled URL, proxy discovery, insecure TLS or paid fallback.
        async with connect(service_url(),open_timeout=10,close_timeout=2,max_size=128*1024,max_queue=16,proxy=None) as upstream:
            await upstream.send(json.dumps({'mode':'2pass','wav_name':run_id,'wav_format':'pcm','audio_fs':16000,'is_speaking':True,'chunk_size':[5,10,5],'chunk_interval':10,'itn':True}))
            await ws.send_json({'type':'ready','run_id':run_id})

            async def upload():
                window_start=time.monotonic()
                window_bytes=0
                while True:
                    frame=await asyncio.wait_for(ws.receive(),60)
                    if frame['type']=='websocket.disconnect':
                        raise WebSocketDisconnect()
                    if frame.get('text'):
                        if frame['text']!='stop':
                            raise ValueError('unexpected message')
                        stopped.set()
                        await asyncio.wait_for(upstream.send(json.dumps({'is_speaking':False,'is_end':True})),5)
                        return
                    payload=frame.get('bytes',b'')
                    if not payload or len(payload)>6400 or len(payload)%2:
                        raise ValueError('invalid audio frame')
                    if time.monotonic()-window_start>1:
                        window_start=time.monotonic()
                        window_bytes=0
                    window_bytes+=len(payload)
                    if window_bytes>64000:
                        raise ValueError('audio rate exceeded')
                    await asyncio.wait_for(upstream.send(payload),5)

            async def download():
                partial=''
                while True:
                    value=json.loads(await upstream.recv())
                    if not isinstance(value,dict) or value.get('error'):
                        raise ValueError('invalid recognition result')
                    if value.get('is_end') is True:
                        if not stopped.is_set() or value.get('is_final') is not True:
                            raise ValueError('unexpected end')
                        await ws.send_json({'type':'complete'})
                        return
                    mode=value.get('mode')
                    text=value.get('text','')
                    if not isinstance(text,str) or len(text)>20000:
                        raise ValueError('invalid recognition text')
                    if not text:
                        continue
                    if mode=='2pass-online':
                        partial+=text
                        if len(partial)>20000:
                            raise ValueError('partial text exceeded')
                        await ws.send_json({'type':'transcript','text':partial,'final':False,'run_id':run_id})
                    elif mode=='2pass-offline':
                        # In 2pass mode the corrected utterance is authoritative;
                        # is_final may describe the entire input, not the utterance.
                        await asyncio.to_thread(persist,ws.app,meeting_id,text)
                        partial=''
                        await ws.send_json({'type':'transcript','text':text,'final':True,'run_id':run_id})
                    else:
                        raise ValueError('unsupported recognition mode')

            sending=asyncio.create_task(upload())
            receiving=asyncio.create_task(download())
            tasks=[sending,receiving]
            done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
            if sending in done:
                await asyncio.wait_for(receiving,15)
            elif stopped.is_set():
                await asyncio.wait_for(sending,5)
            else:
                raise ValueError('upstream stopped before audio input')
    except WebSocketDisconnect:
        pass
    except Exception:
        with suppress(Exception):
            await ws.send_json({'type':'error','message':'转写已中断，录音继续保存'})
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError,Exception):
                await task
        with suppress(Exception):
            await ws.close()
