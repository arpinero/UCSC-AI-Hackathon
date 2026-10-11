import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import agent
import server


def call(base, path, body=None):
    req = urllib.request.Request(base + path, data=body, method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.httpd.server_port}'
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def test_health(self):
        self.assertEqual(call(self.base, '/health'),
                         (200, {'status': 'ok', 'model': agent.MODEL, 'endpoint': agent.ENDPOINT}))

    def test_review_passes_args(self):
        body = json.dumps({'incident': {'a': 1}, 'peer_proposals': [{'p': 1}],
                           'peer_messages': [{'m': 1}], 'previous_proposal': {'v': 0}}).encode()
        with mock.patch.object(agent, 'propose', return_value={'status': 'validated'}) as p:
            self.assertEqual(call(self.base, '/review', body), (200, {'status': 'validated'}))
        p.assert_called_once_with({'a': 1}, peers=[{'m': 1}], peer_proposals=[{'p': 1}], previous={'v': 0})

    def test_bad_requests(self):
        self.assertEqual(call(self.base, '/review', b'{nope')[0], 400)
        self.assertEqual(call(self.base, '/review', b'{}')[0], 400)
        self.assertEqual(call(self.base, '/review', b'{"incident": {}}')[0], 400)  # real validate_incident
        self.assertEqual(call(self.base, '/nope')[0], 404)
        self.assertEqual(call(self.base, '/nope', b'{}')[0], 404)


if __name__ == '__main__':
    unittest.main()
