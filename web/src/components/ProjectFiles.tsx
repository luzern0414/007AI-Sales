import { useState } from "react";
import { Download, FileText, Search, Upload } from "lucide-react";
import { api } from "../api";
import type { FileItem } from "../types";
import { fullTime } from "./Workflow";
import { Empty, ErrorMessage } from "./UI";
import Sources from "./Sources";
import FilePreview,{FileGlyph,originLabels} from './FilePreview';

const parsing: Record<string, string> = {
  ready: "已识别",
  needs_ocr: "待识别扫描件",
  archived: "已归档",
  failed: "识别失败",
  pending: "识别中",
  pending_asr: "转写中",
};
export default function ProjectFiles({
  id,
  files,
  refresh,
}: {
  id: string;
  files: FileItem[];
  refresh: () => void;
}) {
  const [uploading, setUploading] = useState(false),
    [searching, setSearching] = useState(false),
    [error, setError] = useState(""),
    [query, setQuery] = useState("");
  const [results, setResults] = useState<
    { file_id: string; name: string; snippet: string }[] | null
  >(null);
  const [preview,setPreview]=useState('');
  async function upload(selected: FileList | null) {
    if (!selected) return;
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(selected)) {
        const form = new FormData();
        form.append("file", file);
        await api(`/projects/${id}/files`, { method: "POST", body: form });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      refresh();
      setResults(null);
    }
  }
  return (
    <>
      <div className="section-heading">
        <span>项目文件</span>
        <label
          className={"button secondary small " + (uploading ? "disabled" : "")}
        >
          <Upload size={17} />
          {uploading ? "上传中" : "上传文件"}
          <input
            className="sr-only"
            aria-label="上传项目文件"
            type="file"
            multiple
            accept=".pdf,.md,.txt,.docx,.xlsx,.pptx,.drawio,.html,.htm,.png,.jpg,.jpeg,.zip"
            disabled={uploading}
            onChange={(e) => {
              upload(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <form
        className="file-search"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!query.trim()) return;
          setSearching(true);
          setError("");
          try {
            setResults(
              await api(
                `/projects/${id}/search?q=${encodeURIComponent(query.trim())}`,
              ),
            );
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setSearching(false);
          }
        }}
      >
        <input
          aria-label="搜索文件内容"
          value={query}
          maxLength={200}
          placeholder="搜索文件内容"
          onChange={(e) => {
            setQuery(e.target.value);
            if (!e.target.value) setResults(null);
          }}
        />
        <button
          className="icon-button"
          aria-label="搜索"
          disabled={searching || !query.trim()}
        >
          <Search size={20} />
        </button>
      </form>
      <ErrorMessage message={error} />
      {results !== null ? (
        <>
          <div className="section-heading">
            <span>{results.length} 个结果</span>
            <button
              className="text-button"
              onClick={() => {
                setQuery("");
                setResults(null);
              }}
            >
              全部文件
            </button>
          </div>
          {results.map((r) => (
            <article className="search-result" key={r.file_id}>
              <button className="text-button" onClick={()=>setPreview(r.file_id)}>
                {r.name}
                <Download size={18} />
              </button>
              <p>{r.snippet}</p>
            </article>
          ))}
          {!results.length && <Empty title="未找到内容" />}
        </>
      ) : (
        <>
          <div className="file-list">
            {files.map((f) => (
              <article className="file-row" key={f.id}>
                <FileGlyph name={f.name} mime={f.mime}/>
                <button className="file-preview-link" onClick={()=>setPreview(f.id)}>
                  <h3>{f.name.replace(/^\[[^\]]+\]\s*/,'')}</h3>
                  <p>
                    <i className={`origin-dot ${f.origin||'unknown'}`}/>{originLabels[f.origin||'unknown']} · V{f.file_version}
                  </p>
                  <p>
                    {fullTime(f.source_modified_at || f.created_at)} ·{" "}
                    {f.size < 1024 * 1024
                      ? Math.ceil(f.size / 1024) + " KB"
                      : (f.size / 1024 / 1024).toFixed(1) + " MB"}
                  </p>
                </button>
                <a
                  className="icon-button"
                  aria-label={"下载" + f.name}
                  href={`/api/files/${f.id}/download`}
                >
                  <Download size={20} />
                </a>
              </article>
            ))}
          </div>
          {!files.length && <Empty title="暂无文件" />}
        </>
      )}
      <Sources projectId={id} onSaved={refresh} />
      {preview&&<FilePreview id={preview} onClose={()=>setPreview('')} onChanged={refresh}/>}
    </>
  );
}
