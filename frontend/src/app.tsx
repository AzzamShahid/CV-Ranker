import {useCallback,useEffect,useRef,useState,createContext,useContext} from 'react';
import type {ReactNode} from 'react';
import {BrowserRouter,Routes,Route,Outlet,Link,useNavigate,useParams,useLocation,useOutletContext} from 'react-router-dom';
import {client,initializeSession} from './api/client';
import type {Document,ExportRecord,HistoricalRecord,JDApproval,JDDraft,Job,Settings,Weights,Workspace} from './api/client';
import {ROUTES,NAV_ITEMS,parseWorkspaceRoute,workspacePath} from './router';
import {ActionLink,Blank,Button,ErrorState,Loading,Panel,PageHeader,Status,FormField,Message} from './components/ui';
import {DocumentsPage,JDPage,WeightsPage,AssessmentPage} from './pages/Workflow';
import {ProgressPage,RankingsPage,CandidatePage,ReportsPage} from './pages/Results';
import {CockpitPage} from './pages/Cockpit';
import {CockpitIcon, HistoryIcon, SettingsIcon, UploadIcon, DocumentIcon, SlidersIcon, PlayIcon, MenuIcon, PlusIcon} from './components/icons';
import type {IconProps} from './components/icons';
import './theme.css';

export type WorkspaceData={
  workspace:Workspace|null;documents:Document[];draft:JDDraft|null;approved:JDApproval|null;
  weights:Weights|null;jobs:Job[];exports:ExportRecord[];history:HistoricalRecord[];
};
export interface WorkspaceContextValue{
  workspaceId:string;data:WorkspaceData;loading:boolean;error:Error|null;
  refresh:()=>Promise<void>;settings:Settings;
}

const SettingsContext=createContext<Settings|null>(null);
export function useSettings():Settings{
  const value=useContext(SettingsContext);
  if(!value)throw new Error('Session not initialized');
  return value;
}
export function useWorkspace():WorkspaceContextValue{
  return useOutletContext<WorkspaceContextValue>();
}
const empty:WorkspaceData={workspace:null,documents:[],draft:null,approved:null,weights:null,jobs:[],exports:[],history:[]};

function useWorkspaceBundle(workspaceId:string,settings:Settings){
  const [data,setData]=useState<WorkspaceData>(empty);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState<Error|null>(null);
  const refreshCounter=useRef(0);
  const active=useRef(true);
  const refresh=useCallback(async()=>{
    const seq=++refreshCounter.current;
    setLoading(true);setError(null);
    try{
      const [workspace,documents,jd,weights,jobs,exports,history]=await Promise.all([
        client.getWorkspace(workspaceId),client.listDocuments(workspaceId),client.getJD(workspaceId),
        client.getWeights(workspaceId),client.listJobs(workspaceId),client.listExports(workspaceId),
        client.listHistory(workspaceId)
      ]);
      if(active.current&&seq===refreshCounter.current){
        setData({workspace,documents,draft:jd.draft,approved:jd.approved,weights,jobs,exports,history});
      }
    }catch(err:unknown){
      if(active.current&&seq===refreshCounter.current)setError(err instanceof Error?err:new Error('Request could not be validated'));
    }finally{if(active.current&&seq===refreshCounter.current)setLoading(false)}
  },[workspaceId]);
  useEffect(()=>{
    active.current=true;setData(empty);void refresh();
    const counter=refreshCounter;
    return ()=>{active.current=false;counter.current++};
  },[refresh]);
  return {workspaceId,data,loading,error,refresh,settings} satisfies WorkspaceContextValue;
}

function ThemePicker(){
  const [theme,setTheme]=useState<'system'|'light'|'dark'>(()=>{
    const stored=window.localStorage.getItem('textilehr-theme');
    return stored==='light'||stored==='dark'?stored:'system';
  });
  useEffect(()=>{
    const preference=window.matchMedia('(prefers-color-scheme: dark)');
    const update=()=>document.documentElement.dataset.theme=theme==='system'?(preference.matches?'dark':'light'):theme;
    update();preference.addEventListener('change',update);
    window.localStorage.setItem('textilehr-theme',theme);
    return ()=>preference.removeEventListener('change',update);
  },[theme]);
  return <label className="theme-selector" htmlFor="theme-picker">Theme<select id="theme-picker" value={theme}
       onChange={e=>setTheme(e.target.value as 'system'|'light'|'dark')}>
      <option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option>
    </select></label>;
}

