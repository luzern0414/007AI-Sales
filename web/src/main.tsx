import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import {
  Home as HomeIcon,
  FolderKanban,
  Package,
  LayoutGrid,
  Layers3,
} from "lucide-react";
import { api, navigate } from "./api";
import AccountExit from "./components/AccountExit";
import { Loading, ErrorMessage,BackButton } from "./components/UI";
import Auth from "./pages/Auth";
import Home from "./pages/Home";
import Projects from "./pages/Projects";
import ProjectDetail from "./pages/ProjectDetail";
import Products from "./pages/Products";
import Workspace from "./pages/Workspace";
import "./styles.css";
import "./compact.css";
import { RecordingProvider } from "./recording/runtime";
import RecordDock from "./components/RecordDock";
import "./refresh.css";
import "./app.css";

const navigation = [
  { path: "home", label: "首页", icon: HomeIcon },
  { path: "projects", label: "项目管理", icon: FolderKanban },
  { path: "products", label: "产品库", icon: Package },
  { path: "workspace", label: "工作台", icon: LayoutGrid },
];
function App() {
  const [route, setRoute] = useState(location.hash.slice(1) || "home"),
    [user, setUser] = useState<{ id: string; username: string } | null>(null),
    [status, setStatus] = useState<{
      initialized: boolean;
      setup_token_required: boolean;
    } | null>(null),
    [error, setError] = useState(""),
    [checking, setChecking] = useState(true);
  async function check() {
    setChecking(true);
    setError("");
    try {
      const s = await api("/auth/status");
      setStatus(s);
      setUser(s.user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChecking(false);
    }
  }
  useEffect(() => {
    check();
    const onHash = () => setRoute(location.hash.slice(1) || "home");
    window.addEventListener("hashchange", onHash);
    return () => {
      window.removeEventListener("hashchange", onHash);
    };
  }, []);
  if (checking) return <Loading />;
  if (error)
    return (
      <main className="auth-page">
        <div>
          <ErrorMessage message={error} />
          <button className="button" onClick={check}>
            重试
          </button>
        </div>
      </main>
    );
  if (!user)
    return (
      <Auth
        initialized={status?.initialized ?? true}
        needsToken={status?.setup_token_required ?? false}
        onLogin={check}
      />
    );
  const [section, id] = route.split("/");
  return (
    <RecordingProvider userId={user.id}>
      <div className="app-shell">
        <aside className="sidebar">
          <button className="brand" onClick={() => navigate("home")}>
            <span className="brand-mark">
              <Layers3 size={24} />
            </span>
            <span>行序</span>
          </button>
          <nav aria-label="主导航">
            {navigation.map((n) => (
              <button
                key={n.path}
                onClick={() => navigate(n.path)}
                className={section === n.path ? "nav-item active" : "nav-item"}
                aria-current={section === n.path ? "page" : undefined}
              >
                <n.icon size={21} />
                <span>{n.label}</span>
              </button>
            ))}
          </nav>
          <div className="account">
            <span className="avatar">
              {user.username.slice(0, 1).toUpperCase()}
            </span>
            <span>{user.username}</span>
          </div>
        </aside>
        <div className="main-shell">
          <header className={id ? "topbar nested" : "topbar"}>
            {id ? (
              <BackButton to={section==='projects'?'projects':section==='home'?(sessionStorage.getItem('meeting-parent-'+id)||'home'):section}/>
            ) : (
              <span className="mobile-brand"><span className="brand-dot"><Layers3 size={15}/></span>行序<small>{navigation.find((n) => n.path === section)?.label || "首页"}</small></span>
            )}
            <span className="desktop-breadcrumb">
              项目助手<span>/</span>
              {navigation.find((n) => n.path === section)?.label || "首页"}
            </span>
            <div className="topbar-user">
              <span className="avatar small">
                {user.username.slice(0, 1).toUpperCase()}
              </span>
              <AccountExit onExit={() => setUser(null)} />
            </div>
          </header>
          <main className={(section === "home" || !navigation.some((n) => n.path === section)) && !id ? "content with-dock" : "content"} key={route}>
            {section === "projects" ? (
              id ? (
                <ProjectDetail id={id} />
              ) : (
                <Projects />
              )
            ) : section === "products" ? (
              <Products />
            ) : section === "workspace" ? (
              <Workspace />
            ) : (
              <Home meetingId={id} />
            )}
          </main>
          <RecordDock home={(section === "home" || !navigation.some((n) => n.path === section)) && !id} />
        </div>
        <nav className="bottom-nav" aria-label="手机导航">
          {navigation.map((n) => (
            <button
              key={n.path}
              onClick={() => navigate(n.path)}
              className={section === n.path ? "active" : ""}
              aria-current={section === n.path ? "page" : undefined}
            >
              <n.icon size={22} />
              <span>{n.label}</span>
            </button>
          ))}
        </nav>
      </div>
    </RecordingProvider>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
