import { useState } from "react";
import { api, post } from "../api";
import type { Task } from "../types";
import { ErrorMessage } from "./UI";

export default function TaskDependencies({
  task,
  tasks,
  onSaved,
}: {
  task: Task;
  tasks: Task[];
  onSaved: () => void;
}) {
  const [parent, setParent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const parents = tasks.filter((t) => task.depends_on?.includes(t.id));
  async function change(remove?: string) {
    setBusy(true);
    setError("");
    try {
      if (remove)
        await api(`/tasks/${task.id}/dependencies/${remove}`, {
          method: "DELETE",
        });
      else
        await post(`/tasks/${task.id}/dependencies`, { depends_on_id: parent });
      setParent("");
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="dependency-section">
      <h3>前置任务</h3>
      <ErrorMessage message={error} />
      {parents.map((t) => (
        <div className="dependency-row" key={t.id}>
          <span>{t.title}</span>
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => change(t.id)}
            aria-label={"移除前置任务：" + t.title}
          >
            移除
          </button>
        </div>
      ))}
      <label>
        关联任务
        <select
          value={parent}
          onChange={(e) => setParent(e.target.value)}
          disabled={busy}
        >
          <option value="">选择任务</option>
          {tasks
            .filter((t) => t.id !== task.id && !task.depends_on?.includes(t.id))
            .map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
        </select>
      </label>
      <button
        type="button"
        className="button secondary"
        disabled={busy || !parent}
        onClick={() => change()}
      >
        关联
      </button>
    </section>
  );
}
