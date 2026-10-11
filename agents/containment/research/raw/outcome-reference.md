# Containment outcome benchmark

Status: COMPLETE — 48/48 completed cases passed; 48 planned.

Mode: reference; model: fdtn-ai/Foundation-Sec-8B-Instruct. Synthetic simulator outcomes; no real attacks executed.

| Family | Passed / completed | Bytes lost | Additional hosts | Identity abuse |
|---|---:|---:|---:|---:|
| exfiltration | 3/3 | 0 | 0 | 0 |
| lateral_smb | 3/3 | 0 | 0 | 0 |
| lateral_rdp | 3/3 | 0 | 0 | 0 |
| remote_exploit | 3/3 | 0 | 0 | 0 |
| ransomware | 3/3 | 0 | 0 | 0 |
| credential_dump | 3/3 | 0 | 0 | 0 |
| malicious_powershell | 3/3 | 0 | 0 | 0 |
| stolen_session | 3/3 | 0 | 0 | 0 |
| compromised_account | 3/3 | 0 | 0 | 0 |
| authorized_backup | 3/3 | 0 | 0 | 0 |
| ambiguous_alert | 3/3 | 0 | 0 | 0 |
| critical_service | 3/3 | 0 | 0 | 0 |
| protected_destination | 3/3 | 0 | 0 | 0 |
| combined_paths | 3/3 | 0 | 0 | 0 |
| destination_rotation | 3/3 | 0 | 0 | 0 |
| identity_dependencies | 3/3 | 0 | 0 | 0 |

Inference latency: {'p50': 0.0, 'p95': 0.0, 'max': 0}. Benign false-positive incidents: 0/3.
Bytes prevented versus no response: 532486200; additional hosts prevented: 42.

Each raw case includes attack/control traces, no-response, instant fixture reference, and latency-matched fixture reference outcomes. The fixture reference knows scenario truth; it is not another agent or a verified global optimum.

Cases are new development templates with opaque identifiers, not an independently labeled external holdout. Seed variants are correlated. Network containment does not stop local encryption. Rates, dependencies, the 600-second horizon and the 120-second response deadline are explicit benchmark assumptions, not industry standards. A scenario pass compares to a reference at the same response times and enforces that deadline; inspect the instant reference and absolute losses to see latency costs.

Failures:
