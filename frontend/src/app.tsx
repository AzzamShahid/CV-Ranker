import {useCallback,useEffect,useRef,useState,createContext,useContext} from 'react';
import type {ReactNode} from 'react';
import {BrowserRouter,Routes,Route,Outlet,Link,useNavigate,useParams,useLocation,useOutletContext} from 'react-router-dom';
import {client,initializeSession} from './api/client';
import type {Document,ExportRecord,HistoricalRecord,JDApproval,JDDraft,Job,Settings,Weights,Workspace} from './api/client';
import {ROUTES,NAV_ITEMS,parseWorkspaceRoute,workspacePath} from './router';
import {ActionLink,Blank,Button,ErrorState,Loading,Panel,PageHeader,Status,FormField,dateString} from './components/ui';
import {DocumentsPage,JDPage,WeightsPage,AssessmentPage} from './pages/Workflow';
import {ProgressPage,RankingsPage,CandidatePage,ReportsPage} from './pages/Results';
import {CockpitPage} from './pages/Cockpit';
import {CockpitIcon, HistoryIcon, SettingsIcon, UploadIcon, DocumentIcon, SlidersIcon, PlayIcon, MenuIcon, PlusIcon, SunIcon, MoonIcon, MonitorIcon} from './components/icons';
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
    const update=()=>{
      const resolved=theme==='system'?(preference.matches?'dark':'light'):theme;
      document.documentElement.dataset.theme=resolved;
      let meta = document.querySelector('meta[name="color-scheme"]') as HTMLMetaElement | null;
      if (!meta) {
        meta = document.createElement('meta');
        meta.name = 'color-scheme';
        document.head.appendChild(meta);
      }
      meta.content = theme==='system'?'light dark':theme;
    };
    update();preference.addEventListener('change',update);
    window.localStorage.setItem('textilehr-theme',theme);
    return ()=>preference.removeEventListener('change',update);
  },[theme]);
  return <div className="theme-toggle-group" role="group" aria-label="Theme selection">
    <button type="button" className={'theme-toggle-btn '+(theme==='light'?'active':'')}
      onClick={()=>setTheme('light')} title="Light mode" aria-pressed={theme==='light'}>
      <SunIcon size={14}/><span>Light</span></button>
    <button type="button" className={'theme-toggle-btn '+(theme==='dark'?'active':'')}
      onClick={()=>setTheme('dark')} title="Dark mode" aria-pressed={theme==='dark'}>
      <MoonIcon size={14}/><span>Dark</span></button>
    <button type="button" className={'theme-toggle-btn '+(theme==='system'?'active':'')}
      onClick={()=>setTheme('system')} title="System preference" aria-pressed={theme==='system'}>
      <MonitorIcon size={14}/><span>Auto</span></button>
  </div>;
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
     <div><b>{title||settings.organization_name}</b><span className="small">Reliance Weaving Mills AI · Recruitment Intelligence</span></div>
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
     <div className="brand">
       <div className="brand-logo-wrap">
         <img className="logo logo--light" src="/assets/brand/RWML-Logo.svg" alt={settings.organization_name}/>
         <img className="logo logo--dark" src="/assets/brand/RWML-Logo-Dark.svg" alt="" aria-hidden="true"/>
       </div>
       <div className="brand-note">Reliance Weaving Mills Ltd. · Recruitment Intelligence</div></div>
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
    <div className="workspace-hero-banner">
      <div className="workspace-hero-logo-wrap">
        <img className="hero-logo hero-logo--light" src="/assets/brand/RWML-Logo.svg" alt="Reliance Weaving Mills Ltd." />
        <img className="hero-logo hero-logo--dark" src="/assets/brand/RWML-Logo-Dark.svg" alt="Reliance Weaving Mills Ltd." />
      </div>
      <div className="workspace-hero-meta">
        <div className="eyebrow" style={{marginBottom: 4, color: 'var(--brand-green)'}}>A FATIMA GROUP COMPANY · RECRUITMENT INTELLIGENCE</div>
        <h1 style={{margin: '0 0 6px 0', fontSize: '26px'}}>Reliance Weaving Mills AI</h1>
        <p style={{margin: 0, fontSize: '14px', maxWidth: 680}}>
          Verifiable candidate qualification scoring, frozen employer requirement analysis, and durable audit logs.
        </p>
      </div>
    </div>
    <PageHeader title="Assessment workspaces" description="Open an existing recruitment assessment or create a private local workspace."/>
    {error?<ErrorState error={error} retry={()=>{void refresh()}}/>:null}
    <div className="grid cols2"><Panel><h2>Create workspace</h2><FormField id="workspace-title" label="Recruitment workspace name">
      <input id="workspace-title" maxLength={120} value={title} onChange={e=>setTitle(e.target.value)} placeholder="Weaving Production Recruitment"/>
    </FormField><div className="toolbar" style={{marginTop:16}}><Button kind="primary" onClick={()=>{void create()}} disabled={busy||title.trim().length<2}>Create workspace</Button></div></Panel>
     <Panel><h2>Existing workspaces</h2>{items.length===0?<Blank title="No workspaces yet" description="Create a workspace to begin JD review and candidate assessments."/>:
       items.map(item=><div className="step" key={item.id} style={{justifyContent:'space-between',alignItems:'center'}}>
         <div style={{display:'flex',flexDirection:'column',gap:4}}>
           <strong style={{fontSize:15}}>{item.title}</strong>
           <small className="muted">Created {dateString(item.created)}</small>
         </div>
         <ActionLink kind="subtle" size="small" to={workspacePath(item.id,'overview')}>Open workspace</ActionLink>
       </div>)}</Panel>
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
function SettingsPage(){const {settings,workspaceId}=useWorkspace();const navigate=useNavigate();
  const [confirmation,setConfirmation]=useState('');const [deleteError,setDeleteError]=useState<Error|null>(null);
  const [deleting,setDeleting]=useState(false);
  const isConfirmed = ['DELETE', 'DELETE WORKSPACE'].includes(confirmation.trim().toUpperCase());
  async function removeWorkspace(){
    if(!isConfirmed||deleting)return;
    if(!window.confirm('Permanently delete this workspace, its uploaded documents, reports, exports, and saved assessment history?'))return;
    setDeleting(true);setDeleteError(null);
    try{await client.removeWorkspace(workspaceId);navigate('/')}
    catch(e:unknown){setDeleteError(e instanceof Error?e:new Error('Workspace cannot be deleted'))}
    finally{setDeleting(false)}
  }
  return <><PageHeader title="System & Storage Maintenance"
     description="This read-only view never starts a model call. New jobs preserve their selected provider settings."/>
    <div className="stack" style={{gap: 20}}>
      <div className="grid cols2">
        <Panel><h2>Configured models</h2>
          <div className="step"><strong>Ollama</strong><span>{settings.ollama_model}</span></div>
          <div className="step"><strong>OpenRouter</strong><span>{settings.openrouter_model}</span></div>
          <div className="step"><strong>Cloud key</strong><Status value={settings.openrouter_key_configured?'Configured':'Not configured'}/></div>
          <div className="step"><strong>Default provider</strong>{settings.configured_provider}</div>
        </Panel>
        <Panel><h2>Runtime policy</h2>
          <div className="step"><strong>Build</strong><span className="mono small">{settings.engine_build}</span></div>
          <div className="step"><strong>Protocol</strong>{settings.protocol}</div>
          <div className="step"><strong>Deployment</strong>Single operator · loopback</div>
          <p className="small" style={{marginTop: 10}}>Applicant records and credentials are stored outside frontend assets. Cloud model selection requires organization authorization.</p>
        </Panel>
      </div>
      <Panel className="danger-panel" style={{ padding: '24px 28px' }}>
        <h2 className="danger-text" style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          Delete workspace and private records
        </h2>

        <div className="danger-callout" role="alert">
          <div className="danger-callout-header">
            <strong>Irreversible Workspace Deletion</strong>
          </div>
          <p className="danger-callout-text">
            This action removes stored CVs, JD revisions, assessment jobs, source records, and exports for this workspace. It is blocked for running or unknown-delivery jobs. External backups remain outside the application.
          </p>
        </div>

        {deleteError?<ErrorState error={deleteError}/>:null}

        <div style={{maxWidth: 480, marginTop: 16}}>
          <FormField id="workspace-delete-confirm" label="Enter DELETE to confirm deletion">
            <input
              id="workspace-delete-confirm"
              value={confirmation}
              onChange={e=>setConfirmation(e.target.value)}
              placeholder="DELETE"
              autoComplete="off"
              className="mono"
              style={{
                fontSize: 14,
                letterSpacing: '0.08em',
                fontWeight: 600
              }}
            />
          </FormField>
        </div>

        <div style={{marginTop: 18}}>
          <Button
            kind="danger"
            disabled={deleting||!isConfirmed}
            onClick={()=>{void removeWorkspace()}}
            style={isConfirmed ? {
              background: '#dc2626',
              color: '#ffffff',
              boxShadow: '0 2px 8px rgba(220, 38, 38, 0.45)',
              fontWeight: 700,
              padding: '10px 22px'
            } : {
              fontWeight: 600,
              padding: '10px 22px'
            }}
          >
            {deleting ? 'Deleting workspace…' : 'Delete workspace permanently'}
          </Button>
        </div>
      </Panel>
    </div></>}
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
