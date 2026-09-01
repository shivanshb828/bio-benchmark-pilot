# Findings — Commensurability Benchmark Pilot

**Models:** claude-opus-4-6 (temperature 0), gpt-5.6-sol (temperature 1, API-enforced)  
**Date:** 2026-09-01 · **n:** 195 items, 168 unique assay pairs · **1 item excluded** (p122, leakage gate)

---

## What was measured

The same compound measured against the same target in two independent assays
either yields agreeing IC50s (*commensurable* — safe to pool) or diverging ones
(*not commensurable* — pooling injects noise). Observed divergence is the label;
no expert annotation is required. We value-blind the model and ask it to predict
agreement from experimental context alone.

**Arm A (control\_forced):** SMILES + target ID only, no abstention permitted.
**Arm B (metadata):** same plus full ChEMBL assay descriptions.

All figures below are **cluster-weighted** (each of 168 unique assay pairs
weighted equally). 27/195 items (14%) come from two repeated pairs; as-is
figures inflate false-merge by 3–4 pp. As-is figures are shown parenthetically.

---

## Finding 1 — Assay descriptions add no measurable signal in either model

| Model | Arm A bacc | Arm B bacc | McNemar χ²(1) | p |
|---|---|---|---|---|
| Claude | 0.490 [0.409, 0.554] | 0.557 [0.499, 0.607] | 0.403 | **0.525** |
| GPT | 0.514 [0.442, 0.580] | 0.578 [0.503, 0.637] | 2.867 | **0.090** |

Neither improvement is significant. For GPT, descriptions are net harmful:
+47 items correct, −66 newly wrong (net −19). Neither model clears the
structure-only ML baseline (0.578) or the history baseline (0.648).

The failure is not information poverty. Descriptions differ on a detectable
methodology category (detection technology, cell system, substrate) in 66.7%
of item pairs. Accuracy is flat regardless: **bacc 0.503 (descriptions differ)
vs 0.499 (identical categories), Δ = 0.004.** Qualitative analysis of the 10
worst false merges shows the model reads the methodological differences and then
dismisses them with a generic prior ("standard assays typically agree"). The
signal is present; neither model extracts it.

---

## Finding 2 — Two frontier models exhibit opposite default priors

On identical inputs without metadata:

| Model | False merge | False split | Default |
|---|---|---|---|
| Claude | **0.694** (0.734 as-is) | 0.326 | COMMENSURABLE |
| GPT | 0.267 | **0.705** (0.720 as-is) | NOT\_COMMENSURABLE |

Claude calls 69% of truly-divergent pairs poolable. GPT calls 70% of
truly-poolable pairs unpoolable. The biases are symmetric in magnitude and
opposite in direction.

With metadata (Arm B):

| Model | False merge | False split |
|---|---|---|
| Claude | **0.796** (0.831 as-is) | 0.089 |
| GPT | **0.730** (0.768 as-is) | 0.113 |

Both models compress their minority-class error with descriptions while their
dominant error worsens. **Do not average 0.796 and 0.730.** They measure the
same quantity through opposite mechanisms. A single aggregate would obscure
opposite failure modes with opposite downstream consequences (noise injection
vs sample waste).

This divergence — two models with opposite priors on identical inputs — is
itself an argument for independent measurement rather than using any single
model as a curation oracle.

---

## Limitations

**Temperature asymmetry (unavoidable).** Claude ran at temperature 0.
gpt-5.6-sol rejects temperature=0 with HTTP 400 ("Only the default (1) value
is supported") and ran at temperature 1. GPT metrics carry unquantified
run-to-run variance. Treat GPT confidence intervals as lower bounds on
uncertainty until a repeat run is done.

**n=2 models.** No claim about "frontier models in general" is supported by
two models. The false-merge direction is Claude-specific; the false-split
direction is GPT-specific. Both could reverse on a third model.

**99-compound ceiling.** The divergent class covers only 99 unique compounds.
McNemar detects ~15 pp swings at n ≈ 190; the 6–7 pp Arm A→B shifts are below
detection threshold by design.

**GPT abstention asymmetry.** GPT abstained on 26.7% of Arm B items (52/195)
vs 6.7% for Claude (13/195). Committed-only Arm B metrics exclude abstained
items; this subsample may not be representative.

**IC50 only; [0.3, 1.0] band excluded.** Ki and Kd assays omitted (duplicate-
citation artifact). Both baselines and LLM results will degrade when the
ambiguous band is reinstated in v1.
