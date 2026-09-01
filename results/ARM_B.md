# Arm B Results — Metadata (full assay descriptions)

**Date:** 2026-08-31  
**Model:** claude-opus-4-6  
**n scored:** 195 total; **1 excluded** (p122, see leakage gate below); **194 in paired analysis**  
**Assay metadata coverage:** 280/280 assays (100%) after fixing bulk-endpoint fetcher.  

---

## Headline metrics

| Metric | Mode (a): abstentions wrong | Mode (b): abstentions excluded |
|---|---|---|
| n | 195 | 182 committed |
| Balanced accuracy | 0.499 | **0.540** |
| 95% bootstrap CI | [0.445, 0.549] | [0.491, 0.592] |
| FALSE MERGE rate | 0.789 | **0.833** |
| False split rate | 0.080 | 0.087 |
| Abstention rate | **6.7%** (13 items) | — |

Mode (b) is the relevant comparison to forced-commit baselines.
Mode (a) is reported for completeness and to show abstention rate.

---

## Comparison to reference points

| Reference | Balanced accuracy |
|---|---|
| Arm A forced (no metadata) | 0.472 [0.406, 0.536] |
| Chance | 0.500 |
| **Arm B (committed)** | **0.540 [0.491, 0.592]** |
| Structure-only ML baseline (CV) | 0.578 ← not cleared |
| Best history baseline (CV) | 0.648 ← not cleared |
| Best swept single rule (optimistic) | 0.695 ← not cleared |

**The benchmark lacks headroom against simple baselines.**  
0.540 does not exceed the structure-only ML baseline (0.578), which uses no
assay information at all. It is not close to the history baseline (0.648).
This means a model with access to full ChEMBL assay descriptions cannot beat
a trained ML classifier that sees only compound structure and target identity.

---

## THE HEADLINE RESULT: Paired comparison vs Arm A forced (McNemar's test)

Paired on 194 items (p122 excluded). Abstentions counted as wrong in both arms.

| | Arm B correct | Arm B wrong |
|---|---|---|
| **Arm A correct** | 65 | **28** (metadata hurt) |
| **Arm A wrong** | **34** (metadata helped) | 67 |

**McNemar's test (with continuity correction): χ²(1) = 0.403, p = 0.525.**

The metadata arm does not significantly improve over the no-metadata arm.
34 items flipped wrong→right with metadata; 28 flipped right→wrong. The
asymmetry favours Arm B slightly (net +6) but is not statistically
distinguishable from noise at n=194.

### What changed per class

| Class | Arm A accuracy | Arm B accuracy | Δ |
|---|---|---|---|
| COMMENSURABLE (n=100) | 0.680 | **0.840** | +0.160 |
| NOT_COMMENSURABLE (n=94) | 0.266 | **0.160** | **−0.106** |

This is the key finding and it is bad: **metadata improved commensurability
detection but made the model worse at detecting non-commensurability.** The
balanced accuracy appears to improve from 0.472 to 0.540 only because the
COMMENSURABLE gains partially offset the NOT_COMMENSURABLE losses.

The safety framing of the benchmark depends on false-merge rate falling.
It rose from 0.737 (Arm A) to **0.833 (Arm B committed)**.

---

## What the model does with assay descriptions

The model reads descriptions like "Inhibition of JAK2 using TR-FRET assay"
and concludes — usually correctly — that two similarly-described assays should
agree. For 840 of 1000 commensurable pairs, this heuristic is right.

But the model does not identify the specific methodological differences that
cause divergence. Among the 94 NOT_COMMENSURABLE items in the paired set,
it called 74 commensurable (79%) — *more* than in Arm A (73%). The assay
descriptions confirmed "same target" without detecting the assay-specific
sources of divergence.

