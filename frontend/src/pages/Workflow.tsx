import {useCallback,useEffect,useState,useRef} from 'react';
import {useNavigate} from 'react-router-dom';
import {client} from '../api/client';
import {
  rowsToEditable,
  updateRowField,
  updateRowYearText,
  removeRow,
  moveRow,
  createEditableRow,
  editableToCanonical,
  hasRowValidationErrors,
} from '../api/jdRows';
import type {EditableJDRow} from '../api/jdRows';
import {readPendingIntent,startDistinctIntent,submitOnce,markAccepted} from '../api/submissionIntent';
import type {Document,JDRow,RunSettings,WeightInput,Weights} from '../api/client';
import {workspacePath} from '../router';
import {useWorkspace} from '../app';
import {ActionLink,Blank,Button,ErrorState,FormField,Message,PageHeader,Panel,Status,confirmDestructive} from '../components/ui';
import {ArrowUpIcon,ArrowDownIcon,PlusIcon} from '../components/icons';

export function useAction(){
  const [busy,setBusy]=useState(false);const [error,setError]=useState<Error|null>(null);
  const lock=useRef(false);const [notice,setNotice]=useState('');
  const run=useCallback(async(action:()=>Promise<void>)=>{
    if(lock.current)return;lock.current=true;setBusy(true);setError(null);setNotice('');
    try{await action()}catch(e:unknown){setError(e instanceof Error?e:new Error('Action rejected'))}
    finally{lock.current=false;setBusy(false)}
  },[]);
  return {run,busy,error,notice,setNotice};
}

export function Feedback({error,notice}:{error:Error|null;notice:string}){
  return <>{error?<ErrorState error={error}/>:null}
    {notice?<Message kind="success">{notice}</Message>:null}</>;
}

export { client } from '../api/client';
export function DocumentsPage(){
  const {workspaceId,data,refresh}=useWorkspace();const action=useAction();
  const upload=async(kind:'cv'|'jd',files:FileList|null)=>{
    if(!files)return;
    await action.run(async()=>{
      let success=0;const issues:string[]=[];
      for(const file of Array.from(files))try{await client.upload(workspaceId,kind,file);success++}
        catch(e:unknown){issues.push(file.name+': '+(e instanceof Error?e.message:'upload failed'))}
      await refresh();
      action.setNotice(`${success} file(s) accepted.${issues.length?' Errors: '+issues.join('; '):''}`);
    });
  };
  const remove=(file:Document)=>void action.run(async()=>{
    if(!confirmDestructive(file.filename))return;
    await client.removeDocument(workspaceId,file.id);await refresh();action.setNotice('Unreferenced document deleted');
  });
  return <><PageHeader title="Documents & uploads" description="Original job descriptions and applicant CVs are stored with immutable, distinct source identifiers."/>
    <Feedback error={action.error} notice={action.notice}/>
    <div className="grid cols2" style={{marginBottom:19}}>{(['jd','cv'] as const).map(kind=><Panel key={kind}>
      <h2>{kind==='jd'?'Employer job description':'Candidate resumes'}</h2>
      <div className="drop"><strong>{kind==='jd'?'Upload the employer JD':'Upload candidate evidence'}</strong>
        <p>TXT · MD · PDF · DOCX · up to 20 MB per document</p>
        <FormField id={'upload-'+kind} label="Choose files">
          <input id={'upload-'+kind} type="file" accept=".txt,.md,.pdf,.docx" multiple={kind==='cv'}
            disabled={action.busy} onChange={e=>{void upload(kind,e.currentTarget.files);e.currentTarget.value=''}}/>
        </FormField></div></Panel>)}</div>
     <Panel><h2>Workspace documents</h2>{data.documents.length? <div className="table-scroller">
       <table><thead><tr><th scope="col">Original filename</th><th scope="col">Kind</th><th scope="col">Size</th>
         <th scope="col">Source ID</th><th scope="col">Actions</th></tr></thead><tbody>
         {data.documents.map(file=><tr key={file.id}><td><strong>{file.filename}</strong></td><td><Status value={file.kind.toUpperCase()}/></td>
           <td>{(file.byte_size/1024).toFixed(1)} KB</td><td className="mono small">{file.id.slice(0,12)}</td>
           <td><a className="btn small" href={`/api/v1/workspaces/${workspaceId}/documents/${file.id}/download`}>Original</a>
           {' '}<Button size="small" kind="danger" disabled={action.busy} onClick={()=>remove(file)}>Delete</Button></td></tr>)}</tbody></table></div>:
          <Blank title="No uploaded files" description="Begin by providing a job description and one or more CVs."/>}</Panel>
  </>;
}

