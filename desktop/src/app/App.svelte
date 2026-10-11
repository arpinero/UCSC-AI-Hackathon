<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { Shield, Plus, Search, ArrowUp, ArrowUpRight, ChevronDown, ChevronRight, Check, Circle, X, Settings2, Cpu, Radio, FileText, Fingerprint, ShieldCheck, Wrench, Activity, Bell, Layers, Download, Cable, TriangleAlert, Clock3, ArrowRight, PanelRightClose, PanelRightOpen, CheckCheck, MessageSquare, FolderOpen, LoaderCircle } from '@lucide/svelte';
  import Button from '../lib/ui/button.svelte';
  import Textarea from '../lib/ui/textarea.svelte';
  import Badge from '../lib/ui/badge.svelte';
  import { request, mergeEvents, roleNames, summary, friendly, type Run, type Event, type Case } from './api';
  let cases = $state<Case[]>([]), runs = $state<Run[]>([]), current = $state<Run|null>(null);
  let events = $state<Event[]>([]), models = $state<any>(null), connected = $state(false);
  let view = $state('activity'), modal = $state(''), input = $state(''), error = $state(''), search = $state('');
  let busy = $state(false), starting = $state(false), rail = $state(true), mode = $state<'mock'|'live'>('mock');
  let caseId = $state('mitre-T1041'), url = $state('http://127.0.0.1:8787'), decision = $state<'approve'|'reject'|null>(null);
  let pane: HTMLDivElement;
  let composer = $state<HTMLTextAreaElement|null>(null);
  let selectionVersion = 0, notified = '', pollInFlight = false, selectionLoading = false;
  const roles = ['containment','forensics','compliance','fixing'];
  const icons: Record<string, any> = {containment:Shield,forensics:Fingerprint,compliance:ShieldCheck,fixing:Wrench,telemetry:Radio};
  const roleNotes: Record<string,string> = {containment:'Limit the blast radius',forensics:'Preserve and trace evidence',compliance:'Review obligations & policy',fixing:'Restore with verification'};
  let incident = $derived([...events].reverse().find(e => ['incident','incident_updated'].includes(e.type))?.data.incident);
  let queued = $derived(runs.filter(r => r.status==='awaiting_approval'));
  let feed = $derived(events.filter(e => ['incident','agent_finished','agent_failed','message','approval_requested','human_decision','approval_expired','completed','error','chat'].includes(e.type)));
  let activeRole = $derived([...events].reverse().find(e => ['agent_started','agent_finished','agent_failed'].includes(e.type)));
  let running = $derived(current?.status === 'running');
  let messages = $derived(events.filter(e => e.type === 'agent_finished').length);
  let hasPending = $derived(!!current?.pending);
  let filteredRuns = $derived([...runs].reverse().filter(r => r.case_id.toLowerCase().includes(search.toLowerCase())));
  let result = $derived(current?.result);
  const time = (date:string) => new Date(date).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
  const formatNumber = (v:any) => typeof v === 'number' ? v.toLocaleString(undefined,{maximumFractionDigits:1}) : '—';
  function roleState(role:string) {
    const last = [...events].reverse().find(e => e.data.role === role && e.type.startsWith('agent_'));
    return last?.type === 'agent_started' ? 'Working' : last?.type === 'agent_failed' ? 'Failed' : last ? 'Reviewed' : 'Ready';
  }
  async function refresh() {
    try {
      const health = await request('/api/health');
      if (health.service !== 'sentinel-desktop-bridge') throw new Error('This address is a model server. Connect to the Sentinel bridge on port 8787.');
      connected = true;
      [cases, runs] = await Promise.all([request('/api/cases'), request('/api/runs')]);
    } catch (e:any) { connected = false; error = e.message; }
  }
  async function readModels() { try { models = await request('/api/models'); } catch { models = null; } }
  async function poll() {
    if (!current || pollInFlight || selectionLoading) return;
    pollInFlight = true;
    const id = current.id, version = selectionVersion;
    try {
      const update = await request(`/api/runs/${id}?after=${events.length}`);
      if (version !== selectionVersion || id !== current?.id) return;
      const nearEnd = !pane || pane.scrollHeight - pane.scrollTop - pane.clientHeight < 120;
      current = update; events = mergeEvents(events, update.events); connected = true;
      if (update.pending && notified !== update.pending.id) {
        notified = update.pending.id; window.sentinel?.notify();
      }
      if (nearEnd && update.events.length) { await tick(); pane?.scrollTo({top:pane.scrollHeight,behavior:'smooth'}); }
    } catch (e:any) { connected = false; error = e.message; }
    finally { pollInFlight = false; }
  }
  async function selectRun(run:Run) {
    const version = ++selectionVersion;
    selectionLoading = true;
    current = run; events = []; input = ''; decision = null; error = ''; view = 'activity';
    try { const data = await request(`/api/runs/${run.id}`); if (version === selectionVersion) {current=data; events=data.events;} }
    catch(e:any) {if (version === selectionVersion) error=e.message;}
    finally {if (version === selectionVersion) selectionLoading=false;}
  }
  async function start() {
    starting = true; error = '';
    try {
      const data = await request('/api/runs', {case_id:caseId,mode});
      await refresh(); const item = runs.find(r => r.id === data.id);
      if (item) await selectRun(item); modal='';
    } catch(e:any) {error=e.message;} finally { starting=false; }
  }
  function newIncident() { modal = 'new'; error=''; }
  function openDialog(element: HTMLDialogElement) {
    element.showModal();
    return { destroy() {element.close();} };
  }
  async function send() {
    if (!input.trim() || !current || busy) return;
    busy=true; error='';
    try {
      if (decision) {
        if (!current.pending) throw new Error('This checkpoint has closed. Review the current plan before deciding.');
        await request(`/api/runs/${current.id}/decision`, {approval_id:current.pending.id,decision,reason:input.trim()}); decision=null;
      } else await request(`/api/runs/${current.id}/chat`, {message:input.trim()});
      input=''; await poll();
    } catch(e:any) {error=e.message;} finally {busy=false;}
  }
  async function review(choice:'approve'|'reject') {decision=choice; input=''; view='activity'; await tick(); composer?.focus();}
  function ask(text:string) {input=text; composer?.focus();}
  async function exportReport() {
    if (!current) return;
    const data = {run:current,events};
    if (window.sentinel) { await window.sentinel.exportReport(data); return; }
    const blob = new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const href = URL.createObjectURL(blob); const a=document.createElement('a'); a.href=href; a.download=`sentinel-${current.case_id}.json`; a.click(); URL.revokeObjectURL(href);
  }
  async function connect() {
    error='';
    try {
      if (window.sentinel) url=await window.sentinel.configure(url);
      selectionVersion++; current=null; events=[]; runs=[];
      await refresh(); await readModels(); if (connected) modal='';
    } catch(e:any) {error=e.message;}
  }
  onMount(() => {
    let stopped=false, polling=false;
    if(window.sentinel) window.sentinel.connection().then(value => url=value); else url=window.location.origin;
    refresh().then(async()=>{
      const requestedId = new URLSearchParams(window.location.search).get('run');
      const selected = runs.find(r=>r.id===requestedId) || runs.find(r=>r.status==='awaiting_approval') || runs.find(r=>r.status==='running');
      if(selected)await selectRun(selected);
      await readModels();
    });
    const timer=setInterval(async() => {if(polling||stopped)return; polling=true; try{await poll();}finally{polling=false;}},900);
    const statusTimer=setInterval(() => { if(!stopped) refresh(); },10000);
    const modelTimer=setInterval(() => { if(!stopped) readModels(); },30000);
    return () => {stopped=true; clearInterval(timer);clearInterval(statusTimer);clearInterval(modelTimer);};
  });