function SessionGate({children}:{children:ReactNode}){
  const [settings,setSettings]=useState<Settings|null>(null);
  const [error,setError]=useState<Error|null>(null);
  const [version,retry]=useState(0);
  useEffect(()=>{
    let active=true;
    void (async()=>{
      try{await initializeSession();const value=await client.getSettings();if(active)setSettings(value)}
      catch(err:unknown){if(active)setError(err instanceof Error?err:new Error('Service unavailable'))}
    })();
    return()=>{active=false};
  },[version]);
  if(error)return <main className="body"><ErrorState error={error} retry={()=>{setError(null);retry(v=>v+1)}}/></main>;
  if(!settings)return <main className="body"><Loading/></main>;
  return <SettingsContext.Provider value={settings}>{children}</SettingsContext.Provider>;
}

function ShellHeader({title,workspaceId,activePage}:{title:string;workspaceId?:string;activePage?:string|null}){
  const settings=useSettings();
  const isCockpitActive=!activePage||['overview','run','jd','weights','uploads','rankings','candidate','progress'].includes(activePage);
  return <header className="topbar"><div className="workspace-context">
     <img className="emblem" src="/assets/brand/RWML-Logo-Small.svg" alt="" aria-hidden="true"/>
     <div><b>{title||settings.organization_name}</b><span className="small">TextileHR AI · Local assessment</span></div>
    </div>
    {workspaceId ? (
      <nav className="topbar-tabs" aria-label="Main application tabs">
        <Link
          className={`topbar-tab-link ${isCockpitActive ? 'active' : ''}`}
          to={workspacePath(workspaceId, 'overview')}
        >
          <CockpitIcon size={16} />
          <span>Assessment Cockpit</span>
        </Link>
        <Link
          className={`topbar-tab-link ${activePage === 'reports' ? 'active' : ''}`}
          to={workspacePath(workspaceId, 'reports')}
        >
          <HistoryIcon size={16} />
          <span>Assessment History</span>
        </Link>
        <Link
          className={`topbar-tab-link ${activePage === 'settings' ? 'active' : ''}`}
          to={workspacePath(workspaceId, 'settings')}
        >
          <SettingsIcon size={16} />
          <span>System & Storage</span>
        </Link>
      </nav>
    ) : null}
    <div className="top-actions"><ThemePicker/><Link className="btn small" to="/">Workspaces</Link></div></header>;
}

const NAV_ICONS: Record<string, React.FC<IconProps>> = {
  overview: CockpitIcon,
  uploads: UploadIcon,
  jd: DocumentIcon,
  weights: SlidersIcon,
  run: PlayIcon,
  reports: HistoryIcon,
  settings: SettingsIcon,
};

function WorkspaceFrame(){
  const {workspaceId}=useParams<{workspaceId:string}>();
  const settings=useSettings();
  if(!workspaceId)return <MissingResource/>;
  return <WorkspaceFrameContent key={workspaceId} workspaceId={workspaceId} settings={settings}/>;
}
function WorkspaceFrameContent({workspaceId,settings}:{workspaceId:string;settings:Settings}){
  const ctx=useWorkspaceBundle(workspaceId,settings);
  const [menuOpen,setMenuOpen]=useState(false);
  const location=useLocation();
  const [prevPath,setPrevPath]=useState(location.pathname);
  if(location.pathname!==prevPath){
    setPrevPath(location.pathname);
    setMenuOpen(false);
  }
  const current=parseWorkspaceRoute(location.pathname);
  const activePage=current.kind==='workspace'?current.page:null;
  return <div className="app"><aside id="workspace-mobile-menu" className={'sidebar '+(menuOpen?'open':'')} aria-label="Primary navigation">
     <div className="brand"><img className="logo logo--light" src="/assets/brand/RWML-Logo.svg" alt={settings.organization_name}/>
       <img className="logo logo--dark" src="/assets/brand/RWML-Logo-Dark.svg" alt="" aria-hidden="true"/>
       <div className="brand-note">TextileHR AI · Workforce intelligence</div></div>
     <nav className="nav" aria-label="Workspace pages"><div className="nav-label">Workspace</div>
       {NAV_ITEMS.map(item=>{
         const IconComp=NAV_ICONS[item.page];
         return <Link className={activePage===item.page?'active':''} key={item.page}
           aria-current={activePage===item.page?'page':undefined} to={workspacePath(workspaceId,item.page)}>
           {IconComp ? <IconComp size={18} className="symbol-icon" /> : <span className="symbol" aria-hidden="true">{item.symbol}</span>}
           <span>{item.label}</span>
         </Link>;
       })}
     </nav><div className="sidefooter"><strong>Local operator installation</strong>
       <p>CV evidence is processed by the separate Python worker, never by your browser.</p>
       <span className="mono small">Protocol {settings.protocol}</span></div>
    </aside><main className="main"><ShellHeader title={ctx.data.workspace?.title??''} workspaceId={workspaceId} activePage={activePage}/>
       <div className="body"><button className="btn small menu-btn" type="button"
          aria-expanded={menuOpen} aria-controls="workspace-mobile-menu" onClick={()=>setMenuOpen(v=>!v)}>
          <MenuIcon size={14} style={{marginRight:6}} />Menu</button>
         {ctx.error?<ErrorState error={ctx.error} retry={()=>{void ctx.refresh()}}/>:ctx.loading&&!ctx.data.workspace?<Loading/>:
          <Outlet context={ctx}/>}</div>
    </main></div>;
}

