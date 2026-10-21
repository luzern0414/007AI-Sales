import { useState } from "react";
import MeetingView from "./Meeting";
import { ArrowRight, Mic, FolderKanban, Gauge, Sparkles, CalendarClock, Plus, Trash2, ChevronRight } from "lucide-react";
import { useResource, navigate, api } from "../api";
import { shortTime, queueBusy, type Dashboard } from "../types";
import { ErrorMessage, Loading, NewProject, ProjectCard, Empty, ConfirmSheet } from "../components/UI";
import { useRecording, duration, type Meeting } from "../recording/runtime";

export default function Home({ meetingId }: { meetingId?: string }) {
  return meetingId ? <MeetingView id={meetingId} /> : <HomeDashboard />;
}

const meetingStates: Record<string, [string, string]> = {
  ready: ["已整理", "ok"],
  unclassified: ["待归类", "warn"],
  failed: ["整理失败", "bad"],
  pending: ["整理中", "busy"],
  running: ["整理中", "busy"],
  recording: ["录音中", "live"],
};
function meetingState(m: Meeting) {
  if (m.status === "recording") return meetingStates.recording;
  if (m.status !== "finished") return ["未结束", "muted"] as [string, string];
  return meetingStates[m.analysis_status || "pending"] || meetingStates.pending;
}

function greeting() {
  const h = new Date().getHours();
  return h < 6 ? "夜深了" : h < 11 ? "早上好" : h < 14 ? "中午好" : h < 18 ? "下午好" : "晚上好";
}

