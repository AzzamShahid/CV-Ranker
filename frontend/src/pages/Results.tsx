import {useCallback,useEffect,useRef,useState} from 'react';
import {useParams} from 'react-router-dom';
import {client} from '../api/client';
import {consumeSequence,isTerminalJob,newerSnapshot,nextReconnectMs} from '../api/observation';
import {startDistinctIntent} from '../api/submissionIntent';
import type {Job,Ranking,CandidateDetail,JobUsage,SemanticShadow,ReviewHistoryItem,RetentionSummary} from '../api/client';
import {useWorkspace} from '../app';
import {workspacePath} from '../router';
import {ActionLink,Blank,Button,ErrorState,FormField,Loading,Message,PageHeader,Panel,Status,confirmDestructive,dateString} from '../components/ui';
import {
  RefreshIcon,
  CloseIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  DownloadIcon,
  ChartBarIcon,
  SparkleIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  SearchIcon,
} from '../components/icons';

export function useSavedJob(explicitJobId?: string){
  const {workspaceId}=useWorkspace();const params=useParams<{jobId:string}>();
  const jobId=explicitJobId??params.jobId;
  const [job,setJob]=useState<Job|null>(null);const [error,setError]=useState<Error|null>(null);
  const [loading,setLoading]=useState(true);
  const generation=useRef(0);const inflight=useRef<Promise<void>|null>(null);
  const refreshQueued=useRef(false);
  const apply=useCallback((value:Job)=>setJob(previous=>newerSnapshot(previous,value)),[]);
  const load=useCallback(async()=>{
    if(!jobId)return;
    if(inflight.current){refreshQueued.current=true;return inflight.current;}
    const current=++generation.current;
    const task=(async()=>{
      try{
        const value=await client.getJob(workspaceId,jobId);
        if(generation.current===current){apply(value);setError(null)}
      }catch(e:unknown){if(generation.current===current)setError(e instanceof Error?e:new Error('Job not available'))}
      finally{if(generation.current===current)setLoading(false)}
    })();
    inflight.current=task;
    try{await task}finally{if(inflight.current===task){
      inflight.current=null;
      if(refreshQueued.current){refreshQueued.current=false;void load();}
    }}
  },[workspaceId,jobId,apply]);
  useEffect(()=>{
    const gen = generation;
    gen.current++;inflight.current=null;refreshQueued.current=false;
    setJob(null);setLoading(true);void load();
    return()=>{gen.current++};
  },[load]);
  return {jobId,job,error,loading,load,apply};
}

export function useRankings(jobId:string|undefined,offset=0,search=''){
  const {workspaceId}=useWorkspace();const [rows,setRows]=useState<Ranking[]>([]);
  const [error,setError]=useState<Error|null>(null);const [resultRevision,setRevision]=useState(0);
  const [weightRevision,setWeightRevision]=useState(0);
  const [total,setTotal]=useState(0);
  const [officialCount,setOfficialCount]=useState(0);
  const [unfinishedCount,setUnfinishedCount]=useState(0);
  const generation=useRef(0);const inFlight=useRef<Promise<void>|null>(null);
  const refreshQueued=useRef(false);
  const pinned=useRef<{identity:string;resultRevision:number;weightRevision:number}|null>(null);

  const resetPin=useCallback(()=>{
    pinned.current=null;
  },[]);

  const refresh=useCallback(async(forceReplacePin=false)=>{
    if(!jobId)return;
    const identity=`${workspaceId}:${jobId}:${search}`;
    if(pinned.current?.identity!==identity || forceReplacePin || offset===0){
      pinned.current=null;
    }
    if(inFlight.current){refreshQueued.current=true;return inFlight.current;}
    const current=++generation.current;
    const task=(async()=>{
      try{
        const pin=pinned.current;
        const result=await client.listRankings(workspaceId,jobId,{offset,limit:50,search,
          expectedResultRevision:offset>0&&pin?pin.resultRevision:undefined,
          expectedWeightRevision:offset>0&&pin?pin.weightRevision:undefined});

        // On page one (offset === 0), pin is established or replaced with current revision
        if(offset===0 && result.resultRevision!==null && result.weightRevision!==null){
          pinned.current={identity,resultRevision:result.resultRevision,weightRevision:result.weightRevision};
        } else if(!pin && result.resultRevision!==null && result.weightRevision!==null){
          pinned.current={identity,resultRevision:result.resultRevision,weightRevision:result.weightRevision};
        }

        if(pin && offset>0 && (result.resultRevision!==pin.resultRevision || result.weightRevision!==pin.weightRevision)){
          pinned.current=null;
          throw new Error('The ranking changed while you were browsing. Return to page one to load the new revision.');
        }

        if(current===generation.current){
          setRows(result.items);
          setRevision(result.resultRevision??0);
          setWeightRevision(result.weightRevision??0);
          setTotal(result.total);
          setOfficialCount(result.officialCount);
          setUnfinishedCount(result.unfinishedCount);
          setError(null);
        }
      }catch(e:unknown){
        if(current===generation.current){
          setRows([]);
          setError(e instanceof Error?e:new Error('Rankings unavailable'));
        }
      }
    })();
    inFlight.current=task;
    try{await task}finally{if(inFlight.current===task){
      inFlight.current=null;
      if(refreshQueued.current){refreshQueued.current=false;void refresh();}
    }}
  },[workspaceId,jobId,offset,search]);

  useEffect(()=>{
    const gen = generation;
    gen.current++;inFlight.current=null;refreshQueued.current=false;setRows([]);void refresh();
    return()=>{gen.current++};
  },[refresh]);

  return {rows,total,officialCount,unfinishedCount,error,resultRevision,weightRevision,refresh,resetPin};
}

export function ProgressBar({completed,total}:{completed:number;total:number}){
  const percent=total>0?Math.min(100,Math.max(0,Math.round(completed/total*100))):0;
  return <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={total}
    aria-valuenow={completed} aria-label="Candidates committed"><span style={{width:percent+'%'}}/></div>;
}

