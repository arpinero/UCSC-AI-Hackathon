# Reconnect after an address change

Last verified Wi-Fi address: `169.233.72.113`, account `asus`. Tailscale currently has no IP and requires login; there is no verified alternate route. Device SSH ED25519 fingerprint: `SHA256:F12Hgmh9zoQxo3dyFxIFt0M1cnpF5zDqjpW+r7bScUk`.

Update only `HostName` in the included `ssh-config` to the organizer-provided new address. Keep `HostKeyAlias` so SSH verifies the device against its already-trusted key. Do not bypass a key mismatch; establish why it changed first. The configuration contains no password.

```powershell
ssh -F "C:/Users/Administrator/Documents/Codex/2026-10-10/https-github-com-arpinero-ucsc-ai/outputs/containment-agent/ssh-config" containment-gb10
```

The forwarded proposal API is `http://127.0.0.1:8010`; the Foundation model is `http://127.0.0.1:8000/v1`. Evaluate health after reconnect. Password entry belongs in the SSH prompt.

Remote work is under `/home/asus/containment-agent`. Evaluations run with `nohup`; user services have lingering enabled and survive SSH loss. A network disconnect does not stop them. Do not start duplicate evaluations until checking existing jobs/processes:

```bash
cd /home/asus/containment-agent
systemctl --user is-active containment-model containment-api
curl -fsS http://127.0.0.1:8010/health
ps -u asus -o pid,etime,args | grep -E 'mitre_eval|challenge_eval|evaluate.py'
tail -10 logs/mitre-qwen-policy.log
tail -10 logs/mitre-foundation-policy.log
```

Actual current IPv4 address can be read on the device with `ip -4 -br addr`. Final/partial evaluation files are in `results/`, logs in `logs/`; source checkout is `repo/` on branch `containment`. API audit inputs and raw outputs are in `results/audit/`.
