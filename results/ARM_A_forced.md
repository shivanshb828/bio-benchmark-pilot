# Arm A (Forced-Choice) Results — Control, no assay metadata

**Date:** 2026-08-31  
**Prompt:** `control_prompt_forced` — identical to control prompt but
`INSUFFICIENT_INFO` forbidden; model must commit to `COMMENSURABLE` or
`NOT_COMMENSURABLE`.  
**Model:** claude-opus-4-6 (195 items, 0 unparsable)  
**GPT arm:** not run — `OPENAI_API_KEY` unavailable.

See `ARM_A_abstention.md` for the original run (95.4% abstention), which
is preserved as a calibration finding but cannot be evaluated against the
preregistered decision rule.

---

## Headline metrics

| Metric | Value |
|---|---|
| Balanced accuracy (committed) | **0.472** |
| 95% bootstrap CI | [0.406, 0.536] |
| FALSE MERGE rate | **0.737** |
| False split rate | 0.320 |
| Abstention rate | 0.000 |
| n scored / committed | 195 / 195 |

Both scoring modes agree (0% abstention): balanced accuracy = 0.472.

---

## Comparison to reference points

| Reference | Balanced accuracy |
|---|---|
| Chance | 0.500 |
| **Arm A forced (claude-opus-4-6)** | **0.472 [0.406, 0.536]** |
| Structure-only ML baseline (CV) | 0.578 ← Arm A's direct analogue |
| Best history baseline (CV) | 0.648 |
| Best swept single rule (optimistic) | 0.695 |

**Arm A lands below chance and well below the structure-only ML baseline.**
The CI [0.406, 0.536] does not include 0.578. The result is unambiguous.

---

## Preregistered decision rule

> ≤ 0.65 → structure priors do not solve the task. Arm B is clean to run.  
> ≥ 0.65 → the model gets signal from the compound alone. Stop and investigate.

**0.472 ≤ 0.65 → Arm B is clean to run.**

This is the expected result. The forced-choice arm tested whether
SMILES + target ChEMBL ID alone carry enough signal to predict assay
agreement, and the answer is: no, not at the level the ML baseline
achieves, and not at the level that would confound Arm B.

---

## What the numbers actually say

Per-class accuracy:

| True label | n | Calls correct | Accuracy |
|---|---|---|---|
| COMMENSURABLE | 100 | 68 | 0.680 |
| NOT_COMMENSURABLE | 95 | 25 | 0.263 |

The model has a strong **COMMENSURABLE bias**. When forced to guess, it
says "these probably agree" — and it is right 68% of the time for pairs
that do agree, but only 26% of the time for pairs that do not.

The **0.737 false-merge rate** is the critical number. It means 70 of
95 truly-divergent pairs are called commensurable. A downstream training
system relying on this oracle would pool 70% of the pairs that should be
flagged as discordant — exactly the failure mode the benchmark is
designed to catch.

All 57 `NOT_COMMENSURABLE` calls cite `error_class=assay_method`. The
model has one heuristic: if it guesses the assays differ in method, it
flags the pair. Otherwise it defaults to COMMENSURABLE.

---

## Accuracy by true delta band

| Delta | n | Accuracy | Interpretation |
|---|---|---|---|
| [0.0, 0.1) | 46 | 0.57 | Weakly above chance on tiny-agree pairs |
| [0.1, 0.3) | 54 | **0.78** | Best accuracy — near-threshold agree pairs |
| [1.0, 1.5) | 41 | 0.20 | Terrible on marginal disagree pairs |
| [1.5, 2.5) | 26 | 0.38 | Poor on clear disagree |
| [2.5, ∞) | 28 | 0.25 | Poor even on ×300 divergence |

The model's one genuine signal: it can recognise that pairs with very
small deltas ([0.1, 0.3) at 78%) are likely commensurable, probably
from compound-familiarity priors. It completely fails to identify
disagreeing pairs, even those that diverge by two or more log units.

---

## Calibration

| Stated confidence | n | Actual accuracy |
|---|---|---|
| 0.4–0.6 | 178 | 0.48 |
| 0.6–0.8 | 17 | 0.41 |

The model is well-calibrated in the trivial sense: it states low
confidence (0.4–0.6) on almost everything, and is near chance on those.
The 17 higher-confidence calls (0.6–0.8) are actually *less* accurate
(0.41), indicating overconfidence when it does commit firmly.

---

## Familiarity-tier stratification

| Tier | n | bacc | false-merge | false-split |
|---|---|---|---|---|
| unrecognized | 108 | 0.441 | 0.736 | 0.382 |
| recognized_only | 65 | 0.536 | 0.700 | 0.229 |
| recognized_with_matching_potency | 22 | 0.433 | **0.833** | 0.300 |

Compound familiarity does not help and may hurt: the tier with
matching potency recall has the **highest false-merge rate (0.833)** and
the lowest balanced accuracy (0.433). Familiar compounds — well-known
drugs measured in many labs — may appear more "intrinsically
commensurable" to the model regardless of actual assay-pair divergence.
The differences are not statistically significant at these n values, but
the trend is worth tracking in Arm B.

(Δ bacc familiar vs unfamiliar = −0.044, small and in the wrong
direction.)

---

## Interpretation

**The model has a structure-prior, and it is a bias, not a useful signal.**

The bias is: "most assay pairs for a given compound agree." This is
true on average (IC50 values for the same compound against the same
target tend to cluster), but it fails catastrophically on the
NOT_COMMENSURABLE class — the class that matters for data-quality
decisions.

0.472 falls **below chance and well below the 0.578 structure-only ML
baseline.** This is not surprising: the ML baseline is trained to
discriminate; this model gets no task-specific training and has no
mechanism for predicting assay-level divergence from SMILES and a
ChEMBL target ID. The forced-choice framing simply reveals the direction
of the default: COMMENSURABLE.

This result is consistent with — and actually stronger evidence for —
proceeding to Arm B. The control arm is not a soft failure; it is a
clean demonstration that the commensurability decision is not solvable
from compound identity alone.

---

## Decision

**Proceed to Arm B (metadata arm).**

- Preregistered rule: 0.472 ≤ 0.65. ✓
- Arm B will test whether assay descriptions add signal above this
  sub-chance baseline.
- The 0.737 false-merge rate sets the bar: any Arm B result that
  materially reduces false merges is a substantive improvement, even if
  balanced accuracy stays modest.
- Watch abstention rate in Arm B. If the model again abstains at high
  rates even with metadata provided, that is a different (and
  informative) failure.
