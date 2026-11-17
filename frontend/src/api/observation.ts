/** Sequence/revision policy for replayable job observation; no provider calls. */
export interface VersionedSnapshot {id:string;sequence:number;result_revision:number;state:string;}
export const terminalStates=new Set(['completed','completed_with_errors','failed','cancelled']);
export function isTerminalJob(state:string):boolean {return terminalStates.has(state);}
export function newerSnapshot<T extends VersionedSnapshot>(previous:T|null,next:T):T {
  if (!previous || previous.id!==next.id)return next;
  if (next.sequence<previous.sequence)return previous;
  if (next.sequence===previous.sequence && next.result_revision<previous.result_revision)return previous;
  return next;
}
export function consumeSequence(last:number,incoming:number):number|null {
  if (!Number.isSafeInteger(incoming)||incoming<1||incoming<=last)return null;
  return incoming;
}
export function nextReconnectMs(consecutiveErrors:number):number {
  return Math.min(30000,1000*2**Math.max(0,Math.min(5,consecutiveErrors)));
}
