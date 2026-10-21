import { useState } from "react";
import { RefreshCw, Sparkles, ListTodo, Code2, CircleCheck } from "lucide-react";
import { useResource, navigate, post } from "../api";
import { shortTime, queueBusy, type Dashboard, type Workflow } from "../types";
import { ErrorMessage, Loading } from "../components/UI";
import DocumentProgress from "../components/DocumentProgress";

type WorkProject = Dashboard["projects"][number] & { workflow: Workflow; analysis: Workflow["analysis"] };

/** Cross-project portfolio signals; per-project follow-up lives in 项目管理. */
export default function Workspace() {
  const { value: d, error, loading, refresh } = useResource<Dashboard>("/dashboard", 5000);
  const projects = (d?.projects || []) as WorkProject[];
  const [scanning, setScanning] = useState(false),
    [scanError, setScanError] = useState("");
  async function update() {
    setScanning(true);
    setScanError("");
    try {
      const results = await Promise.allSettled(projects.filter((p) => p.directory_path).map((p) => post("/projects/" + p.id + "/development/scan", {})));
      const failed = results.filter((r) => r.status === "rejected").length;
      if (failed) setScanError(`${failed}个项目代码扫描未完成`);
      refresh();
    } finally {
      setScanning(false);
    }
  }
  const totals = projects.reduce(
    (s, p) => {
      const q = p.analysis?.queue;
      return q ? { busy: s.busy + queueBusy(q), done: s.done + q.done, failed: s.failed + q.failed } : s;
    },
    { busy: 0, done: 0, failed: 0 },
  );
  const confirmed = projects.reduce((s, p) => s + (p.workflow?.confirmed || 0), 0);
  const total = projects.reduce((s, p) => s + (p.workflow?.total || 8), 0);
  const board = [...projects].sort((a, b) => (b.workflow?.progress?.percent || 0) - (a.workflow?.progress?.percent || 0));
  const avg = Math.round(board.reduce((t, p) => t + (p.workflow?.progress?.percent || 0), 0) / Math.max(1, board.length));
  const actions = projects.flatMap((p) => p.analysis?.insight?.actions || []);
  const suggestions = actions.filter((a) => !a.state).length, adopted = actions.filter((a) => a.state === "adopt").length;
  const devs = projects.filter((p) => p.analysis?.development).sort((a, b) => b.analysis.development!.day.localeCompare(a.analysis.development!.day));
  return (
    <>
      <div className="page-heading">
        <h1>工作台</h1>
        <button className="text-button" onClick={update} disabled={scanning}>
          <RefreshCw size={15} className={scanning ? "spin" : ""} />
          {scanning ? "扫描中" : "扫描代码"}
        </button>
      </div>
      <ErrorMessage message={error || scanError} />
      {loading && !d ? (
        <Loading />
      ) : (
        <>
          <div className="stat-strip panel">
            <div>
              <CircleCheck size={15} />
              <strong>
                {confirmed}
                <small>/{total}</small>
              </strong>
              <span>已确认节点</span>
            </div>
            <div>
              <ListTodo size={15} />
              <strong>{adopted}</strong>
              <span>已转任务</span>
            </div>
            <div>
              <Sparkles size={15} />
              <strong>{suggestions}</strong>
              <span>AI 建议</span>
            </div>
            <div>
              <Code2 size={15} />
              <strong>{devs.length}</strong>
              <span>开发中</span>
            </div>
          </div>

          <section className="panel-block">
            <div className="section-heading">
              <h2>项目进度</h2>
              <span>{avg}%</span>
            </div>
            {board.map((p) => {
              const pr = p.workflow?.progress, q = p.analysis?.queue, busy = queueBusy(q);
              return (
                <button className="board-row" key={p.id} onClick={() => navigate("projects/" + p.id)}>
                  <span className="board-name">{p.name}</span>
                  <span className="board-stage">{pr?.stage_title}{busy ? <em>整理 {busy}</em> : q?.failed ? <em className="bad">失败 {q.failed}</em> : null}</span>
                  <span className="board-bar"><i className="base" style={{ width: (pr?.confirmed_percent || 0) + "%" }} /><i style={{ width: (pr?.percent || 0) + "%" }} /></span>
                  <strong>{pr?.percent || 0}%</strong>
                </button>
              );
            })}
            {totals.busy > 0 && (
              <div className="ai-progress wide">
                <span className="ai-bar"><i style={{ width: `${Math.round((totals.done / Math.max(1, totals.done + totals.busy)) * 100)}%` }} /></span>
                <span>AI 整理 {totals.done}/{totals.done + totals.busy}</span>
              </div>
            )}
          </section>

          {!!devs.length && (
            <section className="panel-block">
              <div className="section-heading">
                <h2>开发日报</h2>
              </div>
              {devs.map((p) => (
                <button className="dev-row" key={p.id} onClick={() => navigate("projects/" + p.id)}>
                  <time>{shortTime(p.analysis.development!.day, false)}</time>
                  <span className="line-title">{p.name}</span>
                  <p>{p.analysis.development!.summary}</p>
                </button>
              ))}
            </section>
          )}

          <DocumentProgress rows={d?.document_progress || []} />
        </>
      )}
    </>
  );
}
