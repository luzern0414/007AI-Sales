import { patch, useResource } from "../api";
import type { Project } from "../types";
import type { Meeting } from "../recording/runtime";
import { ErrorMessage, Form, Loading, Modal } from "./UI";

export default function MeetingClassification({
  meeting,
  onClose,
  onSaved,
  beforeSave,
}: {
  meeting: Meeting;
  onClose: () => void;
  onSaved: () => void;
  beforeSave: () => Promise<void>;
}) {
  const projects = useResource<Project[]>("/projects");
  const selected =
    meeting.project_ids ?? (meeting.project_id ? [meeting.project_id] : []);
  return (
    <Modal title="会议名称与项目" onClose={onClose}>
      <ErrorMessage message={projects.error} />
      <Form
        onSubmit={async (form) => {
          const data = new FormData(form);
          if (!projects.value || projects.error)
            throw new Error("请先加载项目列表，再保存关联");
          await beforeSave();
          await patch("/meetings/" + meeting.id + "/classification", {
            title: String(data.get("title") || "").trim(),
            project_ids: data.getAll("project_ids"),
            ...(meeting.recordings?.length ? {occurred_at: data.get("occurred_at") ? new Date(String(data.get("occurred_at"))).toISOString() : null} : {}),
          });
          onSaved();
          onClose();
        }}
      >
        <label>
          会议名称
          <input
            name="title"
            defaultValue={meeting.title}
            required
            maxLength={240}
            autoFocus
          />
        </label>
        {!!meeting.recordings?.length && <label>实际会议时间<input name="occurred_at" type="datetime-local" defaultValue={meeting.occurred_at ? new Date(new Date(meeting.occurred_at).getTime()-new Date(meeting.occurred_at).getTimezoneOffset()*60000).toISOString().slice(0,16) : ""}/></label>}
        <div className="form-section-label">关联项目（可多选）</div>
        {projects.loading && !projects.value && <Loading />}
        {projects.value?.map((project) => (
          <label className="checkbox-label" key={project.id}>
            <input
              type="checkbox"
              name="project_ids"
              value={project.id}
              defaultChecked={selected.includes(project.id)}
            />
            {project.name}
          </label>
        ))}
        {!projects.loading && !projects.error && !projects.value?.length && (
          <p className="meta">暂无项目，可稍后关联。</p>
        )}
        {projects.error && (
          <button
            className="text-button"
            type="button"
            onClick={projects.refresh}
          >
            重试加载项目
          </button>
        )}
      </Form>
    </Modal>
  );
}
