"""Team entry point for the qualified proposal API; no direct model fallback."""
import argparse
import json
from pathlib import Path
import urllib.error
import urllib.request
from agent import validate_incident, validate_proposal


def propose(incident, peer_messages=None, previous_proposal=None,
            service_url='http://127.0.0.1:8010', expected_model='qwen3.6:35b', timeout=240):
    try:
        validate_incident(incident)
    except (ValueError, KeyError, TypeError) as error:
        return {'status': 'invalid_input', 'proposal': None, 'error': str(error)}
    envelope = {'incident': incident, 'peer_messages': peer_messages or [],
                'previous_proposal': previous_proposal}
    request = urllib.request.Request(service_url.rstrip('/') + '/propose',
                                     data=json.dumps(envelope).encode(),
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
        if not isinstance(result, dict) or result.get('status') != 'validated':
            raise ValueError('Unexpected proposal service response')
        if result.get('model') != expected_model:
            raise ValueError('Proposal service returned an unqualified model')
        result['proposal'] = validate_proposal(result['proposal'], incident)
        return result
    except urllib.error.HTTPError as error:
        # Never accept a success-looking body on an error HTTP status.
        status = {400: 'invalid_input', 413: 'invalid_input', 422: 'rejected',
                  429: 'busy', 503: 'unavailable'}.get(error.code, 'unavailable')
        return {'status': status, 'proposal': None, 'http_status': error.code}
    except (ValueError, KeyError, TypeError, urllib.error.URLError, TimeoutError, OSError) as error:
        return {'status': 'unavailable', 'proposal': None, 'error': str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('incident'); parser.add_argument('--peers'); parser.add_argument('--previous')
    parser.add_argument('--service-url', default='http://127.0.0.1:8010')
    parser.add_argument('--expected-model', default='qwen3.6:35b')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8')) if p else None
    result = propose(read(args.incident), read(args.peers), read(args.previous),
                     service_url=args.service_url, expected_model=args.expected_model)
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps({'status': result['status'], 'model': result.get('model'), 'output': str(output)}))
    if result['status'] != 'validated':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
