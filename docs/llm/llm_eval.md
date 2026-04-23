# LLM narratives vs the guard (qwen2.5:7b)

30 failures (strongest failure of up to 6 clusters per category), narrative requested from `qwen2.5:7b` at `http://host.docker.internal:11434/v1`.

| | |
|---|---|
| narratives accepted by the guard | **28 / 30** |
| median latency | 13.0 s |
| p90 latency | 16.6 s |

| category | accepted |
|---|---|
| control_instability | 6 / 6 |
| disengagement | 4 / 6 |
| latency_spike | 6 / 6 |
| perception_error | 6 / 6 |
| route_deviation | 6 / 6 |

Guard findings (a narrative can have several; dropped suspects do not reject it):

- number not found in the facts: 2

Rejected narratives fall back to the deterministic template, so every failure still gets a report.

## The two rejections

Both were the guard's mistake, not the model's. The model wrote route completion
0.417 as "41.7%" (failure 6974) and 0.102 as "10.2%" (failure 15070); the guard
did not know a 0-1 fraction may be stated as a percentage and rejected both
narratives as ungrounded. Everything else in them checked out.

After teaching the guard that a fraction may be written as a percentage, both
stored narratives were re-checked and pass. Note this re-check reuses the same
two outputs; a fresh run would sample new narratives.
