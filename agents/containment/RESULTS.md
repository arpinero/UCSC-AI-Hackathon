# Containment research results

Synthetic planning tests; no real attack execution, production certification, or proof of perfect inference. See RESEARCH.md for methods and confounds.

| Run | Passes / completed / planned | Complete | Median seconds | Failures |
|---|---|---|---|---|
| Foundation initial serving integration | 0 / 8 / 8 | True | 15.55 | exfiltration-001, lateral-001, ambiguous-001, injection-001, session-001, no-evidence-001, protected-session-001, peer-injection-001 |
| Foundation template/schema correction | 7 / 8 / 8 | True | 11.17 | injection-001 |
| Foundation constrained-action smoke | 7 / 8 / 8 | True | 23.45 | exfiltration-001 |
| Foundation preliminary MITRE | 9 / 12 / 21 | False | 29.67 | mitre-T1021-001-authorized, mitre-T1210-authorized, mitre-T1486-authorized |
| Foundation evidence-review smoke | 7 / 8 / 8 | True | 31.18 | protected-session-001 |
| Foundation initial challenge | 5 / 6 / 6 | True | 42.25 | challenge-protected-c2 |
| Foundation revised MITRE | 20 / 21 / 21 | True | 37.89 | mitre-T1071-001-authorized |
| Foundation revised smoke | 7 / 8 / 8 | True | 48.53 | session-001 |
| Foundation revised challenge | 5 / 6 / 6 | True | 67.13 | challenge-protected-c2 |
| Qwen incompatible OpenAI adapter | 0 / 3 / 21 | False | 31.8 | mitre-T1041, mitre-T1041-authorized, mitre-T1071-001 |
| Qwen generic-contract native MITRE | 7 / 7 / 21 | False | 46.44 | None |
| Qwen generic-contract challenge | 2 / 3 / 6 | False | 46.55 | challenge-protected-c2 |
| Qwen incident-bound MITRE | 4 / 4 / 21 | False | 53.59 | None |
| Qwen incident-bound challenge | 3 / 4 / 6 | False | 58.7 | challenge-protected-c2 |
| Qwen policy-filtered MITRE | 21 / 21 / 21 | True | 30.04 | None |
| Qwen policy-filtered challenge | 6 / 6 / 6 | True | 46.81 | None |
| Foundation policy-filtered MITRE | 21 / 21 / 21 | True | 31.71 | None |
| Foundation policy-filtered challenge | 6 / 6 / 6 | True | 18.56 | None |
| Foundation policy-filtered smoke | 7 / 8 / 8 | True | 17.59 | injection-001 |
| Qwen policy-filtered smoke | 8 / 8 / 8 | True | 20.28 | None |

Every rejection/unavailable response counts as a failed task. Partial runs are not full benchmark scores. Raw files retain all attempts and errors.

Foundation uses Q8 weights and llama.cpp; Qwen uses Q4_K_M and Ollama with a larger output budget and explicit incident-bound schema text. These compare configured systems under a shared validator, with runtime/prompt/quantization confounds. No statistical superiority claim is warranted.
