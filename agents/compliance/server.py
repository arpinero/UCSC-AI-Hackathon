"""Loopback-only review API so the council can call Compliance like Containment."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os

import agent

PORT = int(os.environ.get('COMPLIANCE_PORT', '8020'))
LOCAL_HOSTS = {'127.0.0.1', 'localhost'}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def local(self):
        # Loopback bind alone doesn't stop a browser on the box: DNS rebinding sends a
        # foreign Host header, and a cross-site form post can't set a JSON content type.
        host = (self.headers.get('Host') or '').rsplit(':', 1)[0]
        if host not in LOCAL_HOSTS:
            self.respond(403, {'error': 'Host must be 127.0.0.1 or localhost'})
            return False
        return True

    def do_GET(self):
        if not self.local():
            return
        if self.path != '/health':
            return self.respond(404, {'error': 'Unknown route'})
        self.respond(200, {'status': 'ok', 'model': agent.MODEL, 'endpoint': agent.ENDPOINT})

    def do_POST(self):
        if not self.local():
            return
        if self.path != '/review':
            return self.respond(404, {'error': 'Unknown route'})
        if not (self.headers.get('Content-Type') or '').startswith('application/json'):
            return self.respond(415, {'error': 'Content-Type must be application/json'})
        try:
            self.connection.settimeout(10)
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 48000:
                return self.respond(413, {'error': 'Body must be 1-48000 bytes'})
            data = json.loads(self.rfile.read(size))
            # propose() fails closed on its own; pass its result through
            self.respond(200, agent.propose(data['incident'], peers=data.get('peer_messages'),
                                            peer_proposals=data.get('peer_proposals'),
                                            previous=data.get('previous_proposal')))
        except (ValueError, KeyError, TypeError, AttributeError, TimeoutError) as exc:
            self.respond(400, {'error': str(exc)})


if __name__ == '__main__':
    print(f'Compliance review API: http://127.0.0.1:{PORT}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
