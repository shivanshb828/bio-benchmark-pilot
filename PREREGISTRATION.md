# Preregistration

Fixed before any model was called. Committed ahead of results so the decision
rules cannot be adjusted to fit whatever comes back.

## Question

Given two independently reported IC50 measurements of the same compound
against the same target, plus their experimental context, can a frontier model
predict whether those measurements are commensurable, **without seeing the
values**?

Blinding the model to the values converts a subjective judgment ("should these
be pooled?") into an objectively scorable prediction ("will these agree?").
Ground truth is free: the divergence between the reported values is the label.

## Labels

- `COMMENSURABLE`      : 0 < |Δ pChEMBL| < 0.3 log units
- `NOT_COMMENSURABLE`  : |Δ pChEMBL| > 1.0 log units
- The [0.3, 1.0] band is excluded from v0 and reinstated in v1.

Δ = 0.0 exactly is excluded. In this export 75.7% of Ki pairs and 19.2% of
IC50 pairs have Δ = 0.0, which is the repeated-citation artifact Kramer et al.
identified: one measurement recorded twice, not two measurements agreeing.
v0 is IC50 only for the same reason.

## Arms

- **A (control, run first)** — compound SMILES and target ID only. No assay
  metadata whatsoever.
- **B (metadata)** — adds full ChEMBL assay descriptions and conditions.
- **C (contamination)** — asks the model to recall the reported value directly.

## Decision rules

| Arm A balanced accuracy | Reading | Action |
|---|---|---|
| > 0.65 | Task is solvable from structure and potency priors alone | Arm B is confounded. Do not proceed without redesign. |
| ≤ 0.65 | Priors do not solve it | Arm B is clean. Proceed. |

| Arm B balanced accuracy | Action |
|---|---|
| ≤ 0.60 with asymmetric false-merge | Strong benchmark. Build it. |
| 0.60 – 0.85 | Check whether failures concentrate by `error_class`. Narrower benchmark. |
| > 0.85 | Capability is largely present. Pivot to the independent-scorer framing. |

Arm C: if the model recalls specific values above chance, the sample is
contaminated and must move to post-cutoff ChEMBL releases.

## Primary metric

Balanced accuracy vs a 0.5 baseline, with bootstrap 95% CI.

## Metric that decides the design

**False merge rate**: proportion of truly-divergent pairs called
`COMMENSURABLE`. False merges poison training data. False splits only cost
sample size. Symmetric error is noise; asymmetric error toward merging is a
safety-relevant capability gap.

## Known limitations

- 99 unique compounds in the divergent pool caps this export at ~95 items per
  class. Scaling past this requires a direct ChEMBL pull.
- pChEMBL collapses assay conditions the model may need; Arm B partly recovers
  this from free-text descriptions.
- Single activity type (IC50). Cross-domain generalization is untested until a
  second loader (BRENDA kcat/Km) is added.