</script>

<div class="workspace">
  <aside class="sidebar">
    <div class="brand"><span class="brand-mark"><Shield size={19} strokeWidth={1.6}/></span><span>sentinel<span class="brand-dot">.</span></span><span class="edition">WEB</span></div>
    <button class="workspace-picker" onclick={() => modal='connection'}><span class="workspace-avatar">IR</span><span>Incident response<small>UCSC security workspace</small></span><ChevronDown size={14}/></button>
    <Button class="new-button" onclick={newIncident}><Plus size={16}/> New investigation <span class="keycap">N</span></Button>
    <label class="search"><Search size={15}/><input aria-label="Search investigations" placeholder="Search investigations" bind:value={search}/></label>
    <div class="sidebar-label">WORKSPACE</div>
    <button class:nav-active={modal!=='models'} class="nav-item" onclick={() => modal=''}><MessageSquare size={17}/> Investigations <span>{runs.length}</span></button>
    <button class="nav-item" onclick={() => modal='models'}><Cpu size={17}/> Models & services <span class="small-dot" class:green={models?.services?.some((s:any)=>s.reachable)}></span></button>
    <button class="nav-item" onclick={() => { if(queued.length) {selectRun(queued[0]);} else if(result?.human_alert?.required) view='activity'; else {error='No approval is waiting in this investigation.';} }}><Bell size={17}/> Review queue <span>{queued.length}</span></button>
    <div class="sidebar-label recent-label">INVESTIGATIONS <span>{filteredRuns.length}</span></div>
    <div class="history">
      {#each filteredRuns as run}
        <button class:selected={current?.id===run.id} class="history-item" onclick={() => selectRun(run)}><span class="history-indicator" class:waiting={run.status==='awaiting_approval'} class:done={run.status==='completed'}></span><span>{run.case_id}<small>{run.mode==='mock'?'Demo':'Live models'} · {friendly(run.status)}</small></span></button>
      {:else}<p class="empty-history">Your investigations will appear here.<br/>Start with a simulated incident.</p>{/each}
    </div>
    <div class="sidebar-bottom"><div class="connection-line"><span class="small-dot" class:green={connected}></span>{connected?'Bridge connected':'Bridge offline'}<button aria-label="Connection settings" onclick={()=>modal='connection'}><Settings2 size={15}/></button></div><button class="profile" onclick={()=>modal='connection'}><span class="user-avatar">YO</span><span>Your workspace<small>Security analyst</small></span><ChevronDown size={14}/></button></div>
  </aside>

  <main class="main">
    <header class="topbar"><div class="breadcrumb">Workspace <ChevronRight size={13}/> <span>{current?current.case_id:'New investigation'}</span></div><div class="top-actions"><span class="mode-pill"><span class="small-dot" class:green={current?.mode==='live'}></span>{current?.mode==='live'?'Live inference':'Simulation'}</span><button class="icon-button" aria-label="Export investigation" disabled={!current} onclick={exportReport}><Download size={17}/></button><button class="icon-button" aria-label="Toggle agent panel" onclick={()=>rail=!rail}>{#if rail}<PanelRightClose size={18}/>{:else}<PanelRightOpen size={18}/>{/if}</button></div></header>
    {#if error}<div class="error-bar" role="alert"><TriangleAlert size={16}/><span>{error}</span><button aria-label="Dismiss error" onclick={()=>error=''}><X size={15}/></button></div>{/if}
    <div class="content-layout" class:without-rail={!rail}>
      <section class="conversation">
        {#if current}
          <div class="incident-header"><div class="eyebrow"><span class="small-dot" class:green={current.status==='completed'}></span>{friendly(current.status)} <span>·</span> {time(current.created)}</div><div class="incident-title"><h1>{current.case_id.startsWith('mitre-') ? 'Investigating '+ current.case_id.replace('mitre-','ATT&CK ') : friendly(current.case_id)}</h1>{#if result}<Badge class="severity-badge">{result.severity.band} · {result.severity.score}</Badge>{/if}</div><p>One incident. Four perspectives. A decision you can trace.</p><nav class="view-tabs" aria-label="Investigation views">{#each ['activity','evidence','metrics'] as tab}<button class:active={view===tab} onclick={()=>view=tab}>{#if tab==='activity'}<Activity size={15}/>{:else if tab==='evidence'}<Fingerprint size={15}/>{:else}<Layers size={15}/>{/if}{tab.charAt(0).toUpperCase()+tab.slice(1)}{#if tab==='evidence'}<span>{incident?.evidence?.length||0}</span>{/if}</button>{/each}</nav></div>
        {/if}
        <div class="conversation-scroll" bind:this={pane}>
          {#if !current}
            <div class="welcome"><div class="welcome-emblem"><Shield size={32} strokeWidth={1.3}/><span></span></div><div class="eyebrow">YOUR INCIDENT RESPONSE WORKSPACE</div><h1>Every signal.<br/><em>One clear picture.</em></h1><p>Follow the investigation, understand each agent’s findings,<br class="wide"/> and make the decisions that matter.</p><div class="welcome-actions"><Button class="primary-button" onclick={newIncident}><Plus size={16}/> Start an investigation</Button><button class="text-button" onclick={()=>modal='connection'}>Connect your pipeline <ArrowUpRight size={15}/></button></div><div class="starter-grid"><button onclick={()=>{caseId='mitre-T1041';mode='mock';modal='new';}}><span class="starter-icon"><Radio size={20}/></span><h3>Trace a suspicious signal</h3><p>Follow a simulated exfiltration incident through the real pipeline.</p><span class="starter-link">Explore a demo <ArrowRight size={14}/></span></button><button onclick={()=>modal='models'}><span class="starter-icon"><Cpu size={20}/></span><h3>Know who’s on the case</h3><p>See agent endpoints, service health and reported model identities.</p><span class="starter-link">View your agents <ArrowRight size={14}/></span></button></div><div class="welcome-foot"><ShieldCheck size={14}/> Human decisions stay in your hands.</div></div>
          {:else if view==='activity'}
            <div class="feed">
              {#each feed as event (event.id)}
                {#if event.type==='incident'}
                  <div class="timeline-note"><Radio size={14}/><span>Incident received <b>{event.data.incident.evidence.length} evidence items</b></span><time>{time(event.time)}</time></div>
                  <div class="intro-card"><span class="micro-label">{current.mode==='mock'?'DEMO INCIDENT · DETERMINISTIC AGENTS':'SIMULATED INCIDENT · LIVE MODELS'}</span><p>{event.data.incident.evidence[0]?.observation}</p><div class="evidence-chips">{#each event.data.incident.evidence.slice(0,3) as evidence}<button onclick={()=>view='evidence'}><FileText size={12}/>{evidence.id}</button>{/each}</div></div>
                {:else if event.type==='agent_finished'}
                  {@const role=event.data.role}{@const Icon=icons[role]||Activity}
                  <article class="agent-message"><div class="agent-avatar {role}"><Icon size={17}/></div><div class="message-body"><div class="message-heading"><strong>{roleNames[role]}</strong><span>{event.data.operation==='vote'?'Final vote':roleNotes[role]}</span><time>{time(event.time)}</time></div><p class="message-text">{summary(event.data.proposal)}</p>{#if event.data.proposal.stance}<span class="stance" class:objection={['object','veto'].includes(event.data.proposal.stance)}>{friendly(event.data.proposal.stance)}</span>{/if}{#if event.data.proposal.actions?.length}<div class="action-list">{#each event.data.proposal.actions as action}<div><span class="action-square"><ChevronRight size={12}/></span><span>{friendly(action.kind)}</span><code>{action.target_id}</code>{#if action.ttl_minutes}<small>{action.ttl_minutes}m TTL</small>{/if}</div>{/each}</div>{/if}<details class="response-details"><summary>Inspect response <span>{event.data.seconds}s</span></summary><pre>{JSON.stringify(event.data.proposal,null,2)}</pre></details></div></article>
                {:else if event.type==='message' && ['object','veto'].includes(event.data.stance)}
                  <div class="negotiation-note"><MessageSquare size={15}/><div><strong>{roleNames[event.data.role]} raised {event.data.stance==='veto'?'a veto':'an objection'}</strong><p>Round {event.data.round} · telemetry v{event.data.telemetry_version}. The pipeline must resolve this before proceeding.</p></div></div>
                {:else if event.type==='approval_requested'}
                  <article class="approval-card"><div class="approval-heading"><span class="approval-icon"><ShieldCheck size={20}/></span><div><span class="micro-label">HUMAN CHECKPOINT</span><h3>{current.pending?.id===event.data.id?'Your review is required':'Plan submitted for review'}</h3></div><span class="plan-version">v{event.data.plan.telemetry_version}</span></div><p>The agents support this plan. Review the exact scope before allowing the simulation to continue.</p><div class="approval-actions-list">{#each [...(event.data.plan.containment.actions||[]),...(event.data.plan.fixing.actions||[])] as action}<div><Check size={14}/><strong>{friendly(action.kind)}</strong><code>{action.target_id}</code></div>{/each}</div><details class="response-details"><summary>Evidence, expiry & rollback</summary><pre>{JSON.stringify(event.data.plan,null,2)}</pre></details>{#if current.pending?.id===event.data.id}<div class="approval-buttons"><Button class="primary-button" onclick={()=>review('approve')}><Check size={15}/> Review & approve</Button><Button class="secondary-button" onclick={()=>review('reject')}>Reject plan</Button><span>A written reason is required</span></div>{:else}<div class="checkpoint-complete"><CheckCheck size={14}/> Checkpoint closed · see decision below</div>{/if}</article>
                {:else if event.type==='human_decision'}
                  <div class="human-message"><div class="human-bubble"><span>You · {event.data.decision==='approve'?'approved this simulation plan':'rejected this plan'}</span><p>{event.data.reason}</p></div><span class="user-avatar">YO</span></div>
                {:else if event.type==='chat'}
                  {#if event.data.role==='human'}<div class="human-message"><div class="human-bubble"><span>You</span><p>{event.data.text}</p></div><span class="user-avatar">YO</span></div>{:else}<article class="agent-message"><div class="agent-avatar assistant"><Shield size={17}/></div><div class="message-body"><div class="message-heading"><strong>Sentinel</strong><span>Incident context</span><time>{time(event.time)}</time></div><p class="message-text">{event.data.text}</p></div></article>{/if}
                {:else if event.type==='completed'}
                  <div class="result-card" class:escalated={event.data.human_alert.required}><div class="result-heading">{#if event.data.human_alert.required}<TriangleAlert size={21}/>{:else}<CheckCheck size={21}/>{/if}<h3>{friendly(event.data.status)}</h3></div><p>{event.data.human_alert.required?'The pipeline stopped for human escalation. Policy gates remain in force.':'The simulation finished. Review the recorded outcome and any remaining risks.'}</p>{#each [...event.data.human_alert.reasons,...event.data.residual_risks] as reason}<p class="risk-line">{reason}</p>{/each}<div class="result-links"><button onclick={()=>view='metrics'}>View outcomes <ArrowUpRight size={14}/></button><button onclick={exportReport}>Export report <Download size={14}/></button></div></div>
                {:else if ['error','agent_failed','approval_expired'].includes(event.type)}
                  <div class="error-card"><TriangleAlert size={17}/>{event.data.message || event.data.error || 'Approval expired. The plan was not accepted.'}</div>
                {/if}
              {/each}
              {#if running}<div class="working-line"><span class="breathing-dot"></span><span>{activeRole?.type==='agent_started'?roleNames[activeRole.data.role]+' is analyzing the incident':'Pipeline is processing'}<span class="animated-ellipsis">…</span></span></div>{/if}
            </div>
          {:else if view==='evidence'}
            <div class="evidence-view"><div class="section-heading"><h2>The evidence behind the decisions</h2><p>Original observations supplied to the agents. Treat captured content as untrusted.</p></div>{#each incident?.evidence||[] as evidence}<article class="evidence-card"><div><span class="evidence-id"><FileText size={14}/>{evidence.id}</span><span class="micro-label">OBSERVATION</span></div><p>{evidence.observation}</p><div class="evidence-chips">{#each evidence.source_host_ids||[] as host}<span>{host}</span>{/each}</div><details class="response-details"><summary>View eligible controls</summary><pre>{JSON.stringify(evidence.actionable_for,null,2)}</pre></details></article>{/each}</div>
          {:else}
            <div class="metrics-view"><div class="section-heading"><h2>Outcomes, with context.</h2><p>Measured from this run’s simulation. Demo latency includes presentation pacing and human review.</p></div><div class="metrics-grid"><div><span>Agent responses</span><strong>{messages}</strong><small>Completed calls in this run</small></div><div><span>Deliberation rounds</span><strong>{result?.rounds ?? '—'}</strong><small>Reported by the protocol</small></div><div><span>Elapsed time</span><strong>{result?formatNumber(result.latency_seconds)+'s':'—'}</strong><small>Includes time awaiting approval</small></div><div><span>Severity</span><strong>{result?result.severity.score+'/100':'—'}</strong><small>Demo policy · uncalibrated score</small></div></div>{#if result}<h3>Simulation state</h3><div class="outcome-table">{#each Object.entries(result.outcomes) as [key,value]}<div><span>{friendly(key)}</span><code>{typeof value==='object'?JSON.stringify(value):String(value)}</code></div>{/each}</div><details class="response-details"><summary>Severity factors & deadlines</summary><pre>{JSON.stringify({severity:result.severity,deadlines:result.deadlines},null,2)}</pre></details>{:else}<div class="empty-metrics"><Clock3 size={26}/><h3>Final outcomes arrive when the run finishes.</h3><p>We don’t fill in results before the pipeline reports them.</p></div>{/if}</div>
          {/if}
        </div>
        <div class="composer-area">
          {#if current}<div class="suggestions"><button onclick={()=>ask('Summarize the evidence and what is still uncertain.')}>Summarize findings</button><button onclick={()=>ask('What risks should I review before approving this plan?')}>Explain the risks</button><button onclick={()=>ask('What are the recorded outcomes and statistics?')}>Show outcomes</button></div>{/if}
          <form class="composer" class:decision-mode={decision!==null} onsubmit={(e)=>{e.preventDefault();send();}}>
            {#if decision}<div class="decision-banner"><ShieldCheck size={15}/><strong>{decision==='approve'?'Approve':'Reject'} the current plan</strong><span>Type your reason below</span><button type="button" aria-label="Cancel decision" onclick={()=>decision=null}><X size={14}/></button></div>{/if}
            <Textarea class="chat-input" bind:ref={composer} bind:value={input} disabled={!current||busy} aria-label={decision?'Decision reason':'Message Sentinel'} placeholder={!current?'Start an investigation to ask about its evidence…':decision?'Explain your decision. This will be recorded in the incident timeline.':'Ask about this incident, its evidence, or the proposed response…'} onkeydown={(e)=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}}/>
            <div class="composer-toolbar"><span><Shield size={13}/>{decision?'Human decision':current?.mode==='live'?'Incident assistant':'Demo context assistant'}<ChevronDown size={12}/></span><button type="submit" class="send-button" aria-label={decision?'Submit decision':'Send message'} disabled={!input.trim()||busy||!current}>{#if busy}<LoaderCircle class="spin" size={17}/>{:else}<ArrowUp size={17}/>{/if}</button></div>
          </form><div class="composer-note">{decision?'Applies only to the exact pending plan. Compliance vetoes stay binding.':'Simulation workspace · actions do not modify real systems'}<span>Shift + Enter for a new line</span></div>
        </div>
      </section>
      {#if rail}<aside class="inspector"><div class="inspector-heading"><span class="micro-label">ON THIS INCIDENT</span><span class="live-label"><span class="small-dot" class:green={running}></span>{running?'Active':'Standby'}</span></div><h2>Your response team</h2><p class="inspector-caption">Specialized perspectives.<br/>A shared incident context.</p><div class="agent-stack">{#each roles as role}{@const Icon=icons[role]}{@const state=roleState(role)}<div class="agent-status" class:is-working={state==='Working'}><span class="agent-avatar {role}"><Icon size={17}/></span><div><strong>{roleNames[role]}</strong><small>{roleNotes[role]}</small></div><span class="agent-state" class:working={state==='Working'}>{#if state==='Working'}<LoaderCircle class="spin" size={13}/>{:else if state==='Reviewed'}<Check size={14}/>{:else}<Circle size={9}/>{/if}</span></div>{/each}</div><div class="inspector-divider"></div><div class="inspector-section"><span class="micro-label">AT A GLANCE</span><dl><div><dt>Evidence items</dt><dd>{incident?.evidence?.length??'—'}</dd></div><div><dt>Agent responses</dt><dd>{current?messages:'—'}</dd></div><div><dt>Telemetry version</dt><dd>{incident?'v'+incident.telemetry_version:'—'}</dd></div><div><dt>Human review</dt><dd class:amber={hasPending}>{hasPending?'Required':current?'No pending request':'—'}</dd></div></dl></div>{#if hasPending}<button class="review-nudge" onclick={()=>review('approve')}><ShieldCheck size={19}/><span>A decision is waiting<small>Review scope, then type your reason</small></span><ChevronRight size={15}/></button>{/if}<div class="inspector-section models-section"><div class="section-inline"><span class="micro-label">MODEL SERVICES</span><button onclick={()=>modal='models'} aria-label="View model services"><ArrowUpRight size={15}/></button></div>{#if current?.mode!=='live'}<p class="demo-model-note">Demo runs use deterministic agents.<br/>No model inference is claimed.</p>{/if}{#each models?.services||[] as service}<div class="model-mini"><span class="small-dot" class:green={service.reachable}></span><span>{roleNames[service.role]}</span><small>{service.reachable?'Reachable':'Offline'}</small></div>{:else}<p class="demo-model-note">Checking service health…</p>{/each}</div><div class="inspector-footer"><Fingerprint size={16}/><p>Every proposal has a source.<br/>Every decision leaves a record.</p></div></aside>{/if}
    </div>
  </main>
</div>

{#if modal}
  <div class="modal-backdrop" role="presentation" onclick={(e)=>{if(e.target===e.currentTarget)modal='';}}>
    <dialog class="modal" use:openDialog oncancel={()=>modal=''} aria-label={modal==='new'?'New investigation':modal==='models'?'Models and services':'Connection settings'}>
      <button class="modal-close" aria-label="Close dialog" onclick={()=>modal=''}><X size={20}/></button>
      {#if modal==='new'}<span class="modal-emblem"><FolderOpen size={23}/></span><span class="eyebrow">START WITH A SIGNAL</span><h2>New investigation</h2><p>Choose an incident fixture and follow the connected pipeline from first proposal to final review.</p><label class="field-label" for="scenario">Incident scenario</label><select id="scenario" bind:value={caseId}>{#each cases as item}<option value={item.id}>{item.title} · {item.evidence_count} evidence items</option>{/each}</select><div class="mode-options"><button class:chosen={mode==='mock'} onclick={()=>mode='mock'}><Layers size={18}/><strong>Demo pipeline</strong><span>Actual protocol, deterministic agents.<br/>Works without model servers.</span></button><button class:chosen={mode==='live'} onclick={()=>mode='live'}><Cpu size={18}/><strong>Live models</strong><span>Uses the bridge host’s services.<br/>All execution stays simulated.</span></button></div><div class="modal-info"><ShieldCheck size={17}/><span>The pipeline pauses for your written approval before applying an accepted simulation plan.</span></div><Button class="primary-button modal-submit" disabled={starting||!connected||!cases.length} onclick={start}>{#if starting}<LoaderCircle class="spin" size={16}/>{:else}<ArrowRight size={16}/>{/if}{starting?'Starting…':'Start investigation'}</Button>
      {:else if modal==='models'}<span class="modal-emblem"><Cpu size={23}/></span><span class="eyebrow">SERVICE INVENTORY</span><h2>The models behind the agents</h2><p>Health is checked on the pipeline host. A reachable service does not by itself prove GPU residency.</p><div class="models-table">{#each models?.services||[] as service}<div><span class="small-dot" class:green={service.reachable}></span><div><strong>{roleNames[service.role]}</strong><code>{service.model}</code><small>{service.endpoint}</small></div><Badge class="service-badge">{service.reachable?'Reachable':'Unavailable'}</Badge></div>{/each}</div><div class="modal-info"><Activity size={17}/><span>Shared inference configuration: {models?.shared_inference?.model||'Unknown'}. Forensics can use this model when no investigation API is configured.</span></div><h3 class="resident-heading">Loaded in shared inference</h3>{#each models?.running_models||[] as resident}<div class="resident-model"><Cpu size={16}/><strong>{resident.name || resident.model}</strong><span>{formatNumber(resident.size_vram/1073741824)} GiB resident</span></div>{:else}<p class="browser-note">No loaded models reported by the configured Ollama endpoint.</p>{/each}<button class="secondary-button" onclick={readModels}>Refresh health</button>
      {:else}<span class="modal-emblem"><Cable size={23}/></span><span class="eyebrow">CONNECT YOUR WORKSPACE</span><h2>Pipeline connection</h2><p>Point Sentinel to the desktop bridge on the machine running the pipeline.</p><label for="bridge-url" class="field-label">Bridge URL</label><input id="bridge-url" class="connection-input" bind:value={url} disabled={!window.sentinel}/><div class="setup-command"><span>Run from the repository root on the pipeline host</span><code>python -m desktop.bridge --port 8787</code></div><div class="modal-info"><Cable size={17}/><span>For ASUS access, privately forward port 8787 in VS Code and paste its HTTPS address here. Port 8000 is the model chat, not this bridge.</span></div><div class="connection-buttons"><Button class="primary-button" onclick={connect}>Connect</Button>{#if window.sentinel && url.startsWith('https://')}<Button class="secondary-button" onclick={async()=>{try{await window.sentinel?.login();}catch(e:any){error=e.message;}}}>Sign in to tunnel</Button>{/if}</div>{#if !window.sentinel}<p class="browser-note">This browser is connected to the server hosting this page. For ASUS access, open the privately forwarded port 8787.</p>{/if}{/if}
      {#if error}<p class="modal-error" role="alert">{error}</p>{/if}
    </dialog>
  </div>
{/if}
