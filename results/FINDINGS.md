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

## Finding 2 — Assay descriptions push both models toward merging

The two models start from opposite priors without metadata, then converge on
the same failure mode when descriptions are provided.

**Arm A — opposite starting priors:**

| Model | False merge | False split | Default |
|---|---|---|---|
| Claude | 0.694 (0.734 as-is) | 0.326 | COMMENSURABLE |
| GPT | 0.267 | 0.705 (0.720 as-is) | NOT\_COMMENSURABLE |

**Arm B — both shift toward merging:**

| Model | False merge | False split | Δ false-merge |
|---|---|---|---|
| Claude | **0.795** (0.831 as-is) | 0.089 | **+0.101** |
| GPT | **0.722** (0.768 as-is) | 0.113 | **+0.455** |

Both false-merge rates rose. GPT's shift is +0.455 — its 0.592-point false-split
collapse converted almost entirely into false merges rather than into correct
calls. When given assay descriptions, GPT migrated from splitting poolable pairs to
merging divergent ones. Net accuracy: −19 items. Errors redistributed, not resolved.

**The shared direction is the stronger claim.** Descriptions induce a
COMMENSURABLE bias in both models regardless of their starting prior. The
opposite starting points (Finding 2A) and the convergent failure mode (Finding 2B)
together suggest that assay descriptions provide the model enough information to
commit — but in the wrong direction. "Same target, similar description" is read
as confirmation of poolability even when the actual values diverge.

**Do not average 0.795 and 0.722.** The Δ 0.073 reflects different starting
positions, not different sensitivity. GPT's shift is larger because it had more
room to move from its NOT\_COMMENSURABLE prior.

The starting-point divergence itself remains a finding: two models with opposite
priors on identical inputs is an argument against using any single model as a
curation oracle — whichever direction it defaults, the other direction's errors
are invisible.

---

## Limitations

**Temperature asymmetry (unavoidable).** Claude ran at temperature 0.
gpt-5.6-sol rejects temperature=0 with HTTP 400 ("Only the default (1) value
is supported") and ran at temperature 1. GPT metrics carry unquantified
run-to-run variance. Treat GPT confidence intervals as lower bounds on
uncertainty until a repeat run is done.

**n=2 models.** No claim about "frontier models in general" is supported by
two models. The description-induced shift toward merging is shared by both
models here, but the magnitude differs substantially (Claude +0.101, GPT
+0.455), and whether the direction is universal or a coincidence of these two
models cannot be determined at n=2. A third model could exhibit a different
pattern.

**99-compound ceiling.** The divergent class covers only 99 unique compounds.
McNemar detects ~15 pp swings at n ≈ 190; the 6–7 pp Arm A→B shifts are below
detection threshold by design.

**GPT abstention asymmetry.** GPT abstained on 26.7% of Arm B items (52/195)
vs 6.7% for Claude (13/195). Committed-only Arm B metrics exclude abstained
items; this subsample may not be representative.

**IC50 only; [0.3, 1.0] band excluded.** Ki and Kd assays omitted (duplicate-
citation artifact). Both baselines and LLM results will degrade when the
ambiguous band is reinstated in v1.
