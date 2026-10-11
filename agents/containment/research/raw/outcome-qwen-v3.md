# Containment outcome benchmark

Status: COMPLETE — 44/48 completed cases passed; 48 planned.

Mode: model; model: qwen3.6:35b. Synthetic simulator outcomes; no real attacks executed.

| Family | Passed / completed | Bytes lost | Additional hosts | Identity abuse |
|---|---:|---:|---:|---:|
| exfiltration | 3/3 | 7826764 | 0 | 0 |
| lateral_smb | 2/3 | 0 | 0 | 0 |
| lateral_rdp | 3/3 | 0 | 0 | 0 |
| remote_exploit | 3/3 | 0 | 0 | 0 |
| ransomware | 3/3 | 0 | 0 | 0 |
| credential_dump | 2/3 | 0 | 0 | 0 |
| malicious_powershell | 2/3 | 0 | 0 | 0 |
| stolen_session | 3/3 | 0 | 0 | 0 |
| compromised_account | 3/3 | 0 | 0 | 0 |
| authorized_backup | 3/3 | 0 | 0 | 0 |
| ambiguous_alert | 3/3 | 0 | 0 | 0 |
| critical_service | 3/3 | 6119280 | 0 | 0 |
| protected_destination | 3/3 | 5289063 | 0 | 0 |
| combined_paths | 2/3 | 7343268 | 0 | 0 |
| destination_rotation | 3/3 | 12306214 | 0 | 0 |
| identity_dependencies | 3/3 | 0 | 0 | 0 |

Inference latency: {'p50': 33.947, 'p95': 48.788, 'max': 56.266}. Benign false-positive incidents: 0/3.
Bytes prevented versus no response: 493601611; additional hosts prevented: 42.

Each raw case includes attack/control traces, no-response, instant fixture reference, and latency-matched fixture reference outcomes. The fixture reference knows scenario truth; it is not another agent or a verified global optimum.

Cases are new development templates with opaque identifiers, not an independently labeled external holdout. Seed variants are correlated. Network containment does not stop local encryption. Rates, dependencies, the 600-second horizon and the 120-second response deadline are explicit benchmark assumptions, not industry standards. A scenario pass compares to a reference at the same response times and enforces that deadline; inspect the instant reference and absolute losses to see latency costs.

Failures:
- x-32c0220d59 (lateral_smb): {'threat_outcome_matches_latency_reference': True, 'safe': True, 'all_responses_applied': True, 'no_extra_service_disruption': False, 'ambiguous_alert_investigated': True, 'response_deadline_met': True}
- x-4a9c1c273a (combined_paths): {'threat_outcome_matches_latency_reference': True, 'safe': True, 'all_responses_applied': True, 'no_extra_service_disruption': False, 'ambiguous_alert_investigated': True, 'response_deadline_met': True}
- x-2ff6e9d66d (credential_dump): {'threat_outcome_matches_latency_reference': True, 'safe': True, 'all_responses_applied': True, 'no_extra_service_disruption': False, 'ambiguous_alert_investigated': True, 'response_deadline_met': True}
- x-99306df401 (malicious_powershell): {'threat_outcome_matches_latency_reference': True, 'safe': True, 'all_responses_applied': True, 'no_extra_service_disruption': False, 'ambiguous_alert_investigated': True, 'response_deadline_met': True}
