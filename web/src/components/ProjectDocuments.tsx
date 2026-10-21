import { useState } from "react";
import Markdown from './Markdown';
import { FileText } from "lucide-react";
import { download, useResource, post } from "../api";
import { time } from "../types";
import { Empty, ErrorMessage, Modal, Form, values } from "./UI";

interface Draft {
  id: string;
  title: string;
  kind: string;
  markdown: string;
  source_revision: number;
  created_at: string;
  document_version: number;
  revision_reason: string;
}
export default function ProjectDocuments({ id }: { id: string }) {
  const { value, error, refresh } = useResource<Draft[]>(
    `/projects/${id}/documents`,
    5000,
  );
  const [selected, setSelected] = useState<Draft | null>(null),
    [failure, setFailure] = useState(""),
    [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  async function exportDraft(format: string) {
    if (!selected) return;
    setBusy(true);
    setFailure("");
    try {
      await download(
        `/documents/${selected.id}/download?format=${format}`,
        selected.title + "-V" + selected.document_version + "." + format,
      );
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="section-heading">
        <h2>方案与清单</h2>
      </div>
      <ErrorMessage message={error} />
      {value?.length ? (
        <div className="file-list">
          {value.map((d) => (
            <button
              key={d.id}
              className="file-row document-row"
              onClick={() => {
                setSelected(d);
                setFailure("");
                setEditing(false);
              }}
            >
              <FileText size={20} />
              <div>
                <h3>{d.title}</h3>
                <p>
                  V{d.document_version} · 讨论稿 · {time(d.created_at)}
                </p>
              </div>
              <span>查看</span>
            </button>
          ))}
        </div>
      ) : (
        <Empty title="暂无方案与清单" />
      )}
      {selected && (
        <Modal title={selected.title} onClose={() => setSelected(null)}>
          <div className="document-actions">
            <button
              className="button secondary"
              onClick={() => setEditing(!editing)}
            >
              {editing ? "取消修订" : "修订"}
            </button>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => exportDraft("md")}
            >
              Markdown
            </button>
            {["proposal", "minutes"].includes(selected.kind) && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => exportDraft("docx")}
              >
                Word
              </button>
            )}
            {["requirements", "client_checklist"].includes(selected.kind) && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => exportDraft("xlsx")}
              >
                Excel
              </button>
            )}
          </div>
          <ErrorMessage message={failure} />
          {editing ? (
            <Form
              label="保存为新版"
              onSubmit={async (f) => {
                const result = await post<Draft>(
                  `/documents/${selected.id}/revisions`,
                  values(f),
                );
                setSelected(result);
                setEditing(false);
                refresh();
              }}
            >
              <label>
                标题
                <input
                  name="title"
                  required
                  maxLength={240}
                  defaultValue={selected.title}
                />
              </label>
              <label>
                正文
                <textarea
                  className="document-editor"
                  name="markdown"
                  required
                  maxLength={200000}
                  defaultValue={selected.markdown}
                />
              </label>
              <label>
                修订依据
                <textarea name="reason" required maxLength={2000} />
              </label>
            </Form>
          ) : (
            <>
              <Markdown text={selected.markdown}/>
              {selected.revision_reason && (
                <p className="meta">修订依据：{selected.revision_reason}</p>
              )}
            </>
          )}
        </Modal>
      )}
    </>
  );
}
