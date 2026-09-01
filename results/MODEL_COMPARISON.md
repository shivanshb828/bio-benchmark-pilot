# Multi-Model Comparison

**Status:** Pilot complete. Two model families tested: Anthropic (Claude Opus 4-6,
two temperature conditions) and OpenAI (GPT-5.6-Sol). Table covers 3 runs
spanning Anthropic × 2 + OpenAI × 1.

All figures **cluster-weighted** (168 unique assay pairs weighted equally;
27/195 items from two repeated pairs). 1 item excluded (p122, leakage gate).
Arm B balanced accuracy is committed-only (abstentions excluded from
denominator). McNemar computed on all paired items, abstentions = wrong.

---

## Results table

| Model | Lab | Temp | Arm A bacc | Arm B bacc | Arm A fm | Arm B fm | Δ fm | McNemar p |
|---|---|---|---|---|---|---|---|---|
| Claude Opus 4-6 | Anthropic | 0 | 0.490 [0.422, 0.559] | 0.558 [0.501, 0.613] | 0.694 | **0.795** | +0.100 | 0.525 |
| Claude Opus 4-6 | Anthropic | default | 0.461 [0.392, 0.530] | 0.556 [0.504, 0.611] | 0.708 | **0.789** | +0.081 | 0.137 |
| GPT-5.6-Sol | OpenAI | default | 0.514 [0.449, 0.584] | 0.583 [0.520, 0.655] | 0.267 | **0.722** | **+0.455** | 0.090 |

**fm** = false-merge rate (NOT\_COMMENSURABLE called COMMENSURABLE).  
**McNemar** = χ²(1) test, continuity corrected, H0: descriptions produce no
change. All p > 0.05.

Additional abstention rates:  
Claude (both): Arm A 0%, Arm B 6.7% (13 items)  
GPT-Sol: Arm A 0%, Arm B 26.7% (52 items) — high abstention, committed-only
metrics may not be representative.

---

## Temperature policy and sensitivity

**Policy (from this run onwards):** every model runs at its API default
temperature, since that is what a practitioner would deploy. `temperature=0`
is sent only to models that accept it and only when explicitly requested.

**Claude temperature sensitivity test:**

| | Arm A bacc | Arm B bacc | Arm B fm |
|---|---|---|---|
| temp=0 | 0.490 | 0.558 | 0.795 |
| temp=default | 0.461 | 0.556 | 0.789 |
| **Δ** | −0.029 | −0.002 | −0.006 |

All differences are within bootstrap CI width (~0.14). **Temperature does not
materially affect Claude's results.** The pre-policy temp=0 run is an adequate
representative; there is no confound worth correcting for. The asymmetry with
GPT (which cannot run at temp=0) is real but immaterial.

---

## Question (a) — Does ANY model improve significantly with assay descriptions?

**No.** All three models have McNemar p > 0.05. The largest signal is GPT at
p = 0.090, which is in the wrong direction: descriptions are net harmful for
GPT (−19 items net correct). All models show non-significant A→B shifts.

The structure-only ML baseline (bacc = 0.578, cross-validated) is matched
or cleared by GPT Arm B (0.583) but not by Claude. The best history baseline
(0.648) is not approached by any model. The benchmark has not been solved.

---

## Question (b) — Do models cluster into camps, or is each idiosyncratic?

**Partial clustering, with a shared direction on the key metric.**

**Arm A (no metadata):**
- Claude: COMMENSURABLE default. fm = 0.694–0.708, fs = 0.326–0.370.
- GPT: NOT\_COMMENSURABLE default. fm = 0.267, fs = 0.705.

Two models, opposite defaults, symmetric magnitudes. This is a 2-model
coincidence, not a pattern — three or four models are needed to distinguish
clustering from idiosyncrasy.

**Arm B (with metadata) — the finding:**

All three models increase their false-merge rate when given descriptions:
Claude +0.081–0.100, GPT +0.455. The direction is shared across models
starting from opposite priors. Descriptions push both toward COMMENSURABLE
regardless of where each began. This is the most replicable result in the
table.

The shared direction is the most replicable result in the table. Whether it is universal across model families or specific to these two requires additional providers. `src/run_arm.py` uses a provider registry; adding a new model is two config lines and an API key.
