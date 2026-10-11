# Containment outcome benchmark

Status: COMPLETE — 20/20 completed cases passed; 20 planned.

Mode: model; model: qwen3.6:35b. Synthetic simulator outcomes; no real attacks executed.

| Family | Passed / completed | Bytes lost | Additional hosts | Identity abuse |
|---|---:|---:|---:|---:|
| authorized_exfiltration | 2/2 | 0 | 0 | 0 |
| authorized_lateral_smb | 2/2 | 0 | 0 | 0 |
| authorized_lateral_rdp | 2/2 | 0 | 0 | 0 |
| authorized_remote_exploit | 2/2 | 0 | 0 | 0 |
| authorized_ransomware | 2/2 | 0 | 0 | 0 |
| authorized_credential_dump | 2/2 | 0 | 0 | 0 |
| authorized_malicious_powershell | 2/2 | 0 | 0 | 0 |
| authorized_stolen_session | 2/2 | 0 | 0 | 0 |
| authorized_compromised_account | 2/2 | 0 | 0 | 0 |
| authorized_identity_dependencies | 2/2 | 0 | 0 | 0 |

Inference latency: {'p50': 17.155, 'p95': 20.682, 'max': 20.982}. Benign false-positive incidents: 0/20.
Bytes prevented versus no response: 0; additional hosts prevented: 0.

Each raw case includes attack/control traces, no-response, instant fixture reference, and latency-matched fixture reference outcomes. The fixture reference knows scenario truth; it is not another agent or a verified global optimum.

Cases are new development templates with opaque identifiers, not an independently labeled external holdout. Seed variants are correlated. Network containment does not stop local encryption. Rates, dependencies, the 600-second horizon and the 120-second response deadline are explicit benchmark assumptions, not industry standards. A scenario pass compares to a reference at the same response times and enforces that deadline; inspect the instant reference and absolute losses to see latency costs.

Failures:
