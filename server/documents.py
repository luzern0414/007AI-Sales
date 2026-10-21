import hashlib
import html
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select

from .auth import Auth
from .common import DB, owned, data
from .db import Project, StoredFile, CaptureEpoch, TranscriptSegment, now
from .recordings import meeting, epoch_manifest,INTERRUPTIONS

router=APIRouter(prefix='/api')


def minutes(db, m):
    project=db.get(Project,m.project_id) if m.project_id else None
    epochs=db.scalars(select(CaptureEpoch).where(CaptureEpoch.meeting_id==m.id)).all()
    complete=all(e.sealed for e in epochs)
    integrity='未录音' if not epochs else '各段已保存；暂停及中断期间未录制' if complete else '存在未完整保存的录音段'
    raw=db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id==m.id).order_by(TranscriptSegment.created_at,TranscriptSegment.begin_ms)).all()
    revision=str(m.version)+(('.asr'+str(len(raw))) if raw else '')
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from .recording_imports import active_recording
    imported=active_recording(db,m.id)
    actual=imported.occurred_at if imported else m.created_at
    occurred=actual+'（时刻未记录）' if actual and len(actual)==10 else datetime.fromisoformat(actual).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M（北京时间）') if actual else '待确认'
    if imported:integrity='已保留导入录音'
    sections=[
        ('基本信息',f'项目：{project.name if project else "待归类"}\n客户：{(project.customer if project else "") or "待确认"}\n会议日期：{occurred}\n状态：讨论稿，待确认\n来源修订：{revision}\n录音：{integrity}'),
        ('会议纪要',m.ai_summary or m.notes or '待整理'),
        ('转写原文',m.transcript or '尚无转写内容'),
        ('来源',f'会议编号：{m.id}\n记录与转写为本次导出的原始依据；未生成额外决定或交付承诺。')
    ]
    if raw:sections.insert(-1,('实时转写原文（待校对）','\n'.join(s.text for s in raw)))
    interruptions=[e for e in epochs if e.interruption_kind]
    if interruptions:sections.insert(-1,('录音中断记录','\n'.join(INTERRUPTIONS[e.interruption_kind]+'；检测时间：'+e.interruption_detected_at for e in interruptions)+'\n检测时间不代表缺口起止，未录制内容无法还原。'))
    return {'title':m.title+' · 会议纪要','revision':revision,'sections':sections}


def render_md(document):
    return '# '+document['title']+'\n\n'+'\n\n'.join('## '+title+'\n\n'+text for title,text in document['sections'])+'\n'


def render_html(document):
    esc=html.escape
    blocks=''.join('<section><h2>'+esc(title)+'</h2><p>'+esc(text).replace('\n','<br>')+'</p></section>' for title,text in document['sections'])
    return '<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><title>'+esc(document['title'])+'</title><style>@page{size:A4;margin:25mm 25mm 23mm}body{font-family:SimSun,"Noto Serif CJK SC",serif;font-size:12pt;color:#192e43;line-height:1.8}h1{font-family:SimHei,sans-serif;font-size:20pt}h2{font-family:SimHei,sans-serif;font-size:15pt;break-after:avoid}p{white-space:normal;overflow-wrap:anywhere}section{margin:18pt 0}a{color:inherit}</style></head><body><h1>'+esc(document['title'])+'</h1>'+blocks+'</body></html>'


def disposition(name,ext):
    return "attachment; filename*=UTF-8''"+quote(name+'.'+ext)


@router.get('/meetings/{meeting_id}/minutes.md')
def md(meeting_id:str,db:DB,user:Auth):
    m=meeting(db,meeting_id,user)
    document=minutes(db,m)
    return Response(render_md(document),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':disposition(m.title,'md'),'X-Document-Revision':document['revision']})


@router.get('/meetings/{meeting_id}/minutes.html')
def page(meeting_id:str,db:DB,user:Auth):
    m=meeting(db,meeting_id,user)
    document=minutes(db,m)
    return HTMLResponse(render_html(document),headers={'X-Document-Revision':document['revision'],'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'"})


@router.get('/meetings/{meeting_id}/minutes.pdf')
def pdf(meeting_id:str,request:Request,db:DB,user:Auth):
    m=meeting(db,meeting_id,user)
    document=minutes(db,m)
    source=render_html(document)
    key=hashlib.sha256(source.encode()).hexdigest()
    target=request.app.state.storage / ('minutes-'+key+'.pdf')
    if not target.exists():
        root=Path(__file__).resolve().parents[1]
        try:
            process=subprocess.run([os.getenv('NODE_EXECUTABLE','node'),str(root/'scripts/render-pdf.mjs'),str(target)],input=source,text=True,encoding='utf-8',capture_output=True,timeout=60,cwd=root)
            if process.returncode or not target.exists() or target.read_bytes()[:5]!=b'%PDF-':
                raise RuntimeError('renderer failed')
        except (OSError,subprocess.TimeoutExpired,RuntimeError):
            target.unlink(missing_ok=True)
            raise HTTPException(503,'PDF生成失败，请重试或下载MD')
    return FileResponse(target,filename=m.title+'.pdf',media_type='application/pdf',headers={'X-Document-Revision':document['revision']})


@router.get('/projects/{project_id}/search')
def search(project_id:str,q:str,db:DB,user:Auth):
    owned(db,Project,project_id,user)
    if not q.strip() or len(q)>200:
        raise HTTPException(422,'请输入搜索内容')
    result=[]
    for file in db.scalars(select(StoredFile).where(StoredFile.project_id==project_id,~StoredFile.mime.like('audio/%')).order_by(StoredFile.created_at.desc())):
        index=file.extracted_text.casefold().find(q.casefold())
        if index>=0:
            result.append({'file_id':file.id,'name':file.name,'snippet':file.extracted_text[max(0,index-60):index+180],'sha256':file.sha256})
        if len(result)>=50:
            break
    return result
