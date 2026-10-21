export interface Project {
  id: string;
  name: string;
  customer: string;
  stage: string;
  status: string;
  due_date: string | null;
  version: number;
  progress: number | null;
  updated_at: string;
  directory_path?: string | null;
  workflow?: Workflow;
  analysis?: Workflow['analysis'];
  counts?: MaterialCounts;
}
export interface MaterialCounts { files: number; client: number; ours: number; meetings: number; latest: string | null }
export interface AnalysisQueue { pending: number; running: number; failed: number; done: number; project: string | null }
export interface WorkflowNode {
  key: string; title: string; confirmed: boolean; occurred_at: string | null;
  evidence: string; version: number; weight?: number;
  ai?: { status: "done" | "doing" | "todo"; evidence: string } | null;
}
export interface FlowProgress {
  percent: number; confirmed_percent: number; basis: "ai" | "confirmed"; stage: string | null;
  stage_title: string; stage_progress: number | null; weights: Record<string, number>;
}
export interface AgentAction { id: string; title: string; why: string; priority: "high" | "medium" | "low"; node: string | null; state: "adopt" | "dismiss" | null }
export interface Insight {
  stage?: string | null; stage_progress?: number;
  nodes?: { key: string; status: "done" | "doing" | "todo"; evidence: string }[];
  actions?: AgentAction[]; questions?: string[]; points?: string[]; analyzed_at?: string;
  thinking?: { facts: string[]; changes: string; stage_reasoning: string; gaps: string[]; review: string[] };
}
export interface AskTurn { id: string; question: string; answer: string; thinking: string[]; basis: string[]; follow_ups: string[]; at: string }
export interface ProjectRisk {
  category: string; title: string; detail: string; source_id: string; source_name: string;
  source_kind: string; quote: string; status: string;
}
export interface Workflow {
  nodes: WorkflowNode[]; confirmed: number; total: number; current: string | null; due_date: string | null; progress?: FlowProgress;
  history?: {id:string;key:string;title:string;occurred_at:string|null;recorded_at:string;evidence:string}[];
  analysis: { status: string; summary: string; next_step: string; background: string; instructions: string;
    development?: {day:string;summary:string;changed:number;baseline:boolean}|null;
    risks: ProjectRisk[]; insight?: Insight; analyzed_at: string | null; input_hash?: string; queue?: AnalysisQueue; unread_sources?: {id:string;name:string;status:string}[] };
}
export interface ProjectDirectories {
  root: string;
  directories: {
    name: string;
    path: string;
    has_docs: boolean;
    bound_project_id: string | null;
  }[];
}
export interface ProjectOverview {
  summary: string;
  previous: string;
  current: string;
  next: string;
  analysis_status: string;
  failed_jobs: { id: string; error: string }[];
  directory: string | null;
  entries: {
    id: string;
    title: string;
    summary: string;
    occurred_at: string;
    source_type: string;
    source_id: string | null;
    source_name: string;
    source_status: "current" | "missing" | "superseded";
    time_basis: string;
  }[];
}
export interface Task {
  id: string;
  project_id: string;
  title: string;
  assignee: string;
  status: string;
  due_date: string | null;
  evidence: string;
  version: number;
  project_name?: string;
  overdue?: boolean;
  depends_on?: string[];
}
export interface ProjectEvent {
  id: string;
  title: string;
  detail: string;
  kind: string;
  occurred_at: string;
  recorded_at: string;
  source_id: string | null;
}
export interface FileItem {
  origin?: string;
  id: string;
  name: string;
  size: number;
  sha256: string;
  created_at: string;
  parse_status: string;
  file_version: number;
  previous_version_id: string | null;
  source_modified_at?: string | null;
  mime?: string;
}
export interface Issue {
  id: string;
  title: string;
  detail: string;
  severity: string;
  status: string;
  assignee: string;
  due_date: string | null;
  resolution: string;
  version: number;
}
export interface Milestone {
  id: string;
  title: string;
  due_date: string;
  status: string;
  evidence: string;
  version: number;
}
export interface Detail {
  project: Project;
  tasks: Task[];
  events: ProjectEvent[];
  files: FileItem[];
  issues: Issue[];
  milestones: Milestone[];
  meetings: { id: string; title: string; created_at: string; occurred_at?: string | null; status: string; recordings?: {file_id: string; name: string}[] }[];
}
export interface Product {
  id: string;
  name: string;
  summary: string;
  internal_notes?: string;
  demo_url: string;
  published?: boolean;
  version: number;
  files: FileItem[];
}
export interface Risk {
  id: string;
  kind: string;
  project_id: string;
  project_name: string;
  source_id: string;
  title: string;
  due_date: string | null;
}
export interface Dashboard {
  document_progress: DocumentProgress[];
  projects: Project[];
  tasks: Task[];
  overdue: number;
  blocked: number;
  updated_at: string;
  risks: Risk[];
}
export interface DocumentProgress {
  id: string;
  project_id: string;
  project_name: string;
  source_key: string;
  subdirectory: string;
  status: string;
  last_synced_at: string | null;
  checked: number;
  total: number;
  progress: number | null;
}
export const stages: Record<string, string> = {
  negotiation: "洽谈",
  requirements: "需求确认",
  proposal: "方案与商务",
  preparation: "实施准备",
  implementation: "实施",
  testing: "联调与试用",
  acceptance: "上线与验收",
  maintenance: "维护",
};
export const states: Record<string, string> = {
  active: "进行中",
  paused: "已暂停",
  delivered: "已交付",
  archived: "已归档",
  cancelled: "已取消",
  todo: "待办",
  doing: "进行中",
  blocked: "受阻",
  review: "待验收",
  done: "已完成",
  open: "待处理",
  working: "处理中",
  resolved: "待复核",
  closed: "已关闭",
  pending: "待完成",
  completed: "已完成",
};
export const kinds: Record<string, string> = {
  project: "项目",
  task: "任务",
  progress: "进展",
  issue: "问题",
  decision: "决定",
  change: "变更",
  note: "记录",
  file: "文件",
  meeting: "会议",
  milestone: "节点",
  document: "文档",
  source: "文档连接",
};
export function day(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat("zh-CN", {
        month: "short",
        day: "numeric",
      }).format(new Date(value.length === 10 ? value + "T12:00:00" : value))
    : "未设日期";
}
export function time(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function eventDetail(text: string) {
  return text.replace(
    /\b(open|working|resolved|closed) → (open|working|resolved|closed)\b/g,
    (_, before, after) => `${states[before]} → ${states[after]}`,
  );
}

/** Relative, compact Chinese date for dense rows: 今天 14:05 / 昨天 / 10月12日 / 2025年3月2日. */
export function shortTime(value: string | null | undefined, withTime = true) {
  if (!value) return "";
  const d = new Date(value.length === 10 ? value + "T12:00:00" : value);
  if (isNaN(d.getTime())) return value;
  const today = new Date(), dayMs = 86400000;
  const start = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((start(today) - start(d)) / dayMs);
  const hm = value.length === 10 || !withTime ? "" : " " + d.toTimeString().slice(0, 5);
  if (diff === 0) return "今天" + hm;
  if (diff === 1) return "昨天" + hm;
  if (d.getFullYear() === today.getFullYear()) return `${d.getMonth() + 1}月${d.getDate()}日` + hm;
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}
export function queueBusy(q?: AnalysisQueue | null) {
  return q ? q.pending + q.running : 0;
}
