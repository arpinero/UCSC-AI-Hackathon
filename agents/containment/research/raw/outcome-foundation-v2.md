# Containment outcome benchmark

Status: PARTIAL — 20/23 completed cases passed; 48 planned.

Mode: model; model: fdtn-ai/Foundation-Sec-8B-Instruct. Synthetic simulator outcomes; no real attacks executed.

| Family | Passed / completed | Bytes lost | Additional hosts | Identity abuse |
|---|---:|---:|---:|---:|
| exfiltration | 2/2 | 2215258 | 0 | 0 |
| lateral_smb | 2/2 | 0 | 0 | 0 |
| lateral_rdp | 2/2 | 0 | 0 | 0 |
| remote_exploit | 1/2 | 0 | 0 | 0 |
| ransomware | 2/2 | 0 | 0 | 0 |
| credential_dump | 2/2 | 0 | 0 | 0 |
| malicious_powershell | 2/2 | 0 | 0 | 0 |
| stolen_session | 1/1 | 0 | 0 | 0 |
| compromised_account | 1/1 | 0 | 0 | 0 |
| authorized_backup | 0/1 | 0 | 0 | 0 |
| ambiguous_alert | 0/1 | 0 | 0 | 0 |
| critical_service | 1/1 | 1649922 | 0 | 0 |
| protected_destination | 1/1 | 1534016 | 0 | 0 |
| combined_paths | 1/1 | 1794721 | 0 | 0 |
| destination_rotation | 1/1 | 2672696 | 0 | 0 |
| identity_dependencies | 1/1 | 0 | 0 | 0 |

Inference latency: {'p50': 20.742, 'p95': 38.07, 'max': 41.33}. Benign false-positive incidents: 1/1.
Bytes prevented versus no response: 222944187; additional hosts prevented: 26.

Each raw case includes attack/control traces, no-response, instant fixture reference, and latency-matched fixture reference outcomes. The fixture reference knows scenario truth; it is not another agent or a verified global optimum.

Cases are new development templates with opaque identifiers, not an independently labeled external holdout. Seed variants are correlated. Network containment does not stop local encryption. Rates, dependencies, the 600-second horizon and the 120-second response deadline are explicit benchmark assumptions, not industry standards. A scenario pass compares to a reference at the same response times and enforces that deadline; inspect the instant reference and absolute losses to see latency costs.

Failures:
- x-20795c89be (remote_exploit): {'threat_outcome_matches_latency_reference': True, 'safe': True, 'all_responses_applied': True, 'no_extra_service_disruption': False, 'ambiguous_alert_investigated': True, 'response_deadline_met': True}
- x-24d3b6d3cc (authorized_backup): {'threat_outcome_matches_latency_reference': True, 'safe': False, 'all_responses_applied': True, 'no_extra_service_disruption': True, 'ambiguous_alert_investigated': True, 'response_deadline_met': True}
- x-6bd5729b7e (ambiguous_alert): {'threat_outcome_matches_latency_reference': True, 'safe': False, 'all_responses_applied': True, 'no_extra_service_disruption': False, 'ambiguous_alert_investigated': False, 'response_deadline_met': True}
