import { useState, useEffect, useRef } from "react";
import {
  Mic,
  Square,
  ArrowUpRight,
  FileText,
  ArrowLeft,
  Download,
  Save,
  Trash2,
} from "lucide-react";
import { api, useResource, navigate, post, patch, download } from "../api";
import ProjectDocuments from "../components/ProjectDocuments";
import MeetingClassification from "../components/MeetingClassification";
import Markdown from '../components/Markdown';
import { ErrorMessage, Loading, ConfirmSheet } from "../components/UI";
import { useRecording, duration, type Meeting } from "../recording/runtime";
export default function MeetingView({ id }: { id: string }) {
  const {
    value: meeting,
    error,
    refresh,
  } = useResource<Meeting>("/meetings/" + id, 5000);
  const r = useRecording();
  const [removing, setRemoving] = useState(false);
  const jobs = useResource<
    { request_id: string; status: string; error: string }[]
  >(`/meetings/${id}/generations`, 5000);
  const running = jobs.value?.some((job) => job.status === "running");
  const manifest = useResource<{
    epochs: {
      id: string;
      sealed: boolean;
      contiguous_frames: number;
      interruption_kind: string | null;
    }[];
  }>(`/meetings/${id}/manifest`, 5000);
  const hasAudio = manifest.value?.epochs.some(
    (e) => e.sealed && e.contiguous_frames > 0,
  );
  const interruptions =
    manifest.value?.epochs.filter((e) => e.interruption_kind).length || 0;
  const raw = useResource<{ id: string; text: string }[]>(
    "/meetings/" + id + "/transcripts",
    5000,
  );
  useEffect(() => {
    if (r.meetingId === id && r.liveText) void raw.refresh();
  }, [id, r.meetingId, r.liveText, raw.refresh]);
  const [notes, setNotes] = useState(""),
    [transcript, setTranscript] = useState(""),
    [status, setStatus] = useState(""),
    [actionError, setError] = useState(""),
    [exporting, setExporting] = useState(false);
  const [generating, setGenerating] = useState(false),
    [generated, setGenerated] = useState(false);
  const [classification, setClassification] = useState(false);
  const [retrying, setRetrying] = useState(false),
    [analysisQueued, setAnalysisQueued] = useState(false);
  const [generationProject, setGenerationProject] = useState("");
  useEffect(() => {
    setAnalysisQueued(false);
  }, [meeting?.analysis_status]);
  const [draft, setDraft] = useState<{
    notes: string;
    transcript: string;
    baseRevision: number;
  } | null>(null);
  const pendingSave = useRef<Promise<void> | null>(null);
  const version = useRef(0),
    dirty = useRef(false),
    saving = useRef(false),
    edits = useRef(0),
    latest = useRef({ notes: "", transcript: "" });
  latest.current = { notes, transcript };
  useEffect(() => {
    if (meeting && meeting.version >= version.current) {
      if (!dirty.current && !saving.current) {
        version.current = meeting.version;
        setNotes(meeting.notes);
        setTranscript(meeting.transcript);
      }
    }
  }, [meeting]);
  useEffect(() => {
    if (!meeting) return;
    let alive = true;
    r.loadDraft(id)
      .then((note) => {
        if (
          alive &&
          note &&
          (note.notes !== meeting.notes ||
            note.transcript !== meeting.transcript)
        )
          setDraft(note);
      })
      .catch((e) => setError(e.message));
    return () => {
      alive = false;
    };
  }, [meeting?.id]);
  async function keepLocal(next: { notes: string; transcript: string }) {
    try {
      await r.saveDraft(id, { ...next, baseRevision: version.current });
      if (!navigator.onLine) setStatus("本机已保存");
    } catch (e) {
      setError("本机记录保存失败");
    }
  }
  async function save() {
    if (pendingSave.current) {
      await pendingSave.current;
      if (dirty.current) await save();
      return;
    }
    if (!dirty.current || !meeting) return;
    saving.current = true;
    const revision = edits.current;
    setStatus("保存中");
    const operation = (async () => {
      try {
        const m = await patch<Meeting>("/meetings/" + id, {
          version: version.current,
          ...latest.current,
        });
        version.current = m.version;
        dirty.current = revision !== edits.current;
        if (!dirty.current)
          await r.clearDraft(id, { notes: m.notes, transcript: m.transcript });
        setStatus(dirty.current ? "待保存" : "已保存");
        setError("");
      } catch (e) {
        setStatus("保存失败");
        setError((e as Error).message);
        throw e;
      } finally {
        saving.current = false;
      }
    })();
    pendingSave.current = operation;
    try {
      await operation;
    } finally {
      pendingSave.current = null;
    }
    if (dirty.current) await save();
  }
  useEffect(() => {
    if (!dirty.current) return;
    const timer = setTimeout(() => save().catch(() => {}), 1200);
    return () => clearTimeout(timer);
  }, [notes, transcript]);
  useEffect(() => {
    const timer = setInterval(() => {
      if (dirty.current && !saving.current) save().catch(() => {});
    }, 5000);
    return () => {
      clearInterval(timer);
      if (dirty.current && !saving.current) save().catch(() => {});
    };
  }, [meeting?.id]);
  if (!meeting) return error ? <ErrorMessage message={error} /> : <Loading />;
  const isCurrent = r.meetingId === id;
  const linkedProjects = meeting.projects?.length
    ? meeting.projects
    : meeting.project_id
      ? [{ id: meeting.project_id, name: "关联项目" }]
      : [];
  const planProject = linkedProjects.some(
    (project) => project.id === generationProject,
  )
    ? generationProject
    : meeting.project_id || linkedProjects[0]?.id || "";
  async function finish() {
    setError("");
    try {
      await save();
      if (isCurrent && r.active) await r.stop();
      await post("/meetings/" + id + "/finish", {});
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="page-heading detail-heading">
        <h1>{meeting.title}</h1>
        <div className="inline-actions">
          <button className="text-button" onClick={() => setClassification(true)}>
            编辑
          </button>
          {!(isCurrent && r.active) && meeting.status !== "recording" && (
            <button className="icon-button danger" aria-label="删除录音" onClick={() => setRemoving(true)}>
              <Trash2 size={17} />
            </button>
          )}
        </div>
      </div>
      {removing && (
        <ConfirmSheet
          title="删除这条录音？"
          detail="录音、转写、纪要及由它生成的文档将一并删除"
          onClose={() => setRemoving(false)}
          onConfirm={async () => {
            await api("/meetings/" + id, { method: "DELETE" });
            navigate(sessionStorage.getItem("meeting-parent-" + id) || "home");
          }}
        />
      )}
      {meeting.occurred_at&&<p className="meta">{meeting.occurred_at.length===10?meeting.occurred_at:new Date(meeting.occurred_at).toLocaleString("zh-CN",{hour12:false})}</p>}
      {meeting.recordings?.map(f=><div className="imported-recording" key={f.file_id}><h2>{f.active === false ? "历史录音" : "会议录音"}</h2><audio controls preload="none" src={`/api/meetings/${id}/audio?recording_id=${f.file_id}`}/><a className="text-button" href={`/api/meetings/${id}/audio?recording_id=${f.file_id}`}><Download size={17}/>{f.name}</a>{f.active===false&&<details><summary>历史原文与纪要</summary><p className="preserve-text">{f.summary||"未生成纪要"}</p><p className="preserve-text">{f.transcript||"未生成转写"}</p></details>}</div>)}
      <div className="meeting-projects">
        {(meeting.projects?.length
          ? meeting.projects
          : meeting.project_id
            ? [{ id: meeting.project_id, name: "查看项目" }]
            : []
        ).map((project) => (
          <button
            className="text-button"
            key={project.id}
            onClick={() => navigate("projects/" + project.id)}
          >
            {project.name}
            <ArrowUpRight size={16} />
          </button>
        ))}
        {!meeting.project_id && !meeting.project_ids?.length && (
          <button
            className="text-button"
            onClick={() => setClassification(true)}
          >
            待归类 · 关联项目
          </button>
        )}
      </div>
      {meeting.analysis_status &&
        ["pending", "queued", "running", "processing", "analyzing"].includes(
          meeting.analysis_status,
        ) && (
          <p className="meta analysis-status" role="status">
            正在整理会议
          </p>
        )}
      {meeting.analysis_status === "failed" && (
        <div className="row-between analysis-status">
          <p className="meta" role="status">
            {analysisQueued ? "等待重新整理" : "会议整理失败"}
          </p>
          <button
            className="text-button"
            disabled={retrying || analysisQueued}
            onClick={async () => {
              setRetrying(true);
              setError("");
              try {
                const all =
                  await api<
                    { id: string; target_id: string; status: string }[]
                  >("/analysis-jobs");
                const failed = all.find(
                  (job) => job.target_id === id && job.status === "failed",
                );
                if (!failed)
                  throw new Error("未找到可重试的整理记录，请刷新会议后重试");
                await post("/analysis-jobs/" + failed.id + "/retry", {});
                setAnalysisQueued(true);
                refresh();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setRetrying(false);
              }
            }}
          >
            {retrying ? "正在提交…" : analysisQueued ? "已提交" : "重新整理"}
          </button>
        </div>
      )}
      {meeting.ai_summary && (
        <Markdown text={meeting.ai_summary}/>
      )}
      <section className="recording-card">
        <div className="recording-state">
          <span className={r.active && isCurrent ? "live-dot" : ""} />
          {r.active && isCurrent
            ? "录音中"
            : meeting.status === "finished"
              ? "已结束"
              : manifest.value?.epochs.length
                ? "已暂停"
                : "未录音"}
          <strong>{isCurrent ? duration(r.localFrames) : ""}</strong>
        </div>
        <div className="recording-controls">
          {meeting.status !== "finished" &&
            (!r.active ? (
              <button
                className="button"
                disabled={r.busy}
                onClick={() =>
                  r
                    .start(meeting)
                    .then(refresh)
                    .catch(() => {})
                }
              >
                <Mic size={19} />
                录音
              </button>
            ) : isCurrent ? (
              <button
                className="button secondary"
                disabled={r.busy}
                onClick={() => r.stop().catch((e) => setError(e.message))}
              >
                <Square size={16} />
                暂停
              </button>
            ) : null)}
          {meeting.status !== "finished" && (
            <button
              className="button secondary"
              disabled={r.busy}
              onClick={finish}
            >
              结束会议
            </button>
          )}
          {meeting.status === "finished" && hasAudio && (
            <a
              className="button secondary"
              href={"/api/meetings/" + id + "/audio"}
            >
              <Download size={18} />
              录音
            </a>
          )}
        </div>
        {isCurrent && (
          <div className="save-status">
            <span>本段本机 {duration(r.localFrames)}</span>
            <span>本段云端 {duration(r.cloudFrames)}</span>
          </div>
        )}
      </section>
      {!!interruptions && (
        <div className="error" role="status">
          录音有中断 · {interruptions} 段
        </div>
      )}
      <ErrorMessage
        message={actionError || error || (isCurrent ? r.error : "")}
      />
      {draft && (
        <div className="recovery">
          <div>
            <strong>有未同步记录</strong>
          </div>
          <button
            className="text-button"
            onClick={() => {
              dirty.current = true;
              edits.current++;
              setNotes(draft.notes);
              setTranscript(draft.transcript);
              setDraft(null);
            }}
          >
            恢复本机
          </button>
          <button
            className="text-button"
            onClick={() => {
              r.clearDraft(id).catch(() => {});
              setDraft(null);
            }}
          >
            使用云端
          </button>
        </div>
      )}
      <div className="section-heading">
        <h2>会议记录</h2>
        <span>{status}</span>
      </div>
      <textarea
        className="meeting-notes"
        aria-label="会议记录"
        value={notes}
        onChange={(e) => {
          dirty.current = true;
          edits.current++;
          setNotes(e.target.value);
          keepLocal({ notes: e.target.value, transcript });
          setStatus("待保存");
        }}
      />
      <div className="section-heading">
        <h2>校对转写</h2>
        <button className="text-button" onClick={() => save().catch(() => {})}>
          <Save size={16} />
          保存
        </button>
      </div>
      <textarea
        className="meeting-notes"
        aria-label="转写内容"
        value={transcript}
        onChange={(e) => {
          dirty.current = true;
          edits.current++;
          setTranscript(e.target.value);
          keepLocal({ notes, transcript: e.target.value });
          setStatus("待保存");
        }}
      />
      <div className="section-heading">
        <h2>实时转写</h2>
        <span>{isCurrent ? r.asrStatus : ""}</span>
      </div>
      <div className="live-transcript">
        {(raw.value ?? []).map((s) => (
          <p key={s.id}>{s.text}</p>
        ))}
        {isCurrent && r.partial && <p className="partial-text">{r.partial}</p>}
        {!raw.value?.length && !r.partial && <span>暂无转写</span>}
      </div>
      <div className="section-heading">
        <h2>文档</h2>
      </div>
      {linkedProjects.length > 1 && (
        <label className="generation-project">
          方案项目
          <select
            value={planProject}
            onChange={(e) => {
              setGenerationProject(e.target.value);
              setGenerated(false);
            }}
            disabled={generating || running}
          >
            {linkedProjects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="document-actions">
        <button
          className="button"
          disabled={generating || running || !planProject}
          onClick={async () => {
            setGenerating(true);
            setError("");
            try {
              await save();
              const generationKey = "generation:" + id + ":" + planProject;
              let requestId = sessionStorage.getItem(generationKey);
              const previous = jobs.value?.find(
                (job) => job.request_id === requestId,
              );
              if (
                !requestId ||
                previous?.status === "failed" ||
                previous?.status === "succeeded"
              ) {
                requestId = crypto.randomUUID();
                sessionStorage.setItem(generationKey, requestId);
              }
              await post("/meetings/" + id + "/generate", {
                request_id: requestId,
                project_id: planProject,
              });
              sessionStorage.removeItem(generationKey);
              setGenerated(true);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setGenerating(false);
              jobs.refresh();
            }
          }}
        >
          <FileText size={18} />
          {generating || running ? "生成中" : "生成方案与清单"}
        </button>
        {generated && planProject && (
          <button
            className="text-button"
            onClick={() => navigate("projects/" + planProject)}
          >
            查看方案与清单
            <ArrowUpRight size={17} />
          </button>
        )}
        {["md", "pdf"].map((format) => (
          <button
            key={format}
            className="button secondary"
            disabled={exporting}
            onClick={async () => {
              setExporting(true);
              setError("");
              try {
                await save();
                await download(
                  "/meetings/" + meeting.id + "/minutes." + format,
                  meeting.title + "." + format,
                );
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setExporting(false);
              }
            }}
          >
            <Download size={18} />
            {exporting ? "生成中" : "纪要 " + format.toUpperCase()}
          </button>
        ))}
      </div>
      {!planProject && (
        <button className="text-button" onClick={() => setClassification(true)}>
          关联项目后生成方案与清单
        </button>
      )}
      {jobs.value?.[0]?.status === "failed" && (
        <ErrorMessage message={jobs.value[0].error} />
      )}
      {planProject && <ProjectDocuments key={planProject} id={planProject} />}
      {classification && (
        <MeetingClassification
          meeting={meeting}
          beforeSave={save}
          onClose={() => setClassification(false)}
          onSaved={refresh}
        />
      )}
    </>
  );
}
