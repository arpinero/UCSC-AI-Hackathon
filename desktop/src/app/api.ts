export type Event = { id: number; time: string; type: string; data: any };
export type Run = { id: string; case_id: string; mode: 'mock'|'live'; status: string; created: string; events?: Event[]; pending?: any; result?: any };
export type Case = { id: string; title: string; family: string; evidence_count: number };
export function mergeEvents(existing: Event[], incoming: Event[]): Event[] {
  return [...new Map([...existing, ...incoming].map(event => [event.id, event])).values()].sort((a, b) => a.id - b.id);
}
export type DesktopAPI = {
  request: (path: string, body?: unknown) => Promise<any>;
  connection: () => Promise<string>;
  configure: (url: string) => Promise<string>;
  login: () => Promise<void>;
  notify: () => Promise<void>;
  exportReport: (data: unknown) => Promise<boolean>;
};
declare global { interface Window { sentinel?: DesktopAPI } }
let csrf = '';
export async function request(path: string, body?: unknown) {
  if (window.sentinel) return window.sentinel.request(path, body);
  const response = await fetch(path, { method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Sentinel-CSRF': csrf }, body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(path.endsWith('/chat') ? 250000 : 20000) });
  if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Bridge unavailable. Start python -m desktop.bridge on the pipeline host.');
  const result = await response.json();
  if (path === '/api/health') csrf = result.csrf_token || '';
  if (!response.ok) throw new Error(result.error || `Bridge returned ${response.status}`);
  return result;
}
export const roleNames: Record<string,string> = {containment:'Containment',forensics:'Forensics',compliance:'Compliance',fixing:'Recovery',telemetry:'Evidence monitor'};
export function friendly(value: string = '') { return value.replaceAll('_', ' ').replaceAll('-', ' '); }
export function summary(proposal: any): string {
  return proposal?.assessment || proposal?.reason || proposal?.summary || proposal?.rationale || proposal?.reasoning ||
    (proposal?.action_reviews ? `Reviewed ${proposal.action_reviews.length} proposed actions against compliance policy.` :
    proposal?.stance ? `${friendly(proposal.stance)} for the shared plan.` : 'Analysis returned. Open details to inspect the structured response.');
}
