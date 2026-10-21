import { useState } from "react";
import { Plus, Search, SlidersHorizontal } from "lucide-react";
import { useResource } from "../api";
import type { Project } from "../types";
import {
  Empty,
  ErrorMessage,
  Loading,
  NewProject,
  ProjectCard,
} from "../components/UI";

export default function Projects() {
  const { value, loading, error, refresh } = useResource<Project[]>(
    "/projects",
    5000,
  );
  const [search, setSearch] = useState(""),
    [newProject, setNew] = useState(false),
    [filter, setFilter] = useState("active");
  const shown = (value ?? []).filter(
    (p) =>
      (filter === "all" || p.status === filter) &&
      (p.name + p.customer).toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>项目管理</h1>
        </div>
        <button className="button" onClick={() => setNew(true)}>
          <Plus size={19} />
          新建项目
        </button>
      </div>
      <div className="search-line">
        <label className="search">
          <Search size={19} />
          <input
            aria-label="搜索项目"
            placeholder="搜索项目、客户"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="filter">
          <SlidersHorizontal size={18} />
          <select
            aria-label="项目状态"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="active">进行中</option>
            <option value="all">全部</option>
            <option value="paused">已暂停</option>
            <option value="delivered">已交付</option>
            <option value="archived">已归档</option>
          </select>
        </label>
      </div>
      <ErrorMessage message={error} />
      {loading && !value ? (
        <Loading />
      ) : (
        <>
          <div className="section-heading">
            <span>{shown.length} 个项目</span>
          </div>
          <div className="project-grid">
            {shown.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
          {!shown.length && (
            <Empty
              title={search ? "未找到项目" : "暂无项目"}
              action="新建项目"
              onClick={() => setNew(true)}
            />
          )}
        </>
      )}
      {newProject && (
        <NewProject onClose={() => setNew(false)} onSaved={refresh} />
      )}
    </>
  );
}
