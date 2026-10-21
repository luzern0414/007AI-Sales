import { useState } from 'react';
import { Check, ChevronDown, Plus, Sparkles } from 'lucide-react';
import { api, useResource, navigate } from '../api';
import type { WorkflowNode } from '../types';
import { shortTime } from '../types';
import { ErrorMessage, Loading } from './UI';
import { FileGlyph, originLabels } from './FilePreview';
import FilePreview from './FilePreview';
import Markdown from './Markdown';

type Attachment = { id: string; name: string; mime: string; origin: string; version: number };
type Activity = { id: string; kind: string; label?: string; title: string; time: string | null; summary: string; detail: string; points?: string[]; ai?: boolean; status?: string;
  attachments: Attachment[]; meeting_ids: string[]; node: (WorkflowNode & { index: number; current: boolean }) | null };

const tones: Record<string, string> = { meeting: 'meeting', development: 'dev', batch: 'file', file: 'file' };

/** Short facts for a card: AI points first, else the listing lines, else one plain sentence. */
function pointsOf(item: Activity) {
  if (item.points?.length) return item.points;
  // Listing lines read "file：what it shows"; the file names are already in the footer, so keep only the content.
  const lines = (item.detail || '').split('\n').filter((l) => /^\s*[-*]\s+/.test(l)).map((l) => l.replace(/^\s*[-*]\s+/, '').replace(/[*`#>]/g, '').trim())
    .map((l) => (item.attachments.length && l.includes('：') ? l.slice(l.indexOf('：') + 1).trim() : item.attachments.length ? '' : l)).filter(Boolean);
  if (lines.length) return [...new Set(lines)].slice(0, 6);
  const text = (item.detail || '').replace(/[#*>`|]/g, ' ').replace(/(^|\s)-\s+/g, ' ').replace(/\s+/g, ' ').trim();
  return text ? [text.length > 60 ? text.slice(0, 60) + '…' : text] : [];
}
const dayLabel = (t: string | null) => (t ? shortTime(t, false) : '日期待确认');
const clock = (t: string | null) => (t && t.length > 10 ? new Date(t).toTimeString().slice(0, 5) : '');

function originOf(list: Attachment[]) {
  const set = new Set(list.map((a) => a.origin));
  return set.size === 1 ? [...set][0] : set.size ? 'mixed' : '';
}

export default function ProjectOverview({ id, onNode, onSaved }: { id: string; onNode: (n: WorkflowNode) => void; onSaved: () => void }) {
  const { value, error, loading, refresh } = useResource<{ items: Activity[] }>(`/projects/${id}/activity`, 5000);
  const [count, setCount] = useState(20), [preview, setPreview] = useState(''), [failure, setFailure] = useState(''), [busy, setBusy] = useState(false),
    [open, setOpen] = useState<Record<string, boolean>>({}), [showNodes, setShowNodes] = useState(false);
  const rows = value?.items || [];
  const nodes = rows.filter((r) => r.node && !r.node.confirmed);
  const events = rows.filter((r) => !r.node || r.node.confirmed);
  function saved() { refresh(); onSaved(); }
  const next = nodes.find((n) => n.node!.ai?.status === 'done') || nodes.find((n) => n.node!.current) || nodes[0];
  return <section className="dense-activity">
    {next && <div className="next-node">
      <span className="next-dot" />
      <div><small>{next.node!.ai?.status==='done'?<><Sparkles size={10}/>AI 判断可确认</>:'下一个节点'}</small><strong>{next.title}</strong>{next.node!.ai?.evidence&&<span className="next-evidence">{next.node!.ai.evidence}</span>}</div>
      <button className="confirm-cta" onClick={() => onNode(next.node!)}><Check size={14} />确认已完成</button>
      {nodes.length > 1 && <button className="text-button" onClick={() => setShowNodes(!showNodes)}>{showNodes ? '收起' : `其余${nodes.length - 1}个`}</button>}
    </div>}
    {showNodes && <div className="pending-nodes">{nodes.filter((n) => n !== next).map((n) => <button key={n.id} className={n.node!.ai?.status || ''} onClick={() => onNode(n.node!)}><i>{n.node!.index}</i>{n.title}<span>{n.node!.ai?.status === 'done' ? 'AI 已判完成' : n.node!.ai?.status === 'doing' ? '进行中' : '确认'}</span></button>)}</div>}
    <div className="section-heading"><h2>项目历程</h2>
      <label className="text-button recording-upload"><Plus size={15} />{busy ? '导入中' : '导入录音'}<input className="sr-only" type="file" accept=".m4a,.mp3,.wav,.ogg,.webm" disabled={busy} onChange={async (e) => { const f = e.target.files?.[0]; e.target.value = ''; if (!f) return; setBusy(true); setFailure(''); try { const body = new FormData(); body.append('file', f); await api(`/projects/${id}/files`, { method: 'POST', body }); saved(); } catch (err) { setFailure((err as Error).message); } finally { setBusy(false); } }} /></label>
    </div>
    <ErrorMessage message={error || failure} />{loading && !value && <Loading />}
    <ol className="tl">{events.slice(0, count).map((item, i, list) => {
      const day = dayLabel(item.time), showDay = i === 0 || day !== dayLabel(list[i - 1].time);
      const n = item.node, tone = n ? 'node' : tones[item.kind] || 'file';
      const head = showDay && <li className="tl-day" key={'d' + item.id}>{day}</li>;
      if (n) return [head, <li className="tl-item node" key={item.id}>
        <span className="tl-dot"><Check size={9} strokeWidth={3} /></span>
        <button className="tl-card tl-node" onClick={() => onNode(n)}>
          <div className="tl-meta"><time>{clock(item.time)}</time><span className="tl-kind node">节点</span></div>
          <h3>{n.title} · 已确认</h3>{n.evidence && <p className="tl-brief">{n.evidence}</p>}
        </button>
      </li>];
      const expanded = !!open[item.id], origin = originOf(item.attachments), points = pointsOf(item);
      const files = item.attachments.length;
      return [head, <li className={'tl-item ' + tone} key={item.id}>
        <span className="tl-dot" />
        <div className={'tl-card' + (expanded ? ' open' : '')} onClick={() => setOpen({ ...open, [item.id]: !expanded })}>
          <div className="tl-meta"><time>{clock(item.time)}</time><span className={'tl-kind ' + tone}>{item.label || '资料'}</span>
            {origin && origin !== 'unknown' && <span className={'tl-origin ' + origin}>{origin === 'mixed' ? '双方' : originLabels[origin]}</span>}</div>
          <h3>{item.summary || item.title}</h3>
          {!!points.length && <ul className="tl-points">{(expanded ? points : points.slice(0, 2)).map((x) => <li key={x}>{x}</li>)}</ul>}
          {expanded && !points.length && item.detail && <div className="tl-full" onClick={(e) => e.stopPropagation()}><Markdown text={item.detail} /></div>}
          <div className="tl-foot">
            {!!files && <span className="glyph-stack">{item.attachments.slice(0, 4).map((a) => <FileGlyph key={a.id} name={a.name} mime={a.mime} size={13} />)}</span>}
            <span className="tl-file">{files > 1 ? `${files} 份文件` : item.attachments[0]?.name || (item.meeting_ids.length ? '会议记录' : item.title)}</span>
            <ChevronDown size={14} className={expanded ? 'flip' : ''} />
          </div>
          {expanded && <div className="timeline-attachments" onClick={(e) => e.stopPropagation()}>
            {item.attachments.map((f) => <button className={`attachment origin-${f.origin}`} key={f.id} onClick={() => setPreview(f.id)} title={originLabels[f.origin]}><FileGlyph name={f.name} mime={f.mime} size={15} /><span>{f.name}</span><i className={`origin-dot ${f.origin}`} /></button>)}
            {item.meeting_ids.map((mid) => <button className="attachment meeting-link" key={mid} onClick={() => { sessionStorage.setItem('meeting-parent-' + mid, 'projects/' + id); navigate('home/' + mid); }}><span>打开会议原文与纪要</span></button>)}
          </div>}
        </div>
      </li>];
    })}</ol>
    {!events.length && !loading && <p className="meta empty-line">暂无记录</p>}
    {events.length > count && <button className="load-more" onClick={() => setCount(count + 20)}>更多记录<ChevronDown size={15} /></button>}
    {preview && <FilePreview id={preview} onClose={() => setPreview('')} onChanged={saved} />}
  </section>;
}