function HomeDashboard() {
  const { value: d, loading, error, refresh } = useResource<Dashboard>("/dashboard", 10000);
  const meetings = useResource<Meeting[]>("/meetings", 5000);
  const recording = useRecording();
  const [newProject, setNew] = useState(false), [managing, setManaging] = useState(false), [removing, setRemoving] = useState<Meeting | null>(null);
  const projects = (d?.projects || []).filter((p) => p.status === "active" || !p.status);
  const weekAgo = Date.now() - 7 * 86400000;
  const weekMeetings = (meetings.value || []).filter((m) => new Date(m.occurred_at || m.created_at).getTime() >= weekAgo).length;
  const avg = Math.round(projects.reduce((s, p) => s + (p.workflow?.progress?.percent || 0), 0) / Math.max(1, projects.length));
  const busy = projects.reduce((s, p) => s + queueBusy(p.analysis?.queue), 0);
  const done = projects.reduce((s, p) => s + (p.analysis?.queue?.done || 0), 0);
  const rank = { high: 0, medium: 1, low: 2 } as Record<string, number>;
  const suggestions = projects
    .flatMap((p) => (p.analysis?.insight?.actions || []).filter((a) => !a.state).map((a) => ({ ...a, project: p })))
    .sort((a, b) => rank[a.priority] - rank[b.priority]);
  const recent = [...projects].sort((a, b) => (b.counts?.latest || b.updated_at).localeCompare(a.counts?.latest || a.updated_at));
  const now = new Date();
  return (
    <>
      <section className="home-hero">
        <div className="hero-line">
          <div>
            <h1>{greeting()}</h1>
            <p>
              {now.getMonth() + 1}月{now.getDate()}日 · 周{"日一二三四五六"[now.getDay()]}
              {recent[0] ? ` · 最近更新「${recent[0].name}」` : ""}
            </p>
          </div>
          <button className="icon-chip" onClick={() => setNew(true)} aria-label="新建项目">
            <Plus size={17} />
          </button>
        </div>
        <div className="stat-strip">
          <button onClick={() => navigate("projects")}>
            <FolderKanban size={15} />
            <strong>{projects.length}</strong>
            <span>进行中</span>
          </button>
          <button onClick={() => document.getElementById("recent-meetings")?.scrollIntoView({ behavior: "smooth" })}>
            <Mic size={15} />
            <strong>{weekMeetings}</strong>
            <span>本周录音</span>
          </button>
          <button onClick={() => document.getElementById("ai-decisions")?.scrollIntoView({ behavior: "smooth" })}>
            <Sparkles size={15} />
            <strong>{suggestions.length}</strong>
            <span>AI 建议</span>
          </button>
          <button onClick={() => navigate("workspace")}>
            <Gauge size={15} />
            <strong>{avg}<small>%</small></strong>
            <span>平均进度</span>
          </button>
        </div>
        {busy > 0 && (
          <div className="ai-progress" role="status">
            <span className="ai-bar">
              <i style={{ width: `${Math.round((done / Math.max(1, done + busy)) * 100)}%` }} />
            </span>
            <span>AI 整理 {done}/{done + busy}</span>
          </div>
        )}
      </section>
      <ErrorMessage message={error || meetings.error} />
      {recording.recoveries.map((e) => (
        <div className="recovery" key={e.id}>
          <div>
            <strong>{e.title}</strong>
            <p>上次录音未上传完 · 本机已保存 {duration(e.totalFrames)}</p>
          </div>
          <button className="button secondary small" disabled={recording.busy} onClick={() => recording.recover(e)}>
            恢复上传
          </button>
        </div>
      ))}
      {loading && !d ? (
        <Loading />
      ) : (
        <>
          {!!suggestions.length && (
            <>
              <div className="section-heading" id="ai-decisions">
                <h2><Sparkles size={14} className="h-icon" />待决策</h2>
                <span>{suggestions.length}</span>
              </div>
              <div className="decision-list">
                {suggestions.slice(0, 4).map((a) => (
                  <button className={"decision-row p-" + a.priority} key={a.project.id + a.id} onClick={() => navigate("projects/" + a.project.id)}>
                    <i />
                    <span className="decision-main"><strong>{a.title}</strong><span>{a.project.name}{a.why ? " · " + a.why : ""}</span></span>
                    <ChevronRight size={15} />
                  </button>
                ))}
              </div>
            </>
          )}
          <div className="section-heading">
            <h2>最近项目</h2>
            <button className="text-button" onClick={() => navigate("projects")}>
              全部 {projects.length}
              <ArrowRight size={15} />
            </button>
          </div>
          <div className="project-grid">
            {recent.slice(0, 4).map((p) => (
              <ProjectCard project={p} key={p.id} />
            ))}
          </div>
          {!projects.length && <Empty title="暂无项目" action="新建项目" onClick={() => setNew(true)} />}
        </>
      )}
      {!!meetings.value?.length && (
        <>
          <div className="section-heading" id="recent-meetings">
            <h2>最近录音</h2>
            <button className="text-button" onClick={() => setManaging(!managing)}>{managing ? "完成" : "管理"}</button>
          </div>
          <div className="meeting-list">
            {meetings.value.slice(0, managing ? 30 : 6).map((m) => {
              const [label, tone] = meetingState(m);
              return (
                <button className="meeting-row" key={m.id} onClick={() => navigate("home/" + m.id)}>
                  <span className="meeting-icon">
                    <Mic size={16} />
                  </span>
                  <span className="meeting-main">
                    <strong>{m.title}</strong>
                    <span>
                      <CalendarClock size={12} />
                      {shortTime(m.occurred_at || m.created_at) || "日期待确认"}
                      {m.projects?.length ? " · " + m.projects.map((p) => p.name).join("、") : ""}
                    </span>
                  </span>
                  {managing && m.status !== "recording" && m.id !== recording.meetingId ? (
                    <span className="row-delete" role="button" aria-label={"删除 " + m.title} onClick={(e) => { e.stopPropagation(); setRemoving(m); }}><Trash2 size={15} /></span>
                  ) : (
                    <span className={"state-chip " + tone}>{label}</span>
                  )}
                </button>
              );
            })}
          </div>
        </>
      )}
      {removing && (
        <ConfirmSheet
          title={"删除「" + removing.title + "」？"}
          detail="录音、转写、纪要及由它生成的文档将一并删除"
          onClose={() => setRemoving(null)}
          onConfirm={async () => { await api("/meetings/" + removing.id, { method: "DELETE" }); meetings.refresh(); refresh(); }}
        />
      )}
      {newProject && <NewProject onClose={() => setNew(false)} onSaved={refresh} />}
    </>
  );
}
