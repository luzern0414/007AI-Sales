import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type FormEvent,
} from "react";
import {
  X,
  FolderOpen,
  Plus,
  LoaderCircle,
  AlertCircle,
  ArrowLeft,
} from "lucide-react";
import { navigate, post, useResource } from "../api";
import {
  stages,
  day,
  shortTime,
  queueBusy,
  type Project,
  type ProjectDirectories,
} from "../types";

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog ref={ref} onCancel={onClose} className="modal">
      <div className="modal-head">
        <h2>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="关闭">
          <X size={21} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
/** Bottom action sheet for destructive confirmation, mini-program style. */
export function ConfirmSheet({ title, detail, action = "删除", onConfirm, onClose }: { title: string; detail?: string; action?: string; onConfirm: () => Promise<void>; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  useEffect(() => { const d = ref.current; d?.showModal(); return () => d?.close(); }, []);
  return (
    <dialog ref={ref} className="sheet" onCancel={onClose} onClick={(e) => e.target === ref.current && !busy && onClose()}>
      <div className="sheet-body">
        <strong>{title}</strong>
        {detail && <p>{detail}</p>}
        <ErrorMessage message={error} />
        <button className="sheet-danger" disabled={busy} onClick={async () => { setBusy(true); setError(""); try { await onConfirm(); onClose(); } catch (e) { setError((e as Error).message); setBusy(false); } }}>
          {busy ? <LoaderCircle className="spin" size={17} /> : action}
        </button>
      </div>
      <button className="sheet-cancel" disabled={busy} onClick={onClose}>取消</button>
    </dialog>
  );
}
export function ErrorMessage({ message }: { message: string }) {
  const display =
    /permission denied|permission dismissed|notallowederror/i.test(message)
      ? "请允许使用麦克风，然后重试录音"
      : /requested device not found|notfounderror/i.test(message)
        ? "未找到麦克风，请连接后重试"
        : /could not start audio|notreadableerror/i.test(message)
          ? "麦克风无法使用，请检查设备后重试"
          : message;
  return message ? (
    <div role="alert" className="error">
      <AlertCircle size={18} />
      {display}
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={22} />
      <span>加载中</span>
    </div>
  );
}
export function Empty({
  title,
  action,
  onClick,
}: {
  title: string;
  action?: string;
  onClick?: () => void;
}) {
  return (
    <div className="empty">
      <FolderOpen size={32} strokeWidth={1.4} />
      <p>{title}</p>
      {action && (
        <button className="button secondary" onClick={onClick}>
          <Plus size={17} />
          {action}
        </button>
      )}
    </div>
  );
}
export function Progress({ value }: { value: number | null }) {
  return (
    <div className="progress-wrap">
      <div className="progress-track">
        <span style={{ width: (value ?? 0) + "%" }} />
      </div>
      <span>{value === null ? "未设计划" : value + "%"}</span>
    </div>
  );
}
export function Ring({ value, confirmed = 0, size = 44, onClick, label, light }: { value: number; confirmed?: number; size?: number; onClick?: () => void; label?: string; light?: boolean }) {
  const style = { "--flow": `${value}%`, "--base": `${Math.min(value, confirmed)}%`, width: size, height: size, flexBasis: size } as React.CSSProperties;
  const body = <span>{value}<small>%</small></span>;
  const cls = "ring" + (light ? " light" : "");
  return onClick ? (
    <button className={cls} style={style} onClick={onClick} aria-label={label}>{body}</button>
  ) : (
    <span className={cls} style={style} aria-label={label}>{body}</span>
  );
}
export function ProjectCard({ project }: { project: Project }) {
  const flow = project.workflow, c = project.counts, q = project.analysis?.queue, insight = project.analysis?.insight;
  const pr = flow?.progress;
  const stage = pr?.stage_title || stages[project.stage];
  const busy = queueBusy(q);
  const todo = (insight?.actions || []).filter((a) => !a.state).length;
  return (
    <button className="project-row" onClick={() => navigate("projects/" + project.id)}>
      <Ring value={pr?.percent || 0} confirmed={pr?.confirmed_percent || 0} label={`整体进度${pr?.percent || 0}%`} />
      <div className="project-info">
        <div className="row-between">
          <h3>{project.name}</h3>
          <span className={"node-chip" + (pr?.basis === "ai" ? " ai" : "")}>{stage}{pr?.stage_progress != null ? ` ${pr.stage_progress}%` : ""}</span>
        </div>
        <p className="project-snippet">{insight?.actions?.find((a) => !a.state)?.title || project.analysis?.next_step || project.analysis?.summary || project.customer || "—"}</p>
        <p className="project-meta">
          {todo > 0 && <span className="accent">建议 {todo}</span>}
          {c && <span>资料 {c.files}</span>}
          {c && c.meetings > 0 && <span>会议 {c.meetings}</span>}
          {busy > 0 && <span className="accent">整理 {busy}</span>}
          {flow?.due_date && <span>{day(flow.due_date)}交付</span>}
          {c?.latest && <span className="push">{shortTime(c.latest, false)}</span>}
        </p>
      </div>
    </button>
  );
}
export function BackButton({to='home'}:{to?:string}){
  return <button className="back-link" aria-label="返回上一级" onClick={()=>navigate(to)}><ArrowLeft size={17}/><span>返回</span></button>;
}
export function Form({
  onSubmit,
  children,
  label = "保存",
}: {
  onSubmit: (form: HTMLFormElement) => Promise<void>;
  children: ReactNode;
  label?: string;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    setError("");
    try {
      await onSubmit(form);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="form">
      <fieldset disabled={busy}>
        {children}
        <ErrorMessage message={error} />
        <button className="button full" type="submit">
          {busy ? (
            <>
              <LoaderCircle className="spin" size={18} />
              保存中
            </>
          ) : (
            label
          )}
        </button>
      </fieldset>
    </form>
  );
}
export function values(form: HTMLFormElement) {
  return Object.fromEntries(new FormData(form)) as Record<string, string>;
}
export function NewProject({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const directories = useResource<ProjectDirectories>("/project-directories");
  const [directoryMode, setDirectoryMode] = useState("new");
  return (
    <Modal title="新建项目" onClose={onClose}>
      <Form
        onSubmit={async (f) => {
          const v = values(f);
          if (!v.name.trim() && !v.directory_name?.trim())
            throw new Error("请填写项目名称或选择项目目录");
          if (v.directory_name && /[\\/:*?"<>|]/.test(v.directory_name))
            throw new Error("目录名称不能包含斜杠或特殊符号");
          await post("/projects", {
            ...v,
            name: v.name.trim() || null,
            directory_name: v.directory_name?.trim() || "",
            create_directory: directoryMode === "new",
          });
          onSaved();
          onClose();
        }}
      >
        <label>
          项目名称
          <input
            name="name"
            maxLength={160}
            autoFocus
            placeholder="可选，默认使用目录名称"
          />
        </label>
        <label>
          项目目录
          <select
            value={directoryMode}
            onChange={(e) => setDirectoryMode(e.target.value)}
          >
            <option value="new">新建目录</option>
            <option value="existing">选择已有目录</option>
            <option value="none">暂不设置</option>
          </select>
        </label>
        {directoryMode === "new" && (
          <label>
            目录名称
            <input name="directory_name" required maxLength={160} />
          </label>
        )}
        {directoryMode === "existing" && (
          <label>
            已有目录
            <select name="directory_name" required defaultValue="">
              <option value="" disabled>
                选择目录
              </option>
              {directories.value?.directories
                .filter((d) => !d.bound_project_id)
                .map((d) => (
                  <option key={d.path} value={d.name}>
                    {d.name}
                  </option>
                ))}
            </select>
          </label>
        )}
        {directoryMode === "existing" && directories.loading && <Loading />}
        {directoryMode === "existing" && (
          <ErrorMessage message={directories.error} />
        )}
        {directoryMode === "existing" && directories.error && (
          <button
            className="text-button"
            type="button"
            onClick={directories.refresh}
          >
            重试加载目录
          </button>
        )}
        {directoryMode === "existing" &&
          !directories.loading &&
          !directories.error &&
          !directories.value?.directories.some((d) => !d.bound_project_id) && (
            <p className="meta">暂无可选目录，可新建目录。</p>
          )}
        <label>
          客户名称
          <input name="customer" maxLength={160} />
        </label>
      </Form>
    </Modal>
  );
}
