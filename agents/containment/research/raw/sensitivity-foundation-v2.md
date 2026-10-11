# Frozen-decision sensitivity experiment

**Counterfactual replay only: no new model inference.**

Source: 30/48 model cases completed.

| Perturbation | Passes / replayed | Bytes lost | New hosts | Policy rejections |
|---|---:|---:|---:|---:|
| observed timing | 24/30 | 18779522 | 0 | 0 |
| instant replay | 24/30 | 0 | 0 | 0 |
| 30 second response | 24/30 | 17621010 | 0 | 0 |
| 120 second response | 24/30 | 70484040 | 0 | 0 |
| 240 second response | 0/30 | 140968080 | 28 | 1 |
| 1 minute TTL | 0/30 | 278403180 | 28 | 0 |
| 3 minute TTL | 0/30 | 207919140 | 28 | 0 |

Frozen decisions are not replanned for changed conditions.
Variants are correlated counterfactuals, not additional model tests.
Late responses retain their original telemetry version and may be rejected.
Scoring references retain their normal TTL; short TTL measures expiry harm.
