import {useState} from 'react';
import {Download, FileText, FileSpreadsheet, FileType2, Mic, Image, Presentation} from 'lucide-react';
import {api,useResource} from '../api';
import {Modal,Loading,ErrorMessage} from './UI';
import Markdown from './Markdown';
export const originLabels:Record<string,string>={client:'客户',ours:'我方',unknown:'来源待确认'};
export function FileGlyph({name,mime='',size=18}:{name:string;mime?:string;size?:number}){
  const ext=name.split('.').pop()?.toLowerCase();
  const Icon=mime.startsWith('audio/')||['m4a','wav','mp3','ogg','webm'].includes(ext||'')?Mic:ext==='xlsx'||ext==='csv'?FileSpreadsheet:ext==='docx'||ext==='doc'?FileType2:ext==='pptx'?Presentation:mime.startsWith('image/')?Image:FileText;
  return <span className={`file-glyph type-${ext}`}><Icon size={size}/></span>;
}
export default function FilePreview({id,onClose,onChanged}:{id:string;onClose:()=>void;onChanged?:()=>void}){
  const {value:f,error,refresh}=useResource<{id:string;name:string;mime:string;markdown:string;origin:string;status:string}>('/files/'+id+'/preview');
  const [failure,setFailure]=useState(''),[busy,setBusy]=useState(false);
  return <Modal title={f?.name.replace(/^\[[^\]]+\]\s*/,'')||'文件'} onClose={onClose}>
    <ErrorMessage message={error||failure}/>{!f&&!error?<Loading/>:f&&<>
      <div className="preview-toolbar"><FileGlyph name={f.name} mime={f.mime}/><select aria-label="资料提供方" className={`origin-select ${f.origin}`} disabled={busy} value={f.origin} onChange={async e=>{setBusy(true);setFailure('');try{await api('/files/'+id+'/origin',{method:'PATCH',body:JSON.stringify({origin:e.target.value})});refresh();onChanged?.();}catch(err){setFailure((err as Error).message);}finally{setBusy(false);}}}>{Object.entries(originLabels).map(([k,v])=><option value={k} key={k}>{v}</option>)}</select><a className="text-button" href={'/api/files/'+id+'/download'}><Download size={17}/>原件</a></div>
      {f.mime.startsWith('audio/')?<audio controls src={'/api/files/'+id+'/download'}/>:f.markdown?<Markdown text={f.markdown}/>:<p className="meta">{f.status==='failed'?'文件解析失败，可下载原件':'暂无可预览正文'}</p>}
    </>}
  </Modal>;
}
