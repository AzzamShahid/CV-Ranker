/** Central direct/deep-link contract, independent of rendered navigation. */
export const ROUTES = {
  overview: '',
  uploads: 'uploads',
  jd: 'jd',
  weights: 'weights',
  run: 'run',
  progress: 'progress/:jobId',
  rankings: 'rankings/:jobId',
  candidate: 'candidate/:jobId/:candidateId',
  reports: 'reports',
  settings: 'settings',
} as const;

export type WorkspacePage = keyof typeof ROUTES;
export type RouteLocation =
  | { kind: 'workspaces' }
  | { kind: 'workspace'; page: WorkspacePage; workspaceId: string; jobId?: string; candidateId?: string }
  | { kind: 'not-found' };

const idPattern = /^[0-9A-Za-z_-]{1,150}$/;
const pageToPattern: Record<WorkspacePage,string> = ROUTES;

export function parseWorkspaceRoute(pathname: string): RouteLocation {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length === 0) return { kind: 'workspaces' };
  if (parts[0] !== 'w' || !idPattern.test(parts[1] ?? '')) return { kind: 'not-found' };
  const workspaceId = parts[1];
  if (parts.length === 2) return { kind: 'workspace',page:'overview',workspaceId };
  const rest = parts.slice(2);
  if(rest.length===1 && rest[0]==='overview')return {kind:'workspace',workspaceId,page:'overview'};
  for (const [page, pattern] of Object.entries(pageToPattern) as [WorkspacePage,string][]) {
    const patternParts=pattern.split('/').filter(Boolean);
    if (patternParts.length !== rest.length) continue;
    let jobId: string | undefined;
    let candidateId: string | undefined;
    let matched=true;
    for (let i=0;i<patternParts.length;i++) {
      const token=patternParts[i];
      if (token === ':jobId') {if (!idPattern.test(rest[i])) matched=false; else jobId=rest[i];}
      else if (token === ':candidateId') {if (!idPattern.test(rest[i])) matched=false; else candidateId=rest[i];}
      else if (token !== rest[i]) matched=false;
    }
    if (matched) return {kind:'workspace',workspaceId,page,jobId,candidateId};
  }
  return {kind:'not-found'};
}

export function workspacePath(workspaceId:string,page:WorkspacePage,
    params: {jobId?:string;candidateId?:string} = {}):string {
  if (!idPattern.test(workspaceId)) throw new Error('Invalid workspace identifier');
  const suffix=ROUTES[page].split('/').filter(Boolean).map(segment=>{
    if (!segment.startsWith(':')) return segment;
    const key=segment.slice(1) as 'jobId'|'candidateId';
    const value=params[key];
    if (!value || !idPattern.test(value)) throw new Error(`Invalid or missing ${key}`);
    return value;
  }).join('/');
  return `/w/${workspaceId}`+(suffix?`/${suffix}`:'');
}

export const NAV_ITEMS = [
  {page:'overview',label:'Overview',symbol:'◫'},
  {page:'uploads',label:'Documents & uploads',symbol:'⇧'},
  {page:'jd',label:'JD review',symbol:'▤'},
  {page:'weights',label:'Weight allocation',symbol:'◈'},
  {page:'run',label:'New assessment',symbol:'▷'},
  {page:'reports',label:'Saved results',symbol:'▥'},
  {page:'settings',label:'System & Storage',symbol:'⚙'},
] as const satisfies readonly {page:WorkspacePage;label:string;symbol:string}[];
