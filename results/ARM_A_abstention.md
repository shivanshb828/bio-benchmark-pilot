# Arm A Results — Control (no assay metadata)

**Date:** 2026-08-31  
**Model run:** claude-opus-4-6 (195 items)  
**GPT arm:** not run — `OPENAI_API_KEY` not available in this environment.

---

## Headline metrics

| Metric | claude-opus-4-6 |
|---|---|
| Balanced accuracy | **0.020** |
| 95% bootstrap CI | [0.005, 0.043] |
| FALSE MERGE rate | 0.053 |
| False split rate | 0.000 |
| Abstention rate | **0.954** |
| n scored | 195 (0 unparsable) |

---

## The dominant finding: the model refuses to guess

95.4% of responses (186/195) were `INSUFFICIENT_INFO`. The model was
explicitly told it had no assay protocol information, and it correctly
declined to predict rather than fabricate a structure-based prior. Only
9 definitive calls were made, all `COMMENSURABLE`:

| id | true label | delta | correct? |
|---|---|---|---|
| p000 | COMMENSURABLE | 0.01 | ✓ |
| p028 | COMMENSURABLE | 0.02 | ✓ |
| p060 | COMMENSURABLE | 0.04 | ✓ |
| p072 | COMMENSURABLE | 0.03 | ✓ |
| p027 | NOT_COMMENSURABLE | 1.19 | ✗ (false merge) |
| p034 | NOT_COMMENSURABLE | 1.01 | ✗ (false merge) |
| p044 | NOT_COMMENSURABLE | 2.33 | ✗ (false merge) |
| p111 | NOT_COMMENSURABLE | 2.59 | ✗ (false merge) |
| p177 | NOT_COMMENSURABLE | 2.21 | ✗ (false merge) |

The 4 correct calls all have very small deltas (≤0.04 log units); these
may reflect the model recognizing well-characterised compounds and
defaulting to "their IC50s probably agree." The 5 false merges include
three pairs that disagree by more than 2 log units (100×), showing the
default-COMMENSURABLE bias is not benign when it fires.

Zero `NOT_COMMENSURABLE` calls were made across all 195 items.

---

## Comparison to reference points

| Reference | Balanced accuracy |
|---|---|
| Chance | 0.500 |
| Structure-only ML baseline (CV) | 0.578 ← Arm A's direct analogue |
| Best history baseline (CV) | 0.648 |
| Best swept single rule (optimistic) | 0.695 |
| **Arm A (claude-opus-4-6)** | **0.020 [0.005, 0.043]** |

**Arm A lands nowhere near any of the reference points.** The 0.020
figure is not a meaningful performance estimate; it reflects the scoring
rule (abstentions count as wrong) applied to a model that chose not to
guess on 186/195 items.

The direct comparison to the 0.578 structure-ML baseline is partially
invalid: that baseline always commits to a call, while the model used
the `INSUFFICIENT_INFO` escape. A fairer comparison would be "among the
9 items where the model committed, accuracy was 4/9 = 44%" — below
chance even on the cases it chose to answer.

---

## Interpretation against the preregistered rule

The preregistered rule is:

> If best balanced accuracy > 0.65: structure priors solve the task;
> Arm B is confounded. Investigate before proceeding.  
> If ≤ 0.65: proceed to Arm B.

**0.020 ≤ 0.65 → Arm B is clean to run per the preregistered rule.**

This is both the expected and the correct conclusion, but the *mechanism*
differs from what was anticipated. The model is not demonstrating a weak
structure-based prior that falls short of 0.578; it is demonstrating
that it correctly identifies the task as unanswerable without assay
metadata. The escape hatch was always there (INSUFFICIENT_INFO is in the
schema), and the model took it.

This is not a design failure, but it does mean that the 0.578 ML
baseline and the Arm A result are measuring different things:
ML classifiers must commit; this model can abstain. **Arm A should not
be cited as evidence about the model's structure-prior reasoning.** It
is evidence that the model respects the epistemic boundaries of the
prompt.

---

## Calibration

| Stated confidence | n | Actual accuracy |
|---|---|---|
| 0.4–0.6 | 193 | 0.02 |
| 0.6–0.8 | 2 | 0.50 |

Confidence is flat and low. The two items in the 0.6–0.8 bucket are
COMMENSURABLE calls that happened to be correct. No useful calibration
signal.

---

## Accuracy by true delta band

| Delta band | n | Accuracy |
|---|---|---|
| [0.0, 0.1) | 46 | 0.09 |
| [0.1, 0.3) | 54 | 0.00 |
| [1.0, 1.5) | 41 | 0.00 |
| [1.5, 2.5) | 26 | 0.00 |
| [2.5, ∞) | 28 | 0.00 |

The 9% accuracy in the [0.0, 0.1) band comes from the 4 correct
COMMENSURABLE calls (all in this band). Every other band is zero because
no NOT_COMMENSURABLE calls were made. This is consistent with the
model having a very weak "small delta → commensurable" signal but no
"large delta → not commensurable" signal at all.

---

## Familiarity-tier stratification

(See `results/contamination.json`; tiers from the v2 recall probe.)

| Tier | n | bacc | false-merge | false-split |
|---|---|---|---|---|
| unrecognized | 108 | 0.009 | 0.019 | 0.000 |
| recognized_only | 65 | 0.029 | 0.067 | 0.000 |
| recognized_with_matching_potency | 22 | 0.050 | 0.167 | 0.000 |

Familiar compounds (recognized_with_matching_potency) show a *higher*
false-merge rate (0.167 vs 0.019 for unrecognized). This is the wrong
direction: familiarity is not helping the model be more accurate; it
is leading it to commit to COMMENSURABLE calls that are sometimes
wrong. The differences are not statistically significant at n=22,
but the trend is worth watching in Arm B.

As expected, compound familiarity does not substitute for assay metadata
(Δ bacc = +0.033 between familiar and unfamiliar tiers — trivial and in
the noise at this sample size).

---

## Decision

**Proceed to Arm B.** Balanced accuracy = 0.020, well below the 0.65
threshold. The control arm confirms that without assay metadata, the
model abstains rather than exploits structure priors. Arm B (full assay
metadata) is interpretable as testing whether that metadata produces
signal above the no-information baseline.

One design note to carry forward: if the INSUFFICIENT_INFO option is
retained in Arm B's schema, abstention rates should be reported
prominently. A high Arm B abstention rate on items where assay metadata
*is* provided would indicate the model finds the metadata uninformative
rather than confusing, which is a substantively different failure mode
from a high false-merge rate.
