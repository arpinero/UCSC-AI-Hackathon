"""Smoke test for the Fixing agent model: one restore prompt, prints output and speed."""
import json
import time
import urllib.request

ENDPOINT = 'http://127.0.0.1:8001/v1/chat/completions'
MODEL = 'fdtn-ai/Foundation-Sec-8B-Reasoning'
PROMPT = ("Host workstation-01 was compromised via a malicious scheduled task (MITRE T1053.005) named "
          "'UpdaterSvc' that runs a PowerShell payload at logon. Forensics has already imaged the disk. "
          "List the ordered restore steps and what you must verify before declaring the host clean. "
          "Then state one question you would ask Compliance before restoring.")


def main():
    body = {'model': MODEL, 'temperature': 0.3, 'max_tokens': 1500, 'messages': [
        {'role': 'system', 'content': 'You are the Fixing member of a simulated incident response council. '
                                      'You restore files and system state only after Compliance approves. Be concise.'},
        {'role': 'user', 'content': PROMPT}]}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.load(response)
    elapsed = time.monotonic() - start
    choice = result['choices'][0]
    message = choice['message']
    timings = result.get('timings', {})
    print('finish_reason:', choice['finish_reason'])
    print('message keys:', sorted(message))
    print('elapsed_s: %.1f  completion_tokens: %s  tok/s: %s' % (
        elapsed, result['usage']['completion_tokens'], round(timings.get('predicted_per_second', 0), 1)))
    if message.get('reasoning_content'):
        print('--- reasoning (first 400 chars) ---')
        print(message['reasoning_content'][:400])
    print('--- content ---')
    print(message['content'])


if __name__ == '__main__':
    main()
