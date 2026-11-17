import type {ReactNode,ButtonHTMLAttributes,CSSProperties} from 'react';
import {Link} from 'react-router-dom';
import {EmptyStateIcon} from './icons';

export function Panel({children,className='',style,id}:{children:ReactNode;className?:string;style?:CSSProperties;id?:string}){
  return <section id={id} style={style} className={'card '+className}>{children}</section>;
}
export function PageHeader({title,description,actions}:{title:string;description:string;actions?:ReactNode}){
  return <header className="pageheading"><div><div className="eyebrow">TextileHR AI · Workforce intelligence</div>
    <h1>{title}</h1><p>{description}</p></div>{actions}</header>;
}
export function Button({children,kind='default',size='regular',...rest}:
  ButtonHTMLAttributes<HTMLButtonElement>&{kind?:'default'|'primary'|'subtle'|'danger'|'ghost';size?:'regular'|'small'}){
  return <button type="button" {...rest} className={'btn '+(kind==='default'?'':kind)+' '+(size==='small'?'small':'')+' '+(rest.className??'')}>{children}</button>;
}
export function ActionLink({children,to,kind='default',size='regular',className=''}:{children:ReactNode;to:string;kind?:'default'|'primary'|'subtle';size?:'regular'|'small';className?:string}){
  return <Link className={'btn '+(kind==='default'?'':kind)+' '+(size==='small'?'small':'')+' '+className} to={to}>{children}</Link>;
}
export function Status({value}:{value:string|null|undefined}){
  const raw=value??'Not ready';
  const css=raw.toLowerCase().replace(/[^a-z]+/g,'-');
  return <span className={'badge '+css}>{raw.replaceAll('_',' ')}</span>;
}
export function FormField({id,label,children,note}:{id:string;label:string;children:ReactNode;note?:string}){
  return <div className="field"><label htmlFor={id}>{label}</label>{children}{note?<div className="help">{note}</div>:null}</div>;
}
export function Blank({title,description,action}:{title:string;description:string;action?:ReactNode}){
  return <div className="empty"><EmptyStateIcon size={32} style={{margin:'0 auto 10px',display:'block',opacity:0.6}} />
    <strong>{title}</strong><p>{description}</p>{action}</div>;
}
export function Message({kind='info',children,style,className=''}:{kind?:'info'|'error'|'success'|'warn';children:ReactNode;style?:CSSProperties;className?:string}){
  return <div style={style} className={'alert '+(kind==='info'?'':kind)+' '+className} role={kind==='error'?'alert':'status'}>{children}</div>;
}
export function Loading(){return <p className="muted" role="status">Loading saved local records…</p>}
export function ErrorState({error,retry}:{error:Error|string;retry?:()=>void}){
  return <Message kind="error">{typeof error==='string'?error:error.message} {retry?<Button onClick={retry} size="small">Retry</Button>:null}</Message>
}
export function confirmDestructive(noun:string):boolean{
  return window.confirm(`Delete ${noun}? This action cannot be undone and referenced records will be protected.`);
}
export function dateString(timestamp:string):string{
  const result=new Date(timestamp);
  return Number.isNaN(result.getTime())?timestamp:result.toLocaleString();
}
