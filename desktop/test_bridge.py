import tempfile
import threading
import time
import unittest
import json
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from council.protocol import run
from council.scenarios import dataset
from desktop.bridge import Workspace, Handler


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Workspace(self.tmp.name, pace=0, approval_timeout=2)

    def tearDown(self):
        for item in self.workspace.runs.values():
            item['signal'].set()
        time.sleep(.03)
        self.tmp.cleanup()

    def pending(self, run_id):
        until = time.monotonic()+2
        while time.monotonic()<until:
            data=self.workspace.snapshot(run_id)
            if data['pending']: return data['pending']
            time.sleep(.01)
        self.fail('No approval checkpoint')

    def finished(self, run_id):
        until = time.monotonic()+3
        while time.monotonic()<until:
            data=self.workspace.snapshot(run_id)
            if data['result']: return data
            time.sleep(.01)
        self.fail('Run did not finish')

    def test_approval_bound_to_plan_and_only_consumed_once(self):
        rid=self.workspace.start('mitre-T1041','mock')
        pending=self.pending(rid)
        self.assertIsNone(self.workspace.snapshot(rid)['result'])
        with self.assertRaises(ValueError): self.workspace.decide(rid,'wrong','approve','test approval')
        self.workspace.decide(rid,pending['id'],'approve','UI test: scope reviewed')
        with self.assertRaises(ValueError): self.workspace.decide(rid,pending['id'],'approve','duplicate')
        final=self.finished(rid)
        self.assertFalse(final['result']['human_alert']['required'])
        self.assertTrue(final['result']['decisions'])
        types=[e['type'] for e in final['events']]
        self.assertLess(types.index('human_decision'),types.index('completed'))

    def test_rejection_never_applies_plan(self):
        rid=self.workspace.start('mitre-T1041','mock')
        pending=self.pending(rid)
        self.workspace.decide(rid,pending['id'],'reject','UI test: reject scope')
        final=self.finished(rid)['result']
        self.assertEqual(final['status'],'ESCALATED')
        self.assertFalse(final['decisions'])
        self.assertFalse(any(r['kind']=='simulated_restoration' for r in final['tool_receipts']))

    def test_timeout_fails_closed(self):
        self.workspace.approval_timeout=.05
        rid=self.workspace.start('mitre-T1041','mock')
        final=self.finished(rid)
        self.assertEqual(final['result']['status'],'ESCALATED')
        self.assertFalse(final['result']['decisions'])
        self.assertTrue(any(e['type']=='approval_expired' for e in final['events']))

    def test_binding_escalation_never_offers_override(self):
        case=next(c for c in dataset() if c.case_id=='mitre-T1003-001')
        offered=[]
        result=run(case,approval=lambda p: offered.append(p) or True)
        self.assertTrue(result['human_alert']['required'])
        self.assertEqual(offered,[])

    def test_no_parallel_runs_or_invalid_modes(self):
        rid=self.workspace.start('mitre-T1041','mock')
        self.pending(rid)
        with self.assertRaises(ValueError): self.workspace.start('mitre-T1041','mock')
        with self.assertRaises(ValueError): self.workspace.start('mitre-T1041','production')

    def test_incremental_events_have_stable_ids(self):
        rid=self.workspace.start('mitre-T1041','mock')
        self.pending(rid)
        data=self.workspace.snapshot(rid)
        self.assertEqual([e['id'] for e in data['events']],list(range(1,len(data['events'])+1)))
        self.assertFalse(self.workspace.snapshot(rid,len(data['events']))['events'])

    def test_restart_history_does_not_resume_pending_approval(self):
        rid=self.workspace.start('mitre-T1041','mock')
        pending=self.pending(rid)
        restored=Workspace(self.tmp.name,pace=0)
        item=restored.snapshot(rid)
        self.assertEqual(item['status'],'interrupted')
        self.assertIsNone(item['pending'])
        with self.assertRaises(ValueError): restored.decide(rid,pending['id'],'approve','stale restart decision')


class WebServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.workspace=Workspace(Path(self.tmp.name)/'reports',pace=0)
        self.server.web_root=(Path(self.tmp.name)/'web').resolve()
        self.server.web_root.mkdir()
        (self.server.web_root/'index.html').write_text('<h1>Sentinel</h1>')
        (self.server.web_root/'app.js').write_text('console.log("Sentinel")')
        (Path(self.tmp.name)/'secret.txt').write_text('private')
        self.server.csrf_token=uuid.uuid4().hex
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.server.allowed_origins={self.base}
        threading.Thread(target=self.server.serve_forever,daemon=True).start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.tmp.cleanup()

    def test_serves_ui_and_health_from_same_host(self):
        with urlopen(self.base) as response:
            self.assertIn(b'Sentinel',response.read())
        with urlopen(self.base+'/api/health') as response:
            self.assertEqual(json.load(response)['csrf_token'],self.server.csrf_token)
        with urlopen(self.base+'/app.js') as response:
            self.assertEqual(response.headers['Content-Type'],'text/javascript')

    def test_traversal_cannot_expose_evidence_or_files(self):
        for route in ['/../secret.txt','/%2e%2e/secret.txt']:
            with self.assertRaises(HTTPError) as error: urlopen(self.base+route)
            self.assertEqual(error.exception.code,404)

    def test_cross_origin_and_missing_token_rejected(self):
        for headers in [{'Origin':'https://evil.example','X-Sentinel-CSRF':self.server.csrf_token},{'Origin':self.base}]:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(self.base+'/api/runs',data=b'{}',headers={'Content-Type':'application/json',**headers}))
            self.assertEqual(error.exception.code,403)

if __name__=='__main__': unittest.main()