function defaultRunSettings(provider:string):RunSettings{
  return {provider:provider==='openrouter'?'openrouter':'ollama',use_llm:true,unified:true,yake_top_k:40};
}

export function JDPage(){
  const {workspaceId,data,settings,refresh}=useWorkspace();const navigate=useNavigate();const action=useAction();
  const jds=data.documents.filter(file=>file.kind==='jd');
  const [selectedJD,setSelectedJD]=useState('');
  const activeJD=selectedJD || (jds.length ? jds[0].id : '');

  const [provider,setProvider]=useState<RunSettings['provider']>(settings.configured_provider==='openrouter'?'openrouter':'ollama');
  const [llm,setLLM]=useState(true);const [yake,setYake]=useState(settings.yake_top_k_default);

  const [draftRows,setDraftRows]=useState<EditableJDRow[]>([]);
  const [draftError,setDraftError]=useState<Error|null>(null);
  const [editingDraftId,setEditingDraftId]=useState<string|null>(null);
  const [dirty,setDirty]=useState(false);
  const [reloadCount,reloadDraft]=useState(0);

  const reloadRequested=useRef(false);
  const lastLoad=useRef(0);
  const dirtyRef=useRef(false);
  const editingRef=useRef<string|null>(null);

  // Derived stale draft detection: user made local edits to a revision that is no longer current on the server
  const isStaleDraft = Boolean(dirty && editingDraftId && data.draft && editingDraftId !== data.draft.id);

  useEffect(()=>{
    let mounted=true;
    const pending=readPendingIntent(workspaceId,'jd_extract');
    if (pending?.state==='pending')void client.getSubmission(workspaceId,pending.key)
      .then(job=>{markAccepted(pending,job.id);if(mounted)navigate(workspacePath(workspaceId,'progress',{jobId:job.id}))})
      .catch(()=>{/* Keep the original key; a retry must not create a new intent. */});
    return()=>{mounted=false};
  },[workspaceId,navigate]);

  useEffect(()=>{
    void refresh();
    const onFocus=()=>{if(!document.hidden)void refresh()};
    window.addEventListener('focus',onFocus);
    return()=>window.removeEventListener('focus',onFocus);
  },[refresh]);

  useEffect(()=>{
    const server=data.draft;
    if(!server)return;
    if(dirtyRef.current&&editingRef.current&&editingRef.current!==server.id){
      return;
    }
    if(editingRef.current===server.id&&!reloadRequested.current)return;
    const token=++lastLoad.current;let live=true;
    void client.getDraft(workspaceId,server.id).then(result=>{
      if(!live||lastLoad.current!==token)return;
      if(dirtyRef.current&&editingRef.current&&editingRef.current!==server.id){return}
      const rows=rowsToEditable(result.rows??[]);
      setDraftRows(rows);
      editingRef.current=server.id;setEditingDraftId(server.id);
      reloadRequested.current=false;dirtyRef.current=false;setDirty(false);setDraftError(null);
    }).catch((e:unknown)=>{if(live)setDraftError(e instanceof Error?e:new Error('Cannot load JD draft'))});
    return()=>{live=false};
  },[workspaceId,data.draft,reloadCount]);

  const modifyField = (clientKey: string, field: keyof JDRow, value: string) => {
    dirtyRef.current=true;setDirty(true);
    setDraftRows(rows=>updateRowField(rows, clientKey, field, value));
  };

  const modifyYears = (clientKey: string, text: string) => {
    dirtyRef.current=true;setDirty(true);
    setDraftRows(rows=>updateRowYearText(rows, clientKey, text));
  };

  const removeCriterion = (clientKey: string) => {
    dirtyRef.current=true;setDirty(true);
    setDraftRows(rows=>removeRow(rows, clientKey));
  };

  const moveCriterion = (fromIndex: number, toIndex: number) => {
    dirtyRef.current=true;setDirty(true);
    setDraftRows(rows=>moveRow(rows, fromIndex, toIndex));
  };

  const addCriterion = () => {
    dirtyRef.current=true;setDirty(true);
    setDraftRows(rows=>[...rows, createEditableRow({
      ID: '',
      Requirement: '',
      Priority: 'required',
      Type: 'skill',
      'JD source': ''
    })]);
  };

  const forceReload=()=>{
    reloadRequested.current=true;
    dirtyRef.current=false;
    editingRef.current=null;
    setDirty(false);
    reloadDraft(n=>n+1);
  };

  useEffect(()=>{
    if(!dirty)return;
    const beforeUnload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=''};
    const intercept=(event:MouseEvent)=>{
      const target=event.target;
      if(!(target instanceof Element))return;
      const link=target.closest('a[href]') as HTMLAnchorElement|null;
      if(!link||new URL(link.href).origin!==window.location.origin)return;
      if(!window.confirm('Discard unsaved JD review changes?')){
        event.preventDefault();event.stopPropagation();
      }
    };
    window.addEventListener('beforeunload',beforeUnload);
    document.addEventListener('click',intercept,true);
    return()=>{window.removeEventListener('beforeunload',beforeUnload);document.removeEventListener('click',intercept,true)};
  },[dirty]);

  const outgoingRows=():JDRow[]=>{
    if(hasRowValidationErrors(draftRows)){
      throw new Error('Please resolve highlighted minimum experience validation errors before saving.');
    }
    return editableToCanonical(draftRows);
  };

  const start=()=>void action.run(async()=>{
    if(!activeJD)throw new Error('Choose a JD');
    const request={document_id:activeJD,provider,use_llm:llm,unified:false,yake_top_k:yake};
    const job=await submitOnce(workspaceId,'jd_extract',request,
      key=>client.getSubmission(workspaceId,key),
      key=>client.startJD(workspaceId,activeJD,request,key));
    navigate(workspacePath(workspaceId,'progress',{jobId:job.id}));
  });

  const save=(approve:boolean)=>void action.run(async()=>{
    if(!data.draft||!editingDraftId)throw new Error('Extract a JD first');
    if(isStaleDraft||data.draft.id!==editingDraftId)
      throw new Error('A newer JD draft exists. Reload and review before modifying it.');
    const rows=outgoingRows();
    if(approve){
      if(dirty&&data.approved?.draft_id===data.draft.id)
        throw new Error('This JD is already frozen. Save a new draft revision before approving changes.');
      await client.approveJD(workspaceId,editingDraftId,data.draft.revision,rows);
      dirtyRef.current=false;setDirty(false);
      await refresh();navigate(workspacePath(workspaceId,'weights'));
    }else{
      await client.reviseJD(workspaceId,editingDraftId,data.draft.revision,rows);
      dirtyRef.current=false;editingRef.current=null;setDirty(false);
      await refresh();action.setNotice('New draft revision saved. Review it before approval.');
    }
  });

  return <><PageHeader title="JD extraction, review & approval"
    description="Validate all employer-stated obligations against original source quotations before freezing a JD revision."/>
    <Feedback error={action.error??draftError} notice={action.notice}/>
    {isStaleDraft?<Message kind="warn">A newer JD revision was published while you were editing. Your unsaved edits are preserved locally; reload the server revision before another save. <Button onClick={forceReload}>Discard edits and load latest</Button></Message>:null}
    {dirty&&!isStaleDraft?<Message kind="warn">Unsaved JD review changes. Save a successor revision before navigating away.</Message>:null}
    <Panel><h2>Source and extraction settings</h2><div className="grid cols3">
     <FormField id="jd-source" label="Job description"><select id="jd-source" value={activeJD} onChange={e=>setSelectedJD(e.target.value)}>
       <option value="">Choose uploaded JD</option>{jds.map(d=><option key={d.id} value={d.id}>{d.filename}</option>)}</select></FormField>
     <FormField id="jd-model" label="Provider"><select id="jd-model" value={provider} onChange={e=>setProvider(e.target.value as RunSettings['provider'])}>
        <option value="ollama">Ollama · local</option><option value="openrouter">OpenRouter · cloud</option></select></FormField>
     <FormField id="yake-count" label="YAKE candidates"><input type="number" id="yake-count" min={1} max={150} value={yake}
        onChange={e=>setYake(Number(e.target.value))}/></FormField>
    </div><label className="row"><input type="checkbox" checked={llm} onChange={e=>setLLM(e.target.checked)}/>
        Enable LLM-based JD extraction</label>
    <div className="toolbar" style={{marginTop:14}}><Button kind="primary" disabled={!activeJD||action.busy} onClick={start}>Extract JD in worker</Button>
      <Button onClick={()=>{startDistinctIntent(workspaceId,'jd_extract');action.setNotice('A separate extraction intent has been created. Click Extract to submit.') }}>
        New independent extraction</Button>
      <ActionLink to={workspacePath(workspaceId,'uploads')}>Upload additional JD</ActionLink></div></Panel>
    {data.draft?<Panel className="review-panel"><div className="card-header"><h2>Review requirement meaning</h2><Status value={'Draft '+data.draft.revision}/></div>
     <p>Required, Preferred and unresolved priorities must reflect employer wording. Experience and education restrictions and compound AND/OR obligations stay source-bound.</p>
     {draftRows.map((row,index)=><div className="why" key={row._clientKey}>
       <div className="card-header"><strong>{row.ID||'NEW'} · Requirement {index+1}</strong><Status value={row.Priority}/></div>
       <div className="stack" style={{gap: 12}}>
         <FormField id={`req-${row._clientKey}`} label="Requirement text">
           <textarea id={`req-${row._clientKey}`} rows={2} style={{minHeight: 54}} value={row.Requirement} onChange={e=>modifyField(row._clientKey,'Requirement',e.target.value)}/>
         </FormField>
         <div className="grid cols2">
           <FormField id={`prio-${row._clientKey}`} label="Priority">
             <select id={`prio-${row._clientKey}`} value={row.Priority} onChange={e=>modifyField(row._clientKey,'Priority',e.target.value)}>
               <option value="required">Required</option>
               <option value="preferred">Preferred</option>
               <option value="unknown">Unknown — supervisor review</option>
             </select>
           </FormField>
           <FormField id={`kind-${row._clientKey}`} label="Requirement type">
             <select id={`kind-${row._clientKey}`} value={row.Type} onChange={e=>modifyField(row._clientKey,'Type',e.target.value)}>
               {['skill','experience','education','certification','license','responsibility','eligibility','other'].map(t=><option value={t} key={t}>{t}</option>)}
             </select>
           </FormField>
         </div>
         <FormField id={`source-${row._clientKey}`} label="Exact employer quotation">
           <textarea id={`source-${row._clientKey}`} rows={2} style={{minHeight: 54}} value={row['JD source']} onChange={e=>modifyField(row._clientKey,'JD source',e.target.value)}/>
         </FormField>
       </div>
        <details><summary>Approved compound conditions and qualification constraints</summary>
         <div className="grid cols2"><FormField id={`mandatory-${row._clientKey}`} label="Mandatory JD parts ( | separated)">
          <textarea id={`mandatory-${row._clientKey}`} value={row['Mandatory JD parts']??''}
            onChange={e=>modifyField(row._clientKey,'Mandatory JD parts',e.target.value)}/></FormField>
          <FormField id={`alts-${row._clientKey}`} label="Alternative groups (JSON)"><textarea id={`alts-${row._clientKey}`}
            value={row['Alternative groups JSON']??''} onChange={e=>modifyField(row._clientKey,'Alternative groups JSON',e.target.value)}/></FormField>
          <FormField id={`expr-${row._clientKey}`} label="Complete condition expression (JSON)"><textarea id={`expr-${row._clientKey}`}
            value={row['Complete JD expression JSON']??''} onChange={e=>modifyField(row._clientKey,'Complete JD expression JSON',e.target.value)}/></FormField>
          <div><FormField id={`minimum-years-${row._clientKey}`} label="Minimum experience (years; blank = derive from JD)">
            <input id={`minimum-years-${row._clientKey}`} inputMode="decimal" value={row.yearText}
              onChange={e=>modifyYears(row._clientKey,e.target.value)} />
            </FormField>
            {row.yearError?<p className="small" style={{color:'var(--color-danger, #ef4444)',marginTop:4}}>{row.yearError}</p>:null}
            <strong>Degree level / field</strong><p>{row['Degree level']||'—'} · {row['Field of study']||'—'}</p></div>
         </div></details>
         <div className="toolbar" style={{marginTop:8}}>
           <Button size="small" kind="danger" disabled={draftRows.length<=1} onClick={()=>removeCriterion(row._clientKey)}>Remove criterion</Button>
           <Button size="small" disabled={index===0} onClick={()=>moveCriterion(index,index-1)}><ArrowUpIcon size={13} style={{marginRight:4}} />Move up</Button>
           <Button size="small" disabled={index===draftRows.length-1} onClick={()=>moveCriterion(index,index+1)}><ArrowDownIcon size={13} style={{marginRight:4}} />Move down</Button>
         </div>
       </div>)}
       <div className="toolbar" style={{ marginTop: 20, marginBottom: 8, gap: 12 }}>
         <Button onClick={addCriterion}><PlusIcon size={14} style={{marginRight:6}} />Add source-backed criterion</Button>
       <Button disabled={action.busy||draftRows.length===0||isStaleDraft} onClick={()=>save(false)}>Save new revision</Button>
       <Button kind="primary" disabled={action.busy||draftRows.length===0||isStaleDraft||Boolean(dirty&&data.approved?.draft_id===data.draft.id)} onClick={()=>save(true)}>Approve and freeze JD</Button>
       </div>
    </Panel>:<div style={{marginTop:18}}><Blank title="No extracted JD draft" description="Choose a source, then use the worker to extract employer requirements."/></div>}
    {data.approved?<Message kind="success">Approved revision {data.approved.revision}: {data.approved.body.requirements.length} frozen criteria.
      Existing jobs retain the revision they started with.</Message>:null}
  </>;
}

