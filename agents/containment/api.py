"""Loopback-only proposal API for the team's transport adapter."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import uuid
import urllib.request
import urllib.error
from agent import propose, MODEL

ENDPOINT = os.environ.get('CONTAINMENT_ENDPOINT', 'http://127.0.0.1:8000/v1')
SELECTED_MODEL = os.environ.get('CONTAINMENT_MODEL', MODEL)
MAX_TOKENS = int(os.environ.get('CONTAINMENT_MAX_TOKENS', '2200'))
REASONING = os.environ.get('CONTAINMENT_REASONING_EFFORT')

SLOTS = threading.BoundedSemaphore(2)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != '/health':
            return self.respond(404, {'error': 'Unknown route'})
        try:
            native = ENDPOINT.rstrip('/').endswith('/api')
            health = ENDPOINT.rstrip('/') + '/tags' if native else ENDPOINT.rstrip('/').removesuffix('/v1') + '/health'
            with urllib.request.urlopen(health, timeout=2) as response:
                ready = response.status == 200
                if native:
                    ready = ready and any(m['name'] == SELECTED_MODEL for m in json.load(response)['models'])
        except (urllib.error.URLError, TimeoutError, OSError):
            ready = False
        self.respond(200 if ready else 503, {'service': 'containment-proposals',
                     'mode': 'simulation', 'inference_ready': ready,
                     'model': SELECTED_MODEL,
                     'weights': os.environ.get('CONTAINMENT_WEIGHTS', 'fdtn-ai/Foundation-Sec-8B-Instruct-Q8_0-GGUF')})

    def do_POST(self):
        if self.path != '/propose':
            return self.respond(404, {'error': 'Unknown route'})
        if not SLOTS.acquire(blocking=False):
            return self.respond(429, {'error': 'Two requests already active; retry later'})
        try:
            self.connection.settimeout(10)
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 48000:
                return self.respond(413, {'error': 'Body must be 1-48000 bytes'})
            data = json.loads(self.rfile.read(size))
            result = propose(data['incident'], peers=data.get('peer_messages'), previous=data.get('previous_proposal'),
                             endpoint=ENDPOINT, model=SELECTED_MODEL, max_tokens=MAX_TOKENS, reasoning_effort=REASONING)
            audit_id = str(uuid.uuid4())
            root = Path(__file__).parent / 'results' / 'audit'
            root.mkdir(parents=True, exist_ok=True)
            (root / (audit_id + '.json')).write_text(json.dumps({'input': data, 'result': result}, indent=2))
            result['audit_id'] = audit_id
            self.respond(200 if result['status'] == 'validated' else 503 if result['status'] == 'unavailable' else 422, result)
        except (ValueError, KeyError, TypeError, TimeoutError) as exc:
            self.respond(400, {'error': str(exc)})
        finally:
            SLOTS.release()


if __name__ == '__main__':
    print('Containment proposal API: http://127.0.0.1:8010', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8010), Handler).serve_forever()
