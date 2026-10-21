import { useState } from 'react';
import { ArrowRight, Circle, Sparkles, CalendarDays, Undo2, CheckCircle2, FileText, Mic } from 'lucide-react';
import { api, post, navigate } from '../api';
import type { Workflow, WorkflowNode, Detail } from '../types';
import { Modal, Form, values, Empty, Ring } from './UI';
import { queueBusy } from '../types';

export function fullTime(value: string | null | undefined) {
  return value ? value.length===10?value:new Intl.DateTimeFormat('zh-CN', {year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value)) : '';
}
function localTime(value: string | null) {
  if (!value) return '';
  const d = new Date(value);
  return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
}

export function WorkflowHero({ flow, detail, onNode, onTab }: {flow: Workflow; detail: Detail; onNode: (node:WorkflowNode)=>void; onTab:(tab:string)=>void}) {
  const files = detail.files.filter(f=>!(f.mime||'').startsWith('audio/'));
  const client = files.filter(f=>f.origin==='client').length, ours = files.filter(f=>f.origin==='ours').length;
  const q = flow.analysis.queue, busy = queueBusy(q), insight = flow.analysis.insight || {};
  const pr = flow.progress;
  const stageNode = flow.nodes.find(n=>n.key===pr?.stage) || flow.nodes.find(n=>n.key===flow.current);
  return <section className="cockpit">
    <div className="cockpit-top">
      <Ring value={pr?.percent||0} confirmed={pr?.confirmed_percent||0} size={66} light onClick={()=>stageNode&&onNode(stageNode)} label={`整体进度${pr?.percent||0}%`}/>
      <div className="cockpit-stage">
        <span className="cockpit-kicker">{pr?.basis==='ai'?<><Sparkles size={11}/>AI 评估</>:'已确认'}{pr&&pr.confirmed_percent>0&&<em>确认 {pr.confirmed_percent}%</em>}</span>
        <strong>{pr?.stage_title||'全部完成'}{pr?.stage_progress!=null&&<small>{pr.stage_progress}%</small>}</strong>
        {flow.due_date&&<span className="cockpit-health"><CalendarDays size={12}/>{flow.due_date}交付</span>}
      </div>
    </div>
    <StageTrack flow={flow} onNode={onNode}/>
    <div className="cockpit-chips">
      <button onClick={()=>onTab('files')}><FileText size={12}/>{files.length}</button>
      {client>0&&<button className="client" onClick={()=>onTab('files')}>客户 {client}</button>}
      {ours>0&&<button className="ours" onClick={()=>onTab('files')}>我方 {ours}</button>}
      <button onClick={()=>onTab('overview')}><Mic size={12}/>{detail.meetings.length}</button>
      {busy>0&&<span className="busy"><span className="ai-bar"><i style={{width:`${Math.round((q!.done/Math.max(1,q!.done+busy))*100)}%`}}/></span>{busy}</span>}
    </div>
  </section>;
}

/** Eight equal segments: solid = confirmed, tinted = AI judged in progress or done, outlined = not started. */
export function StageTrack({flow,onNode}:{flow:Workflow;onNode:(node:WorkflowNode)=>void}) {
  return <div className="stage-track" role="list">{flow.nodes.map(n=>{
    const state = n.confirmed?'done':n.ai?.status==='done'?'ai-done':n.key===flow.progress?.stage?'current':n.ai?.status==='doing'?'doing':'';
    const fill = n.key===flow.progress?.stage&&flow.progress?.stage_progress!=null?flow.progress.stage_progress:0;
    return <button role="listitem" key={n.key} className={'stage '+state} onClick={()=>onNode(n)} aria-label={`${n.title}，${n.confirmed?'已确认':n.ai?.status==='done'?'AI判断已完成':'未确认'}`}>
      <i style={state==='current'?{'--fill':`${fill}%`} as React.CSSProperties:undefined}/>
      <span>{n.title.slice(0,2)}</span>
    </button>;})}</div>;
}

