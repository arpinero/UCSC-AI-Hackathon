import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch
from benchmark_cases import dataset, reference_proposal
from containment_client import propose


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.case = dataset((17,))[0]; self.received = []
        self.code = 200
        self.body = {'status': 'validated', 'model': 'qwen3.6:35b',
                     'proposal': reference_proposal(self.case)}
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                owner.received.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(owner.code); self.end_headers()
                self.wfile.write(owner.body if isinstance(owner.body, bytes) else json.dumps(owner.body).encode())
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def call(self, **kwargs):
        return propose(self.case['incident'], service_url=self.url, **kwargs)

    def test_round_trip_preserves_incident_and_peer_envelope(self):
        original = copy.deepcopy(self.case['incident'])
        result = self.call(peer_messages=['Untrusted peer suggestion'])
        self.assertEqual(result['status'], 'validated')
        route, data = self.received[0]
        self.assertEqual(route, '/propose'); self.assertEqual(data['incident'], original)
        self.assertEqual(data['peer_messages'], ['Untrusted peer suggestion'])
        self.assertEqual(self.case['incident'], original)

    def test_error_status_cannot_return_success(self):
        self.code = 400
        result = self.call()
        self.assertEqual(result['status'], 'invalid_input'); self.assertIsNone(result['proposal'])

    def test_unavailable_service_never_calls_direct_inference(self):
        self.code = 503
        with patch('agent.propose', side_effect=AssertionError('Unexpected fallback')):
            result = self.call()
        self.assertEqual(result['status'], 'unavailable'); self.assertIsNone(result['proposal'])

    def test_malformed_service_json_is_rejected(self):
        self.body = b'not JSON'
        self.assertEqual(self.call()['status'], 'unavailable')

    def test_stale_returned_proposal_is_rejected(self):
        self.body['proposal']['telemetry_version'] += 1
        self.assertEqual(self.call()['status'], 'unavailable')

    def test_unqualified_model_is_rejected(self):
        self.body['model'] = 'experimental-model'
        self.assertEqual(self.call()['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
