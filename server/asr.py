"""DashScope SDK streaming adapter. Audio archiving never depends on this route."""
import asyncio
import json
import os
import time
from contextlib import suppress

from fastapi import APIRouter,HTTPException,WebSocket,WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .auth import Auth,digest
from .common import DB,data
from .db import LoginSession,User,TranscriptSegment,now,uid
from .recordings import meeting

router=APIRouter(prefix='/api')


def provider():
    return os.getenv('REALTIME_ASR_PROVIDER','dashscope').strip().lower()


def configured():
    if provider()=='funasr':
        from .funasr import service_url
        return service_url() is not None
    if provider()=='dashscope':
        return all(os.getenv(key) for key in ('DASHSCOPE_API_KEY','DASHSCOPE_WS_URL','DASHSCOPE_ASR_MODEL'))
    return False


def persist_untimed(app,mid,text):
    # FunASR final messages don't consistently carry a meeting-relative time axis.
    # Preserve real words without inventing audio locations or treating text as an ID.
    with app.state.sessions() as db:
        db.add(TranscriptSegment(meeting_id=mid,run_id=uid(),begin_ms=None,end_ms=None,text=text))
        refresh_finished_analysis(db,mid)
        db.commit()


def refresh_finished_analysis(db,mid):
    from .db import Meeting,Project
    from .automation import enqueue_meeting
    m=db.get(Meeting,mid)
    if m and m.status=='finished':
        owner=m.owner_id or (db.get(Project,m.project_id).owner_id if m.project_id else None)
        if owner:enqueue_meeting(db,m,db.get(User,owner))


def persist_sentence(app,mid,run_id,sentence):
    if not sentence.get('sentence_end') or not sentence.get('text'):
        return
    begin=int(sentence.get('begin_time') or 0)
    end=int(sentence.get('end_time') or begin)
    if len(sentence['text'])>20000:return
    with app.state.sessions() as db:
        exists=db.scalar(select(TranscriptSegment.id).where(TranscriptSegment.meeting_id==mid,TranscriptSegment.run_id==run_id,TranscriptSegment.begin_ms==begin))
        if exists:return
        db.add(TranscriptSegment(meeting_id=mid,run_id=run_id,begin_ms=begin,end_ms=end,text=sentence['text']))
        refresh_finished_analysis(db,mid)
        try:db.commit()
        except IntegrityError:db.rollback()


@router.get('/meetings/{meeting_id}/transcripts')
def transcripts(meeting_id:str,db:DB,user:Auth):
    meeting(db,meeting_id,user)
    return [data(x) for x in db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id==meeting_id).order_by(TranscriptSegment.created_at,TranscriptSegment.begin_ms))]


@router.websocket('/meetings/{meeting_id}/transcribe')
async def stream(ws:WebSocket,meeting_id:str):
    origins=set(os.getenv('ALLOWED_ORIGINS','http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8765,http://localhost:8765').split(','))
    if ws.headers.get('origin') and ws.headers['origin'] not in origins:
        await ws.close(1008);return
    try:
        with ws.app.state.sessions() as db:
            token=ws.cookies.get('sales_session','')
            login=db.get(LoginSession,digest(token)) if token else None
            if login is None or login.expires_at<now():raise HTTPException(401)
            user=db.get(User,login.user_id);meeting(db,meeting_id,user)
    except HTTPException:
        await ws.close(1008);return
    await ws.accept()
    if not configured():
        await ws.send_json({'type':'unavailable','message':'转写未连接'});await ws.close();return
    if provider()=='funasr':
        from .funasr import relay
        await relay(ws,meeting_id,persist_untimed)
        return
    run_id=uid();loop=asyncio.get_running_loop();queue=asyncio.Queue(maxsize=256)
    def enqueue(value):
        if queue.full():
            while not queue.empty():queue.get_nowait()
            queue.put_nowait({'type':'error','message':'转写处理繁忙，请会后重试'})
        else:queue.put_nowait(value)
    recognition=None;sender=None
    try:
        import dashscope
        from dashscope.audio.asr import Recognition,RecognitionCallback
        dashscope.base_websocket_api_url=os.environ['DASHSCOPE_WS_URL']

        class Callback(RecognitionCallback):
            def on_event(self,result):
                sentence=result.get_sentence()
                if sentence and 'text' in sentence:
                    loop.call_soon_threadsafe(enqueue,{'type':'transcript','text':sentence['text'],'final':bool(sentence.get('sentence_end')),'sentence':sentence,'run_id':run_id})
            def on_error(self,result):loop.call_soon_threadsafe(enqueue,{'type':'error','message':'转写服务中断，录音继续保存'})
            def on_complete(self):loop.call_soon_threadsafe(enqueue,{'type':'complete'})
        recognition=Recognition(model=os.environ['DASHSCOPE_ASR_MODEL'],format='pcm',sample_rate=16000,callback=Callback(),api_key=os.environ['DASHSCOPE_API_KEY'])
        await asyncio.wait_for(asyncio.to_thread(recognition.start),15)
        await ws.send_json({'type':'ready','run_id':run_id})

        async def forward():
            while True:
                event=await queue.get()
                if event['type']=='transcript':
                    await asyncio.to_thread(persist_sentence,ws.app,meeting_id,run_id,event['sentence'])
                    event={k:v for k,v in event.items() if k!='sentence'}
                await ws.send_json(event)
                if event['type'] in ('error','complete'):return
        sender=asyncio.create_task(forward())
        window_start=time.monotonic();window_bytes=0
        while True:
            frame=await asyncio.wait_for(ws.receive(),60)
            if frame['type']=='websocket.disconnect':break
            if frame.get('text'):
                if frame['text']=='stop':break
                raise ValueError('unexpected message')
            payload=frame.get('bytes',b'')
            if len(payload)>6400 or len(payload)%2:raise ValueError('invalid frame')
            if time.monotonic()-window_start>1:window_start=time.monotonic();window_bytes=0
            window_bytes+=len(payload)
            if window_bytes>64000:raise ValueError('audio rate exceeded')
            await asyncio.wait_for(asyncio.to_thread(recognition.send_audio_frame,payload),5)
    except (WebSocketDisconnect,asyncio.TimeoutError,ValueError,OSError,RuntimeError):
        with suppress(Exception):await ws.send_json({'type':'error','message':'转写已中断，录音继续保存'})
    except Exception:
        with suppress(Exception):await ws.send_json({'type':'error','message':'转写服务暂不可用'})
    finally:
        if recognition:
            with suppress(Exception):await asyncio.wait_for(asyncio.to_thread(recognition.stop),5)
        if sender:
            with suppress(Exception):await asyncio.wait_for(asyncio.shield(sender),3)
            sender.cancel()
            with suppress(asyncio.CancelledError):await sender
        with suppress(Exception):await ws.close()
