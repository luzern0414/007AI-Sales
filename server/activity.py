"""Compact, evidence-preserving project timeline grouped by business artifact."""
import json,re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import select,or_
from fastapi import APIRouter
from .auth import Auth
from .common import DB,owned
from .db import Project,StoredFile,SourceImport,Meeting,MeetingProject,DevelopmentDay,AnalysisJob
from .recording_imports import active_recording,business_time
from .workflow import flow

router=APIRouter(prefix='/api')
INTERNAL=re.compile(r'数据库设计|数据设计|系统开发|开发指南|开发约定|系统架构|架构设计|模块设计|接口设计|ui设计|交互说明|原型|测试用例|测试计划|测试报告|部署方案|回滚方案|开发计划|环境搭建|开发规范|技术架构|technical.design|architecture',re.I)
MEETING_SUFFIX=re.compile(r'[-_ ·]*(?:FunASR)?(?:会议纪要|录音转写|转写原文|转写稿|会议记录|会议录音)$',re.I)
# Legacy per-file summaries restated the whole project or only listed missing facts; they confuse readers.
BOILERPLATE=re.compile(r'未见决定|未载决定|均属背景|均未见|未见负责人|未表明已实施|形成未实施')
KINDS=[('纪要','会议纪要'),('合同','合同'),('报价','报价'),('需求','需求材料'),('验收','验收材料'),('方案','方案'),('汇报','汇报材料'),('计划','计划'),('报告','报告'),('清单','清单'),('调研','调研')]
TOPICS=[('数据|数据库','数据设计'),('架构|模块|接口','架构接口'),('ui|UI|交互|原型|页面','交互设计'),('测试|缺陷|验收记录','测试质量'),('部署|回滚|发布','部署发布'),('计划|plan','开发计划')]


def clean_name(name):
    if name.startswith('['):name=re.sub(r'^\[[^\]]+\]\s*','',name).split(' · ')[-1]
    return Path(name.replace('\\','/')).stem


def key_name(name):
    return re.sub(r'[\s_·—\-（）()]','',MEETING_SUFFIX.sub('',clean_name(name))).casefold()


def source_scope(name):
    # Imported names encode their parent directory; local uploads have no scope prefix.
    if name.startswith('[') and ' · ' in name:
        return name.rsplit(' · ',1)[0].casefold()
    return str(Path(name.replace('\\','/')).parent).casefold()


def local_day(value):
    if not value:return ''
    if len(value)==10:return value
    try:return datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    except ValueError:return value[:10]


def readable(text,limit=120):
    from .project_analysis import concise
    value=re.sub(r'[#*>`|]','',text or '').strip()
    value=re.sub(r'^按文件排序[，,]\s*','',value)
    if not value or value.startswith('此前') or BOILERPLATE.search(value):return ''
    value=re.sub(r'^(?:本文件|该文件)(?:为|是)\s*','',value)
    return concise(value,limit)


def brief(text):
    return readable(text) or ''


def material_kind(f):
    if f.mime.startswith('image/'):return '配图'
    title=clean_name(f.name)
    for marker,label in KINDS:
        if marker in title:return label
    if f.mime.endswith('sheet') or f.name.lower().endswith(('.xlsx','.csv')):return '表格'
    return '资料'


def file_description(f):
    who={'client':'客户提供','ours':'我方提供'}.get(f.origin,'新增')
    return f'{who}{material_kind(f)}《{clean_name(f.name)}》'


def internal_file(f):
    return bool(INTERNAL.search(f.name)) or bool(re.search(r'(^| · )(architecture|adr|plans|research_notes|meeting-agent)( · |$)|development[-_]|ui[-_](spec|design)|database[-_]',f.name,re.I)) or any(x in f.name for x in ('02-产品与开发','02-开发过程','02-开发与实施','02_开发','开发文档','技术文档'))


def attachment(f):
    return {'id':f.id,'name':clean_name(f.name)+Path(f.name).suffix,'mime':f.mime,'origin':f.origin,'version':f.file_version}


def common_prefix(names):
    if len(names)<2:return ''
    prefix=names[0]
    for name in names[1:]:
        while prefix and not name.startswith(prefix):prefix=prefix[:-1]
    return prefix.rstrip('_-· （(') if len(prefix.rstrip('_-· （('))>=2 else ''


def latest_digests(db,pid):
    job=db.scalar(select(AnalysisJob).where(AnalysisJob.kind=='project',AnalysisJob.target_id==pid,AnalysisJob.status.in_(['succeeded','superseded'])).order_by(AnalysisJob.updated_at.desc()).limit(1))
    try:return json.loads(job.result_json).get('digests',{}) if job else {}
    except ValueError:return {}


