import { z } from 'zod';

export class ApiError extends Error {
  constructor(readonly status:number, readonly code:string, message:string) {super(message);this.name='ApiError';}
}

const workspace=z.object({id:z.string(),title:z.string(),revision:z.number(),created:z.string(),updated:z.string()});
const document=z.object({id:z.string(),workspace_id:z.string(),kind:z.enum(['cv','jd']),filename:z.string(),
  sha256:z.string(),byte_size:z.number(),extraction_state:z.string(),extraction_error:z.string().nullable().optional(),created:z.string()});
const state=z.enum(['queued','running','paused','completed','completed_with_errors','failed','cancelling','cancelled']);
const job=z.object({id:z.string(),workspace_id:z.string(),kind:z.enum(['jd_extract','assess']),state,
  request:z.record(z.string(),z.unknown()),progress:z.number(),total:z.number(),sequence:z.number(),
  result_revision:z.number(),cancel_requested:z.boolean(),error_code:z.string().nullable().optional(),
  error_message:z.string().nullable().optional(),eligible_at:z.number().nullable().optional(),
  created:z.string(),updated:z.string()});
const weightPolicy=z.object({experience:z.number(),education:z.number(),jd:z.number(),split_jd:z.boolean(),
  jd_view:z.string(),jd_allocation:z.enum(['pooled','weighted_split']),jd_required_share:z.number().nullable(),
  jd_preferred_share:z.number().nullable(),requirement_shares_percent_of_category:z.record(z.string(),z.number()),
  default_requirement_allocation:z.enum(['equal','custom'])});
const weights=z.object({revision:z.number(),body:weightPolicy});
const ranking=z.object({candidate_index:z.number(),candidate_id:z.string(),candidate:z.string(),
  weighted_score:z.number().nullable(),verified_floor:z.number().nullable(),provisional:z.boolean(),
  score_status:z.string(),unverified_count:z.number(),jd_overall:z.string(),required:z.string(),preferred:z.string(),
  experience:z.string(),education:z.string(),review:z.string(),rank:z.number().nullable(),
  breakdown:z.record(z.string(),z.unknown()),
  placement_reason:z.string().nullable().optional(),
  score_gap:z.number().nullable().optional()});
const exportRecord=z.object({id:z.string(),job_id:z.string(),workspace_id:z.string(),
  weight_revision:z.number(),result_revision:z.number(),size:z.number(),created:z.string()});
const historicalRecord=z.object({id:z.string(),workspace_id:z.string(),source_name:z.string(),
  source_build:z.string(),created:z.string()});
const segment=z.object({segment_id:z.string(),section:z.string(),text:z.string()});
const checkpoint=z.object({Segment:z.string(),Section:z.string(),Text:z.string(),
  Sources:z.array(z.string()),Why:z.array(z.string()),'Highlight terms':z.array(z.string()),
  'Validated against CV':z.boolean()});
const criterion=z.object({ID:z.string(),Requirement:z.string(),Priority:z.string(),
  Result:z.enum(['Found','Transferable','Not Found','Assessment incomplete','Unverified']),
  Why:z.string(),'JD source':z.string(),Kind:z.string(),'Evidence level':z.string(),
  Checkpoints:z.array(checkpoint),'Display checkpoints':z.array(checkpoint),
  'Review recommended':z.boolean(),'Processing state':z.string(),
  'Failure code':z.string().nullable()});
const candidate=z.object({candidate_name:z.string(),candidate_source:z.string(),primary_score:z.number().nullable(),
  matched_required:z.number(),total_required:z.number(),matched_preferred:z.number(),total_preferred:z.number(),
  evaluation_mode:z.string(),errors:z.array(z.string()).optional()}).passthrough();

const reasoningItem=z.union([
  z.object({
    requirement_id:z.string().default(''),
    requirement:z.string().default(''),
    priority:z.string().default(''),
    category:z.string().nullable().optional(),
    decision:z.string().default(''),
    points:z.number().nullable().optional(),
    why:z.string().default('')
  }),
  z.string().transform(str=>({
    requirement_id:'',
    requirement:str,
    priority:'',
    category:null,
    decision:'',
    points:null,
    why:''
  }))
]);
export type ReasoningItem=z.infer<typeof reasoningItem>;

