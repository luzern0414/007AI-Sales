import { useState } from "react";
import { Pencil, MessageSquarePlus } from "lucide-react";
import { useResource, patch } from "../api";
import type { Detail, Workflow, WorkflowNode } from "../types";
import { ErrorMessage, Loading, Modal, Form, values } from "../components/UI";
import ProjectFiles from "../components/ProjectFiles";
import ProjectOverview from "../components/ProjectOverview";
import { WorkflowHero, NodeDialog, AnalysisDialog } from "../components/Workflow";
import { AgentBrief, AskPanel } from "../components/Agent";

export default function ProjectDetail({id}:{id:string}) {
  const {value:d,error,loading,refresh}=useResource<Detail>("/projects/"+id,5000);
  const workflow=useResource<Workflow>(`/projects/${id}/workflow`,5000);
  const [tab,setTab]=useState(()=>["files","ask"].includes(location.hash.split("/")[2])?location.hash.split("/")[2]:"overview");
  const [seed,setSeed]=useState("");
  const [modal,setModal]=useState("");
  const [selected,setSelected]=useState<WorkflowNode|null>(null);
  function saved(){refresh();workflow.refresh();}
  if(loading&&!d)return <Loading/>;
  if(!d)return <ErrorMessage message={error}/>;
  const p=d.project, flow=workflow.value;
  return <>
    <div className="page-heading detail-heading"><div className="project-title"><h1 title={p.name}>{p.name}</h1>{p.customer&&<span className="customer-name">{p.customer}</span>}</div><div className="inline-actions"><button className="icon-button" aria-label="修改项目" onClick={()=>setModal("project")}><Pencil size={17}/></button><button className="icon-button" aria-label="补充项目信息" onClick={()=>setModal("analysis")}><MessageSquarePlus size={18}/></button></div></div>
    <ErrorMessage message={error||workflow.error}/>
    {workflow.error&&<button className="text-button" onClick={workflow.refresh}>重试</button>}
    {flow&&<WorkflowHero flow={flow} detail={d} onNode={setSelected} onTab={setTab}/>}
    <nav className="tabs segmented" aria-label="项目视图">{[["overview","概览",0],["ask","问 AI",0],["files","文件",d.files.length]].map(([key,label,count])=><button key={key as string} className={tab===key?"active":""} onClick={()=>setTab(key as string)}>{label}{!!count&&<small>{count}</small>}</button>)}</nav>
    {tab==="overview"&&<>
      {flow&&<AgentBrief id={id} flow={flow} onSaved={saved} onAsk={(q)=>{setSeed(q);setTab("ask");}}/>}
      <ProjectOverview id={id} onNode={setSelected} onSaved={saved}/>
    </>}
    {tab==="ask"&&flow&&<AskPanel id={id} flow={flow} seed={seed} onSeedUsed={()=>setSeed("")}/>}
    {tab==="files"&&<ProjectFiles id={id} files={d.files} refresh={saved}/>}
    {selected&&flow&&<NodeDialog id={id} node={selected} flow={flow} onClose={()=>setSelected(null)} onSaved={saved}/>}
    {modal==="analysis"&&flow&&<AnalysisDialog id={id} flow={flow} onClose={()=>setModal("")} onSaved={saved}/>}
    {modal==="project"&&<Modal title="编辑项目" onClose={()=>setModal("")}><Form onSubmit={async f=>{await patch("/projects/"+id,{...values(f),version:p.version});setModal("");saved();}}>
      <label>项目名称<input name="name" defaultValue={p.name} required maxLength={160}/></label>
      <label>客户名称<input name="customer" defaultValue={p.customer} maxLength={160}/></label>
    </Form></Modal>}
  </>;
}
