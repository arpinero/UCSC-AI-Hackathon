"""Reproducible outcome benchmark; real inference, simulated consequences."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
import agent
import eval_checkpoint
from benchmark_cases import dataset, reference_proposal
from simulator import Simulator


def advance_updates(sim, end):
    for update in sim.case['updates']:
        if sim.time <= update['at'] <= end and update['incident']['telemetry_version'] > sim.incident['telemetry_version']:
            sim.advance(update['at']); sim.update(update['incident'])
    sim.advance(end)


def run_case(case, predictor, fixed_latency=None):
    sim = Simulator(case); attempts = []; previous = None; schedule = []
    # Initial response, then replan each independently supplied telemetry update.
    for decision in range(1+len(case['updates'])):
        if decision:
            advance_updates(sim, max(sim.time,case['updates'][decision-1]['at']))
        if sim.time >= case['horizon_seconds']: break
        incident = copy.deepcopy(sim.incident)
        started = time.monotonic()
        result = predictor(incident, previous)
        elapsed = time.monotonic()-started
        latency = result.get('latency_seconds',elapsed) if fixed_latency is None else fixed_latency
        if not isinstance(latency,(int,float)) or not math.isfinite(latency) or latency < 0:
            raise ValueError('Invalid response latency')
        advance_updates(sim,min(case['horizon_seconds'],sim.time+latency))
        applied = result.get('status') == 'validated' and sim.apply(result['proposal'])
        attempts.append({'input_version':incident['telemetry_version'],'returned_at_sim_seconds':sim.time,
                         'applied':bool(applied),'result':result})
        schedule.append(sim.time)
        if applied: previous = result['proposal']
    advance_updates(sim,case['horizon_seconds'])
    passive = Simulator(case); advance_updates(passive,case['horizon_seconds'])
    instant = Simulator(case)
    instant.apply(reference_proposal(case))
    for update in case['updates']:
        advance_updates(instant,update['at']); instant.apply(reference_proposal(case,instant.incident,update['reference']))
    advance_updates(instant,case['horizon_seconds'])
    matched = Simulator(case)
    for at in schedule:
        advance_updates(matched,at)
        refs = case['reference']
        for update in case['updates']:
            if update['at'] <= at: refs = update['reference']
        matched.apply(reference_proposal(case,matched.incident,refs))
    advance_updates(matched,case['horizon_seconds'])
    outcomes = sim.snapshot(); baseline = passive.snapshot(); ref = matched.snapshot()
    dimensions = ('bytes_lost','additional_hosts_compromised','identity_abuse_events')
    coverage = all(outcomes[k] <= ref[k]+1e-6 for k in dimensions)
    safe = outcomes['policy_rejections']==0 and outcomes['false_positive_controls']==0 and outcomes['evidence_gap_seconds']==0
    statuses = all(a['result']['status']=='validated' and a['applied'] for a in attempts)
    # Match explicit scenario dependencies; no claim that these model reality.
    disruption = outcomes['service_disruption_seconds'] <= ref['service_disruption_seconds']+1e-6
    investigated = case['truth'] != 'ambiguous' or any(e['type']=='evidence_requested' for e in outcomes['trace'])
    deadline = all(a['result'].get('latency_seconds',0) <= case['response_deadline_seconds'] for a in attempts)
    return {'incident_id':case['case_id'],'family':case['family'],'technique':case['technique'],
            'seed':case['seed'],'truth':case['truth'],'status':'validated' if statuses else 'failed',
            'scenario_pass':coverage and safe and statuses and disruption and investigated and deadline,
            'checks':{'threat_outcome_matches_latency_reference':coverage,'safe':safe,
                      'all_responses_applied':statuses,'no_extra_service_disruption':disruption,
                      'ambiguous_alert_investigated':investigated,'response_deadline_met':deadline},
            'inference':attempts,'outcomes':outcomes,'no_response':baseline,
            'instant_fixture_reference':instant.snapshot(),'latency_matched_fixture_reference':ref,
            'benefit':{k:baseline[k]-outcomes[k] for k in dimensions}}


def percentile(values,p):
    if not values: return None
    ordered=sorted(values); pos=(len(ordered)-1)*p
    low=int(pos); high=min(low+1,len(ordered)-1)
    return round(ordered[low]+(ordered[high]-ordered[low])*(pos-low),3)


def wilson(success,total):
    if not total: return None
    z=1.96; p=success/total; den=1+z*z/total
    mid=(p+z*z/(2*total))/den
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [round(max(0,mid-half),4),round(min(1,mid+half),4)]


def summarize(results):
    latencies=[a['result']['latency_seconds'] for r in results for a in r['inference'] if 'latency_seconds' in a['result']]
    groups={}
    for r in results:
        g=groups.setdefault(r['family'],{'completed':0,'passed':0,'bytes_lost':0,'additional_hosts_compromised':0,'identity_abuse_events':0})
        g['completed']+=1; g['passed']+=int(r['scenario_pass'])
        for k in ('bytes_lost','additional_hosts_compromised','identity_abuse_events'): g[k]+=r['outcomes'][k]
    benign=[r for r in results if r['truth']=='benign']
    false=sum(r['outcomes']['false_positive_controls']>0 for r in benign)
    completed=len(results); passed=sum(r['scenario_pass'] for r in results)
    return {'completed':completed,'passed':passed,'families':groups,
            'latency_seconds':{'p50':percentile(latencies,.5),'p95':percentile(latencies,.95),'max':max(latencies,default=None)},
            'benign_incidents':len(benign),'benign_false_positive_incidents':false,
            'benign_false_positive_rate':false/len(benign) if benign else None,
            'descriptive_wilson_95':wilson(passed,completed),
            'interval_caveat':'Correlated seed variants violate independence. Descriptive interval only; not population accuracy.',
            'total_bytes_prevented':sum(r['benefit']['bytes_lost'] for r in results),
            'total_additional_hosts_prevented':sum(r['benefit']['additional_hosts_compromised'] for r in results),
            'policy_rejections':sum(r['outcomes']['policy_rejections'] for r in results),
            'response_failures':sum(a['result']['status']!='validated' for r in results for a in r['inference']),
            'correction_attempts':sum(max(0,len(a['result'].get('attempts',[]))-1) for r in results for a in r['inference'])}


def report(data,path):
    s=data['summary']; complete=s['completed']==data['planned']
    lines=['# Containment outcome benchmark', '',f"Status: {'COMPLETE' if complete else 'PARTIAL'} — {s['passed']}/{s['completed']} completed cases passed; {data['planned']} planned.",
           '',f"Mode: {data['mode']}; model: {data['config']['model']}. Synthetic simulator outcomes; no real attacks executed.",
           '', '| Family | Passed / completed | Bytes lost | Additional hosts | Identity abuse |', '|---|---:|---:|---:|---:|']
    for name,g in s['families'].items(): lines.append(f"| {name} | {g['passed']}/{g['completed']} | {g['bytes_lost']:.0f} | {g['additional_hosts_compromised']} | {g['identity_abuse_events']} |")
    lines += ['',f"Inference latency: {s['latency_seconds']}. Benign false-positive incidents: {s['benign_false_positive_incidents']}/{s['benign_incidents']}.",
              f"Bytes prevented versus no response: {s['total_bytes_prevented']:.0f}; additional hosts prevented: {s['total_additional_hosts_prevented']}.",
              '', 'Each raw case includes attack/control traces, no-response, instant fixture reference, and latency-matched fixture reference outcomes. The fixture reference knows scenario truth; it is not another agent or a verified global optimum.',
              '', 'Cases are new development templates with opaque identifiers, not an independently labeled external holdout. Seed variants are correlated. Network containment does not stop local encryption. Rates, dependencies, the 600-second horizon and the 120-second response deadline are explicit benchmark assumptions, not industry standards. A scenario pass compares to a reference at the same response times and enforces that deadline; inspect the instant reference and absolute losses to see latency costs.',
              '', 'Failures:', *[f"- {r['incident_id']} ({r['family']}): {r['checks']}" for r in data['results'] if not r['scenario_pass']]]
    Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',default='results/outcome-foundation.json'); p.add_argument('--resume',action='store_true')
    p.add_argument('--model',default=agent.MODEL); p.add_argument('--endpoint',default='http://127.0.0.1:8000/v1')
    p.add_argument('--max-tokens',type=int,default=2200); p.add_argument('--reasoning-effort')
    p.add_argument('--seeds',default='17,29,43'); p.add_argument('--limit',type=int)
    p.add_argument('--mode',choices=['model','reference'],default='model')
    args=p.parse_args(); cases=dataset(tuple(int(s) for s in args.seeds.split(',')))
    if args.limit: cases=cases[:args.limit]
    config=eval_checkpoint.configuration(args,cases)
    config.update(mode=args.mode,source_hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                  for name in ('simulator.py','outcome_benchmark.py','benchmark_cases.py','agent.py','eval_checkpoint.py')})
    if args.resume and Path(args.output).exists() and not json.loads(Path(args.output).read_text()).get('config'):
        raise RuntimeError('Outcome checkpoints require configuration hashes')
    results,notes=eval_checkpoint.load(args.output,config,[c['case_id'] for c in cases],args.resume)
    for case in cases[len(results):]:
        if args.mode=='reference':
            def predictor(incident,previous):
                refs=case['reference']
                for update in case['updates']:
                    if incident['telemetry_version'] >= update['incident']['telemetry_version']: refs=update['reference']
                return {'status':'validated','proposal':reference_proposal(case,incident,refs),'latency_seconds':0,'attempts':[]}
        else:
            def predictor(incident,previous):
                return agent.propose(incident,args.endpoint,args.model,previous=previous,max_tokens=args.max_tokens,reasoning_effort=args.reasoning_effort)
        result=run_case(case,predictor); result['model']=args.model
        results.append(result)
        data={'config':config,'mode':args.mode,'planned':len(cases),'resume_notes':notes,
              'summary':summarize(results),'results':results}
        eval_checkpoint.save(args.output,data); report(data,Path(args.output).with_suffix('.md'))
        print(case['case_id'],case['family'],result['scenario_pass'],data['summary']['latency_seconds'],flush=True)
    if not results: raise RuntimeError('Empty benchmark')


if __name__=='__main__': main()