const headToHeadComparison=z.object({
  against_candidate_index:z.number(),
  against:z.string(),
  rank:z.number().nullable().optional(),
  score_gap:z.number().nullable().optional(),
  top_candidate_advantages:z.array(reasoningItem).default([]),
  other_candidate_advantages:z.array(reasoningItem).default([]),
  is_tie:z.boolean().default(false)
});
export type HeadToHeadComparison=z.infer<typeof headToHeadComparison>;

const rankingReasoning=z.object({
  summary:z.string().default(''),
  placement_reason:z.string().default(''),
  rank:z.number().nullable().optional(),
  score:z.number().nullable().optional(),
  strengths:z.array(reasoningItem).default([]),
  gaps:z.array(reasoningItem).default([]),
  transferable:z.array(reasoningItem).default([]),
  head_to_head_summary:z.string().default(''),
  top_candidate_advantages:z.array(reasoningItem).default([]),
  other_candidate_advantages:z.array(reasoningItem).default([]),
  score_gap:z.number().nullable().optional(),
  all_comparisons:z.array(headToHeadComparison).default([])
}).optional().nullable();

export type CandidateRankingReasoning = z.infer<typeof rankingReasoning>;

const candidateDetail=z.object({result_revision:z.number(),candidate,final:z.object({Criteria:z.array(criterion),
  Candidate:z.string(),Notices:z.array(z.string()),'Run warnings':z.array(z.string()),
  Provisional:z.boolean(),'Required matched':z.number(),'Required total':z.number(),
  'Preferred matched':z.number(),'Preferred total':z.number(),
  Transferable:z.number(),'Processing incomplete':z.number()}).passthrough(),
  original_segments:z.array(segment),requirements:z.array(z.object({
    requirement_id:z.string(),name:z.string(),priority:z.string(),
    jd_evidence:z.string(),constraint:z.record(z.string(),z.unknown())
  }).passthrough()),
  ranking_reasoning:rankingReasoning});

const focusedReview=z.object({
  candidate_id:z.string(),requirement_id:z.string(),prior_verdict:z.string(),
  new_verdict:z.string(),explanation:z.string(),result_revision:z.number(),
  citations:z.array(z.record(z.string(),z.unknown())).default([])
});
const reviewHistoryItem=z.object({
  id:z.string(),job_id:z.string(),candidate_id:z.string(),requirement_id:z.string(),
  prior_verdict:z.string(),new_verdict:z.string(),explanation:z.string(),
  sources:z.array(z.record(z.string(),z.unknown())).default([]),created:z.string()
});
const semanticShadowItem=z.object({
  requirement_id:z.string(),candidate_id:z.string(),similarity:z.number(),
  finding:z.string(),source_segments:z.array(z.string()).default([])
});
const semanticShadow=z.object({
  ready:z.boolean(),scoring_unchanged:z.boolean(),notice:z.string(),
  items:z.array(semanticShadowItem).default([])
});
const tokenUsage=z.object({
  prompt_tokens:z.number().nullable().optional(),
  completion_tokens:z.number().nullable().optional(),
  total_tokens:z.number().nullable().optional()
});
const jobUsage=z.object({
  job_id:z.string(),provider:z.string(),model:z.string(),
  logical_model_calls:z.number(),actual_model_request_attempts:z.number(),
  token_usage:tokenUsage,estimated_cost_usd:z.number().nullable().optional(),
  cost_label:z.string(),reused_prompt_calls:z.number(),preserved_unknown:z.boolean()
});
const retentionSummary=z.object({
  workspace_id:z.string(),eligible_jobs:z.number(),eligible_exports:z.number(),
  eligible_documents:z.number(),protected_active_jobs:z.number(),
  protected_unknown_delivery_jobs:z.number(),default_retention_days:z.number()
});
const retentionPurgeResult=z.object({
  purged_jobs:z.number(),purged_exports:z.number(),
  purged_documents:z.number(),retention_days:z.number()
});