export { client } from '../api/client';
export function ProgressPage(){
 const {workspaceId}=useWorkspace();const {jobId,job,error,loading,load}=useSavedJob();
 const rows=useRankings(jobId);
 const [busy,setBusy]=useState(false);const [actionError,setActionError]=useState<Error|null>(null);
 const [notice,setNotice]=useState('');const [online,setOnline]=useState(true);
 const [observationEpoch,setObservationEpoch]=useState(0);
 const stopObservation=useRef<()=>void>(()=>{});const actionLock=useRef(false);
 const [ack,setAck]=useState('');
 const lastSeq=useRef(0);const refreshRef=useRef(load);refreshRef.current=load;
 const ranksRef=useRef(rows.refresh);ranksRef.current=rows.refresh;
 useEffect(()=>{
   if(!jobId)return;
   let mounted=true;let stream:EventSource|null=null;
   let poller:number|null=null;let reconnect:number|null=null;
   let refreshTimer:number|null=null;let errors=0;let healthy=false;let stopped=false;
   lastSeq.current=0;
   const endpoint=`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/jobs/${encodeURIComponent(jobId)}/events`;
   const clean=()=>{
     if(stream){stream.close();stream=null}
     if(poller!==null){window.clearInterval(poller);poller=null}
     if(reconnect!==null){window.clearTimeout(reconnect);reconnect=null}
     if(refreshTimer!==null){window.clearTimeout(refreshTimer);refreshTimer=null}
   };
   stopObservation.current=()=>{stopped=true;clean()};
   const fetchAuthoritative=async()=>{
     if(!mounted||stopped)return;
     await refreshRef.current();await ranksRef.current();
   };
   const scheduleRefresh=()=>{
     if(refreshTimer!==null)return;
     refreshTimer=window.setTimeout(()=>{
       refreshTimer=null;void fetchAuthoritative();
     },140);
   };
   const connect=()=>{
     if(!mounted||stopped)return;
     if(stream){stream.close();stream=null}
     stream=new EventSource(endpoint,{withCredentials:true});
     stream.onopen=()=>{
       if(!mounted)return;healthy=true;errors=0;setOnline(true);
     };
     const update=(e:Event)=>{
       if(!mounted||stopped)return;
       const message=e as MessageEvent<string>;
       if(message.type==='snapshot'){
         try{
           const record:unknown=JSON.parse(message.data);
           if(record&&typeof record==='object'&&'sequence' in record&&'id' in record&&
             (record as {id:unknown}).id===jobId){
             const snap=record as {sequence:unknown;state?:unknown};
             if(typeof snap.sequence==='number'&&snap.sequence>=lastSeq.current){
               lastSeq.current=snap.sequence;
               scheduleRefresh();
               if(typeof snap.state==='string'&&isTerminalJob(snap.state)){
                 stopped=true;void Promise.all([refreshRef.current(),ranksRef.current()]);clean();
               }
             }
           }
         }catch{scheduleRefresh()}
         return;
       }
       if(message.type==='replay_expired'){scheduleRefresh();return}
       const seq=Number(message.lastEventId);
       const newer=consumeSequence(lastSeq.current,seq);
       if(newer===null)return;
       lastSeq.current=newer;
       scheduleRefresh();
       if(['completed','completed_with_errors','failed','cancelled'].includes(message.type)){
         // A final refresh recovers the stored result even when the event
         // contains no applicant details, then the connection settles.
         void Promise.all([refreshRef.current(),ranksRef.current()]);
         stopped=true;clean();
       }
     };
     for(const name of ['snapshot','queued','running','progress','candidate_committed',
       'paused','completed','completed_with_errors','failed','cancelled',
       'worker_lost','recovery_acknowledged','replay_expired']){
       stream.addEventListener(name,update);
     }
     stream.onerror=()=>{
       if(!mounted||stopped)return;
       healthy=false;setOnline(false);errors++;
       if(stream){stream.close();stream=null}
       if(reconnect!==null)window.clearTimeout(reconnect);
       reconnect=window.setTimeout(()=>{reconnect=null;connect()},nextReconnectMs(errors));
     };
   };
   connect();
   // Poll only when event delivery is unavailable. No duplicate active
   // stream+poll traffic, no repeated terminal job reads.
   poller=window.setInterval(()=>{
     if(mounted&&!healthy&&!stopped)void fetchAuthoritative();
   },12000);
   return()=>{mounted=false;stopped=true;clean()};
 },[workspaceId,jobId,observationEpoch]);

 const jobState = job?.state;
 useEffect(()=>{
   if(jobState&&(['completed','completed_with_errors','failed','cancelled','paused']).includes(jobState))
     stopObservation.current();
 },[jobState]);

 const action=async(fn:()=>Promise<void>)=>{
   if(actionLock.current)return;actionLock.current=true;setBusy(true);setActionError(null);setNotice('');
   try{await fn();await load();await rows.refresh()}catch(e:unknown){setActionError(e instanceof Error?e:new Error('Action failed'))}
   finally{actionLock.current=false;setBusy(false)}
 };
 const canResume=job?.state==='paused'||job?.state==='failed'||job?.state==='cancelled'||job?.state==='completed_with_errors';
 const cooldown=job?.eligible_at!==null&&job?.eligible_at!==undefined&&job.eligible_at*1000>Date.now();
 return <><PageHeader title="Assessment progress" description="The worker commits each candidate independently. Closing or refreshing this page does not create another job."
   actions={<ActionLink to={workspacePath(workspaceId,'reports')}>Saved jobs</ActionLink>}/>
   {error?<ErrorState error={error} retry={()=>{void load()}}/>:null}{rows.error?<ErrorState error={rows.error} retry={()=>{void rows.refresh()}}/>:null}
   {actionError?<ErrorState error={actionError}/>:null}{notice?<Message kind="success">{notice}</Message>:null}
   {!online?<Message kind="warn">Live connection interrupted. Saved progress is still readable through periodic polling.</Message>:null}
   {loading&&!job?<Loading/>:!job?<Blank title="Job not found" description="This job is unavailable in the current workspace."/>:<>
   <Panel><div className="card-header"><h2>{job.kind==='assess'?'Candidate evaluation':'Job-description extraction'}</h2><Status value={job.state}/></div>
    <div className="row between"><b>{job.progress} of {job.total} committed</b><span className="mono small">{job.id.slice(0,16)}</span></div>
    <ProgressBar completed={job.progress} total={job.total}/>
    <div className="grid cols3" style={{marginTop:19}}><div><small>Started</small><p>{dateString(job.created)}</p></div>
       <div><small>Result revision</small><p>{job.result_revision}</p></div>
       <div><small>Event sequence</small><p>{job.sequence}</p></div></div>
    {job.error_code?<Message kind="warn"><strong>{job.error_code}</strong> · {job.error_message??'Inspect the saved failure before retrying.'}</Message>:null}
    {cooldown?<Message kind="warn">Next retry eligible at {new Date((job.eligible_at??0)*1000).toLocaleString()}.</Message>:null}
    <div className="toolbar" style={{marginTop:15}}>{job.kind==='assess'?<ActionLink to={workspacePath(workspaceId,'rankings',{jobId:job.id})}
       kind="primary">View candidate rankings</ActionLink>:<ActionLink to={workspacePath(workspaceId,'jd')} kind="primary">Review extracted JD</ActionLink>}
      {['queued','running','cancelling'].includes(job.state)?<Button kind="danger" disabled={busy||job.state==='cancelling'} onClick={()=>{
        void action(async()=>{await client.controlJob(workspaceId,job.id,'cancel');setNotice('Cancellation requested. In-flight paid calls may still complete.')})
      }}>Request cancellation</Button>:null}
      {canResume&&job.error_code!=='worker_unknown_delivery'?<Button kind="subtle" disabled={busy||cooldown} onClick={()=>{
        void action(async()=>{await client.controlJob(workspaceId,job.id,'resume');setObservationEpoch(v=>v+1);setNotice('Job requeued with existing checkpoints preserved.')})
      }}>Resume eligible work</Button>:null}
    </div>
   </Panel>
   {job.error_code==='worker_unknown_delivery'?<Panel>
      <h2>Uncertain worker delivery — operator resolution required</h2>
      <Message kind="warn">A model request might have been sent before the worker stopped. Retrying could incur a duplicate provider charge. Committed candidates remain preserved.</Message>
      <Button onClick={()=>{void action(async()=>{
        const result=await client.resolveUnknown(workspaceId,job.id,'inspect');
        if(typeof result==='object'&&result!==null&&'committed_candidates' in result)
          setNotice(`Saved candidate checkpoint count: ${String(result.committed_candidates)}. No provider call was made.`);
      })}}>Inspect saved checkpoints</Button>
      <FormField id="duplicate-cost-ack" label="To authorize a possible duplicate paid request, enter the exact acknowledgement phrase"
         note="I ACCEPT THE RISK OF DUPLICATE PROVIDER CHARGES">
        <input id="duplicate-cost-ack" value={ack} onChange={e=>setAck(e.target.value)} autoComplete="off"/>
      </FormField><Button kind="danger" disabled={busy||ack!=='I ACCEPT THE RISK OF DUPLICATE PROVIDER CHARGES'}
        onClick={()=>{if(window.confirm('Permit a retry that may duplicate a paid provider operation?'))void action(async()=>{
           await client.resolveUnknown(workspaceId,job.id,'accept_duplicate_risk',ack);
           setObservationEpoch(v=>v+1);setNotice('Operator acknowledgement recorded. Only incomplete candidates will be rescheduled.');
        })}}>Acknowledge risk and requeue</Button>
    </Panel>:null}
   <Panel><div className="card-header"><h2>Committed candidates</h2><Status value={rows.total+' saved results'}/></div>
    {rows.rows.length?<div className="table-scroller"><table><thead><tr><th>Candidate</th><th>Official score</th><th>Assessment state</th><th>Evidence</th></tr></thead><tbody>
      {rows.rows.map(row=><tr key={row.candidate_id}><td>{row.candidate}</td><td><b>{row.weighted_score===null?'Unavailable':row.weighted_score.toFixed(2)+'%'}</b></td>
       <td><Status value={row.score_status}/></td><td><ActionLink to={workspacePath(workspaceId,'candidate',{jobId:job.id,candidateId:row.candidate_id})}>Inspect</ActionLink></td></tr>)}
    </tbody></table></div>:<Blank title="No committed candidates yet" description="The worker has not completed its first candidate checkpoint."/>}
    {rows.total>rows.rows.length?<p className="help">Showing the first {rows.rows.length} of {rows.total}. Open Rankings to page through every candidate.</p>:null}</Panel>
   </>}
 </>;
}