def group_key(item):
    from .automation import hashed
    return hashed(['timeline-group-v1',sorted(a['id'] for a in item['attachments']),sorted(item['meeting_ids'])])[:20]


def batch(items,scope):
    """Same-directory material from one local day reads as a single delivery."""
    names=[i['title'] for i in items]
    main=next((i for i in items if re.search(r'方案|报告|纪要|需求|合同|报价|计划|汇报版',i['title']) and not all(a['mime'].startswith('image/') for a in i['attachments'])),items[0])
    prefix=common_prefix(names)
    count=sum(len(i['attachments']) for i in items)
    origins={a['origin'] for i in items for a in i['attachments']}
    who='客户提供' if origins=={'client'} else '我方提供' if origins=={'ours'} else '新增'
    headline=f'{who}{prefix}系列{len(items)}项资料' if prefix else f'{who}《{main["title"]}》等{len(items)}项资料'
    lines=[f'- {i["title"]}：{i["summary"]}' if i['summary'] and not i['summary'].endswith(f'《{i["title"]}》') else f'- {i["title"]}' for i in items]
    return {'id':'batch-'+main['id'],'kind':'batch','label':'资料','title':main['title']+f' 等{count}份','time':max(i['time'] for i in items),'sort_time':max(i['sort_time'] for i in items),
            'summary':headline,'detail':'\n'.join(lines),'attachments':[a for i in items for a in i['attachments']],'meeting_ids':[],'node':None,'children':items}