export type Workspace=z.infer<typeof workspace>;
export type Document=z.infer<typeof document>;
export type Job=z.infer<typeof job>;
export type Weights=z.infer<typeof weights>;
export type WeightPolicy=z.infer<typeof weightPolicy>;
export type Ranking=z.infer<typeof ranking>;
export type CandidateDetail=z.infer<typeof candidateDetail>;
export type ExportRecord=z.infer<typeof exportRecord>;
export type HistoricalRecord=z.infer<typeof historicalRecord>;
export type FocusedReview=z.infer<typeof focusedReview>;
export type ReviewHistoryItem=z.infer<typeof reviewHistoryItem>;
export type SemanticShadow=z.infer<typeof semanticShadow>;
export type JobUsage=z.infer<typeof jobUsage>;
export type RetentionSummary=z.infer<typeof retentionSummary>;
export type RetentionPurgeResult=z.infer<typeof retentionPurgeResult>;
export type JDRow={ID:string;Requirement:string;Priority:string;Type:string;'JD source':string;
  'Mandatory JD parts'?:string;'Alternative groups JSON'?:string;'Complete JD expression JSON'?:string;
  'Minimum years'?:number|null;'Degree level'?:string;'Field of study'?:string;
  'Evidence standard'?:string;'Duration subject'?:string};
export type JDDraft={id:string;workspace_id:string;document_id:string;revision:number;body:unknown;rows?:JDRow[]};
export type JDApproval={id:string;workspace_id:string;draft_id:string;revision:number;body:{requirements:Array<{
  requirement_id:string;name:string;priority:string;constraint?:unknown
}>;warnings?:string[]}};

const jdDraft=z.object({id:z.string(),workspace_id:z.string(),document_id:z.string(),revision:z.number(),
  body:z.unknown(),rows:z.array(z.object({ID:z.string(),Requirement:z.string(),Priority:z.string(),Type:z.string(),
    'JD source':z.string(),'Mandatory JD parts':z.string().optional(),
    'Alternative groups JSON':z.string().optional(), 'Complete JD expression JSON':z.string().optional(),
    'Minimum years':z.number().nonnegative().nullable().optional(),'Degree level':z.string().optional(),
    'Field of study':z.string().optional(), 'Evidence standard':z.string().optional(),
    'Duration subject':z.string().optional()}).passthrough()).optional()});
const approval=z.object({id:z.string(),workspace_id:z.string(),draft_id:z.string(),revision:z.number(),
  body:z.object({requirements:z.array(z.object({requirement_id:z.string(),name:z.string(),priority:z.string(),
    constraint:z.unknown().optional()}).passthrough()),warnings:z.array(z.string()).optional()}).passthrough()});

let csrf: string|null=null;
const API='/api/v1';
const object=z.record(z.string(),z.unknown());

export async function initializeSession():Promise<void>{
  const response=await fetch(API+'/session',{credentials:'same-origin',cache:'no-store'});
  if(!response.ok)throw new ApiError(response.status,'session_unavailable','Local session unavailable');
  const parsed=z.object({csrf_token:z.string()}).parse(await response.json());
  csrf=parsed.csrf_token;
}

async function request(path:string,options: {method?:'GET'|'POST'|'PUT'|'DELETE';body?:unknown;key?:string;signal?:AbortSignal} = {}):Promise<unknown> {
  const method=options.method??'GET';
  const headers:Record<string,string>={};
  if(method!=='GET'){
    if(csrf===null)throw new ApiError(401,'session_required','Reload to initialize local session');
    headers['X-CSRF-Token']=csrf;
    if(!(options.body instanceof FormData))headers['Content-Type']='application/json';
  }
  if(options.key)headers['Idempotency-Key']=options.key;
  const response=await fetch(API+path,{method,headers,signal:options.signal,credentials:'same-origin',cache:'no-store',
    body:options.body===undefined?undefined:options.body instanceof FormData?options.body:JSON.stringify(options.body)});
  const raw:unknown=await response.json().catch(()=>({code:'unreadable_response',message:'Service returned unreadable JSON'}));
  if(!response.ok){
    const parsed=z.object({code:z.string().default('http_error'),message:z.string().default('Request failed')}).safeParse(raw);
    throw new ApiError(response.status,parsed.success?parsed.data.code:'unexpected_response',
      parsed.success?parsed.data.message:`HTTP ${response.status}`);
  }
  return raw;
}
function ws(id:string):string{return '/workspaces/'+encodeURIComponent(id)}
function jpath(id:string,jid:string):string{return ws(id)+'/jobs/'+encodeURIComponent(jid)}

