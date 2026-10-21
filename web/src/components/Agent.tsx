import { useEffect, useRef, useState } from "react";
import { Sparkles, Check, X, RefreshCw, Brain, ChevronDown, ArrowUp, Square, LoaderCircle, CornerDownRight, ListChecks, ChevronRight } from "lucide-react";
import { post, stream, useResource } from "../api";
import type { Workflow, AgentAction, AskTurn } from "../types";
import { shortTime } from "../types";
import { ErrorMessage } from "./UI";
import Markdown from "./Markdown";

const priority: Record<string, string> = { high: "高", medium: "中", low: "低" };
const nodeNames: Record<string, string> = { negotiation: "客户洽谈", requirements: "需求确认", proposal: "方案提交", contract: "合同签订", development: "开发启动", delivery: "项目交付", acceptance: "验收通过", maintenance: "维护移交" };
/** Older reasoning may mention internal keys; readers see plain stage names. */
const plain = (t: string) => t.replace(/workflow中?/gi, "流程").replace(/\bstage(_progress)?\b/g, "阶段").replace(/\b(negotiation|requirements|proposal|contract|development|delivery|acceptance|maintenance)\b/g, (k) => nodeNames[k]);

/** The agent's current judgement: summary, decisions to take, open questions and the reasoning behind them. */
export function AgentBrief({ id, flow, onSaved, onAsk }: { id: string; flow: Workflow; onSaved: () => void; onAsk: (q: string) => void }) {
  const a = flow.analysis, insight = a.insight || {};
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(""), [error, setError] = useState("");
  // Older reviews only have a paragraph; show it sentence by sentence until the next review writes points.
  const points = insight.points?.length ? insight.points : (a.summary || "").split(/(?<=[。；！？])/).map((x) => x.trim()).filter(Boolean).slice(0, 5);
  const thinking = insight.thinking;
  const actions = (insight.actions || []).filter((x) => x.state !== "dismiss");
  const rethinking = a.status === "pending" || a.status === "running" || a.queue?.project === "pending" || a.queue?.project === "running";
  async function act(x: AgentAction, verdict: "adopt" | "dismiss") {
    setBusy(x.id); setError("");
    try { await post(`/projects/${id}/insight/actions`, { action_id: x.id, verdict }); onSaved(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  async function rethink() {
    setBusy("rethink"); setError("");
    try { await post(`/projects/${id}/analyze`, { background: a.background, instructions: a.instructions, expected_hash: a.input_hash }); onSaved(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  if (!points.length && !actions.length) return <section className="brief empty-brief">
    <header><span className="brief-mark"><Sparkles size={14} /></span><strong>AI 参谋</strong><span className="brief-state"><LoaderCircle size={13} className="spin" />思考中</span></header>
  </section>;
  return <section className="brief">
    <header>
      <span className="brief-mark"><Sparkles size={14} /></span><strong>AI 参谋</strong>
      {a.analyzed_at && <time>{shortTime(a.analyzed_at)}</time>}
      <button className={"brief-refresh" + (rethinking ? " busy" : "")} onClick={rethink} disabled={!!busy || rethinking} aria-label="重新思考">
        <RefreshCw size={14} className={rethinking || busy === "rethink" ? "spin" : ""} />{rethinking ? "思考中" : "重新思考"}
      </button>
    </header>
    {!!points.length && <ul className="brief-points">{points.map((x) => <li key={x}>{x}</li>)}</ul>}
    {!!actions.length && <div className="brief-actions">
      <div className="brief-sub"><ListChecks size={13} />下一步</div>
      {actions.map((x) => <div className={"action-row p-" + x.priority + (x.state ? " handled" : "")} key={x.id}>
        <span className="action-pri">{priority[x.priority]}</span>
        <div className="action-text"><strong>{x.title}</strong>{x.why && <span>{x.why}</span>}</div>
        {x.state === "adopt" ? <span className="action-done"><Check size={13} />已转任务</span> : <div className="action-buttons">
          <button className="adopt" disabled={!!busy} onClick={() => act(x, "adopt")} aria-label={"采纳：" + x.title}>{busy === x.id ? <LoaderCircle size={14} className="spin" /> : <Check size={15} />}</button>
          <button className="dismiss" disabled={!!busy} onClick={() => act(x, "dismiss")} aria-label={"忽略：" + x.title}><X size={15} /></button>
        </div>}
      </div>)}
    </div>}
    {!actions.length && a.next_step && <p className="brief-next"><CornerDownRight size={14} />{a.next_step}</p>}
    {!!insight.questions?.length && <div className="brief-questions">{insight.questions.map((q) => <button key={q} onClick={() => onAsk(q)}>{q}</button>)}</div>}
    {thinking && <div className="brief-thinking">
      <button className="thinking-toggle" onClick={() => setOpen(!open)} aria-expanded={open}><Brain size={13} />思考过程<ChevronDown size={14} className={open ? "flip" : ""} /></button>
      {open && <div className="thinking-body">
        {!!thinking.facts.length && <dl><dt>事实</dt>{thinking.facts.map((f) => <dd key={f}>{plain(f)}</dd>)}</dl>}
        {thinking.changes && <dl><dt>变化</dt><dd>{plain(thinking.changes)}</dd></dl>}
        {thinking.stage_reasoning && <dl><dt>判断</dt><dd>{plain(thinking.stage_reasoning)}</dd></dl>}
        {!!thinking.gaps.length && <dl><dt>缺口</dt>{thinking.gaps.map((g) => <dd key={g}>{plain(g)}</dd>)}</dl>}
        {!!thinking.review?.length && <dl className="review"><dt>自检</dt>{thinking.review.map((g) => <dd key={g}>{plain(g)}</dd>)}</dl>}
      </div>}
    </div>}
    <ErrorMessage message={error} />
  </section>;
}

const starters = ["下一步最该做什么？", "现在卡在哪？", "客户最在意什么？", "汇报要讲哪几点？"];
type Live = { question: string; text: string; error?: string };

/** Streams the answer as it is written; finished turns come back from the server with follow-ups. */
export function AskPanel({ id, flow, seed, onSeedUsed }: { id: string; flow: Workflow; seed: string; onSeedUsed: () => void }) {
  const history = useResource<AskTurn[]>(`/projects/${id}/asks`);
  const [text, setText] = useState(""), [live, setLive] = useState<Live | null>(null), [done, setDone] = useState<AskTurn[]>([]);
  const abort = useRef<AbortController | null>(null), end = useRef<HTMLDivElement>(null), used = useRef("");
  const stored = history.value || [];
  const turns = [...stored].reverse().concat(done.filter((t) => !stored.some((s) => s.id === t.id)));
  const streaming = !!live && !live.error;
  async function ask(q: string) {
    const question = q.trim();
    if (!question || abort.current) return;
    const controller = new AbortController(); abort.current = controller;
    setText(""); setLive({ question, text: "" });
    try {
      await stream(`/projects/${id}/ask/stream`, { question }, (event, data) => {
        if (event === "delta") setLive((l) => l && { ...l, text: l.text + data.t });
        else if (event === "done") { setDone((d) => [...d, data as AskTurn]); setLive(null); }
        else if (event === "error") setLive((l) => l && { ...l, error: data.message });
      }, controller.signal);
    } catch (e) {
      setLive((l) => l && { ...l, error: (e as Error).message });
    } finally {
      abort.current = null;
    }
  }
  useEffect(() => { if (seed && used.current !== seed) { used.current = seed; ask(seed); onSeedUsed(); } }, [seed]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [turns.length, live?.text.length]);
  const suggestions = [...(flow.analysis.insight?.questions || []).slice(0, 2), ...starters].slice(0, 4);
  const last = turns[turns.length - 1];
  return <section className="ask">
    {!turns.length && !live && <div className="ask-empty">
      <span className="brief-mark big"><Sparkles size={18} /></span>
      <div className="ask-starters">{suggestions.map((s) => <button key={s} onClick={() => ask(s)}><span>{s}</span><ChevronRight size={15} /></button>)}</div>
    </div>}
    {turns.map((t) => <article className="qa" key={t.id}>
      <p className="qa-q">{t.question}</p>
      <div className="qa-a"><Markdown text={t.answer} /></div>
    </article>)}
    {live && <article className="qa">
      <p className="qa-q">{live.question}</p>
      <div className={"qa-a" + (streaming ? " streaming" : "")}>
        {live.text ? <Markdown text={live.text.split("<<<")[0]} /> : !live.error && <span className="qa-wait"><i /><i /><i /></span>}
        {live.error && <p className="qa-error">{live.error}<button onClick={() => { const q = live.question; setLive(null); ask(q); }}>重试</button></p>}
      </div>
    </article>}
    {!live && !!last?.follow_ups.length && <div className="qa-follow">{last.follow_ups.map((f) => <button key={f} onClick={() => ask(f)}><CornerDownRight size={13} />{f}</button>)}</div>}
    <ErrorMessage message={history.error} />
    <div ref={end} />
    <form className="ask-bar" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder="问这个项目…" maxLength={500} aria-label="向 AI 提问" />
      {streaming ? <button type="button" className="stop" onClick={() => abort.current?.abort()} aria-label="停止"><Square size={13} fill="currentColor" /></button>
        : <button type="submit" disabled={!text.trim()} aria-label="发送"><ArrowUp size={18} /></button>}
    </form>
  </section>;
}