function WorkspacesHome(){
  const settings=useSettings();const [items,setItems]=useState<Workspace[]>([]);
  const [title,setTitle]=useState('');const [error,setError]=useState<Error|null>(null);
  const [busy,setBusy]=useState(false);const navigate=useNavigate();
  const refresh=useCallback(async()=>{try{setItems(await client.listWorkspaces())}catch(e:unknown){setError(e instanceof Error?e:new Error('Cannot list workspaces'))}},[]);
  useEffect(()=>{void refresh()},[refresh]);
  async function create(){if(busy||title.trim().length<2)return;setBusy(true);
    try{const workspace=await client.createWorkspace(title.trim());navigate(workspacePath(workspace.id,'overview'))}
    catch(e:unknown){setError(e instanceof Error?e:new Error('Cannot create workspace'))}
    finally{setBusy(false)}
  }
  return <div className="app"><main className="main"><ShellHeader title={settings.organization_name}/><div className="body">
    <PageHeader title="Assessment workspaces" description="Open an existing recruitment assessment or create a private local workspace."/>
    {error?<ErrorState error={error} retry={()=>{void refresh()}}/>:null}
    <div className="grid cols2"><Panel><h2>Create workspace</h2><FormField id="workspace-title" label="Recruitment workspace name">
      <input id="workspace-title" maxLength={120} value={title} onChange={e=>setTitle(e.target.value)} placeholder="Weaving Production Recruitment"/>
    </FormField><div className="toolbar" style={{marginTop:16}}><Button kind="primary" onClick={()=>{void create()}} disabled={busy||title.trim().length<2}>Create workspace</Button></div></Panel>
     <Panel><h2>Existing workspaces</h2>{items.length===0?<Blank title="No workspaces yet" description="Create a workspace to begin JD review and candidate assessments."/>:
       items.map(item=><div className="step" key={item.id}><div style={{flex:1}}><strong>{item.title}</strong>
          <small>Created {item.created}</small></div><ActionLink to={workspacePath(item.id,'overview')}>Open</ActionLink></div>)}</Panel>
    </div></div></main></div>;
}