export function WorkflowCards({flow,onNode}:{flow:Workflow;onNode:(node:WorkflowNode)=>void}) {
  return <div className="node-grid">{flow.nodes.map((n,i)=><button key={n.key} className={`node-card ${n.confirmed?'confirmed':''}`} onClick={()=>onNode(n)}>
    <div className="row-between"><span className="node-number">{String(i+1).padStart(2,'0')}</span>{n.confirmed?<CheckCircle2 size={22}/>:<Circle size={22}/>}</div>
    <h2>{n.title}</h2><span className="badge">{n.confirmed?'已确认':flow.current===n.key?'当前环节':'待确认'}</span>
    <time>{fullTime(n.occurred_at)}</time>{n.evidence&&<p>{n.evidence}</p>}
    <span className="node-action">{n.confirmed?'查看确认':'确认节点'}<ArrowRight size={16}/></span>
  </button>)}</div>;
}

export function NodeDialog({id,node,flow,onClose,onSaved}:{id:string;node:WorkflowNode;flow:Workflow;onClose:()=>void;onSaved:()=>void}) {
  const [revoke,setRevoke]=useState(false);
  const signed=flow.nodes.find(n=>n.key==='contract')?.confirmed;
  const canPlan=['contract','development','delivery','acceptance','maintenance'].includes(node.key)&&(signed||node.key==='contract');
  return <Modal title={node.title} onClose={onClose}>
    {!node.confirmed&&node.ai?.evidence&&<p className={'ai-judgement '+node.ai.status}><Sparkles size={13}/><b>{node.ai.status==='done'?'AI 判断已完成':node.ai.status==='doing'?'AI 判断进行中':'AI 判断未开始'}</b>{node.ai.evidence}</p>}
    <Form label={revoke?'撤回确认':node.confirmed?'更新确认':'确认节点'} onSubmit={async f=>{
      const v=values(f);
      await api(`/projects/${id}/workflow/${node.key}`, {method:'PUT',body:JSON.stringify({version:node.version,confirmed:!revoke,evidence:v.evidence,occurred_at:revoke?null:new Date(v.occurred_at).toISOString(),...(v.due_date?{due_date:v.due_date}:{})})});
      onSaved();onClose();
    }}>
      {!revoke&&<label>实际发生时间<input type="datetime-local" name="occurred_at" required defaultValue={localTime(node.occurred_at)} max={localTime(new Date().toISOString())}/></label>}
      <label>{revoke?'撤回原因':'确认依据'}<textarea key={revoke?'revoke':'confirm'} name="evidence" required maxLength={4000} defaultValue={revoke?'':node.evidence||(node.ai?.status==='done'?node.ai.evidence:'')} placeholder={revoke?'填写原因':'邮件、合同、交付记录等'}/></label>
      {!revoke&&canPlan&&<label>计划交付<input type="date" name="due_date" defaultValue={flow.due_date||''}/></label>}
      {node.confirmed&&<button type="button" className="text-button" onClick={()=>setRevoke(!revoke)}><Undo2 size={16}/>{revoke?'返回确认':'撤回确认'}</button>}
    </Form>
    {!!flow.history?.some(h=>h.key===node.key)&&<details className="node-history"><summary>确认记录</summary>{flow.history.filter(h=>h.key===node.key).map(h=><article key={h.id}><strong>{h.title}</strong>{h.occurred_at&&<time>发生于 {fullTime(h.occurred_at)}</time>}<time>记录于 {fullTime(h.recorded_at)}</time><p>{h.evidence}</p></article>)}</details>}
  </Modal>;
}

export function AnalysisDialog({id,flow,onClose,onSaved}:{id:string;flow:Workflow;onClose:()=>void;onSaved:()=>void}) {
  return <Modal title="补充项目信息" onClose={onClose}><Form label="同步给 Agent" onSubmit={async f=>{
    const v=values(f);await post(`/projects/${id}/analyze`,{...v,expected_hash:flow.analysis.input_hash});onSaved();onClose();
  }}><label>项目背景<textarea name="background" defaultValue={flow.analysis.background} maxLength={30000} placeholder="补充业务背景、客户现状"/></label><label>本次分析要求<textarea name="instructions" defaultValue={flow.analysis.instructions} maxLength={10000} placeholder="关注的变化或待确认事项"/></label></Form></Modal>;
}