def project_activity(db,p,digests=None):
    from .automation import visible_progress
    from .project_analysis import concise
    progress={(r.source_type,r.source_id):r for r in visible_progress(db,p.id)}
    files=list(db.scalars(select(StoredFile).where(StoredFile.project_id==p.id).order_by(StoredFile.created_at,StoredFile.id)))
    replaced={f.previous_version_id for f in files if f.previous_version_id}
    missing=set(db.scalars(select(SourceImport.file_id).where(SourceImport.missing.is_(True))))
    files=[f for f in files if f.id not in replaced|missing]
    meetings=list(db.scalars(select(Meeting).where(or_(Meeting.project_id==p.id,Meeting.id.in_(select(MeetingProject.meeting_id).where(MeetingProject.project_id==p.id))))))
    items=[];groups={};meeting_keys={};internal={}
    for m in meetings:
        recording=active_recording(db,m.id)
        audio=db.get(StoredFile,recording.file_id) if recording else None
        row=progress.get(('meeting',m.id))
        actual=recording.occurred_at if recording else m.created_at
        title=m.title if m.title_locked or m.ai_summary or not audio else clean_name(audio.name)
        summary=readable(row.summary if row else '') or readable(m.ai_summary) or readable(m.transcript or m.notes) or f'会议《{title}》已记录，待整理纪要。'
        item={'id':'meeting-'+m.id,'kind':'meeting','label':'会议','title':title,'time':actual,'sort_time':actual or m.created_at,
              'summary':summary,'detail':m.ai_summary or m.notes,'attachments':[attachment(audio)] if audio else [],'meeting_ids':[m.id],'node':None,
              'sources':[('meeting',m.id)],'status':m.analysis_status or m.status}
        items.append(item)
        scope=source_scope(audio.name) if audio else '.'
        meeting_keys.setdefault((scope,key_name(title)),[]).append(item)
        meeting_keys.setdefault((scope,key_name(m.title)),[]).append(item)
    for f in files:
        if f.mime.startswith('audio/'):continue
        row=progress.get(('file',f.id));at=business_time(f)[0]
        if internal_file(f):
            internal.setdefault(local_day(at),[]).append((f,row));continue
        key=key_name(f.name)
        candidates=list({item['id']:item for item in meeting_keys.get((source_scope(f.name),key),[])}.values())
        # Exact source topic plus a single occurrence or matching explicit day; never broad date-only matching.
        candidate=next((item for item in candidates if item['time'] and local_day(item['time'])==local_day(at)),None)
        if not candidate and len(candidates)==1:candidate=candidates[0]
        if candidate and (MEETING_SUFFIX.search(clean_name(f.name)) or key_name(f.name)==key_name(candidate['title'])):
            candidate['attachments'].append(attachment(f));candidate['sources'].append(('file',f.id))
            if not candidate['detail'] and f.extracted_text:candidate['detail']=f.extracted_text
            continue
        group=(source_scope(f.name),key,f.file_version)
        if group not in groups:
            item={'id':'file-'+f.id,'kind':'file','label':material_kind(f),'title':clean_name(f.name),'time':at,'sort_time':at,
                  'summary':readable(row.summary if row else '') or file_description(f),
                  'detail':readable(row.current,400) if row else '', 'attachments':[],'meeting_ids':[],'node':None,'sources':[],'scope':group[0]}
            groups[group]=item;items.append(item)
        groups[group]['attachments'].append(attachment(f));groups[group]['sources'].append(('file',f.id))
        if at>groups[group]['time']:groups[group]['time']=groups[group]['sort_time']=at
    by_day={}
    for item in [i for i in items if i['kind']=='file']:by_day.setdefault((item['scope'],local_day(item['time'])),[]).append(item)
    for (scope,_),members in by_day.items():
        if len(members)<2:continue
        merged=batch(sorted(members,key=lambda i:i['sort_time']),scope)
        merged['sources']=[s for i in members for s in i['sources']]
        for member in members:items.remove(member)
        items.append(merged)
    for day,rows in internal.items():
        summaries=list(dict.fromkeys(x for x in (readable(r.summary,70) for _,r in rows if r) if x))
        topics=[label for pattern,label in TOPICS if any(re.search(pattern,f.name) for f,_ in rows)]
        names=list(dict.fromkeys(clean_name(f.name) for f,_ in rows))
        items.append({'id':'docs-development-'+day,'kind':'development','label':'开发','title':'开发进度','time':day,'sort_time':day,
                      'summary':f'更新{len(rows)}份研发文档'+('：'+'、'.join(topics[:3]) if topics else ''),
                      'detail':'涉及：'+'、'.join(names[:8])+('等' if len(names)>8 else '')+'。'+('\n\n'+'\n'.join('- '+s for s in summaries[:6]) if summaries else ''),
                      'attachments':[],'meeting_ids':[],'node':None,'sources':[]})
    for r in db.scalars(select(DevelopmentDay).where(DevelopmentDay.project_id==p.id)):
        result=json.loads(r.result_json)
        if result['baseline'] and not result.get('commits') or not result['changed'] and not result.get('commits'):continue
        existing=next((i for i in items if i['kind']=='development' and i['time']==r.day),None)
        if existing:
            existing['summary']=result['summary'];existing['detail']='\n'.join([existing['detail'],*('- '+c for c in result.get('commits',[]))])
        else:items.append({'id':'code-'+r.day,'kind':'development','label':'开发','title':'开发进度','time':r.day,'sort_time':r.day,'summary':result['summary'],'detail':'\n'.join('- '+c for c in result.get('commits',[])),'attachments':[],'meeting_ids':[],'node':None,'sources':[]})
    digests=latest_digests(db,p.id) if digests is None else digests
    for item in items:
        item['key']=group_key(item)
        digest=digests.get(item['key'])
        if digest and item['kind'] in ('file','batch','meeting'):
            # The digest replaces the mechanical listing; attachments already show every file.
            item['summary']=digest['headline'];item['detail']=digest['detail'];item['points']=digest.get('points') or []
            item['ai']=True
    lifecycle=flow(db,p)
    for index,n in enumerate(lifecycle['nodes']):
        items.append({'id':'node-'+n['key'],'kind':'node','label':'节点','title':n['title'],'time':n['occurred_at'],'sort_time':n['occurred_at'] or '','summary':n['evidence'] or '',
                      'detail':'','attachments':[],'meeting_ids':[],'node':{**n,'index':index+1,'current':lifecycle['current']==n['key']},'sources':[]})
    dated=sorted([i for i in items if i['time']],key=lambda i:(i['sort_time'],i['id']),reverse=True)
    unknown=[i for i in items if not i['time'] and i['kind']!='node']
    pending=[i for i in items if not i['time'] and i['kind']=='node']
    return {'items':dated+unknown+pending}


def public(item):
    return {k:v for k,v in item.items() if k not in ('sources','children','scope','sort_time')}


def digest_inputs(db,p,source_summaries):
    """Timeline groups with their evidence summaries, for one contextual AI pass."""
    rows=[i for i in project_activity(db,p,digests={})['items'] if i['kind'] in ('file','batch','meeting')]
    output=[]
    for item in sorted(rows,key=lambda i:i['sort_time'] or ''):
        notes=[]
        for kind,sid in item['sources']:
            text=source_summaries.get(sid)
            if not text and kind=='file':
                f=db.get(StoredFile,sid)
                text=(f.extracted_text or '')[:500] if f else ''
            if not text and kind=='meeting':
                m=db.get(Meeting,sid)
                text=(m.ai_summary or m.transcript or '')[:1200] if m else ''
            if text:notes.append(text)
        output.append({'key':group_key(item),'kind':item['kind'],'date':local_day(item['time']),'title':item['title'],
                       'files':[{'name':a['name'],'origin':a['origin']} for a in item['attachments']][:12],'evidence':notes[:8]})
    return output


@router.get('/projects/{pid}/activity')
def activity(pid:str,db:DB,user:Auth):
    return {'items':[public(i) for i in project_activity(db,owned(db,Project,pid,user))['items']]}
