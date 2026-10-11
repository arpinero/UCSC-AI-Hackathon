<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { Moon, PanelLeft, Shield, Plus, Search, ArrowUp, ArrowUpRight, ChevronDown, ChevronRight, Check, Circle, X, Settings2, Cpu, Radio, FileText, Fingerprint, ShieldCheck, Wrench, Activity, Bell, Layers, Download, Cable, TriangleAlert, Clock3, ArrowRight, PanelRightClose, PanelRightOpen, CheckCheck, MessageSquare, FolderOpen, LoaderCircle } from '@lucide/svelte';
  import AgentOutput from './AgentOutput.svelte';
  import ResponseBody from './ResponseBody.svelte';
  import CodeBlock from './CodeBlock.svelte';
  import Button from '../lib/ui/button.svelte';
  import ChatFormTextarea from '../lib/llama/ChatFormTextarea.svelte';
  import {INPUT_CLASSES} from '../lib/llama/css-classes';
  import * as Sidebar from '../lib/ui/sidebar';
  import * as Tooltip from '../lib/ui/tooltip';
  import {ModeWatcher, toggleMode} from 'mode-watcher';
  import Badge from '../lib/ui/badge.svelte';
  import {suggestions} from './interactions.mjs';
  import { request, mergeEvents, roleNames, friendly, type Run, type Event, type Case } from './api';
  let cases = $state<Case[]>([]), runs = $state<Run[]>([]), current = $state<Run|null>(null);
  let events = $state<Event[]>([]), models = $state<any>(null), connected = $state(false);
  let pipelineHost = $state('');
  let view = $state('activity'), modal = $state(''), input = $state(''), error = $state(''), search = $state('');
  let busy = $state(false), starting = $state(false), rail = $state(false), sidebarOpen = $state(false), mode = $state<'mock'|'live'>('live');
  let caseId = $state('mitre-T1041'), url = $state('http://127.0.0.1:8787'), decision = $state<'approve'|'reject'|null>(null);
  let selectedEvidence = $state(''), selectedAgent = $state('');
  let pane: HTMLDivElement;
  let composer = $state<ChatFormTextarea|null>(null);
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
  let evidenceIds = $derived((incident?.evidence||[]).map((e:any)=>String(e.id)));
  let latestResponse = $derived([...events].reverse().find(e=>e.type==='agent_finished'));
  let agentResponse = $derived([...events].reverse().find(e=>e.type==='agent_finished' && e.data.role===selectedAgent && e.data.operation!=='vote') || [...events].reverse().find(e=>e.type==='agent_finished' && e.data.role===selectedAgent));
  let quickActions = $derived(suggestions({running,pending:hasPending,decision:!!decision,escalated:!!result?.human_alert?.required,view,latestRole:latestResponse?.data.role||''}));
  let humanReview = $derived(hasPending || !!result?.human_alert?.required);
  function serviceFor(role:string) {return models?.services?.find((s:any)=>s.role===role);}
  function modelName(role:string) {const name=serviceFor(role)?.model;return !name || name==='Identity not reported'?'Model not reported':name;}

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
      pipelineHost = health.host || new URL(url).hostname;
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
    current = run; events = []; input = ''; decision = null; error = ''; view = 'activity'; selectedEvidence=''; selectedAgent='';
    try { const data = await request(`/api/runs/${run.id}`); if (version === selectionVersion) {current=data; events=data.events;} }
    catch(e:any) {if (version === selectionVersion) error=e.message;}
    finally {if (version === selectionVersion) selectionLoading=false;}
  }
  async function start() {
    starting = true; error = '';
    try {
      if (mode === 'live') {
        models = await request('/api/models');
        const missing = models.services.filter((service:any) => (service.required ?? ['containment','compliance','fixing'].includes(service.role)) && !service.reachable);
        if (missing.length) throw new Error(`Live services unavailable on ${pipelineHost}: ${missing.map((service:any)=>roleNames[service.role]).join(', ')}. Open the bridge running on the ASUS, or connect these services through local forwarding.`);
      }
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
  async function ask(text:string) {
    if(decision) return;
    modal=''; input=text; await tick();
    pane?.scrollTo({top:pane.scrollHeight,behavior:'smooth'}); composer?.focus();
  }
  async function showView(next:string) {view=next; await tick(); pane?.scrollTo({top:0,behavior:'smooth'});}
  function inspectEvidence(id='') {selectedEvidence=evidenceIds.includes(id)?id:''; modal=''; showView('evidence');}
  function inspectAgent(role:string) {selectedAgent=role; modal='agent';}
  async function jumpTo(selector:string) {
    view='activity'; modal=''; await tick();
    const matches=pane?.querySelectorAll<HTMLElement>(selector);
    const target=matches?.[matches.length-1];
    if(target && pane) pane.scrollTo({top:Math.max(0,target.offsetTop-pane.offsetTop-16),behavior:'smooth'});
  }
  function quickAction(action:any) {
    if(action.action==='draft') ask(action.text);
    else if(action.action==='evidence') inspectEvidence();
    else if(action.action==='latest') inspectAgent(latestResponse?.data.role||'containment');
    else if(action.action==='agents') rail=true;
    else if(action.action==='plan') jumpTo('.approval-card');
    else if(action.action==='escalation') jumpTo('.result-card');
    else if(action.action==='cancel') decision=null;
    else if(action.action==='models') modal='models';
    else showView(action.action);
  }
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

<!-- Layout uses llama.cpp +layout.svelte's floating Sidebar.Provider/Root/Inset. -->
<Tooltip.Provider delayDuration={200}>
<ModeWatcher defaultMode="dark" track={false} modeStorageKey="sentinel-theme" disableHeadScriptInjection />
<Sidebar.Provider bind:open={sidebarOpen}>
<div class="flex h-screen w-full">
  <Sidebar.Root variant="floating" class="h-full">
    <Sidebar.Header class="p-3">
      <div class="flex items-center justify-between px-2 py-2"><div class="sentinel-brand"><Shield size={18}/><strong>Sentinel</strong></div><Button variant="ghost" size="icon" aria-label="Close sidebar" onclick={()=>sidebarOpen=false}><PanelLeft size={16}/></Button></div>
      <Button variant="ghost" class="justify-start" onclick={newIncident}><Plus size={16}/>New investigation</Button>
      <label class="flex items-center gap-2 px-3 py-2"><Search size={16}/><input class="w-full bg-transparent text-sm outline-none" aria-label="Search investigations" placeholder="Search conversations..." bind:value={search}/></label>
      <Button variant="ghost" class="justify-start" onclick={()=>modal='models'}><Cpu size={16}/>Models & services</Button>
    </Sidebar.Header>
    <Sidebar.Content><Sidebar.Group><Sidebar.GroupLabel>Investigations</Sidebar.GroupLabel><Sidebar.GroupContent><Sidebar.Menu>
      {#each filteredRuns as run}<Sidebar.MenuItem><Sidebar.MenuButton isActive={current?.id===run.id} onclick={()=>selectRun(run)}><MessageSquare size={16}/><span>{run.case_id}</span></Sidebar.MenuButton><div class="px-7 pb-2 text-xs text-muted-foreground">{run.mode==='live'?'Live models':'Deterministic'} · {friendly(run.status)}</div></Sidebar.MenuItem>{:else}<p class="px-3 py-4 text-sm text-muted-foreground">No investigations yet.</p>{/each}
    </Sidebar.Menu></Sidebar.GroupContent></Sidebar.Group></Sidebar.Content>
    <Sidebar.Footer class="p-3"><Button variant="ghost" class="justify-start" onclick={()=>modal='connection'}><Settings2 size={16}/>Connection settings</Button><Button variant="ghost" class="justify-start" onclick={toggleMode}><Moon size={16}/>Toggle theme</Button><div class="px-3 py-2 text-xs text-muted-foreground">{connected?'Connected to '+pipelineHost:'Bridge offline'}</div></Sidebar.Footer>
  </Sidebar.Root>
  <div class="icon-strip" class:strip-hidden={sidebarOpen}><Sidebar.Trigger/><Button variant="ghost" size="icon" aria-label="New investigation" onclick={newIncident}><Plus size={18}/></Button><Button variant="ghost" size="icon" aria-label="Search investigations" onclick={()=>sidebarOpen=true}><Search size={18}/></Button><Button variant="ghost" size="icon" aria-label="Models and services" onclick={()=>modal='models'}><Cpu size={18}/></Button><Button variant="ghost" size="icon" aria-label="Toggle theme" onclick={toggleMode}><Moon size={18}/></Button></div>
  <Sidebar.Inset class="flex flex-1 flex-col overflow-hidden">
    <header class="topbar" class:empty-header={!current}><div class="flex items-center gap-2"><button class="mobile-trigger" aria-label="Open sidebar" onclick={()=>sidebarOpen=!sidebarOpen}><PanelLeft size={18}/></button><button class="model-picker" onclick={()=>modal='models'}>Security pipeline<ChevronDown size={15}/></button></div><div class="top-actions"><span class="mode-pill">{current?.mode==='live'?'Live models':current?'Deterministic':'ASUS pipeline'}</span><button class="icon-button" aria-label="Export investigation" disabled={!current} onclick={exportReport}><Download size={17}/></button><button class="icon-button" aria-label="Toggle agent panel" onclick={()=>rail=!rail}><PanelRightOpen size={18}/></button></div></header>
    {#if error}<div class="error-bar" role="alert"><TriangleAlert size={16}/><span>{error}</span><button aria-label="Dismiss error" onclick={()=>error=''}><X size={15}/></button></div>{/if}
    <div class="content-layout" class:without-rail={!rail}>
      <section class="conversation" class:empty={!current}>
        {#if current}
          <div class="incident-header"><div class="eyebrow"><span class="small-dot" class:green={current.status==='completed'}></span>{friendly(current.status)} <span>·</span> {time(current.created)}</div><div class="incident-title"><h1>{current.case_id.startsWith('mitre-') ? 'Investigating '+ current.case_id.replace('mitre-','ATT&CK ') : friendly(current.case_id)}</h1>{#if result}<Badge class="severity-badge">{result.severity.band} · {result.severity.score}</Badge>{/if}</div><nav class="view-tabs" aria-label="Investigation views">{#each ['activity','evidence','metrics'] as tab}<button class:active={view===tab} onclick={()=>{selectedEvidence='';showView(tab);}}>{#if tab==='activity'}<Activity size={15}/>{:else if tab==='evidence'}<Fingerprint size={15}/>{:else}<Layers size={15}/>{/if}{tab.charAt(0).toUpperCase()+tab.slice(1)}{#if tab==='evidence'}<span>{incident?.evidence?.length||0}</span>{/if}</button>{/each}</nav><div class="stage-navigation" aria-label="Explore agent stages">{#each roles as role}{@const Icon=icons[role]}<button title={roleState(role)+" · Open "+roleNames[role]+" response"} onclick={()=>inspectAgent(role)}><Icon size={12}/>{roleNames[role]}<span class="small-dot" class:green={roleState(role)==="Reviewed"} class:breathing-dot={roleState(role)==="Working"}></span></button>{/each}</div></div>
        {/if}
        <div class="conversation-scroll" bind:this={pane}>
          {#if !current}
            <div class="welcome"><div class="welcome-brand"><Shield size={26}/></div><h1 class="mb-2 text-2xl font-semibold tracking-tight md:text-3xl">Sentinel</h1><p class="text-muted-foreground md:text-lg">Investigate an incident. Review the response.</p><div class="welcome-actions"><button onclick={newIncident}><Plus size={14}/>Choose an incident</button><button onclick={()=>modal="models"}><Cpu size={14}/>Model services</button>{#if runs.length}<button onclick={()=>selectRun(runs[runs.length-1])}><MessageSquare size={14}/>Resume latest</button>{/if}</div></div>
          {:else if view==='activity'}
            <div class="feed">
              {#each feed as event (event.id)}
                {#if event.type==='incident'}
                  <div class="timeline-note"><Radio size={14}/><span>Incident received <b>{event.data.incident.evidence.length} evidence items</b></span><time>{time(event.time)}</time></div>
                  <div class="intro-card"><span class="micro-label">{current.mode==='mock'?'DEMO INCIDENT · DETERMINISTIC AGENTS':'SIMULATED INCIDENT · LIVE MODELS'}</span><p>{event.data.incident.evidence[0]?.observation}</p><div class="evidence-chips">{#each event.data.incident.evidence.slice(0,3) as evidence}<button onclick={()=>inspectEvidence(evidence.id)}><FileText size={12}/>{evidence.id}</button>{/each}</div></div>
                {:else if event.type==='agent_finished'}
                  {@const role=event.data.role}{@const Icon=icons[role]||Activity}
                  <article class="agent-message" data-role={role}><div class="agent-avatar {role}"><Icon size={16}/></div><div class="message-body"><div class="message-heading"><strong>{roleNames[role]}</strong>{#if event.data.operation==='vote'}<span>Final vote</span>{/if}{#if event.data.proposal.stance}<span class="stance-label" class:objection={['object','veto'].includes(event.data.proposal.stance)}>{friendly(event.data.proposal.stance)}</span>{/if}<time>{time(event.time)}</time></div><AgentOutput proposal={event.data.proposal} {role} seconds={event.data.seconds} {evidenceIds} onEvidence={inspectEvidence} onAsk={ask} canAsk={!decision}/></div></article>
                {:else if event.type==='message' && ['object','veto'].includes(event.data.stance)}
                  <div class="negotiation-note"><MessageSquare size={15}/><div><strong>{roleNames[event.data.role]} raised {event.data.stance==='veto'?'a veto':'an objection'}</strong><p>Round {event.data.round} · telemetry v{event.data.telemetry_version}. The pipeline must resolve this before proceeding.</p></div></div>
                {:else if event.type==='approval_requested'}
                  <article class="approval-card"><div class="approval-heading"><span class="approval-icon"><ShieldCheck size={20}/></span><div><span class="micro-label">HUMAN CHECKPOINT</span><h3>{current.pending?.id===event.data.id?'Your review is required':'Plan submitted for review'}</h3></div><span class="plan-version">v{event.data.plan.telemetry_version}</span></div><p>The agents support this plan. Review the exact scope before allowing the simulation to continue.</p><div class="approval-actions-list">{#each [...(event.data.plan.containment.actions||[]),...(event.data.plan.fixing.actions||[])] as action}<div><Check size={14}/><strong>{friendly(action.kind)}</strong><code>{action.target_id}</code></div>{/each}</div><details class="response-details"><summary>Evidence, expiry & rollback</summary><CodeBlock value={event.data.plan} label="Proposed plan"/></details>{#if current.pending?.id===event.data.id}<div class="approval-buttons"><Button class="primary-button" onclick={()=>review('approve')}><Check size={15}/> Review & approve</Button><Button class="secondary-button" onclick={()=>review('reject')}>Reject plan</Button><span>A written reason is required</span></div>{:else}<div class="checkpoint-complete"><CheckCheck size={14}/> Checkpoint closed · see decision below</div>{/if}</article>
                {:else if event.type==='human_decision'}
                  <div class="human-message"><div class="human-bubble"><span>You · {event.data.decision==='approve'?'approved this simulation plan':'rejected this plan'}</span><p>{event.data.reason}</p></div><span class="user-avatar">YO</span></div>
                {:else if event.type==='chat'}
                  {#if event.data.role==='human'}<div class="human-message"><div class="human-bubble"><span>You</span><p>{event.data.text}</p></div><span class="user-avatar">YO</span></div>{:else}<article class="agent-message"><div class="agent-avatar assistant"><Shield size={17}/></div><div class="message-body"><div class="message-heading"><strong>Sentinel</strong><span>Incident context</span><time>{time(event.time)}</time></div><ResponseBody content={event.data.text} {evidenceIds} onEvidence={inspectEvidence}/></div></article>{/if}
                {:else if event.type==='completed'}
                  <div class="result-card" class:escalated={event.data.human_alert.required}><div class="result-heading">{#if event.data.human_alert.required}<TriangleAlert size={21}/>{:else}<CheckCheck size={21}/>{/if}<h3>{friendly(event.data.status)}</h3></div><p>{event.data.human_alert.required?'The pipeline stopped for human escalation. Policy gates remain in force.':'The simulation finished. Review the recorded outcome and any remaining risks.'}</p>{#each [...event.data.human_alert.reasons,...event.data.residual_risks] as reason}<p class="risk-line">{reason}</p>{/each}<div class="result-links"><button onclick={()=>view='metrics'}>View outcomes <ArrowUpRight size={14}/></button><button onclick={exportReport}>Export report <Download size={14}/></button></div></div>
                {:else if ['error','agent_failed','approval_expired'].includes(event.type)}
                  <div class="error-card"><TriangleAlert size={17}/>{event.data.message || event.data.error || 'Approval expired. The plan was not accepted.'}</div>
                {/if}
              {/each}
              {#if running}<div class="working-line"><span class="breathing-dot"></span><span>{activeRole?.type==='agent_started'?roleNames[activeRole.data.role]+' is analyzing the incident':'Pipeline is processing'}<span class="animated-ellipsis">…</span></span></div>{/if}
            </div>
          {:else if view==='evidence'}
            <div class="evidence-view"><div class="section-heading"><h2>Evidence {#if selectedEvidence}<span class="selected-source">{selectedEvidence}</span>{/if}</h2><p>Observations supplied to the agents.</p></div><div class="evidence-filter" aria-label="Filter evidence"><button class:chosen={!selectedEvidence} onclick={()=>selectedEvidence=""}>All evidence</button>{#each incident?.evidence||[] as item}<button class:chosen={selectedEvidence===item.id} onclick={()=>{selectedEvidence=item.id;pane?.scrollTo({top:0});}}>{item.id}</button>{/each}</div>{#each (incident?.evidence||[]).filter((e:any)=>!selectedEvidence || e.id===selectedEvidence) as evidence}<article class="evidence-card"><div><span class="evidence-id"><FileText size={14}/>{evidence.id}</span><span class="micro-label">OBSERVATION</span></div><ResponseBody content={evidence.observation} {evidenceIds} onEvidence={inspectEvidence}/><div class="evidence-chips">{#each evidence.source_host_ids||[] as host}<span>{host}</span>{/each}</div><details class="response-details"><summary>View eligible controls</summary><CodeBlock value={evidence.actionable_for} label="Eligible controls"/></details><div class="response-followups"><button disabled={!!decision} onclick={()=>ask(`Explain evidence ${evidence.id}: what does it establish, what is uncertain, and which proposed controls cite it?`)}>Explain this evidence<span>↗</span></button><button onclick={()=>{rail=true;showView("activity");}}>Browse agent responses<span>→</span></button></div></article>{/each}</div>
          {:else}
            <div class="metrics-view"><div class="section-heading"><h2>Run metrics</h2><p>Recorded from this run. Elapsed time includes model calls and any human review.</p></div><div class="metrics-grid"><div><span>Agent responses</span><strong>{messages}</strong><small>Completed calls in this run</small></div><div><span>Deliberation rounds</span><strong>{result?.rounds ?? '—'}</strong><small>Reported by the protocol</small></div><div><span>Elapsed time</span><strong>{result?formatNumber(result.latency_seconds)+'s':'—'}</strong><small>Includes time awaiting approval</small></div><div><span>Severity</span><strong>{result?result.severity.score+'/100':'—'}</strong><small>Demo policy · uncalibrated score</small></div></div>{#if result}<h3>Simulation state</h3><div class="outcome-table">{#each Object.entries(result.outcomes) as [key,value]}<div><span>{friendly(key)}</span><code>{typeof value==='object'?JSON.stringify(value):String(value)}</code></div>{/each}</div><details class="response-details"><summary>Severity factors & deadlines</summary><CodeBlock value={{severity:result.severity,deadlines:result.deadlines}} label="Policy factors"/></details>{:else}<div class="empty-metrics"><Clock3 size={26}/><h3>The run is still in progress.</h3><p>Metrics will appear when it finishes.</p></div>{/if}</div>
          {/if}
        <div class="composer-area">
          {#if current}<div class="suggestions" aria-label="Suggested next steps">{#each quickActions as action}<button title={action.action==="draft"?"Draft a question; press Send to ask":"Open investigation details"} onclick={()=>quickAction(action)}>{action.label}{#if action.action==="draft"}<ArrowUpRight size={11}/>{/if}</button>{/each}</div>{/if}
          <form class="composer {INPUT_CLASSES}" class:decision-mode={decision!==null} onsubmit={(e)=>{e.preventDefault();send();}}>
            {#if decision}<div class="decision-banner"><ShieldCheck size={15}/><strong>{decision==='approve'?'Approve':'Reject'} the current plan</strong><span>Type your reason below</span><button type="button" aria-label="Cancel decision" onclick={()=>decision=null}><X size={14}/></button></div>{/if}
            <ChatFormTextarea class="px-5 pt-4" bind:this={composer} bind:value={input} disabled={!current||busy} placeholder={!current?'Ask anything...':decision?'Explain your decision. This will be recorded in the incident timeline.':'Ask about this incident, its evidence, or the proposed response…'} onKeydown={(e)=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}}/>
            <div class="composer-toolbar"><Button type="button" variant="ghost" size="icon" class="rounded-full bg-background shadow-sm" aria-label="New investigation" onclick={newIncident}><Plus size={18}/></Button><div class="flex items-center gap-3"><button type="button" class="composer-model" onclick={()=>modal='models'}><Cpu size={13}/>{decision?'Human decision':'Security pipeline'}<ChevronDown size={12}/></button><button type="submit" class="send-button" aria-label={decision?'Submit decision':'Send message'} disabled={!input.trim()||busy||!current}>{#if busy}<LoaderCircle class="spin" size={17}/>{:else}<ArrowUp size={17}/>{/if}</button></div></div>
          </form><div class="composer-note">{decision?'Applies only to the exact pending plan. Compliance vetoes stay binding.':'Simulation workspace · actions do not modify real systems'}<span>Shift + Enter for a new line</span></div>
        </div>
        </div>
      </section>
      {#if rail}<aside class="inspector" aria-label="Agent status"><div class="inspector-title"><h2>Agents</h2><button aria-label="Close agent panel" onclick={()=>rail=false}><X size={16}/></button></div><div class="run-state"><span class="small-dot" class:green={running}></span>{running?'Processing':current?friendly(current.status):'No active incident'}<span>{messages} responses</span></div><div class="agent-stack">{#each roles as role}{@const Icon=icons[role]}{@const state=roleState(role)}<div class="agent-status"><span class="agent-avatar {role}"><Icon size={15}/></span><div class="agent-identity"><button class="agent-name" onclick={()=>inspectAgent(role)}>{roleNames[role]}<ChevronRight size={11}/></button><button class="agent-model" onclick={()=>modal='models'}>{modelName(role)}</button></div><span class="agent-state" class:working={state==='Working'} class:failed={state==='Failed'}>{#if state==='Working'}<LoaderCircle class="spin" size={12}/>{/if}{state}</span></div>{/each}</div><div class="incident-stats"><button disabled={!current} onclick={()=>inspectEvidence()}><strong>{incident?.evidence?.length??'—'}</strong><span>Evidence ↗</span></button><div><strong>{incident?'v'+incident.telemetry_version:'—'}</strong><span>Telemetry</span></div></div>{#if humanReview}<div class="review-status"><ShieldCheck size={16}/><div><strong>Human review {hasPending?'required':'requested'}</strong><p>{hasPending?'The proposed plan is waiting for your decision.':'Compliance stopped the run for review.'}</p></div></div>{#if hasPending}<Button variant="outline" class="w-full" onclick={()=>review('approve')}>Review plan</Button>{/if}{/if}<button class="panel-model-link" onclick={()=>modal='models'}><Cpu size={14}/>Model services<ChevronRight size={13}/></button></aside>{/if}

    </div>
  </Sidebar.Inset>
</div>
</Sidebar.Provider>
</Tooltip.Provider>

{#if modal}
  <div class="modal-backdrop" role="presentation" onclick={(e)=>{if(e.target===e.currentTarget)modal='';}}>
    <dialog class="modal" class:services-modal={modal==='models'} use:openDialog oncancel={()=>modal=''} aria-label={modal==='agent'?'Agent response':modal==='new'?'New investigation':modal==='models'?'Models and services':'Connection settings'}>
      <button class="modal-close" aria-label="Close dialog" onclick={()=>modal=''}><X size={20}/></button>
      {#if modal==='agent'}
        <div class="services-title"><h2>{roleNames[selectedAgent]} response</h2></div>
        <div class="agent-tabs" aria-label="Choose agent">{#each roles as role}<button class:chosen={selectedAgent===role} onclick={()=>selectedAgent=role}>{roleNames[role]}</button>{/each}</div>
        {#if agentResponse}<div class="agent-preview-status">{roleState(selectedAgent)} · {time(agentResponse.time)} · {agentResponse.data.seconds}s</div><AgentOutput proposal={agentResponse.data.proposal} role={selectedAgent} seconds={agentResponse.data.seconds} {evidenceIds} onEvidence={inspectEvidence} onAsk={ask} canAsk={!decision}/><button class="panel-model-link" onclick={()=>jumpTo(`[data-role="${selectedAgent}"]`)}>View in activity<ArrowRight size={13}/></button>
        {:else}<div class="agent-waiting"><Clock3 size={20}/><h3>{roleState(selectedAgent)==='Working'?'Analysis in progress':roleState(selectedAgent)==='Failed'?'Analysis failed':'No response yet'}</h3><p>{roleState(selectedAgent)==='Failed'?'Review the recorded failure in Activity.':current?'This agent has not returned a response for this incident.':'Choose an incident to begin.'}</p><button onclick={()=>inspectEvidence()}>Inspect available evidence</button><button onclick={()=>modal='models'}>Check model services</button></div>{/if}
      {:else if modal==='new'}<span class="modal-emblem"><FolderOpen size={23}/></span><h2>New investigation</h2><p>Choose an incident fixture and follow the connected pipeline from first proposal to final review.</p><label class="field-label" for="scenario">Incident scenario</label><select id="scenario" bind:value={caseId}>{#each cases as item}<option value={item.id}>{item.title} · {item.evidence_count} evidence items</option>{/each}</select><div class="mode-options"><button class:chosen={mode==='mock'} onclick={()=>mode='mock'}><Layers size={18}/><strong>Demo pipeline</strong><span>Actual protocol, deterministic agents.<br/>Works without model servers.</span></button><button class:chosen={mode==='live'} onclick={()=>mode='live'}><Cpu size={18}/><strong>Live models</strong><span>Uses the bridge host’s services.<br/>All execution stays simulated.</span></button></div><div class="modal-info"><ShieldCheck size={17}/><span>The pipeline pauses for your written approval before applying an accepted simulation plan.</span></div><Button class="primary-button modal-submit" disabled={starting||!connected||!cases.length} onclick={start}>{#if starting}<LoaderCircle class="spin" size={16}/>{:else}<ArrowRight size={16}/>{/if}{starting?'Starting…':'Start investigation'}</Button>
      {:else if modal==='models'}<div class="services-title"><Cpu size={20}/><h2>Model services</h2></div><p class="services-host">{pipelineHost || 'Pipeline host'}<span>{models?.services?.filter((s:any)=>s.reachable).length||0} / {models?.services?.length||0} online</span></p><div class="service-list">{#each models?.services||[] as service}{@const Icon=icons[service.role]||Cpu}<div class="service-row"><span class="agent-avatar {service.role}"><Icon size={16}/></span><div><strong>{roleNames[service.role]}</strong><code>{modelName(service.role)}</code>{#if service.shared}<span class="shared-label">Shared runtime</span>{:else if service.model_source==='configured'}<span class="shared-label">Configured label, not reported by the service</span>{/if}</div><span class="service-health" class:online={service.reachable}><span class="small-dot" class:green={service.reachable}></span>{service.reachable?'API online':'Offline'}</span></div>{/each}</div>{#if models?.running_models?.length}<div class="runtime-section"><h3>Loaded in shared runtime</h3>{#each models.running_models as resident}<div class="runtime-row"><code>{resident.name||resident.model}</code><span>{formatNumber(resident.size_vram/1073741824)} GiB</span></div>{/each}</div>{/if}<details class="connection-details"><summary>Connection details</summary><p>API status reports reachability. The loaded list comes from the shared inference runtime.</p>{#each models?.services||[] as service}<div><span>{roleNames[service.role]}</span><code>{service.endpoint}</code></div>{/each}</details><div class="services-footer"><button class="secondary-button" onclick={readModels}>Refresh</button><span>Checked every 30 seconds</span></div>
      {:else}<span class="modal-emblem"><Cable size={23}/></span><h2>Pipeline connection</h2><p>Point Sentinel to the desktop bridge on the machine running the pipeline.</p><label for="bridge-url" class="field-label">Bridge URL</label><input id="bridge-url" class="connection-input" bind:value={url} disabled={!window.sentinel}/><div class="setup-command"><span>Run from the repository root on the pipeline host</span><code>python -m desktop.bridge --port 8787</code></div><div class="modal-info"><Cable size={17}/><span>For ASUS access, privately forward port 8787 in VS Code and paste its HTTPS address here. Port 8000 is the model chat, not this bridge.</span></div><div class="connection-buttons"><Button class="primary-button" onclick={connect}>Connect</Button>{#if window.sentinel && url.startsWith('https://')}<Button class="secondary-button" onclick={async()=>{try{await window.sentinel?.login();}catch(e:any){error=e.message;}}}>Sign in to tunnel</Button>{/if}</div>{#if !window.sentinel}<p class="browser-note">This browser is connected to the server hosting this page. For ASUS access, open the privately forwarded port 8787.</p>{/if}{/if}
      {#if error}<p class="modal-error" role="alert">{error}</p>{/if}
    </dialog>
  </div>
{/if}
