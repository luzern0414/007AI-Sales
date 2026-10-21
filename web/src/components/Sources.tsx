import { useState } from "react";
import { Link2, RefreshCw, Plus, Unplug } from "lucide-react";
import { useResource, post, api } from "../api";
import { Form, Modal, values, ErrorMessage, Empty } from "./UI";
import { time } from "../types";

interface Source {
  id: string;
  source_key: string;
  subdirectory: string;
  status: string;
  last_synced_at: string | null;
  last_error: string;
  summary: string;
  enabled: boolean;
}
const labels: Record<string, string> = {
  pending: "待同步",
  synced: "已同步",
  failed: "同步失败",
  stale: "来源有变更",
  disabled: "已断开",
};
export default function Sources({
  projectId,
  onSaved,
}: {
  projectId: string;
  onSaved: () => void;
}) {
  const links = useResource<Source[]>(
    "/projects/" + projectId + "/sources",
    10000,
  );
  const roots = useResource<{ key: string }[]>("/document-sources");
  const [modal, setModal] = useState(false),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  async function sync(link: Source) {
    setBusy(link.id);
    setError("");
    try {
      await post("/sources/" + link.id + "/sync", {});
      links.refresh();
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <div className="section-heading">
        <h2>文档连接</h2>
        <button className="text-button" onClick={() => setModal(true)}>
          <Plus size={17} />
          连接
        </button>
      </div>
      <ErrorMessage message={error || links.error} />
      {links.value?.map((link) => (
        <article className="source-row" key={link.id}>
          <Link2 size={20} />
          <div>
            <h3>
              {link.source_key}
              {link.subdirectory ? " / " + link.subdirectory : ""}
            </h3>
            <p>
              {labels[link.status] || link.status}
              {link.last_synced_at ? " · " + time(link.last_synced_at) : ""}
            </p>
            {link.last_error && <p className="overdue">{link.last_error}</p>}
          </div>
          {link.enabled && (
            <>
              <button
                className="icon-button"
                aria-label={"同步" + link.source_key}
                disabled={!!busy}
                onClick={() => sync(link)}
              >
                <RefreshCw
                  size={18}
                  className={busy === link.id ? "spin" : ""}
                />
              </button>
              <button
                className="icon-button"
                aria-label={"断开" + link.source_key}
                disabled={!!busy}
                onClick={async () => {
                  setError("");
                  try {
                    await api("/sources/" + link.id, { method: "DELETE" });
                    links.refresh();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                <Unplug size={17} />
              </button>
            </>
          )}
          {!link.enabled && (
            <button
              className="text-button"
              disabled={!!busy}
              onClick={async () => {
                setBusy(link.id);
                setError("");
                try {
                  await post("/sources/" + link.id + "/reconnect", {});
                  links.refresh();
                  onSaved();
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy("");
                }
              }}
            >
              重新连接
            </button>
          )}
        </article>
      ))}
      {modal && (
        <Modal title="连接文档" onClose={() => setModal(false)}>
          {roots.value?.length ? (
            <Form
              label="连接"
              onSubmit={async (f) => {
                await post("/projects/" + projectId + "/sources", values(f));
                links.refresh();
                setModal(false);
              }}
            >
              <label>
                文档来源
                <select name="source_key" required>
                  {roots.value.map((r) => (
                    <option key={r.key} value={r.key}>
                      {r.key}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                子目录
                <input name="subdirectory" maxLength={240} />
              </label>
            </Form>
          ) : (
            <Empty title="尚未配置文档来源" />
          )}
        </Modal>
      )}
    </>
  );
}
