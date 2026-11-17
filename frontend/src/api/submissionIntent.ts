/** Durable, opaque local UI operation intent. No CV, JD, secrets or settings stored. */
export type IntentKind = 'jd_extract' | 'assess';
export type SubmissionIntent = {
  version: 1;
  workspace: string;
  kind: IntentKind;
  fingerprint: string;
  key: string;
  state: 'pending' | 'accepted';
  created: number;
  jobId?: string;
};
const prefix = 'textilehr:submission-intent:v1:';
function locationFor(workspace:string,kind:IntentKind):string {return `${prefix}${workspace}:${kind}`;}
function epochFor(workspace:string,kind:IntentKind):string {return `${prefix}epoch:${workspace}:${kind}`;}
function jsonStable(value:unknown):string {
  if (Array.isArray(value)) return `[${value.map(jsonStable).join(',')}]`;
  if (value && typeof value === 'object') {
    const fields=Object.entries(value as Record<string,unknown>).sort(([a],[b])=>a<b?-1:a>b?1:0);
    return `{${fields.map(([key,item])=>`${JSON.stringify(key)}:${jsonStable(item)}`).join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}
async function sha256(value:string):Promise<string> {
  const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value));
  return Array.from(new Uint8Array(hash),part=>part.toString(16).padStart(2,'0')).join('');
}
/** Intent creation is deterministic across tabs; concurrent same requests share one key. */
export async function submissionIntent(workspace:string,kind:IntentKind,payload:unknown):Promise<SubmissionIntent> {
  const epoch=localStorage.getItem(epochFor(workspace,kind)) ?? '0';
  const fingerprint=await sha256(jsonStable({workspace,kind,payload,epoch}));
  const path=locationFor(workspace,kind);
  const old=readPendingIntent(workspace,kind);
  if (old?.fingerprint===fingerprint)return old;
  const intent:SubmissionIntent={version:1,workspace,kind,fingerprint,key:`ui-${fingerprint}`,state:'pending',created:Date.now()};
  // Contains only a hashed request identity and opaque key, not filenames or CV data.
  localStorage.setItem(path,JSON.stringify(intent));
  return intent;
}
export function readPendingIntent(workspace:string,kind:IntentKind):SubmissionIntent|null {
  try {
    const raw=localStorage.getItem(locationFor(workspace,kind));
    if (!raw)return null;
    const value:unknown=JSON.parse(raw);
    if (!value||typeof value!=='object')return null;
    const row=value as Partial<SubmissionIntent>;
    if (row.version!==1||row.workspace!==workspace||row.kind!==kind||
       typeof row.key!=='string'||!/^ui-[a-f0-9]{64}$/.test(row.key)||
       typeof row.fingerprint!=='string'||row.fingerprint.length!==64||
       (row.state!=='pending'&&row.state!=='accepted'))return null;
    return row as SubmissionIntent;
  }catch{return null;}
}
export function markAccepted(intent:SubmissionIntent,jobId:string):void {
  const latest=readPendingIntent(intent.workspace,intent.kind);
  if (latest?.key!==intent.key)return; // A newer intent must not be overwritten.
  localStorage.setItem(locationFor(intent.workspace,intent.kind),JSON.stringify({...intent,state:'accepted',jobId}));
}
/** Explicitly opt in to a *new* job for identical inputs; no implicit key rotation. */
export function startDistinctIntent(workspace:string,kind:IntentKind):void {
  const old=Number(localStorage.getItem(epochFor(workspace,kind))??'0');
  localStorage.setItem(epochFor(workspace,kind),String(Number.isSafeInteger(old)&&old>=0?old+1:1));
  localStorage.removeItem(locationFor(workspace,kind));
}

/** Resolve an accepted but unacknowledged submission *before* a new POST. */
export async function submitOnce<T extends {id:string}>(
  workspace:string, kind:IntentKind, payload:unknown,
  lookup:(key:string)=>Promise<T>, submit:(key:string)=>Promise<T>,
):Promise<T> {
  const intent=await submissionIntent(workspace,kind,payload);
  let missing=false;
  try {
    const existing=await lookup(intent.key);
    markAccepted(intent,existing.id);
    return existing;
  }catch(error:unknown) {
    // Only a definite HTTP 404 authorizes a new POST. A disconnected
    // lookup could mean the server already accepted the original request.
    missing=Boolean(error && typeof error==='object' && 'status' in error &&
      (error as {status:unknown}).status===404);
    if (!missing)throw error;
  }
  try {
    const job=await submit(intent.key);
    markAccepted(intent,job.id);
    return job;
  }catch(original:unknown) {
    // The POST response may have been lost after the DB transaction committed.
    // A read can recover the durable job without another assessment request.
    try {
      const job=await lookup(intent.key);
      markAccepted(intent,job.id);
      return job;
    }catch {throw original;}
  }
}