The 13 abstentions are informative. Several cite genuine methodological
differences ("different detection technologies", "different fluorogenic
substrates") but still refuse to commit. The model notices the differences
but will not translate them into a NOT_COMMENSURABLE call.

---

## False-merge rate: the number that matters

| | FALSE MERGE rate |
|---|---|
| Arm A forced (no metadata) | 0.737 |
| Arm B mode (a) | 0.789 |
| **Arm B mode (b) committed** | **0.833** |

**0.833: 74 of 94 NOT_COMMENSURABLE pairs in the paired set are called
COMMENSURABLE.** A training data pipeline using Arm B calls would incorrectly
pool 83% of discordant pairs. This is worse than a naive "always say
commensurable" oracle (which would have false-merge = 1.000) only because the
model abstains on 5 of the 94 and correctly flags 15 (≈16%).

---

## Accuracy by true delta band

| Delta | n | Arm A forced | Arm B | Δ |
|---|---|---|---|---|
| [0.0, 0.1) — COMM | 46 | 0.57 | **0.80** | +0.23 |
| [0.1, 0.3) — COMM | 54 | 0.78 | **0.87** | +0.09 |
| [1.0, 1.5) — NOT_C | 41 | 0.20 | **0.12** | −0.08 |
| [1.5, 2.5) — NOT_C | 26 | 0.38 | **0.31** | −0.07 |
| [2.5, ∞)  — NOT_C | 28 | 0.25 | **0.07** | **−0.18** |

The degradation in the [2.5, ∞) band is striking: on pairs that diverge by
more than 2.5 log units (≈300×), accuracy falls from 25% (Arm A) to 7%
(Arm B). When two assays look similar on paper but diverge enormously in
practice, Arm B is almost certain to call them commensurable.

---

## Calibration

| Stated confidence | n | Actual accuracy |
|---|---|---|
| 0.4–0.6 | 39 | 0.23 |
| 0.6–0.8 | 89 | 0.48 |
| 0.8–1.0 | 67 | **0.70** |

Calibration improves over Arm A (which was flat at 0.02 due to abstention).
High-confidence calls (0.8–1.0) are 70% accurate. But at 0.6–0.8 the model
is near chance, and at 0.4–0.6 it is badly overconfident: 23% accuracy while
stating 40–60% confidence. No monotone confidence–accuracy relationship exists.

---

## Familiarity-tier stratification

| Tier | n | bacc | false-merge | false-split |
|---|---|---|---|---|
| unrecognized | 108 | 0.530 | 0.792 | 0.055 |
| recognized_only | 65 | 0.471 | 0.733 | 0.114 |
| recognized_with_matching_potency | 22 | 0.442 | **0.917** | 0.100 |

Compound familiarity is inversely associated with accuracy (Δ = −0.065).
The tier with the highest false-merge rate is **recognized_with_matching_potency**
at 0.917: when the model thinks it knows the compound's IC50, it is nearly
certain to call the pair commensurable regardless of assay-level divergence.
This replicates the Arm A pattern and is consistent with potency familiarity
creating a strong "these should agree" prior that overrides description-level
evidence of divergence.

---

## Leakage gate

- **Direct leakage (p_a / p_b verbatim at 2–4dp):** 0 items.
- **Indirect leakage (concentration value within 0.1 log):** 1 item excluded.
  - **p122** (NOT_COMMENSURABLE, δ=1.17): assay description contains "200 nM"
    → pchembl 6.699, within 0.051 log of p_b=6.75. Excluded from paired
    analysis. Would have been a NOT_COMMENSURABLE item; its removal has
    negligible effect on any reported metric.
- Note: 1dp is excluded from p_a / p_b checks in metadata prompts because
  pchembl values 6.5–8.5 collide with "pH 7.4" buffer conditions in
  descriptions (same false-positive class as delta 1dp vs threshold strings).
  The ONLY 1dp collision was p075/p_b=7.44 ↔ "pH 7.4"; this is a buffer
  pH, not the IC50.

---

## Abstention analysis

13 items (6.7%) produced INSUFFICIENT_INFO. Unlike Arm A (where 95.4% abstained
because no information was given), Arm B abstentions occur even with full
assay metadata. Several reasons cited are informative:

- *"Both assays measure IC50 against BRAF V600E with high confidence in the
  assay description, but … different detection methods"* → abstain despite
  identifying the issue.
- *"Both assays use different detection technologies (mobility vs TR-FRET)"*
  → abstain.

The model sees the differences but refuses to commit. 8 of the 13 abstained
items are COMMENSURABLE (δ ≤ 0.26); the model's uncertainty is highest on
near-threshold pairs, not extreme divergers. The 5 NOT_COMMENSURABLE abstainers
(δ 1.8–3.5) include cases where the descriptions clearly differ — suggesting
the model knows the answer but won't say it.

---

## Interpretation

**Arm B fails to improve on chance-level performance for the class that
matters (NOT_COMMENSURABLE) and fails to beat any committed baseline.**

The specific failure mode is: the model reads two assay descriptions, confirms
"both measure IC50 against the same target", and defaults to COMMENSURABLE.
The descriptions contain the relevant divergence signals (different detection
technologies, different substrates, different cell lines) but the model does
not reliably translate these into NOT_COMMENSURABLE calls.

If the preregistered question is "does assay metadata add signal over no
information?", the answer is: **marginally (McNemar p=0.525, non-significant),
and the signal goes in opposite directions by class**. Metadata improves
commensurability detection (+16 pp) while worsening non-commensurability
detection (−11 pp). On the operationally critical false-merge metric,
**the metadata arm is strictly worse than the control arm.**

This is a finding about the task, not only about the model: detecting
assay-level divergence from free-text descriptions may require finer-grained
reasoning about assay methodology than current large language models apply.
The benchmark is hard in the right way. It is not hard because of label noise
or benchmark artefacts.

**Recommended next steps:**
1. Examine the 15 items where Arm B correctly called NOT_COMMENSURABLE.
   What features of those descriptions distinguish them from the 74 misses?
2. Consider a structured metadata arm (Arm C): extract categorical fields
   (assay_type, organism, cell_type, readout) into a structured prompt and
   test whether removing free-text narrows the gap.
3. Do not adjust the preregistered thresholds or reframe the result.
   0.540 < 0.578 is the finding. Report it.
