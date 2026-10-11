# Council baseline results

Mode: **mock**. Completed 57/57.

Mock results are integration checks, not multi-model performance claims.

| Metric | Council | Single-pass |
|---|---:|---:|
| completed | 57 | 57 |
| escalations | 9 | 29 |
| consensus_cases | 48 | 0 |
| containment_fixture_pass | {"passed": 24, "total": 25} | {"passed": 24, "total": 25} |
| fixing_fixture_pass | {"passed": 55, "total": 57} | {"passed": 19, "total": 57} |
| compliance_fixture_pass | {"passed": 23, "total": 25} | {"passed": 23, "total": 25} |
| expected_human_check | {"passed": 4, "total": 4} | {"passed": 4, "total": 4} |
| full_horizon_cases | 48 | 28 |
| mean_rounds | 1.736842105263158 | 1.0 |
| mean_forensic_citation_coverage | 0.9824561403508771 | 0.9824561403508771 |
| full_horizon_outcome_totals | {"bytes_lost": 21383430.0, "additional_hosts_compromised": 0, "identity_abuse_events": 0, "local_files_damaged": 180.0, "false_positive_controls": 0} | {"bytes_lost": 5875560.0, "additional_hosts_compromised": 0, "identity_abuse_events": 0, "local_files_damaged": 1200.0, "false_positive_controls": 0} |

Paired full-horizon cases: 28. Only compare network loss on this shared subset.
Raw full-horizon totals above cover different case sets and must not be interpreted as relative effectiveness.

## Limitations
- Synthetic and correlated fixtures; not production attack detection.
- Mock policies are hand-written and tuned to fixture vocabulary, not LLM intelligence.
- Single-pass baseline does not process updates; this measures protocol differences, not equal-compute superiority.
- Escalated traces are partial and excluded from full-horizon loss totals.
- Severity weights are uncalibrated; no escalation precision/recall claimed without independent labels.
- Forensic citation coverage measures IDs, not factual quality or chain-of-custody assurance.