export function RankingsPage(){
 const {workspaceId,data}=useWorkspace();const {jobId,job,error,loading}=useSavedJob();
 const [nameFilter,setNameFilter]=useState('');const [page,setPage]=useState(0);
 const result=useRankings(jobId,page*50,nameFilter);
 const [busy,setBusy]=useState(false);const [exportError,setExportError]=useState<Error|null>(null);
 const [usage,setUsage]=useState<JobUsage|null>(null);
 const [showUsage,setShowUsage]=useState(false);
 const [shadow,setShadow]=useState<SemanticShadow|null>(null);
 const [showShadow,setShowShadow]=useState(false);
 const [shadowLoading,setShadowLoading]=useState(false);
 const filtered=result.rows;

 const handleRefreshRankings=()=>{
   setPage(0);
   result.resetPin();
   void result.refresh(true);
 };

 const loadUsage=async()=>{
   if(!job)return;
   try{
     const u=await client.getJobUsage(workspaceId,job.id);
     setUsage(u);
     setShowUsage(true);
   }catch(e:unknown){
     setExportError(e instanceof Error?e:new Error('Failed to load usage metrics'));
   }
 };

 const loadShadow=async()=>{
   if(!job)return;
   setShadowLoading(true);
   try{
     const s=await client.runSemanticShadow(workspaceId,job.id);
     setShadow(s);
     setShowShadow(true);
   }catch(e:unknown){
     setExportError(e instanceof Error?e:new Error('Failed to load semantic shadow'));
   }finally{
     setShadowLoading(false);
   }
 };

 const createExport=async()=>{
  if(!job||!data.weights||busy)return;setBusy(true);setExportError(null);
  try{
    const latest=await client.getJob(workspaceId,job.id);
    if(latest.result_revision!==result.resultRevision||data.weights.revision!==result.weightRevision)
      throw new Error('Result or weight revision changed. Reload before export.');
    const file=await client.export(workspaceId,job.id,latest.result_revision,data.weights.revision);
    const link=document.createElement('a');link.href=`/api/v1/workspaces/${workspaceId}/exports/${file.id}/download`;
    link.download='Reliance_Weaving_Mills_Assessment.zip';document.body.append(link);link.click();link.remove();
  }catch(e:unknown){setExportError(e instanceof Error?e:new Error('Export failed'))}
  finally{setBusy(false)}
 };

 return <><PageHeader title="Candidate rankings" description="Canonical, source-grounded ranking from the existing Python engine. An incomplete candidate has no official score."
  actions={<ActionLink to={workspacePath(workspaceId,'reports')}>Saved results</ActionLink>}/>
  {error?<ErrorState error={error}/>:null}
  {result.error?<Panel className="error-panel">
    <Message kind="warn"><strong>Revision notice:</strong> {result.error.message}</Message>
    <div className="toolbar" style={{marginTop:8}}>
      <Button kind="primary" onClick={handleRefreshRankings}>Refresh rankings (load latest revision)</Button>
    </div>
  </Panel>:null}
  {exportError?<ErrorState error={exportError}/>:null}
  {loading&&!job?<Loading/>:!job?<Blank title="Job unavailable" description="Open a saved assessment from Reports."/>:<>
    <div className="grid cols3 stat-grid">
      <Panel className="stat-card">
        <small className="stat-title">{nameFilter ? 'Filtered' : 'Total Evaluated'}</small>
        <div className="stat-value">{result.total}</div>
        <span className="small text-muted stat-desc">{nameFilter ? 'Matches search query' : 'All candidates in run'}</span>
      </Panel>
      <Panel className="stat-card">
        <small className="stat-title">Official Scores</small>
        <div className="stat-value">{result.officialCount}</div>
        <span className="small text-muted stat-desc">{nameFilter ? 'Matching completed' : 'Completed evaluations'}</span>
      </Panel>
      <Panel className="stat-card">
        <small className="stat-title">Unfinished</small>
        <div className="stat-value">{result.unfinishedCount}</div>
        <span className="small text-muted stat-desc">{nameFilter ? 'Matching incomplete' : 'Incomplete or pending'}</span>
      </Panel>
    </div>
    {showUsage&&usage?<Panel>
      <div className="card-header"><h2>Provider Usage & Cost Metrics</h2>
        <Button size="small" onClick={()=>setShowUsage(false)}>Close</Button></div>
      <p className="small">Job scope: <span className="mono">{usage.job_id}</span> · Provider: <strong>{usage.provider}</strong> · Model: <strong>{usage.model}</strong></p>
      <div className="grid cols3" style={{marginTop:12,marginBottom:12}}>
        <div><small>Logical model calls</small><p>{usage.logical_model_calls}</p></div>
        <div><small>HTTP request attempts</small><p>{usage.actual_model_request_attempts}</p></div>
        <div><small>Prompt reuses</small><p>{usage.reused_prompt_calls}</p></div>
      </div>
      <p><strong>Tokens:</strong> {usage.token_usage.prompt_tokens!==null&&usage.token_usage.prompt_tokens!==undefined?`Prompt: ${usage.token_usage.prompt_tokens} · Completion: ${usage.token_usage.completion_tokens} · Total: ${usage.token_usage.total_tokens}`:'Preserved as unknown (provider did not report)'}</p>
      <p><strong>Cost:</strong> {usage.cost_label}</p>
      <small className="help">All provider credentials and keys remain strictly server-side and are excluded from UI, logs and exports.</small>
    </Panel>:null}
    {showShadow&&shadow?<Panel>
      <div className="card-header"><h2>Optional Semantic Shadow Diagnostics</h2>
        <Button size="small" onClick={()=>setShowShadow(false)}>Close</Button></div>
      <Message kind="warn">{shadow.notice}</Message>
      {shadow.items.length?<div className="table-scroller" style={{marginTop:12}}><table>
        <thead><tr><th>Requirement</th><th>Candidate</th><th>Similarity</th><th>Diagnostic Finding</th></tr></thead>
        <tbody>{shadow.items.map((item,idx)=><tr key={idx}>
          <td>{item.requirement_id}</td><td><span className="mono">{item.candidate_id.slice(0,12)}</span></td>
          <td>{(item.similarity*100).toFixed(1)}%</td><td>{item.finding}</td>
        </tr>)}</tbody>
      </table></div>:<Blank title="No shadow findings" description="Semantic shadow returned no diagnostic findings."/>}
    </Panel>:null}
    <Panel>
      <div className="card-header">
        <div>
          <h2>Verified weighted leaderboard</h2>
          <span className="small text-muted">Authoritative ranking snapshot from Python assessment engine</span>
        </div>
        <div className="row" style={{gap:8}}>
          <Status value={'Weights revision '+result.weightRevision}/>
          <Button kind="primary" size="small" onClick={()=>{void createExport()}} disabled={busy||result.resultRevision===0}>
            <DownloadIcon size={14} style={{marginRight:4}} />Export this result + weight revision
          </Button>
        </div>
      </div>
      <div className="leaderboard-toolbar">
        <div className="search-field-container" style={{ position: 'relative' }}>
          <SearchIcon size={15} style={{ position: 'absolute', left: 12, top: 13, color: 'var(--text-muted)', pointerEvents: 'none' }} />
          <input id="candidate-filter" value={nameFilter}
            onChange={e=>{setNameFilter(e.target.value);setPage(0)}} placeholder="Search all evaluated candidates..."
            style={{ paddingLeft: 36 }}
            className="search-input"
            aria-label="Filter candidates by filename or name"
          />
        </div>
        <div className="toolbar-actions">
          <Button size="small" onClick={handleRefreshRankings}>
            <RefreshIcon size={14} style={{marginRight:4}} />Refresh rankings
          </Button>
          <Button size="small" onClick={()=>void loadUsage()}>
            <ChartBarIcon size={14} style={{marginRight:4}} />Usage & costs
          </Button>
          <Button size="small" disabled={shadowLoading} onClick={()=>void loadShadow()}>
            <SparkleIcon size={14} style={{marginRight:4}} />
            {shadowLoading?'Running shadow...':'Semantic shadow'}
          </Button>
          <ActionLink to={workspacePath(workspaceId,'weights')} className="btn small">Edit weights</ActionLink>
          <ActionLink to={workspacePath(workspaceId,'progress',{jobId:job.id})} className="btn small">Progress</ActionLink>
        </div>
      </div>
      {filtered.length?<div className="table-scroller"><table className="cockpit-table"><thead><tr><th>Rank</th><th>Candidate</th><th>Score</th>
       <th>Required</th><th>Preferred</th><th>Experience</th><th>Education</th><th>State</th><th>Why</th></tr></thead>
       <tbody>{filtered.map(row=><tr key={row.candidate_id} className="cockpit-table-row">
       <td className="font-bold">{row.rank===null?'—':'#'+row.rank}</td><td><strong>{row.candidate}</strong></td>
       <td className="font-bold mono">{row.weighted_score===null?'Not ready':row.weighted_score.toFixed(2)+'%'}</td><td>{row.required}</td>
       <td>{row.preferred}</td><td>{row.experience}</td><td>{row.education}</td><td><Status value={row.score_status}/></td>
       <td><ActionLink to={workspacePath(workspaceId,'candidate',{jobId:job.id,candidateId:row.candidate_id})}>Why <ArrowRightIcon size={12} style={{marginLeft:3}} /></ActionLink></td>
       </tr>)}</tbody></table></div>:<Blank title="No matching results" description="Try a different filter or review job progress."/>}
      <div className="cockpit-pagination">
        <span className="small text-muted">Showing {filtered.length? page*50+1:0}–{Math.min((page+1)*50,result.total)} of {result.total} matching candidates (page {page+1} of {Math.max(1, Math.ceil(result.total/50))})</span>
        <div className="pagination-buttons">
          <Button size="small" disabled={page===0} onClick={()=>setPage(v=>Math.max(0,v-1))}>
            <ChevronLeftIcon size={13} style={{marginRight:4}} />Previous page
          </Button>
          <Button size="small" disabled={(page+1)*50>=result.total} onClick={()=>setPage(v=>v+1)}>
            Next page<ChevronRightIcon size={13} style={{marginLeft:4}} />
          </Button>
        </div>
      </div>
    </Panel>
    {filtered?.length ? (
      <Panel>
        <div className="card-header">
          <div>
            <div className="eyebrow" style={{ marginBottom: 4 }}>Evidence-Based Ranking Rationale</div>
            <h2 style={{ margin: '0 0 4px 0' }}>Ranking explained · Why candidates ranked this way</h2>
            <p className="small text-muted" style={{ margin: 0 }}>
              One clear explanation per candidate under approved JD priorities. Detailed evidence is available in candidate view.
            </p>
          </div>
        </div>
        <div className="stack" style={{ gap: 12, marginTop: 14 }}>
          {filtered.map(row => (
            <div key={row.candidate_id} className="why" style={{ margin: 0, padding: '14px 18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="num" style={{ padding: '3px 8px', fontSize: 13, fontWeight: 700, borderRadius: 6 }}>
                    {row.rank === null ? '—' : `#${row.rank}`}
                  </span>
                  <strong style={{ fontSize: 14 }}>{row.candidate}</strong>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <strong style={{ fontSize: 14, color: 'var(--brand-green)' }}>
                    {row.weighted_score === null ? 'Not ready' : `${row.weighted_score.toFixed(2)}%`}
                  </strong>
                  <ActionLink size="small" to={workspacePath(workspaceId, 'candidate', { jobId: job.id, candidateId: row.candidate_id })}>
                    Why <ArrowRightIcon size={12} style={{ marginLeft: 3 }} />
                  </ActionLink>
                </div>
              </div>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                {row.placement_reason || 'Verified match score under approved employer priorities.'}
              </p>
            </div>
          ))}
        </div>
      </Panel>
    ) : null}
    <div className="compliance-disclaimer-card">
      <small className="disclaimer-text">
        These are evidence-grounded CV comparisons, not independent verification of professional competence. Transferable evidence earns no direct requirement credit.
      </small>
    </div>
  </>}
 </>;
}

export function CandidateDetailView({
  workspaceId,
  jobId,
  candidateId,
  onClose,
  onBackToLeaderboard,
  onFocusedReviewComplete
}:{
  workspaceId:string;
  jobId:string;
  candidateId:string;
  onClose?:()=>void;
  onBackToLeaderboard?:()=>void;
  onFocusedReviewComplete?:()=>void;
}){
  const [detail,setDetail]=useState<CandidateDetail|null>(null);
  const [error,setError]=useState<Error|null>(null);
  const [weighted,setWeighted]=useState<Ranking|null>(null);
  const [weightRevision,setWeightRevision]=useState<number|null>(null);
  const [focusedBusy,setFocusedBusy]=useState<string|null>(null);
  const [focusedNotice,setFocusedNotice]=useState<string|null>(null);
  const [history,setHistory]=useState<ReviewHistoryItem[]>([]);
  const [showHistory,setShowHistory]=useState(false);
  const [activeTab,setActiveTab]=useState<'all'|'verdicts'|'passages'>('all');
  const [compareCandidateIndex,setCompareCandidateIndex]=useState<number|null>(null);

  const reload=useCallback(()=>{
    void Promise.all([
      client.getCandidate(workspaceId,jobId,candidateId),
      client.candidateWeighted(workspaceId,jobId,candidateId),
      client.getReviewHistory(workspaceId,jobId,candidateId)
    ]).then(([candidate,weightedResult,historyItems])=>{
      if(candidate.result_revision!==weightedResult.resultRevision){
        setError(new Error('Assessment changed during loading. Refresh the candidate details.'));return;
      }
      setDetail(candidate);
      setWeighted(weightedResult.result);
      setWeightRevision(weightedResult.weightRevision);
      setHistory(historyItems);
      setError(null);
    }).catch((e:unknown)=>{setError(e instanceof Error?e:new Error('Candidate evidence not found'))});
  },[workspaceId,jobId,candidateId]);

  useEffect(()=>{
    reload();
    const refocus=()=>{if(!document.hidden)reload()};
    window.addEventListener('focus',refocus);
    return()=>window.removeEventListener('focus',refocus);
  },[reload]);

  const handleFocusedReview=async(reqId:string)=>{
    if(focusedBusy||!detail)return;
    setFocusedBusy(reqId);
    setFocusedNotice(null);
    try{
      const res=await client.runFocusedReview(workspaceId,jobId,candidateId,reqId,undefined,undefined,detail.result_revision);
      setFocusedNotice(`Focused review completed: ${res.new_verdict} (revision ${res.result_revision}). ${res.explanation}`);
      reload();
      onFocusedReviewComplete?.();
    }catch(e:unknown){
      setError(e instanceof Error?e:new Error('Focused review failed'));
    }finally{
      setFocusedBusy(null);
    }
  };

  if(error)return <ErrorState error={error}/>;
  if(!detail)return <Loading/>;

  return <>
    <Panel>
      <div className="eyebrow" style={{ marginBottom: 4 }}>INDIVIDUAL CANDIDATE REVIEW</div>
      <h2 style={{ margin: '0 0 4px 0' }}>Final JD-to-CV assessment</h2>
      <p className="small text-muted" style={{ margin: '0 0 16px 0' }}>
        Inspect each candidate's decisions, supporting evidence, and reasoning.
      </p>

      <div className="card-header" style={{ padding: '12px 16px', background: 'var(--surface-strong)', borderRadius: 12, border: '1px solid var(--border-soft)' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16 }}>{detail.candidate.candidate_name}</h3>
          <span className="mono small text-muted">Document source: {detail.candidate.candidate_source}</span>
        </div>
        <div className="row" style={{gap:8}}>
          {onBackToLeaderboard ? (
            <Button size="small" kind="primary" onClick={onBackToLeaderboard}>
              <ArrowUpIcon size={13} style={{marginRight:4}} />Back to Leaderboard
            </Button>
          ) : null}
          <Status value={!weighted||weighted.weighted_score===null?'Assessment incomplete':
            'Weighted score '+weighted.weighted_score.toFixed(2)+'%'}/>
          {candidateId?<a className="btn small subtle" href={`/api/v1/workspaces/${workspaceId}/documents/${candidateId}/download`}>
            <DownloadIcon size={14} style={{marginRight:4}} />Download source</a>:null}
          {onClose?<Button size="small" onClick={onClose} aria-label="Close candidate evidence">
            <CloseIcon size={14} style={{marginRight:4}} />Close</Button>:null}
        </div>
      </div>

      <div className="candidate-metric-grid" style={{ marginTop: 14 }}>
        <div className="candidate-metric-box">
          <span className="metric-label">Weighted Score</span>
          <span className="metric-val">{weighted?.weighted_score!=null?`${weighted.weighted_score.toFixed(1)}%`:'—'}</span>
          <span className="metric-sub">{weighted?.rank?`Official Rank #${weighted.rank}`:'Incomplete'}</span>
        </div>
        <div className="candidate-metric-box">
          <span className="metric-label">JD Matched</span>
          <span className="metric-val">{detail.candidate.matched_required + detail.candidate.matched_preferred} / {detail.candidate.total_required + detail.candidate.total_preferred}</span>
          <span className="metric-sub">Verified Found criteria</span>
        </div>
        <div className="candidate-metric-box">
          <span className="metric-label">Transferable</span>
          <span className="metric-val">{detail.final.Transferable ?? 0}</span>
          <span className="metric-sub">Not counted as matched</span>
        </div>
        <div className="candidate-metric-box">
          <span className="metric-label">Required / Preferred</span>
          <span className="metric-val" style={{ fontSize: 18 }}>{detail.candidate.matched_required}/{detail.candidate.total_required} · {detail.candidate.matched_preferred}/{detail.candidate.total_preferred}</span>
          <span className="metric-sub">Engine: {detail.candidate.evaluation_mode}</span>
        </div>
      </div>

      <div className="small" style={{marginTop:12,color:'var(--text-muted)'}}>
        Scoring projection revision {weightRevision??'not ready'} · Primary engine score {detail.candidate.primary_score===null?'unavailable':detail.candidate.primary_score.toFixed(2)+'%'} · Official weighted rank {weighted?.rank===null||!weighted?'unavailable':'#'+weighted.rank}
      </div>

      {/* Deduplicated candidate-level operational notices (omitting per-criterion trace repeats) */}
      {(() => {
        const rawNotices = [
          ...(detail.candidate.errors || []),
          ...(detail.final.Notices || [])
        ];
        const unique = Array.from(new Set(rawNotices)).filter(msg =>
          !msg.includes('contradicted the declared source relationship') &&
          !msg.includes('education ambiguous') &&
          !msg.includes('unresolved after grouped correction')
        );
        if (!unique.length) return null;
        return <Message kind="warn" style={{ marginTop: 12 }}>{unique.slice(0, 3).join(' · ')}</Message>;
      })()}
      {focusedNotice ? <Message kind="success" style={{ marginTop: 12 }}>{focusedNotice}</Message> : null}

      {/* EVIDENCE-BASED RANKING EXPLANATION (Image 1) */}
      {detail.ranking_reasoning ? (
        <div className="evidence-explanation-block" style={{ marginTop: 20 }}>
          <div className="section-eyebrow">EVIDENCE-BASED RANKING EXPLANATION</div>
          <h2 className="section-title" style={{ margin: '4px 0 6px 0' }}>Why this CV received its ranking</h2>
          <p className="section-subtitle" style={{ margin: '0 0 16px 0', color: 'var(--text-muted)' }}>
            What helped this candidate's score, and what held it back.
          </p>

          {/* ASSESSMENT SUMMARY CARD */}
          <div className="assessment-summary-card">
            <div className="summary-card-header">
              <span className="summary-card-eyebrow">ASSESSMENT SUMMARY</span>
              <span className="summary-card-rank-badge mono">
                Rank #{detail.ranking_reasoning.rank ?? '—'} · {detail.ranking_reasoning.score != null ? `${detail.ranking_reasoning.score.toFixed(2)}%` : '—'}
              </span>
            </div>
            <div className="summary-candidate-title">
              {detail.candidate.candidate_name} · ranking rationale
            </div>
            <p className="summary-rationale-text">
              {detail.ranking_reasoning.summary}
            </p>
          </div>

          {/* TWO COLUMNS: WHAT HELPED vs WHAT REDUCED THE MATCH */}
          <div className="score-factors-grid" style={{ marginTop: 18 }}>
            <div className="score-factor-column positive">
              <div className="factor-column-header positive">
                <span className="factor-check-icon">✓</span> WHAT HELPED THIS CV
              </div>
              <div className="factor-cards-list">
                {detail.ranking_reasoning.strengths.length > 0 ? (
                  detail.ranking_reasoning.strengths.map((item, idx) => (
                    <div key={idx} className="factor-card positive">
                      <div className="factor-card-title">{item.requirement}</div>
                      <div className="factor-card-points positive mono">
                        +{item.points != null ? item.points.toFixed(2) : '0.00'} points
                      </div>
                      <div className="factor-card-why">{item.why}</div>
                    </div>
                  ))
                ) : (
                  <div className="factor-card-empty">No positive points earned from verified Found criteria.</div>
                )}
              </div>
            </div>

            <div className="score-factor-column negative">
              <div className="factor-column-header negative">
                <span className="factor-cross-icon">◇</span> WHAT REDUCED THE MATCH
              </div>
              <div className="factor-cards-list">
                {detail.ranking_reasoning.gaps.length > 0 ? (
                  detail.ranking_reasoning.gaps.map((item, idx) => (
                    <div key={idx} className="factor-card negative">
                      <div className="factor-card-title">{item.requirement}</div>
                      <div className="factor-card-points negative mono">
                        {item.points != null ? item.points.toFixed(2) : '0.00'} points unearned
                      </div>
                      <div className="factor-card-why">{item.why}</div>
                    </div>
                  ))
                ) : (
                  <div className="factor-card-empty">No unmet criteria identified.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {/* HEAD-TO-HEAD COMPARISON (Image 2) */}
      {(() => {
        if (!detail.ranking_reasoning) return null;
        const comps = detail.ranking_reasoning.all_comparisons || [];
        const activeComp = comps.length > 0
          ? (comps.find(c => c.against_candidate_index === compareCandidateIndex) || comps[0])
          : null;
        const hasAdvantages = (activeComp?.top_candidate_advantages?.length ?? 0) > 0 ||
          (activeComp?.other_candidate_advantages?.length ?? 0) > 0 ||
          detail.ranking_reasoning.top_candidate_advantages.length > 0;

        if (!activeComp && !hasAdvantages && !detail.ranking_reasoning.head_to_head_summary) {
          return null;
        }

        const scoreDiff = activeComp?.score_gap ?? detail.ranking_reasoning.score_gap;
        const leaderAdvantages = activeComp?.top_candidate_advantages ?? detail.ranking_reasoning.top_candidate_advantages;
        const otherAdvantages = activeComp?.other_candidate_advantages ?? detail.ranking_reasoning.other_candidate_advantages;

        return (
          <div className="head-to-head-block" style={{ marginTop: 28, marginBottom: 20 }}>
            <div className="section-eyebrow">HEAD-TO-HEAD COMPARISON</div>
            <h2 className="section-title" style={{ margin: '4px 0 6px 0' }}>
              {detail.ranking_reasoning.rank === 1 ? 'Why this candidate ranks first' : 'Head-to-head comparative analysis'}
            </h2>
            <p className="head-to-head-summary-text" style={{ margin: '0 0 16px 0', color: 'var(--text-secondary)' }}>
              {detail.ranking_reasoning.head_to_head_summary}
            </p>

            {comps.length > 1 ? (
              <div className="head-to-head-selector-row" style={{ marginBottom: 14 }}>
                <label htmlFor="compare-candidate-select" className="compare-label" style={{ marginRight: 8, fontSize: 13, fontWeight: 600 }}>
                  Compare against
                </label>
                <select
                  id="compare-candidate-select"
                  className="compare-select"
                  value={activeComp?.against_candidate_index ?? ''}
                  onChange={(e) => setCompareCandidateIndex(Number(e.target.value))}
                >
                  {comps.map((c) => (
                    <option key={c.against_candidate_index} value={c.against_candidate_index}>
                      {c.against} {c.rank ? `(Rank #${c.rank})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {scoreDiff != null ? (
              <div className="score-diff-banner">
                <div className="score-diff-label">Weighted score difference</div>
                <div className="score-diff-number mono">
                  {scoreDiff.toFixed(2)} points
                </div>
              </div>
            ) : null}

            <div className="head-to-head-columns-grid">
              <div className="head-to-head-column">
                <h3 className="comparison-col-title">
                  Where the leader has additional verified matches
                </h3>
                <div className="comparison-items-list">
                  {leaderAdvantages.length > 0 ? (
                    leaderAdvantages.map((item, idx) => (
                      <div key={idx} className="comparison-advantage-item">
                        <span className="advantage-req-name font-bold">{item.requirement}</span>
                        {item.points != null ? <span className="advantage-points mono"> · {item.points.toFixed(2)} points</span> : null}
                        <span className="advantage-sep"> — </span>
                        <span className="advantage-why">{item.why}</span>
                      </div>
                    ))
                  ) : (
                    <div className="comparison-empty-text">No additional Found requirements in this comparison.</div>
                  )}
                </div>
              </div>

              <div className="head-to-head-column">
                <h3 className="comparison-col-title">
                  Where the other candidate has additional verified matches
                </h3>
                <div className="comparison-items-list">
                  {otherAdvantages.length > 0 ? (
                    otherAdvantages.map((item, idx) => (
                      <div key={idx} className="comparison-advantage-item">
                        <span className="advantage-req-name font-bold">{item.requirement}</span>
                        {item.points != null ? <span className="advantage-points mono"> · {item.points.toFixed(2)} points</span> : null}
                        <span className="advantage-sep"> — </span>
                        <span className="advantage-why">{item.why}</span>
                      </div>
                    ))
                  ) : (
                    <div className="comparison-empty-text">No additional Found requirements in this comparison.</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      <div className="detail-subnav">
        <button type="button" className={`detail-subnav-btn ${activeTab==='all'?'active':''}`} onClick={()=>setActiveTab('all')}>
          Stacked View (All Sections)
        </button>
        <button type="button" className={`detail-subnav-btn ${activeTab==='verdicts'?'active':''}`} onClick={()=>setActiveTab('verdicts')}>
          Requirement Verdicts ({detail.final.Criteria.length})
        </button>
        <button type="button" className={`detail-subnav-btn ${activeTab==='passages'?'active':''}`} onClick={()=>setActiveTab('passages')}>
          Original Extracted Passages ({detail.original_segments.length})
        </button>
      </div>
    </Panel>

    {activeTab==='all'||activeTab==='verdicts'?<Panel>
      <div className="card-header">
        <h2>Requirement verdicts and reasoning</h2>
        <span className="small text-muted">{detail.final.Criteria.length} evaluated criteria</span>
      </div>
      <div className="criteria-cards-list">
        {detail.final.Criteria.map(row=><div className="criterion-verdict-card" key={row.ID}>
          <div className="criterion-header">
            <div className="criterion-title-wrap">
              <span className="criterion-id-tag mono">{row.ID}</span>
              <h3 className="criterion-title">{row.Requirement}</h3>
            </div>
            <Status value={row.Result}/>
          </div>
          <div className="criterion-tags">
            <span className={`badge small ${row.Priority.toLowerCase()==='required'?'primary':''}`}>{row.Priority}</span>
            <span className="badge small">{row.Kind}</span>
            <span className="badge small text-muted">{row['Evidence level']}</span>
            <span className={`badge small ${row['Review recommended'] ? 'warning' : 'subtle'}`}>
              {row['Review recommended'] ? 'Review suggested' : 'Source assessed'}
            </span>
          </div>
          <div className="criterion-body">
            <div className="criterion-section-label">Assessment Reasoning</div>
            <p className="criterion-why-text">{row.Why}</p>
          </div>
          {row['JD source']?<details className="criterion-jd-quote">
            <summary className="criterion-jd-summary">Original employer requirement</summary>
            <blockquote className="criterion-quote-content">{row['JD source']}</blockquote>
          </details>:null}
          {row['Processing state']!=='completed'&&row['Processing state']!=='legacy'?<Message kind="warn">
            Processing: {row['Processing state']} · {row['Failure code']||'No completed result'}
          </Message>:null}
          {row.Checkpoints.length?<div className="criterion-checkpoints">
            <div className="criterion-section-label">Cited CV Evidence ({row.Checkpoints.length})</div>
            <div className="checkpoints-list">
              {row.Checkpoints.map(source=><div className="checkpoint-item" key={source.Segment}>
                <div className="checkpoint-header">
                  <span className="badge small mono">{source.Segment}</span>
                  <span className="checkpoint-section">{source.Section}</span>
                  <span className={`checkpoint-status ${source['Validated against CV']?'valid':'review'}`}>
                    {source['Validated against CV']?'✓ Matched original source':'Citation requires review'}
                  </span>
                </div>
                <blockquote className="checkpoint-text">{source.Text}</blockquote>
              </div>)}
            </div>
          </div>:<p className="small text-muted" style={{margin:'8px 0 0'}}>No affirmative source citation is recorded for this criterion.</p>}
          <div className="criterion-actions">
            <Button size="small" disabled={focusedBusy===row.ID} onClick={()=>void handleFocusedReview(row.ID)}>
              {focusedBusy===row.ID?'Evaluating...':'Focused review'}
            </Button>
          </div>
        </div>)}
      </div>

      {history.length?<div style={{marginTop:20,paddingTop:16,borderTop:'1px solid var(--border-soft)'}}>
        <Button size="small" onClick={()=>setShowHistory(v=>!v)}>
          {showHistory?'Hide review history':'Show review history ('+history.length+')'}
        </Button>
        {showHistory?<div style={{marginTop:12}}>
          {history.map(item=><div className="why" key={item.id} style={{marginBottom:8}}>
            <strong>{item.requirement_id}: {item.prior_verdict} <ArrowRightIcon size={12} style={{margin:'0 4px',display:'inline-block'}} /> {item.new_verdict}</strong>
            <p className="small">{dateString(item.created)} · {item.explanation}</p>
          </div>)}
        </div>:null}
      </div>:null}
    </Panel>:null}

    {activeTab==='all'||activeTab==='passages'?<Panel className="extracted-passages-panel" id="extracted-cv-passages">
      <div className="card-header">
        <div>
          <h2>Original extracted CV passages</h2>
          <span className="small text-muted">{detail.original_segments.length} verified candidate text segments extracted from source document</span>
        </div>
        {candidateId?<a className="btn small subtle" href={`/api/v1/workspaces/${workspaceId}/documents/${candidateId}/download`}>
          <DownloadIcon size={14} style={{marginRight:4}} />Download source</a>:null}
      </div>
      {detail.original_segments.length?<div className="passages-stream">
        {detail.original_segments.map(source=><div className="passage-card" key={source.segment_id}>
          <div className="passage-header">
            <span className="badge small mono">{source.segment_id}</span>
            <span className="passage-section-tag">{source.section}</span>
          </div>
          <div className="passage-body">{source.text}</div>
        </div>)}
      </div>:<Blank title="No original segments" description="Source extraction coverage may be incomplete; do not infer absence from missing material."/>}
    </Panel>:null}
  </>;
}

export function CandidatePage(){
 const {workspaceId}=useWorkspace();const {jobId,candidateId}=useParams<{jobId:string;candidateId:string}>();
 return <><PageHeader title="Candidate details & Why" description="Original cited evidence, three completed verdicts, and separate technical processing states."
    actions={jobId?<ActionLink to={workspacePath(workspaceId,'rankings',{jobId})}>Back to rankings</ActionLink>:null}/>
    {jobId&&candidateId?<CandidateDetailView key={`${jobId}:${candidateId}`} workspaceId={workspaceId} jobId={jobId} candidateId={candidateId}/>:
      <Blank title="Candidate not specified" description="Return to rankings and choose a candidate to inspect."/>}
 </>;
}

export function ReportsPage(){
 const {workspaceId,data,refresh}=useWorkspace();const [busy,setBusy]=useState(false);const [error,setError]=useState<Error|null>(null);
 const [notice,setNotice]=useState('');
 const [retentionDays,setRetentionDays]=useState(30);
 const [retention,setRetention]=useState<RetentionSummary|null>(null);

 useEffect(()=>{
  let mounted=true;
  client.getRetentionSummary(workspaceId,retentionDays).then(res=>{
    if(mounted)setRetention(res);
  }).catch(()=>{/* optional retention summary */});
  return()=>{mounted=false};
 },[workspaceId,retentionDays]);

 const doAction=async(task:()=>Promise<void>)=>{
  if(busy)return;setBusy(true);setError(null);setNotice('');
  try{await task();await refresh()}catch(e:unknown){setError(e instanceof Error?e:new Error('Action failed'))}finally{setBusy(false)}
 };

 const purgeOldData=async()=>{
  if(confirmDestructive(`data older than ${retentionDays} days`)){
    void doAction(async()=>{
      const res=await client.purgeRetention(workspaceId,retentionDays);
      setNotice(`Retention purge completed: ${res.purged_jobs} jobs, ${res.purged_exports} exports, ${res.purged_documents} documents purged.`);
      const updated=await client.getRetentionSummary(workspaceId,retentionDays);
      setRetention(updated);
    });
  }
 };

 const importReport=(files:FileList|null)=>{
  if(!files?.length)return;const file=files[0];
  void doAction(async()=>{await client.importHistory(workspaceId,file);setNotice('Historical report archived read-only, not revalidated under the current protocol.')});
 };
 return <><PageHeader title="Saved results & exports" description="Resume durable jobs, download exact result revisions, and inspect historical imports without reprocessing them."/>
  {error?<ErrorState error={error}/>:null}{notice?<Message kind="success">{notice}</Message>:null}
  <Panel><h2>Saved assessment jobs</h2>{data.jobs.length?<div className="table-scroller"><table>
    <thead><tr><th>Job</th><th>Created</th><th>Progress</th><th>State</th><th>Job Controls & Details</th></tr></thead>
    <tbody>{data.jobs.map(job=><tr key={job.id}><td><strong>{job.kind==='assess'?'Candidate assessment':'JD extraction'}</strong><br/>
      <small className="mono">{job.id.slice(0,12)}</small></td><td>{dateString(job.created)}</td><td>{job.progress}/{job.total}</td>
      <td><Status value={job.state}/></td><td><div className="toolbar" style={{gap:6}}>
        <ActionLink size="small" to={workspacePath(workspaceId,'progress',{jobId:job.id})}>Progress</ActionLink>
        {job.kind==='assess'?<ActionLink size="small" to={workspacePath(workspaceId,'rankings',{jobId:job.id})}>Rankings</ActionLink>:null}
        <Button kind="danger" size="small" disabled={busy} onClick={()=>{
         if(confirmDestructive('saved job '+job.id.slice(0,8)))void doAction(async()=>{
           await client.removeJob(workspaceId,job.id);
           startDistinctIntent(workspaceId,job.kind==='assess'?'assess':'jd_extract');
           setNotice('Saved job, candidate results and associated exports deleted.');
         })}}>Delete</Button>
      </div></td></tr>)}</tbody></table></div>:
      <Blank title="No saved jobs" description="Start a JD extraction or candidate assessment."/>}</Panel>
  <Panel><h2>Generated ZIP reports</h2>{data.exports.length?<div className="table-scroller"><table><thead>
    <tr><th>Created</th><th>Result revision</th><th>Weight revision</th><th>Size</th><th>Export Actions</th></tr></thead><tbody>
    {data.exports.map(item=><tr key={item.id}><td>{dateString(item.created)}</td><td>{item.result_revision}</td>
      <td>{item.weight_revision}</td><td>{(item.size/1024).toFixed(1)} KB</td><td><div className="toolbar" style={{gap:6}}>
       <a className="btn small" href={`/api/v1/workspaces/${workspaceId}/exports/${item.id}/download`}>Download ZIP</a>
       <Button kind="danger" size="small" disabled={busy} onClick={()=>{if(confirmDestructive('export '+item.id.slice(0,8)))void doAction(async()=>{
         await client.removeExport(workspaceId,item.id);setNotice('Export record and file deleted. External backups are unaffected.')
       })}}>Delete</Button></div></td></tr>)}</tbody></table></div>:
       <Blank title="No exports" description="Export a completed assessment from its rankings page."/>}</Panel>
  <Panel><h2>Data Retention Policy & Purge Automation</h2>
    <p className="small">Configurable local retention. Active jobs and unknown provider deliveries are strictly protected from purge.</p>
    {retention?<div className="grid cols3" style={{marginTop:12,marginBottom:12}}>
      <div><small>Eligible terminal jobs</small><p>{retention.eligible_jobs}</p></div>
      <div><small>Eligible exports</small><p>{retention.eligible_exports}</p></div>
      <div><small>Protected active / unknown</small><p>{retention.protected_active_jobs+retention.protected_unknown_delivery_jobs}</p></div>
    </div>:null}
    <div className="toolbar" style={{alignItems:'flex-end'}}>
      <div style={{width:160}}>
        <FormField id="retention-days" label="Retention period (days)">
          <input id="retention-days" type="number" min={1} max={3650} value={retentionDays}
            onChange={e=>setRetentionDays(Math.max(1,parseInt(e.target.value)||30))}/>
        </FormField>
      </div>
      <Button kind="danger" disabled={busy} onClick={()=>void purgeOldData()}>
        Purge eligible data ({retentionDays}d)
      </Button>
    </div>
  </Panel>
  <Panel><h2>Historical assessment imports</h2><Message kind="warn">Imported historical results remain historical. Old results are never silently certified under protocol 58.</Message>
    <FormField id="historic-report" label="Import supported historical JSON or TextileHR ZIP"><input id="historic-report" type="file" accept=".json,.zip"
      onChange={e=>{importReport(e.currentTarget.files);e.currentTarget.value=''}}/></FormField>
    {data.history.map(item=><div className="step" key={item.id}><div style={{flex:1}}><strong>{item.source_name}</strong>
      <small>Source build {item.source_build} · {dateString(item.created)}</small></div><Status value="Historical"/></div>)}
  </Panel>
 </>;
}
