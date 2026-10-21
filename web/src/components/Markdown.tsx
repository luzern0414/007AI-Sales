import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
export default function Markdown({text}:{text:string}){
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{a:({children,href})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,img:({alt})=><span>{alt}</span>}}>{text}</ReactMarkdown></div>;
}
