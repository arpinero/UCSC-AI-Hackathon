<script lang="ts">
  import {Clock3, FileText, ShieldCheck} from '@lucide/svelte';
  import ResponseBody from './ResponseBody.svelte';
  import CodeBlock from './CodeBlock.svelte';
  import {summary, friendly} from './api';
  let {proposal,role,seconds,evidenceIds=[],onEvidence}: {proposal:any;role:string;seconds:number;evidenceIds:string[];onEvidence:()=>void}=$props();
  let citations=$derived([...new Set<string>([...(proposal.evidence_ids||[]),...(proposal.actions||[]).flatMap((action:any)=>action.evidence_ids||[])])].filter(id=>evidenceIds.includes(id)));
</script>
<ResponseBody content={summary(proposal)} {evidenceIds}/>
{#if proposal.actions?.length}<div class="output-section-label">{role==='fixing'?'Proposed changes':'Proposed controls'}</div><div class="proposed-actions">{#each proposal.actions as action}<div class="proposed-action"><div class="action-title"><strong>{friendly(action.kind)}</strong><code>{action.target_id}</code>{#if action.ttl_minutes}<span><Clock3 size={11}/>{action.ttl_minutes} min</span>{/if}</div>{#if action.reason}<ResponseBody content={action.reason} {evidenceIds}/>{/if}<div class="action-sources">{#each action.evidence_ids||[] as id}<button onclick={onEvidence}><FileText size={11}/>{id}</button>{/each}</div></div>{/each}</div>{/if}
{#if role==='forensics' && proposal.timeline?.length}<ol class="finding-timeline">{#each proposal.timeline as item}<li><div><span>{#each (item.evidence_ids||[item.evidence_id]).filter((id:string)=>id&&evidenceIds.includes(id)) as id}<button onclick={onEvidence}>{id}</button>{/each}</span>{#if item.timestamp}<time>{item.timestamp}</time>{/if}</div><ResponseBody content={item.observation||item.finding||''} {evidenceIds}/></li>{/each}</ol>{/if}
{#if role==='forensics' && proposal.api_findings?.uncertainties?.length}<details class="open-questions"><summary>Open questions <span>{proposal.api_findings.uncertainties.length}</span></summary><ul>{#each proposal.api_findings.uncertainties as uncertainty}<li><ResponseBody content={uncertainty} {evidenceIds}/></li>{/each}</ul></details>{/if}
{#if role==='compliance' && proposal.action_reviews?.length}<div class="policy-reviews">{#each proposal.action_reviews as item}<div><span class="policy-verdict" class:objection={item.stance!=='support'}><ShieldCheck size={12}/>{friendly(item.stance)}</span><code>{item.target_id}</code><ResponseBody content={item.reason||''} {evidenceIds}/></div>{/each}</div>{/if}
{#if citations.length}<div class="source-strip"><span>Sources</span>{#each citations as id}<button onclick={onEvidence}>{id}</button>{/each}</div>{/if}
<details class="response-details"><summary>Structured response <span>{seconds}s</span></summary><CodeBlock value={proposal}/></details>
