import { ArrowUpRight, Link2 } from "lucide-react";
import { navigate } from "../api";
import { time, type DocumentProgress as Summary } from "../types";
import { Progress } from "./UI";

const labels: Record<string, string> = {
  pending: "待同步",
  synced: "已同步",
  stale: "需复查",
  failed: "同步失败",
};
export default function DocumentProgress({ rows }: { rows: Summary[] }) {
  if (!rows.length) return null;
  return (
    <>
      <div className="section-heading">
        <h2>文档进度</h2>
      </div>
      <div className="progress-list">
        {rows.map((row) => (
          <button
            key={row.id}
            onClick={() => navigate(`projects/${row.project_id}/files`)}
          >
            <div className="row-between">
              <h3>{row.project_name}</h3>
              <ArrowUpRight size={18} />
            </div>
            <p className="meta document-progress-source">
              <Link2 size={16} />
              {row.source_key}
              {row.subdirectory ? " / " + row.subdirectory : ""}
            </p>
            {row.total > 0 ? (
              <>
                <Progress value={row.progress} />
                <p className="meta">
                  已勾选 {row.checked}/{row.total}
                </p>
              </>
            ) : (
              <p className="meta">暂无勾选项</p>
            )}
            <p className="meta">
              {labels[row.status] || "待检查"}
              {row.last_synced_at ? " · " + time(row.last_synced_at) : ""}
            </p>
          </button>
        ))}
      </div>
    </>
  );
}
