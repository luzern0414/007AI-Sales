import ProjectDocuments from "./ProjectDocuments";
import { fullTime } from "./Workflow";
import { useState } from "react";
import { useRecording, type Meeting } from "../recording/runtime";
import {
  Plus,
  Flag,
  AlertTriangle,
  Check,
  ArrowUpRight,
  FileText,
} from "lucide-react";
import { api, post, patch, navigate } from "../api";
import { day, time, type Detail, type Issue, type Milestone } from "../types";
import { Modal, Form, values, Empty, ErrorMessage } from "./UI";

const issueStates: Record<string, string> = {
  open: "待处理",
  working: "处理中",
  resolved: "待复核",
  closed: "已关闭",
};
const severity: Record<string, string> = {
  normal: "一般",
  high: "重要",
  blocking: "阻断",
};

export function ProjectDelivery({
  detail,
  tab,
  onSaved,
}: {
  detail: Detail;
  tab: string;
  onSaved: () => void;
}) {
  const [modal, setModal] = useState(""),
    [issue, setIssue] = useState<Issue | null>(null),
    [milestone, setMilestone] = useState<Milestone | null>(null);
  const id = detail.project.id;
  const recording = useRecording();
  const [uploading,setUploading]=useState(false);
  const [starting, setStarting] = useState(false),
    [recordingError, setRecordingError] = useState("");
  return (
    <>
      {tab === "issues" && (
        <>
          <div className="section-heading">
            <h2>已记录问题</h2><span>
              {detail.issues.filter((i) => i.status !== "closed").length}{" "}
              项未关闭
            </span>
            <button className="text-button" onClick={() => setModal("issue")}>
              <Plus size={17} />
              新增问题
            </button>
          </div>
          <div className="task-list">
            {detail.issues.map((i) => (
              <button
                className="task-row"
                key={i.id}
                onClick={() => {
                  setIssue(i);
                  setModal("issue-edit");
                }}
              >
                <AlertTriangle
                  size={20}
                  className={i.severity === "blocking" ? "overdue" : ""}
                />
                <div>
                  <h3>{i.title}</h3>
                  <p>
                    {severity[i.severity]} · {i.assignee || "待指派"} ·{" "}
                    {day(i.due_date)}
                  </p>
                </div>
                <span className="task-status">{issueStates[i.status]}</span>
              </button>
            ))}
          </div>
          {!detail.issues.length && <Empty title="暂无问题" />}
        </>
      )}
      {tab === "milestones" && (
        <>
          <div className="section-heading">
            <span>交付节点</span>
            <button
              className="text-button"
              onClick={() => setModal("milestone")}
            >
              <Plus size={17} />
              新增节点
            </button>
          </div>
          <div className="task-list">
            {detail.milestones.map((m) => (
              <button
                className="task-row"
                key={m.id}
                onClick={() => {
                  setMilestone(m);
                  setModal("milestone-edit");
                }}
              >
                {m.status === "completed" ? (
                  <Check size={20} />
                ) : (
                  <Flag size={20} />
                )}
                <div>
                  <h3>{m.title}</h3>
                  <p>{day(m.due_date)}</p>
                </div>
                <span className="task-status">
                  {m.status === "completed" ? "已完成" : "待完成"}
                </span>
              </button>
            ))}
          </div>
          {!detail.milestones.length && <Empty title="暂无交付节点" />}
        </>
      )}
      {tab === "meetings" && (
        <>
          <div className="section-heading">
            <h2>项目会议</h2>
            <button
              className="text-button"
              disabled={starting || recording.busy}
              onClick={async () => {
                if (recording.active)
                  return navigate("home/" + recording.meetingId);
                setStarting(true);
                setRecordingError("");
                let meeting: Meeting | null = null;
                try {
                  meeting = await post<Meeting>("/meetings/start", {});
                  await recording.start(meeting);
                  navigate("home/" + meeting.id);
                } catch (e) {
                  setRecordingError((e as Error).message);
                  if (meeting) navigate("home/" + meeting.id);
                } finally {
                  setStarting(false);
                }
              }}
            >
              {starting
                ? "正在开始录音…"
                : recording.active
                  ? "返回录音"
                  : "开始录音记录"}
            </button>
          </div>
          <label className="text-button recording-upload">{uploading?"导入中":"导入录音"}<input className="sr-only" type="file" accept=".m4a,.wav,.mp3,.ogg,.webm" disabled={uploading} onChange={async e=>{const file=e.target.files?.[0];e.target.value="";if(!file)return;setUploading(true);setRecordingError("");try{const body=new FormData();body.append("file",file);await api(`/projects/${id}/files`,{method:"POST",body});onSaved();}catch(err){setRecordingError((err as Error).message);}finally{setUploading(false);}}}/></label>
          <ErrorMessage message={recordingError} />
          <div className="file-list">
            {detail.meetings.map((m) => (
              <button
                className="file-row"
                aria-label={m.title}
                key={m.id}
                onClick={() => navigate("home/" + m.id)}
              >
                <span className="file-icon">
                  <FileText size={22} />
                </span>
                <div>
                  <h3>{m.title}</h3>
                  <p>
                    {fullTime(m.occurred_at)} ·{" "}
                    {m.status === "finished" ? "已结束" : "待保存"}
                  </p>
                </div>
                <ArrowUpRight size={18} />
              </button>
            ))}
          </div>
          {!detail.meetings.length && <Empty title="暂无会议" />}
          <ProjectDocuments id={id} />
        </>
      )}
      {modal === "issue" && (
        <Modal title="新增问题" onClose={() => setModal("")}>
          <Form
            onSubmit={async (f) => {
              const v = values(f);
              await post("/projects/" + id + "/issues", {
                ...v,
                due_date: v.due_date || null,
              });
              setModal("");
              onSaved();
            }}
          >
            <label>
              问题
              <input name="title" maxLength={240} required autoFocus />
            </label>
            <label>
              影响
              <select name="severity">
                {Object.entries(severity).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label>
              负责人
              <input name="assignee" maxLength={100} />
            </label>
            <label>
              截止日期
              <input name="due_date" type="date" />
            </label>
            <label>
              详情
              <textarea name="detail" maxLength={20000} />
            </label>
          </Form>
        </Modal>
      )}
      {modal === "issue-edit" && issue && (
        <Modal title={issue.title} onClose={() => setModal("")}>
          <Form
            onSubmit={async (f) => {
              await patch("/issues/" + issue.id, {
                ...values(f),
                version: issue.version,
              });
              setModal("");
              onSaved();
            }}
          >
            {issue.detail && <p className="detail-text">{issue.detail}</p>}
            <label>
              状态
              <select name="status" defaultValue={issue.status}>
                {Object.entries(issueStates).map(([k, v]) => (
                  <option value={k} key={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label>
              处理结果
              <textarea
                name="resolution"
                defaultValue={issue.resolution}
                maxLength={20000}
              />
            </label>
          </Form>
        </Modal>
      )}
      {modal === "milestone" && (
        <Modal title="新增交付节点" onClose={() => setModal("")}>
          <Form
            onSubmit={async (f) => {
              await post("/projects/" + id + "/milestones", values(f));
              setModal("");
              onSaved();
            }}
          >
            <label>
              节点名称
              <input name="title" maxLength={240} required autoFocus />
            </label>
            <label>
              计划日期
              <input name="due_date" type="date" required />
            </label>
          </Form>
        </Modal>
      )}
      {modal === "milestone-edit" && milestone && (
        <Modal title={milestone.title} onClose={() => setModal("")}>
          <Form
            onSubmit={async (f) => {
              await patch("/milestones/" + milestone.id, {
                ...values(f),
                version: milestone.version,
              });
              setModal("");
              onSaved();
            }}
          >
            <label>
              状态
              <select name="status" defaultValue={milestone.status}>
                <option value="pending">待完成</option>
                <option value="completed">已完成</option>
              </select>
            </label>
            <label>
              计划日期
              <input
                name="due_date"
                type="date"
                required
                defaultValue={milestone.due_date}
              />
            </label>
            <label>
              完成依据
              <textarea name="evidence" defaultValue={milestone.evidence} />
            </label>
            <label>
              日期变更依据
              <textarea name="reason" maxLength={2000} />
            </label>
          </Form>
        </Modal>
      )}
    </>
  );
}