export function Overview(){const {workspaceId,data,settings}=useWorkspace();
  const candidates=data.documents.filter(d=>d.kind==='cv');
  const active=data.jobs.filter(j=>j.state==='queued'||j.state==='running');
  return <><PageHeader title="Recruitment overview" description="Live persisted workflow, frozen hiring requirements, and source-grounded candidate results."
     actions={<ActionLink kind="primary" to={workspacePath(workspaceId,'run')}><PlusIcon size={14} style={{marginRight:6}} />New assessment</ActionLink>}/>
    <div className="grid cols3"><Panel><span className="small">Uploaded candidate CVs</span><div className="stat-value">{candidates.length}</div></Panel>
      <Panel><span className="small">JD approval</span><div className="stat-value">{data.approved?'Approved':'Pending'}</div></Panel>
      <Panel><span className="small">Queued / running</span><div className="stat-value">{active.length}</div></Panel></div>
    <div className="grid cols2" style={{marginTop:19}}><Panel><h2>Assessment workflow</h2>
      <p>Upload employer requirements, review exact source quotations, approve a frozen JD, configure weights, and submit your CV batch to the Python worker.</p>
      <div className="toolbar"><ActionLink to={workspacePath(workspaceId,'uploads')} kind="primary">Upload documents</ActionLink>
      <ActionLink to={workspacePath(workspaceId,'jd')}>Review JD</ActionLink></div></Panel>
      <Panel><h2>Recent jobs</h2>{data.jobs.length?data.jobs.slice(0,6).map(job=><div className="step" key={job.id}>
        <div style={{flex:1}}><strong>{job.kind==='assess'?'Candidate assessment':'JD extraction'}</strong>
        <small>{job.progress}/{job.total} committed</small></div><Status value={job.state}/>
        <Link className="btn small" to={workspacePath(workspaceId,'progress',{jobId:job.id})}>Open</Link></div>):
        <Blank title="No jobs" description="No processing has been submitted."/>}</Panel></div>
    <p className="small" style={{marginTop:21}}>Model: {settings.ollama_model} (local) · Protocol {settings.protocol}</p>
  </>;
}
function SettingsPage(){const {settings,workspaceId,data}=useWorkspace();const navigate=useNavigate();
  const [confirmation,setConfirmation]=useState('');const [deleteError,setDeleteError]=useState<Error|null>(null);
  const [deleting,setDeleting]=useState(false);
  async function removeWorkspace(){
    if(confirmation!=='DELETE WORKSPACE'||deleting)return;
    if(!window.confirm('Permanently delete this workspace, its uploaded documents, reports, exports, and saved assessment history?'))return;
    setDeleting(true);setDeleteError(null);
    try{await client.removeWorkspace(workspaceId);navigate('/')}
    catch(e:unknown){setDeleteError(e instanceof Error?e:new Error('Workspace cannot be deleted'))}
    finally{setDeleting(false)}
  }
  return <><PageHeader title="System & Storage Maintenance"
     description="This read-only view never starts a model call. New jobs preserve their selected provider settings."/>
    <div className="grid cols2"><Panel><h2>Configured models</h2><div className="step"><strong>Ollama</strong><span>{settings.ollama_model}</span></div>
       <div className="step"><strong>OpenRouter</strong><span>{settings.openrouter_model}</span></div>
       <div className="step"><strong>Cloud key</strong><Status value={settings.openrouter_key_configured?'Configured':'Not configured'}/></div>
       <div className="step"><strong>Default provider</strong>{settings.configured_provider}</div></Panel>
     <Panel><h2>Runtime policy</h2><div className="step"><strong>Build</strong><span className="mono small">{settings.engine_build}</span></div>
       <div className="step"><strong>Protocol</strong>{settings.protocol}</div>
       <div className="step"><strong>Deployment</strong>Single operator · loopback</div>
       <p className="small">Applicant records and credentials are stored outside frontend assets. Cloud model selection requires organization authorization.</p></Panel></div>
    <Panel><h2 className="danger-text">Delete workspace and private records</h2>
      <Message kind="warn">This action removes stored CVs, JD revisions, assessment jobs, source records, and exports for this workspace. It is blocked for running or unknown-delivery jobs. External backups remain outside the application.</Message>
      {deleteError?<ErrorState error={deleteError}/>:null}
      <FormField id="workspace-delete-confirm" label="Enter DELETE WORKSPACE to confirm">
        <input id="workspace-delete-confirm" value={confirmation} onChange={e=>setConfirmation(e.target.value)}
          autoComplete="off"/></FormField><Button kind="danger" disabled={deleting||confirmation!=='DELETE WORKSPACE'}
          onClick={()=>{void removeWorkspace()}}>Delete {data.workspace?.title??'workspace'}</Button>
    </Panel></>}
function MissingResource(){return <main className="body"><PageHeader title="Resource not found"
   description="The link is incomplete, invalid, or its saved resource is no longer available."/>
   <ActionLink to="/">Return to workspaces</ActionLink></main>}

const pages:Record<keyof typeof ROUTES,()=>ReactNode>={
  overview:()=> <CockpitPage/>,uploads:()=> <DocumentsPage/>,jd:()=> <JDPage/>,
  weights:()=> <WeightsPage/>,run:()=> <AssessmentPage/>,
  progress:()=> <ProgressPage/>,rankings:()=> <RankingsPage/>,candidate:()=> <CandidatePage/>,
  reports:()=> <ReportsPage/>,settings:()=> <SettingsPage/>,
};
export default function App(){return <BrowserRouter><SessionGate><Routes>
   <Route path="/" element={<WorkspacesHome/>}/>
   <Route path="/w/:workspaceId" element={<WorkspaceFrame/>}>
     <Route path="overview" element={<CockpitPage/>}/>
     {Object.entries(ROUTES).map(([name,path])=>{
       const child=pages[name as keyof typeof ROUTES]();
       return path===''?<Route key={name} index element={child}/>:
          <Route key={name} path={path} element={child}/>;
     })}
     <Route path="*" element={<MissingResource/>}/>
   </Route>
   <Route path="*" element={<MissingResource/>}/>
 </Routes></SessionGate></BrowserRouter>}
