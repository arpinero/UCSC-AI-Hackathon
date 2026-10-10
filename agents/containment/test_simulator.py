import copy
import unittest
from benchmark_cases import dataset, reference_proposal
from outcome_benchmark import run_case, percentile, summarize
from simulator import Simulator


class SimulatorTests(unittest.TestCase):
    def case(self,family): return next(c for c in dataset((17,)) if c['family']==family)
    def test_all_reference_cases(self):
        for case in dataset():
            with self.subTest(family=case['family'],seed=case['seed']):
                def predict(incident,previous):
                    refs=case['reference'] if incident['telemetry_version']==1 else case['updates'][0]['reference']
                    return {'status':'validated','proposal':reference_proposal(case,incident,refs),'latency_seconds':0}
                self.assertTrue(run_case(case,predict)['scenario_pass'])
    def test_latency_costs_bytes(self):
        case=self.case('exfiltration'); sim=Simulator(case); sim.advance(30)
        sim.apply(reference_proposal(case)); sim.advance(600)
        self.assertEqual(sim.metrics['bytes_lost'],30*case['events'][0]['rate'])
    def test_expiry_restores_attack(self):
        case=self.case('exfiltration'); sim=Simulator(case); proposal=reference_proposal(case)
        proposal['actions'][0]['ttl_minutes']=1; sim.apply(proposal); sim.advance(600)
        self.assertEqual(sim.metrics['bytes_lost'],540*case['events'][0]['rate'])
    def test_rollback_preserves_unrelated_control(self):
        case=self.case('combined_paths'); sim=Simulator(case); sim.apply(reference_proposal(case))
        key=next(c['key'] for c in sim.controls if c['action']['kind']=='block_egress')
        sim.rollback(key); self.assertEqual(len(sim.active()),1)
        sim.advance(600); self.assertEqual(sim.metrics['additional_hosts_compromised'],0)
        self.assertGreater(sim.metrics['bytes_lost'],0)
    def test_stale_and_protected_proposals_cannot_execute(self):
        case=self.case('destination_rotation'); sim=Simulator(case); proposal=reference_proposal(case)
        sim.update(case['updates'][0]['incident']); self.assertFalse(sim.apply(proposal))
        self.assertEqual(sim.active(),[])
        case=self.case('protected_destination'); proposal=reference_proposal(case)
        proposal['actions'][0].update(kind='block_egress',target_id=next(a['id'] for a in case['incident']['assets'] if a.get('protected')),scope_host_ids=case['initial_compromised'])
        self.assertFalse(Simulator(case).apply(proposal))
    def test_isolation_does_not_stop_local_encryption(self):
        case=self.case('ransomware'); sim=Simulator(case); proposal=reference_proposal(case)
        proposal['actions'][0]['kind']='isolate_host'; sim.apply(proposal); sim.advance(600)
        self.assertEqual(sim.metrics['local_files_damaged'],1200)
        self.assertEqual(sim.metrics['additional_hosts_compromised'],0)
    def test_account_disable_leaves_issued_session(self):
        case=self.case('identity_dependencies'); sim=Simulator(case); proposal=reference_proposal(case)
        proposal['actions']=[a for a in proposal['actions'] if a['kind']=='disable_account']
        for r in proposal['evidence_review']:
            if r['evidence_id'] not in proposal['actions'][0]['evidence_ids']: r['decision']='no_action'
        self.assertTrue(sim.apply(proposal)); sim.advance(600)
        self.assertEqual(sim.metrics['identity_abuse_events'],3)
    def test_scope_does_not_block_other_host(self):
        case=self.case('exfiltration'); sim=Simulator(case); sim.apply(reference_proposal(case))
        e=copy.deepcopy(case['events'][0]); e['source']='another-host'
        self.assertFalse(sim.blocked(e,sim.active()))
    def test_service_cost_union_and_renewal(self):
        case=self.case('ransomware'); sim=Simulator(case); p=reference_proposal(case)
        p['actions'][0]['kind']='isolate_host'; sim.apply(p); sim.advance(10); sim.apply(p); sim.advance(60)
        self.assertEqual(sim.metrics['service_disruption_seconds'],60)
    def test_partition_invariance(self):
        case=self.case('ransomware'); a=Simulator(case); b=Simulator(case)
        a.advance(600)
        for t in (100,200,300,400,500,600): b.advance(t)
        self.assertEqual(a.metrics,b.metrics)
    def test_opaque_identifiers_and_reproducibility(self):
        self.assertEqual(dataset(),dataset())
        for case in dataset():
            self.assertNotIn(case['family'],case['incident']['incident_id'])
            self.assertNotIn('truth',case['incident'])
            self.assertNotIn('reference',case['incident'])
    def test_rejected_response_has_real_losses(self):
        case=self.case('exfiltration')
        r=run_case(case,lambda i,p:{'status':'rejected','proposal':None,'latency_seconds':2})
        self.assertFalse(r['scenario_pass']); self.assertEqual(r['outcomes']['bytes_lost'],r['no_response']['bytes_lost'])
    def test_percentiles(self): self.assertEqual(percentile([1,2,3,4,5],.95),4.8)
    def test_late_stale_response_fails(self):
        case=self.case('destination_rotation')
        def predict(incident,previous):
            refs=case['reference'] if incident['telemetry_version']==1 else case['updates'][0]['reference']
            return {'status':'validated','proposal':reference_proposal(case,incident,refs),'latency_seconds':250}
        r=run_case(case,predict)
        self.assertFalse(r['scenario_pass'])
        self.assertEqual(r['outcomes']['policy_rejections'],1)
    def test_ambiguous_abstention_requires_investigation(self):
        case=self.case('ambiguous_alert'); p=reference_proposal(case); p['actions']=[]
        for review in p['evidence_review']: review['decision']='no_action'
        r=run_case(case,lambda i,prev:{'status':'validated','proposal':p,'latency_seconds':0})
        self.assertFalse(r['scenario_pass'])
    def test_policy_update_removes_illegal_active_control(self):
        case=self.case('exfiltration'); sim=Simulator(case); sim.apply(reference_proposal(case))
        new=copy.deepcopy(case['incident']); new['telemetry_version']=2
        for a in new['assets']:
            if a['id']==case['reference'][0][1]: a['protected']=True
        sim.update(new); self.assertEqual(sim.active(),[])
    def test_no_spread_from_uncompromised_peer(self):
        case=self.case('lateral_smb'); case['events']=[case['events'][-1]]
        sim=Simulator(case); sim.advance(600)
        self.assertEqual(sim.metrics['additional_hosts_compromised'],0)


if __name__=='__main__': unittest.main()
