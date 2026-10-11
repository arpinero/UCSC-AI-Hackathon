# ASUS live UI connection

The bridge and council must run on the ASUS to reach its loopback model services. A Windows `python -m desktop.bridge` process does not connect to ASUS models by itself. The private VS Code port forwarding gives the browser access to the ASUS bridge; it does not move the GPU services onto Windows.

Current isolated checkout: `/home/asus/sentinel-web`, branch `desktop-ui`, synced with council `e0312bd`. UI/API port: 8787, forwarded privately through the existing authenticated VS Code session.

Current real-model configuration:

```bash
cd /home/asus/sentinel-web
env -u COUNCIL_FIXING_ENDPOINT -u COUNCIL_FIXING_MODEL \
  COUNCIL_MODEL=gemma4:26b \
  COUNCIL_FORENSICS_URL=http://127.0.0.1:8747 \
  python3 -m desktop.bridge --port 8787 \
  --origin https://b68plvc5-8787.usw3.devtunnels.ms
```

- Containment: dedicated service on 8010; health reported `qwen3.6:35b` on 2026-10-10.
- Compliance: dedicated service on 8020.
- Forensics: teammate's v1 API on 8747.
- Recovery and peer votes: real `gemma4:26b` inference through Ollama on 11434, using the council's supported shared-model configuration.
- All incident fixtures and action execution remain simulated. Live mode means real model inference, not modifications to real hosts.

The optional Recovery model endpoint on 8001 was tested first. Run `20314cc16b4749b094318fc24e10e48d` completed Containment in 46.045 seconds, then Recovery timed out after 240 seconds. That failure is retained in the event journal; it was not replaced with mock output. The optional model service was left untouched.

The subsequent real-model run is `4d36e846d28842a79972514929df3fee`. Its completion is not claimed until the recorded protocol result is inspected. Open a specific investigation using `?run=RUN_ID` on the ASUS UI address.

The UI now preflights required live services before starting a run. The model inventory reports the actual configured routes, including shared inference, instead of displaying an unused specialist server. Current checks: 35 Python tests, 6 JavaScript tests, and a clean frontend check/build.
