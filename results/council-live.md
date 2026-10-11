# Council baseline results

Mode: **live**. Completed 12/12.

Mock results are integration checks, not multi-model performance claims.

| Metric | Council | Single-pass |
|---|---:|---:|
| completed | 12 | 12 |
| escalations | 4 | 12 |
| consensus_cases | 8 | 0 |
| containment_fixture_pass | {"passed": 12, "total": 12} | {"passed": 7, "total": 12} |
| fixing_fixture_pass | {"passed": 12, "total": 12} | {"passed": 0, "total": 12} |
| compliance_fixture_pass | {"passed": 12, "total": 12} | {"passed": 0, "total": 12} |
| expected_human_check | {"passed": 0, "total": 0} | {"passed": 0, "total": 0} |
| full_horizon_cases | 8 | 0 |
| mean_rounds | 1.4166666666666667 | 1.0 |
| mean_forensic_citation_coverage | 0.7777777777777778 | 0.0 |
| full_horizon_outcome_totals | {"bytes_lost": 2757532.468000045, "additional_hosts_compromised": 0, "identity_abuse_events": 0, "local_files_damaged": 0.0, "false_positive_controls": 0} | {"bytes_lost": 0, "additional_hosts_compromised": 0, "identity_abuse_events": 0, "local_files_damaged": 0, "false_positive_controls": 0} |

Paired full-horizon cases: 0. Only compare network loss on this shared subset.
Raw full-horizon totals above cover different case sets and must not be interpreted as relative effectiveness.

## Limitations
- Synthetic and correlated fixtures; not production attack detection.
- Mock policies are hand-written and tuned to fixture vocabulary, not LLM intelligence.
- Single-pass baseline does not process updates; this measures protocol differences, not equal-compute superiority.
- Escalated traces are partial and excluded from full-horizon loss totals.
- Severity weights are uncalibrated; no escalation precision/recall claimed without independent labels.
- Forensic citation coverage measures IDs, not factual quality or chain-of-custody assurance.