export const client={
  listWorkspaces:async():Promise<Workspace[]>=>z.object({items:z.array(workspace)}).parse(await request('/workspaces')).items,
  createWorkspace:async(title:string):Promise<Workspace>=>workspace.parse(await request('/workspaces',{method:'POST',body:{title}})),
  getWorkspace:async(id:string):Promise<Workspace>=>workspace.parse(await request(ws(id))),
  removeWorkspace:async(id:string):Promise<void>=>{
    z.object({deleted:z.string()}).parse(await request(ws(id),{method:'DELETE',body:{confirmation:'DELETE WORKSPACE'}}));
  },
  listDocuments:async(id:string):Promise<Document[]>=>z.object({items:z.array(document)}).parse(await request(ws(id)+'/documents')).items,
  upload:async(id:string,kind:'jd'|'cv',file:File):Promise<Document>=>{
    const form=new FormData();form.append('file',file,file.name);
    return document.parse(await request(ws(id)+'/documents?kind='+kind,{method:'POST',body:form}));
  },
  removeDocument:async(id:string,docId:string):Promise<void>=>{
    z.object({deleted:z.string()}).parse(await request(ws(id)+'/documents/'+encodeURIComponent(docId),
      {method:'DELETE',body:{confirmation:'DELETE'}}));
  },
  getJD:async(id:string):Promise<{draft:JDDraft|null;approved:JDApproval|null}>=>{
    const result=await request(ws(id)+'/jd');
    return z.object({draft:jdDraft.nullable(),approved:approval.nullable()}).parse(result);
  },
  getDraft:async(id:string,draftId:string):Promise<JDDraft>=>jdDraft.parse(await request(ws(id)+'/jd/drafts/'+encodeURIComponent(draftId))),
  startJD:async(id:string,documentId:string,settings:RunSettings,key:string):Promise<Job>=>job.parse(
    await request(ws(id)+'/jd/extraction-jobs',{method:'POST',key,body:{document_id:documentId,...settings}})),
  reviseJD:async(id:string,draftId:string,revision:number,rows:JDRow[]):Promise<JDDraft>=>jdDraft.parse(
    await request(ws(id)+'/jd/drafts/'+encodeURIComponent(draftId),{method:'PUT',body:{draft_id:draftId,revision,rows}})),
  approveJD:async(id:string,draftId:string,revision:number,rows:JDRow[]):Promise<JDApproval>=>approval.parse(
    await request(ws(id)+'/jd/approve',{method:'POST',body:{draft_id:draftId,revision,rows}})),
  getWeights:async(id:string):Promise<Weights>=>weights.parse(await request(ws(id)+'/weights')),
  saveWeights:async(id:string,revision:number,policy:WeightInput):Promise<Weights>=>weights.parse(
    await request(ws(id)+'/weights',{method:'PUT',body:{revision,weights:policy}})),
  rebalance:async(id:string,requirementId?:string,newShare?:number,shares?:Record<string,number>):Promise<Record<string,number>>=>z.object({shares:z.record(z.string(),z.number())}).parse(
    await request(ws(id)+'/weights/rebalance',{method:'POST',body:{requirement_id:requirementId,new_share:newShare,shares}})).shares,
  startAssessment:async(id:string,ids:string[],approvedRevisionId:string,settings:RunSettings,key:string):Promise<Job>=>job.parse(
    await request(ws(id)+'/assessment-jobs',{method:'POST',key,body:{candidate_ids:ids,approved_revision_id:approvedRevisionId,...settings}})),
  getSubmission:async(id:string,key:string):Promise<Job>=>job.parse(await request(ws(id)+'/submissions/'+encodeURIComponent(key))),
  listJobs:async(id:string):Promise<Job[]>=>z.object({items:z.array(job)}).parse(await request(ws(id)+'/jobs')).items,
  removeJob:async(id:string,jid:string):Promise<void>=>{
    z.object({deleted:z.string()}).parse(await request(jpath(id,jid),{method:'DELETE',body:{confirmation:'DELETE'}}));
  },
  getJob:async(id:string,jid:string):Promise<Job>=>job.parse(await request(jpath(id,jid))),
  controlJob:async(id:string,jid:string,action:'cancel'|'resume'):Promise<Job>=>job.parse(await request(jpath(id,jid)+'/'+action,{method:'POST',body:{}})),
  resolveUnknown:async(id:string,jid:string,choice:'inspect'|'accept_duplicate_risk',acknowledgement?:string):Promise<unknown>=>
    request(jpath(id,jid)+'/resolve-unknown',{method:'POST',body:{resolution:choice,acknowledgement}}),
  listRankings:async(id:string,jid:string,options?:{offset?:number;limit?:number;search?:string;
      expectedResultRevision?:number;expectedWeightRevision?:number}):Promise<{
      items:Ranking[];total:number;offset:number;limit:number;search:string;
      resultRevision:number|null;weightRevision:number|null;
      officialCount:number;unfinishedCount:number;
      comparativeSummary:string|null}>=>{
    const query=new URLSearchParams();
    if(options?.offset!==undefined)query.set('offset',String(options.offset));
    if(options?.limit!==undefined)query.set('limit',String(options.limit));
    if(options?.search)query.set('search',options.search);
    if(options?.expectedResultRevision!==undefined)query.set('expected_result_revision',String(options.expectedResultRevision));
    if(options?.expectedWeightRevision!==undefined)query.set('expected_weight_revision',String(options.expectedWeightRevision));
    const result=z.object({items:z.array(ranking),total:z.number(),offset:z.number(),limit:z.number(),
      search:z.string(),result_revision:z.number().nullable(),weight_revision:z.number().nullable(),
      official_count:z.number().optional().default(0),unfinished_count:z.number().optional().default(0),
      comparative_summary:z.string().nullable().optional()}).parse(
      await request(jpath(id,jid)+'/rankings?'+query.toString()));
    return {items:result.items,total:result.total,offset:result.offset,limit:result.limit,search:result.search,
      resultRevision:result.result_revision,weightRevision:result.weight_revision,
      officialCount:result.official_count,unfinishedCount:result.unfinished_count,
      comparativeSummary:result.comparative_summary??null};
  },
  candidateWeighted:async(id:string,jid:string,docId:string):Promise<{
      result:Ranking;resultRevision:number;weightRevision:number}>=>{
    const response=z.object({candidate_id:z.string(),result_revision:z.number(),weight_revision:z.number(),
      result:ranking}).parse(await request(jpath(id,jid)+'/candidates/'+encodeURIComponent(docId)+'/weighted'));
    return {result:response.result,resultRevision:response.result_revision,weightRevision:response.weight_revision};
  },
  getCandidate:async(id:string,jid:string,docId:string):Promise<CandidateDetail>=>
    candidateDetail.parse(await request(jpath(id,jid)+'/candidates/'+encodeURIComponent(docId))),
  listExports:async(id:string):Promise<ExportRecord[]>=>z.object({items:z.array(exportRecord)}).parse(await request(ws(id)+'/exports')).items,
  export:async(id:string,jid:string,resultRev:number,weightRev:number):Promise<ExportRecord>=>
    exportRecord.parse(await request(jpath(id,jid)+'/exports',{method:'POST',body:{revision:resultRev,weight_revision:weightRev}})),
  removeExport:async(id:string,eid:string):Promise<void>=>{
    z.object({deleted:z.string()}).parse(await request(ws(id)+'/exports/'+encodeURIComponent(eid),
      {method:'DELETE',body:{confirmation:'DELETE'}}));
  },
  listHistory:async(id:string):Promise<HistoricalRecord[]>=>z.object({items:z.array(historicalRecord)}).parse(
    await request(ws(id)+'/historical-reports')).items,
  importHistory:async(id:string,file:File):Promise<void>=>{
    const form=new FormData();form.append('file',file,file.name);
    await request(ws(id)+'/historical-reports',{method:'POST',body:form});
  },
  getSettings:async():Promise<Settings>=>settingsSchema.parse(await request('/settings')),
  eventHistory:async(id:string,jid:string,after=0):Promise<{items:JobEvent[];snapshot:Job}>=>{
    return z.object({items:z.array(event),snapshot:job}).parse(await request(jpath(id,jid)+'/event-history?after='+after));
  },
  runFocusedReview:async(id:string,jid:string,docId:string,reqId:string,provider?:string,useLlm?:boolean,expectedResultRevision?:number):Promise<FocusedReview>=>
    focusedReview.parse(await request(jpath(id,jid)+'/candidates/'+encodeURIComponent(docId)+'/focused-review',{
      method:'POST',body:{requirement_id:reqId,provider,use_llm:useLlm,expected_result_revision:expectedResultRevision}
    })),
  getReviewHistory:async(id:string,jid:string,docId:string):Promise<ReviewHistoryItem[]>=>
    z.object({items:z.array(reviewHistoryItem)}).parse(
      await request(jpath(id,jid)+'/candidates/'+encodeURIComponent(docId)+'/review-history')
    ).items,
  runSemanticShadow:async(id:string,jid:string,topK=5):Promise<SemanticShadow>=>
    semanticShadow.parse(await request(jpath(id,jid)+'/semantic-shadow',{
      method:'POST',body:{top_k:topK}
    })),
  getSemanticShadow:async(id:string,jid:string):Promise<SemanticShadow>=>
    semanticShadow.parse(await request(jpath(id,jid)+'/semantic-shadow')),
  getJobUsage:async(id:string,jid:string):Promise<JobUsage>=>
    jobUsage.parse(await request(jpath(id,jid)+'/usage')),
  getRetentionSummary:async(id:string,days=30):Promise<RetentionSummary>=>
    retentionSummary.parse(await request(ws(id)+'/retention?days='+days)),
  purgeRetention:async(id:string,days=30):Promise<RetentionPurgeResult>=>
    retentionPurgeResult.parse(await request(ws(id)+'/retention/purge',{
      method:'POST',body:{retention_days:days}
    }))
};

