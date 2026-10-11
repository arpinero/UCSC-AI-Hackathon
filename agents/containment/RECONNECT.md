# Reconnect after an address change

## VS Code Remote Tunnels

The organizer-provided screen shows a running tunnel named `asus-machine` at https://vscode.dev/tunnel/asus-machine. The Windows client extension `ms-vscode.remote-server` version 1.5.4 was installed successfully. Remote access was verified around 16:00 PDT on October 10 after the user completed Microsoft account authentication. The remote shell reported `asus@16RW`, architecture `aarch64`, and uptime about one hour.

Open the URL and choose **Microsoft Account**, using the account that started the tunnel on the ASUS device (the user reports this is a teammate's account). For desktop VS Code, press F1 and run **Remote - Tunnels: Connect to Tunnel...**, then select `asus-machine`. Open `/home/asus/containment-agent` after connecting. Keep the device's tunnel process running. The web editor includes the tunnel client; the desktop extension provides an alternative client. No account credentials are recorded here.

This uses the device's outbound tunnel connection and does not require its Wi-Fi address to remain fixed. It does not make the containment model/API publicly available. Once connected, verify the device identity, service health, and existing evaluator processes using the commands below before resuming. Persistence of the tunnel after device reboot still needs verification.

Official connection instructions: https://code.visualstudio.com/docs/remote/tunnels

## SSH fallback

Last verified Wi-Fi address: `169.233.72.113`, account `asus`. Tailscale currently has no IP and requires login; there is no verified alternate route. Device SSH ED25519 fingerprint: `SHA256:F12Hgmh9zoQxo3dyFxIFt0M1cnpF5zDqjpW+r7bScUk`.

Update only `HostName` in the included `ssh-config` to the organizer-provided new address. Keep `HostKeyAlias` so SSH verifies the device against its already-trusted key. Do not bypass a key mismatch; establish why it changed first. The configuration contains no password.

```powershell
ssh -F "C:/Users/Administrator/Documents/Codex/2026-10-10/https-github-com-arpinero-ucsc-ai/outputs/containment-agent/ssh-config" containment-gb10
```

The forwarded proposal API is `http://127.0.0.1:8010`; the Foundation model is `http://127.0.0.1:8000/v1`. Evaluate health after reconnect. Password entry belongs in the SSH prompt.

Remote work is under `/home/asus/containment-agent`. Evaluations run with `nohup`; user services have lingering enabled and survive SSH loss. A network disconnect does not stop them. Do not start duplicate evaluations until checking existing jobs/processes:

`nohup` evaluations do not survive device reboot. The model/API services were verified to restart after a reboot around 14:58 PDT. The boot-resumable evaluation service was installed, enabled and verified active through the tunnel at 15:59:47 PDT. All 34 tests passed on the device before startup. To reinstall from the containment checkout after confirming no duplicate evaluators are running:

```bash
cd /home/asus/containment-agent
git -C repo pull --ff-only
cp repo/agents/containment/{agent.py,api.py,mitre_eval.py,challenge_eval.py,evaluate.py,eval_checkpoint.py,run-evaluations.sh,containment-evaluations.service} .
mkdir -p ~/.config/systemd/user
cp containment-evaluations.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now containment-evaluations
systemctl --user status containment-evaluations --no-pager
```

The service checks model endpoints before scoring and uses `--resume` for both models' MITRE, challenge and smoke suites. It preserves failed cases and rejects configuration changes rather than silently mixing experiments. Completed suites are skipped. Disable the evaluation service after research completion if future boot runs are unnecessary.

```bash
cd /home/asus/containment-agent
systemctl --user is-active containment-model containment-api
curl -fsS http://127.0.0.1:8010/health
ps -u asus -o pid,etime,args | grep -E 'mitre_eval|challenge_eval|evaluate.py'
tail -10 logs/mitre-qwen-policy.log
tail -10 logs/mitre-foundation-policy.log
```

Actual current IPv4 address can be read on the device with `ip -4 -br addr`. Final/partial evaluation files are in `results/`, logs in `logs/`; source checkout is `repo/` on branch `containment`. API audit inputs and raw outputs are in `results/audit/`.

## Current outcome run

The old `containment-evaluations` service completed its regression suites and has been disabled to prevent boot attempts with a changed inference configuration. `containment-outcomes` is enabled and runs the revised v3 adapter: Qwen first, then Foundation, with separate checkpoints. It resumes only an exact matching configuration. The prior stopped Foundation v1/v2 results remain intact.

```bash
cd /home/asus/containment-agent
systemctl --user is-active containment-model containment-api containment-outcomes
tail -5 logs/outcome-qwen-v3.log
tail -5 logs/outcome-foundation-v3.log
python3 -m unittest discover -q
```

Use the full result's completion count before reporting a score. A running service or a reference-mode pass does not establish completed model performance. The source tests currently pass 59 tests locally and on the ASUS device.