export function WeightEditor({
  current,
  workspaceId,
  refresh,
  action,
  requirements
}:{
  current:Weights;
  workspaceId:string;
  refresh:()=>Promise<void>;
  action:ReturnType<typeof useAction>;
  requirements:Array<{requirement_id:string;name:string;priority:string}>;
}){
  const [draft,setDraft]=useState<WeightInput>(()=>({
    experience:current.body.experience,
    education:current.body.education,
    jd:current.body.jd,
    split_jd:current.body.split_jd,
    jd_allocation:current.body.jd_allocation,
    jd_required_share:current.body.jd_required_share??80,
    requirement_shares_percent_of_category:{...current.body.requirement_shares_percent_of_category}
  }));

  const total=draft.experience+draft.education+draft.jd;
  const change=(key:keyof WeightInput,value:WeightInput[keyof WeightInput])=>setDraft(w=>({...w,[key]:value}));
  const save=()=>void action.run(async()=>{
    await client.saveWeights(workspaceId,current.revision,draft);
    await refresh();
    action.setNotice('Saved authoritative weight projection; no model assessment was dispatched.');
  });
  const rebalance=(id:string,value:number)=>void action.run(async()=>{
    const shares=await client.rebalance(workspaceId,id,value,draft.requirement_shares_percent_of_category);
    setDraft(w=>({...w,requirement_shares_percent_of_category:shares}));
  });
  const even=()=>void action.run(async()=>{
    const shares=await client.rebalance(workspaceId);
    setDraft(w=>({...w,requirement_shares_percent_of_category:shares}));
  });

  const getCategory = (req: (typeof requirements)[0]): 'experience' | 'education' | 'jd' => {
    const c = (req as { constraint?: { kind?: string } }).constraint;
    if (c?.kind === 'experience') return 'experience';
    if (c?.kind === 'education') return 'education';
    const lower = req.name.toLowerCase();
    if (lower.includes('years of') || lower.includes('years professional') || lower.includes('full-time professional experience')) return 'experience';
    if (lower.includes("bachelor's") || lower.includes("master's") || lower.includes('degree') || lower.includes('bachelor') || lower.includes('phd')) return 'education';
    return 'jd';
  };

  const byCategory = {
    experience: requirements.filter(r => getCategory(r) === 'experience'),
    education: requirements.filter(r => getCategory(r) === 'education'),
    jd: requirements.filter(r => getCategory(r) === 'jd'),
  };

  const categoryWeights = {
    experience: draft.experience,
    education: draft.education,
    jd: draft.jd,
  };

  const activeWeight = (byCategory.experience.length ? categoryWeights.experience : 0) +
                       (byCategory.education.length ? categoryWeights.education : 0) +
                       (byCategory.jd.length ? categoryWeights.jd : 0);

  const calculatePotential = (req: (typeof requirements)[0], cat: 'experience' | 'education' | 'jd', share: number) => {
    const catEntries = byCategory[cat];
    if (!catEntries.length || activeWeight <= 0) return 0;
    if (cat === 'jd' && draft.jd_allocation === 'weighted_split') {
      const isReq = req.priority.toLowerCase() === 'required';
      const sameGroup = catEntries.filter(r => (r.priority.toLowerCase() === 'required') === isReq);
      const sameGroupSum = sameGroup.reduce((acc, r) => {
        const s = draft.requirement_shares_percent_of_category[r.requirement_id] ?? (100.0 / catEntries.length);
        return acc + s;
      }, 0);
      const selected = draft.jd_required_share ?? 80;
      const groupAlloc = isReq ? selected : (100 - selected);
      const hasReq = catEntries.some(r => r.priority.toLowerCase() === 'required');
      const hasPref = catEntries.some(r => r.priority.toLowerCase() !== 'required');
      const activeAlloc = (hasReq ? selected : 0) + (hasPref ? (100 - selected) : 0);
      const normGroupAlloc = activeAlloc > 0 ? (groupAlloc / activeAlloc) : 1;
      return (100.0 * categoryWeights[cat] / activeWeight) * normGroupAlloc * (sameGroupSum > 0 ? (share / sameGroupSum) : 0);
    }
    return (100.0 * categoryWeights[cat] / activeWeight) * (share / 100.0);
  };

  return <>
    <Panel><div className="card-header"><h2>Category weights</h2><Status value={'Revision '+current.revision}/></div>
     <div className="grid cols3">{(['experience','education','jd'] as const).map(key=><FormField key={key} id={'weight-'+key}
       label={(key==='jd'?'Other JD criteria':key==='education'?'Education':'Experience')+' (%)'}>
       <input id={'weight-'+key} type="number" min={0} max={100} step={1} value={draft[key]}
        onChange={e=>change(key,Number(e.target.value))}/></FormField>)}</div>
     <Message kind={total===100?'success':'warn'}>Category total: {total}%. Must equal 100%.</Message>
     <div className="grid cols2"><FormField id="weight-policy" label="JD allocation policy"><select id="weight-policy"
         value={draft.jd_allocation} onChange={e=>change('jd_allocation',e.target.value as WeightInput['jd_allocation'])}>
         <option value="pooled">Combined Required + Preferred</option><option value="weighted_split">Explicit Required/Preferred split</option>
       </select></FormField>
       {draft.jd_allocation==='weighted_split'?<FormField id="weight-required" label="Required share (%)">
        <input id="weight-required" type="number" min={0} max={100} step={1} value={draft.jd_required_share}
          onChange={e=>change('jd_required_share',Number(e.target.value))}/></FormField>:null}</div></Panel>
     <Panel>
       <div className="card-header">
         <div>
           <div className="eyebrow" style={{ marginBottom: 4 }}>Review & prioritize</div>
           <h2 style={{ margin: '0 0 4px 0' }}>Step 5 · Edit individual JD allocations</h2>
           <p className="small text-muted" style={{ margin: 0 }}>
             Give individual requirements more or less influence within their category.
           </p>
         </div>
       </div>

       <div style={{ marginTop: 12, padding: '12px 14px', background: 'var(--bg-soft)', borderRadius: 10, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
         Changing one share automatically rebalances the other items in its category. Items keep their reviewed shares of their category. In pooled mode, Required and Preferred share one Requirements pool; in weighted-split mode, their groups receive the selected allocation before item shares are normalized.
       </div>

       <div className="allocation-categories-container" style={{ marginTop: 18 }}>
         {(['experience', 'education', 'jd'] as const).map(cat => {
           const entries = byCategory[cat];
           if (!entries.length) return null;
           const catLabel = cat === 'jd' ? 'Jd' : cat.charAt(0).toUpperCase() + cat.slice(1);
           return (
             <div key={cat} className="allocation-category-card" style={{ marginBottom: 18 }}>
               <div className="allocation-category-header font-bold" style={{ fontSize: 14, marginBottom: 10, color: 'var(--text-primary)' }}>
                 {catLabel} · {entries.length} requirement(s) · 100% of this category
               </div>
               <div className="allocation-items-list" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                 {entries.map(req => {
                   const defaultShare = Number((100.0 / entries.length).toFixed(2));
                   const currentShare = draft.requirement_shares_percent_of_category[req.requirement_id] ?? defaultShare;
                   const potential = calculatePotential(req, cat, currentShare);

                   return (
                     <div
                       key={req.requirement_id}
                       className="allocation-item-card"
                       style={{
                         display: 'flex',
                         alignItems: 'center',
                         justifyContent: 'space-between',
                         gap: 16,
                         padding: '12px 16px',
                         background: 'var(--surface-strong)',
                         border: '1px solid var(--border-soft)',
                         borderRadius: 10,
                       }}
                     >
                       <div className="allocation-item-info" style={{ flex: 1, minWidth: 0 }}>
                         <div className="allocation-item-title" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                           <span className="mono" style={{ color: 'var(--text-muted)', marginRight: 6 }}>{req.requirement_id}</span>
                           <span>{req.name}</span>
                           {cat === 'jd' ? (
                             <span className="badge small" style={{ marginLeft: 8 }}>
                               {req.priority.charAt(0).toUpperCase() + req.priority.slice(1)}
                             </span>
                           ) : null}
                         </div>
                         <div className="allocation-item-potential mono" style={{ fontSize: 12, color: 'var(--accent)', marginTop: 4 }}>
                           Possible overall score: {potential.toFixed(2)} / 100 points
                         </div>
                       </div>

                       <div className="allocation-item-stepper" style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                         <button
                           type="button"
                           className="stepper-btn"
                           disabled={action.busy || entries.length === 1}
                           onClick={() => {
                             const nextVal = Math.max(0, Math.round((currentShare - 1) * 100) / 100);
                             rebalance(req.requirement_id, nextVal);
                           }}
                           aria-label="Decrease share"
                         >
                           −
                         </button>
                         <input
                           type="number"
                           className="stepper-input mono"
                           aria-label={`Share of ${req.name}`}
                           min={0}
                           max={100}
                           step={0.01}
                           value={Number(currentShare.toFixed(2))}
                           onChange={e => {
                             const val = Number(e.target.value);
                             setDraft(w => ({
                               ...w,
                               requirement_shares_percent_of_category: {
                                 ...w.requirement_shares_percent_of_category,
                                 [req.requirement_id]: val,
                               },
                             }));
                           }}
                           onBlur={e => {
                             const val = Number(e.target.value);
                             if (Number.isFinite(val)) {
                               rebalance(req.requirement_id, val);
                             }
                           }}
                         />
                         <button
                           type="button"
                           className="stepper-btn"
                           disabled={action.busy || entries.length === 1}
                           onClick={() => {
                             const nextVal = Math.min(100, Math.round((currentShare + 1) * 100) / 100);
                             rebalance(req.requirement_id, nextVal);
                           }}
                           aria-label="Increase share"
                         >
                           +
                         </button>
                       </div>
                     </div>
                   );
                 })}
               </div>
             </div>
           );
         })}
       </div>
     </Panel>
     <div className="toolbar" style={{ marginTop: 24, marginBottom: 44, gap: 12 }}>
       <Button disabled={action.busy} onClick={even}>Reset to equal shares</Button>
       <Button kind="primary" disabled={action.busy||total!==100} onClick={save}>Save weight revision</Button>
       <ActionLink
         to={workspacePath(workspaceId,'run')}
         style={{
           border: '1.5px solid var(--brand-green)',
           color: 'var(--brand-green)',
           background: 'transparent',
           fontWeight: 600,
           borderRadius: 8,
           padding: '9px 18px',
           display: 'inline-flex',
           alignItems: 'center',
           minHeight: 40,
           textDecoration: 'none'
         }}
       >
         Proceed to assessment &rarr;
       </ActionLink>
     </div>
  </>;
}

export function WeightsPage(){
  const {workspaceId,data,refresh}=useWorkspace();const action=useAction();
  const current=data.weights;
  if(!current)return <><PageHeader title="Weight allocation" description="Use the engine's existing weighting policy."/><Blank title="No weights ready" description="Load or approve a JD first."/></>;
  const requirements=data.approved?.body.requirements??[];

  return <><PageHeader title="Weight allocation" description="Recalculate scores from existing verified decisions; weight changes never call the assessment provider."/>
   <Feedback error={action.error} notice={action.notice}/>
   {!data.approved?<Blank title="Approve JD first" description="A frozen JD is required for individual requirement shares."/>:
     <WeightEditor key={`${workspaceId}:${current.revision}`} current={current} workspaceId={workspaceId} refresh={refresh} action={action} requirements={requirements} />}
  </>;
}

export function AssessmentPage(){
  const {workspaceId,data,settings}=useWorkspace();const navigate=useNavigate();const action=useAction();
  const [selected,setSelected]=useState<string[]>([]);
  const [config,setConfig]=useState<RunSettings>(()=>defaultRunSettings(settings.configured_provider));
  const cvs=data.documents.filter(d=>d.kind==='cv');
  useEffect(()=>{
    let mounted=true;
    const pending=readPendingIntent(workspaceId,'assess');
    if (pending?.state==='pending')void client.getSubmission(workspaceId,pending.key)
      .then(job=>{markAccepted(pending,job.id);if(mounted)navigate(workspacePath(workspaceId,'progress',{jobId:job.id}))})
      .catch(()=>{/* Not found or offline: retain the key for an explicit retry. */});
    return()=>{mounted=false};
  },[workspaceId,navigate]);
  const start=()=>void action.run(async()=>{
    if(!data.approved)throw new Error('Approve the JD before assessment');
    if(!selected.length)throw new Error('Select at least one CV');
    const request={candidate_ids:selected,approved_revision_id:data.approved.id,...config};
    const result=await submitOnce(workspaceId,'assess',request,
      key=>client.getSubmission(workspaceId,key),
      key=>client.startAssessment(workspaceId,selected,data.approved!.id,config,key));
    navigate(workspacePath(workspaceId,'progress',{jobId:result.id}));
  });
  return <><PageHeader title="New candidate assessment" description="Submit a bounded batch with frozen JD meaning and model settings. The worker runs independently of your browser."/>
    <Feedback error={action.error} notice={action.notice}/><div className="split">
    <Panel><div className="card-header"><h2>Candidate CVs</h2><Status value={`${selected.length} selected`}/></div>
      {cvs.length?cvs.map(doc=><label className="step row" key={doc.id}>
        <input type="checkbox" checked={selected.includes(doc.id)} onChange={e=>setSelected(previous=>e.target.checked?
           [...new Set([...previous,doc.id])]:previous.filter(id=>id!==doc.id))}/>
        <span><strong>{doc.filename}</strong><small className="mono">{doc.id.slice(0,12)}</small></span>
      </label>):<Blank title="No CVs yet" description="Upload one or more candidate documents before creating an assessment."/>}
      <div className="toolbar" style={{marginTop:14}}><Button size="small" onClick={()=>setSelected(cvs.map(c=>c.id))}>Select all</Button>
        <Button size="small" onClick={()=>setSelected([])}>Clear</Button></div>
    </Panel><div className="stack"><Panel><h2>Assessment configuration</h2>
      <FormField id="run-provider" label="Model provider"><select id="run-provider" value={config.provider}
       onChange={e=>setConfig(v=>({...v,provider:e.target.value as RunSettings['provider']}))}>
       <option value="ollama">Local Ollama</option><option value="openrouter">OpenRouter cloud</option></select></FormField>
      <details style={{marginTop:12}}><summary style={{cursor:'pointer',fontWeight:600,fontSize:13,color:'var(--accent)'}}>Engine and evaluation settings</summary>
        <div style={{marginTop:12,display:'grid',gap:12}}>
          <label className="row"><input type="checkbox" checked={config.use_llm} onChange={e=>setConfig(v=>({...v,use_llm:e.target.checked,unified:e.target.checked&&v.unified}))}/>
            Enable AI evaluation</label>
          <label className="row"><input type="checkbox" checked={config.unified}
            disabled={!config.use_llm} onChange={e=>setConfig(v=>({...v,unified:e.target.checked}))}/>Unified assessment mode</label>
          <FormField id="run-yake" label="YAKE candidate-phrase limit"><input type="number" id="run-yake" min={1} max={150}
            value={config.yake_top_k} onChange={e=>setConfig(v=>({...v,yake_top_k:Number(e.target.value)}))}/></FormField>
          {config.provider==='openrouter'&&config.use_llm?<>
            <Message kind="warn">Cloud mode can transmit authorized applicant evidence and incur charges. Limits cannot exceed server safety settings.</Message>
            <div className="grid cols2">
             <FormField id="cloud-context" label="Context token ceiling"><input id="cloud-context" type="number" min={2048}
               max={settings.openrouter_context_tokens} value={config.openrouter_context_tokens??settings.openrouter_context_tokens}
               onChange={e=>setConfig(v=>({...v,openrouter_context_tokens:Number(e.target.value)}))}/></FormField>
             <FormField id="cloud-output" label="Output token ceiling"><input id="cloud-output" type="number" min={1}
               max={settings.openrouter_output_tokens} value={config.openrouter_output_tokens??settings.openrouter_output_tokens}
               onChange={e=>setConfig(v=>({...v,openrouter_output_tokens:Number(e.target.value)}))}/></FormField>
             <FormField id="cloud-requests" label="Maximum requests per assessment"><input id="cloud-requests" type="number" min={1}
               max={settings.openrouter_max_requests_per_assessment}
               value={config.openrouter_max_requests_per_assessment??settings.openrouter_max_requests_per_assessment}
               onChange={e=>setConfig(v=>({...v,openrouter_max_requests_per_assessment:Number(e.target.value)}))}/></FormField>
            </div>
          </>:null}
        </div>
      </details>
    </Panel><Panel><h2>Submission summary</h2><div className="step"><strong>Approved JD revision</strong><Status value={data.approved?String(data.approved.revision):'Not approved'}/></div>
       <div className="step"><strong>Candidate files</strong>{selected.length}</div>
       <div className="toolbar" style={{ marginTop: 18, marginBottom: 14, gap: 12 }}>
         <Button kind="primary" disabled={action.busy||selected.length===0||!data.approved} onClick={start}>Start assessment</Button>
         <Button disabled={action.busy} onClick={()=>{startDistinctIntent(workspaceId,'assess');action.setNotice('A new independent run has been authorized; submit again to create it.')}}>Create separate run with same inputs</Button>
       </div>
       <p className="help" style={{ marginTop: 12, lineHeight: 1.5 }}>The same submission intent always reopens its existing job, including after a lost response or browser restart. Explicitly create a separate run to reassess identical inputs. Refresh, theme and progress never start assessment calls.</p>
    </Panel></div></div>
  </>;
}