const event=z.object({job_id:z.string(),seq:z.number(),kind:z.string(),payload:object,created:z.string()});
export type JobEvent=z.infer<typeof event>;
export type RunSettings={provider:'ollama'|'openrouter';use_llm:boolean;unified:boolean;yake_top_k:number;
  openrouter_context_tokens?:number;openrouter_output_tokens?:number;openrouter_max_requests_per_assessment?:number};
export type WeightInput={experience:number;education:number;jd:number;split_jd:boolean;
  jd_allocation:'pooled'|'weighted_split';jd_required_share:number;
  requirement_shares_percent_of_category:Record<string,number>};
const settingsSchema=z.object({engine_build:z.string(),protocol:z.number(),available_providers:z.array(z.string()),
  configured_provider:z.string(),organization_name:z.string(),ollama_model:z.string(),openrouter_model:z.string(),
  openrouter_key_configured:z.boolean(),yake_top_k_default:z.number(),
  openrouter_context_tokens:z.number(),openrouter_output_tokens:z.number(),
  openrouter_max_requests_per_assessment:z.number(),local_only:z.boolean()});
export type Settings=z.infer<typeof settingsSchema>;

// Type-level check: these schemas must continue to match generated public DTO
// contracts from FastAPI, not privately invented application field names.
const _checkWorkspace:(v:Workspace)=>TextileHRApi.WorkspaceDTO = value=>value;
const _checkJob:(v:Job)=>TextileHRApi.JobSnapshotDTO = value=>value;
const _checkRanking:(v:Ranking)=>TextileHRApi.RankingDTO = value=>value;
const _checkWeight:(v:Weights)=>TextileHRApi.WeightsDTO = value=>value;
const _checkCandidate:(v:CandidateDetail)=>TextileHRApi.CandidateDetailDTO = value=>value;
const _checkFocusedReview:(v:FocusedReview)=>TextileHRApi.FocusedReviewDTO = value=>value;
const _checkJobUsage:(v:JobUsage)=>TextileHRApi.JobUsageDTO = value=>value;
const _checkRetentionSummary:(v:RetentionSummary)=>TextileHRApi.RetentionSummaryDTO = value=>value;
void [_checkWorkspace,_checkJob,_checkRanking,_checkWeight,_checkCandidate,_checkFocusedReview,_checkJobUsage,_checkRetentionSummary];
