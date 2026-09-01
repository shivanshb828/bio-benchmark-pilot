# Commensurability

**Can a frontier model tell whether two independently reported bioactivity measurements can legitimately be pooled into one training set?**

Status: **Pilot complete.** Two model families evaluated (Anthropic, OpenAI); within-model
replication run. See [FINDINGS.md](results/FINDINGS.md) for the summary.

---

## Why this matters

Drug discovery models are trained on bioactivity measurements pooled from public
databases. The pooling step assumes the measurements are comparable. Often they
are not, and the resulting noise is large enough to swamp the effects those
models are trying to learn.

The size of the problem is documented:

| Finding | Source |
|---|---|
| Under minimal curation, ~65% of same-target IC50 pairs differ by >0.3 log units and 27% by >1.0 | Landrum & Riniker, *JCIM* 2024 |
| ~19% of PDBBind protein-protein records carried Kd values unsupported by their primary publication; correcting them moved a random-forest model's Pearson r on log₁₀(Kd) by ~8 points | Ye et al., *Database* 2025 |
| Reproducibility ceiling on ChEMBL Ki data is ~0.44 pKi mean error, comparable in size to many claimed model improvements | Kramer et al. |

Two things have changed recently that make this worth measuring rather than
merely noting.

First, the field's standard mitigation is a blunt rule: don't pool across
assays. That is safe and expensive. It discards usable data, and sample size is
the binding constraint on most bioactivity models. The valuable capability is
not avoiding bad merges, which a simple filter already does. It is *selective*
pooling: recovering the merges that are legitimate.

Second, autonomous extraction systems now generate biological training records
at a scale no one can hand-verify, and evaluate themselves with LLM judges. A
problem previously handled by human judgment is now handled by automated
judgment with no independent scorer. This repository is a step toward one.

## The design

Grading a curation agent normally requires expert adjudication, which is slow
and expensive. We avoid that entirely.

We find cases where the same compound was measured against the same target in
**two separate assays**. Both values are known. If they agree, the assays were
comparable; if they diverge, they were not. We then hide the values, show the
model only the experimental context, and ask it to predict agreement.

**Ground truth is free**, because the observed divergence is the label. No
expert panel, no annotation budget.

### Labels

- `COMMENSURABLE` — 0 < |Δ pChEMBL| < 0.3 log units
- `NOT_COMMENSURABLE` — |Δ pChEMBL| > 1.0 log units
- The [0.3, 1.0] band is excluded in v0 and reinstated in v1.

Exact-zero deltas are excluded. In this export 75.7% of Ki pairs and 19.2% of
IC50 pairs have Δ = 0.0, which is the repeated-citation artifact Kramer
identified: one measurement recorded twice, not two measurements agreeing.
Including them would make the agreeing class mostly duplicate rows. v0 is IC50
only for the same reason.

### Arms

| Arm | What the model sees | Purpose |
|---|---|---|
| A (control) | compound SMILES, target ID | Null model. If structure priors predict the label, Arm B is confounded. |
| A-forced | same, no abstention permitted | Comparable to ML baselines, which must commit. |
| B (metadata) | + full ChEMBL assay descriptions and conditions | The actual question. |
| Recall v2 | SMILES, then SMILES + target | Contamination probe. |

## Dataset

Derived from the ChEMBL32 max-curation export in
[rinikerlab/overlapping_assays](https://github.com/rinikerlab/overlapping_assays)
(MIT). See `ATTRIBUTION.md`.

```
pool             5,300 nonzero IC50 pairs, 38 targets, 380 compounds
labelled         2,243 agreeing / 727 divergent
eval sample      195 items (100 agree / 95 disagree), 37 targets
median delta     0.100 (agree) / 1.630 (disagree)
```

The divergent class draws on only 99 unique compounds, which caps this export
at roughly 200 balanced items. Scaling past that requires a direct ChEMBL pull.

**Pipeline validation.** Our pairing code reproduces the source paper's
published max-curation IC50 statistics: 46.6% of pairs differ by >0.3 log units
against their ~48%, and 11.1% by >1.0 against their ~13%. If a change to
`build_sample.py` moves these, the change is wrong.

## Results so far

### Model comparison (cluster-weighted, 168 unique assay pairs)

| Model | Lab | Arm A bacc | Arm B bacc | Arm A fm | Arm B fm | Δ fm | McNemar p |
|---|---|---|---|---|---|---|---|
| Claude Opus 4-6 (temp=0) | Anthropic | 0.490 | 0.558 | 0.694 | **0.795** | +0.100 | 0.525 |
| Claude Opus 4-6 (default) | Anthropic | 0.461 | 0.556 | 0.708 | **0.789** | +0.081 | 0.137 |
| GPT-5.6-Sol | OpenAI | 0.514 | 0.583 | 0.267 | **0.722** | **+0.455** | 0.090 |

**fm** = false-merge rate. All McNemar p > 0.05. Both models increase false-merge with descriptions despite opposite starting priors. Full analysis: [FINDINGS.md](results/FINDINGS.md) · [MODEL_COMPARISON.md](results/MODEL_COMPARISON.md) · [GPT_FLIPS.md](results/GPT_FLIPS.md) · [GPT_FLIPS_SIMILARITY.md](results/GPT_FLIPS_SIMILARITY.md).

---

### Baselines: how much headroom is there?

If a simple rule matches LLM performance, the benchmark measures nothing.
Cross-validated with GroupKFold by target, so no target appears in both train
and test.

| Predictor | balanced accuracy |
|---|---|
| Chance | 0.500 |
| Structure only, RDKit descriptors | 0.578 ± 0.047 |
| Assay/target history | 0.648 ± 0.070 |
| Best single rule, threshold swept on eval set (optimistic) | 0.695 |

Best honest baseline is ~0.65. That is moderate headroom: enough room for a
model to demonstrate something, not enough to be comfortable. An LLM needs to
clearly exceed 0.65 for the benchmark to be defensible.

One finding worth its own line: assay-pair history is the strongest signal, but
it is available for only **47.7%** of pairs, and when available the median
number of other shared compounds is **one**. The practical alternative to asking
a model, look at the overlap you already have, works on half the data and rests
on a single observation when it works at all. That gap is the strongest argument
for the benchmark that has come out of this work.

### Contamination

If the model memorized these values during training, the benchmark measures
recall rather than reasoning.

The v1 probe keyed on assay ChEMBL ID and returned 0/30. That result is
preserved but uninformative: no model memorizes assay-ID-indexed lookups, so
zero was the expected outcome either way.

The v2 probe keys on compound and target identity, which is how this information
would appear in training text. The model claimed to know a potency for 53 of 195
items and hit within 0.5 log on 22 of those, a 41.5% hit rate. Because IC50
values cluster tightly, that must be compared against a null:

| Null model | hit rate |
|---|---|
| Constant guess at pool median (pChEMBL 6.80) | 23.1% |
| Constant guess at 100 nM | 30.8% |
| Random draw from pool marginal | 29.4% [23.6%, 35.4%] |
| Restricted to the 53 claimed items | 29.9% [18.9%, **41.5%**] |
| **Observed** | **41.5%** |

The observed rate sits exactly at the upper bound of the null interval, so there
is **no statistically significant evidence of contamination**. This is the
weakest possible pass and is reported as such.

The structural argument is stronger than the statistic. Our label is assay
divergence, not potency. Recovering it from memory requires recalling both
values from both assays independently. Knowing that a compound is roughly 20 nM
against its target does not tell you whether two specific assays measuring it
agree with each other.

### Arm A: do structure priors alone predict the label?

Run with abstention permitted, the model declined on 186/195 items, correctly
recognizing that it had been given no assay information. That is a calibration
finding, not a measurement of the intended quantity, and it is preserved in
`ARM_A_abstention.md`. On the 9 items where it did commit it scored 4/9, with
all 5 errors being false merges, three of them on pairs diverging by more than
2 log units.

Rerun forced-choice, comparable to the ML baselines:

| | balanced accuracy |
|---|---|
| **Arm A forced (claude)** | **0.472 [0.406, 0.536]** |
| Chance | 0.500 |
| Structure-only ML baseline | 0.578 |

The interval straddles chance and excludes the ML baseline. Structure and target
identity alone carry no usable signal, which means **Arm B is unconfounded**:
whatever it produces cannot be attributed to medicinal chemistry intuition.

The operative number is the **false-merge rate of 0.737**. Without assay
information the model calls roughly three quarters of truly divergent pairs
poolable. The asymmetry is stark: 68% correct on agreeing pairs, 26% on
diverging ones. This is a default toward merging in the absence of signal, not
anti-correlation with truth.

### Arm B — Metadata (full assay descriptions)

**Model:** claude-opus-4-6 · **n:** 195 scored, 1 excluded (leakage gate),
194 in paired analysis · **Coverage:** 280/280 assay descriptions (100%)

| Metric | Mode (a): abstentions wrong | Mode (b): abstentions excluded |
|---|---|---|
| Balanced accuracy | 0.499 [0.445, 0.549] | **0.540 [0.491, 0.592]** |
| FALSE MERGE rate | 0.789 | **0.833** |
| False split rate | 0.080 | 0.087 |
| Abstention rate | **6.7%** (13 items) | — |

Reference points:

| Predictor | balanced accuracy |
|---|---|
| Arm A forced (no metadata, claude) | 0.472 [0.406, 0.536] |
| Chance | 0.500 |
| **Arm B (claude, committed)** | **0.540 [0.491, 0.592]** |
| Structure-only ML baseline | 0.578 — **not cleared** |
| Best history baseline | 0.648 — **not cleared** |

**McNemar's test (194 paired items, continuity corrected):
χ²(1) = 0.403, p = 0.525 — not significant.**
34 items flipped wrong→right with metadata; 28 flipped right→wrong.

**Accuracy by delta band:**

| Delta | n | Arm A forced | Arm B | Δ |
|---|---|---|---|---|
| [0.0, 0.1) — COMM | 46 | 0.57 | **0.80** | +0.23 |
| [0.1, 0.3) — COMM | 54 | 0.78 | **0.87** | +0.09 |
| [1.0, 1.5) — NOT_C | 41 | 0.20 | **0.12** | −0.08 |
| [1.5, 2.5) — NOT_C | 26 | 0.38 | **0.31** | −0.07 |
| [2.5, ∞) — NOT_C | 28 | 0.25 | **0.07** | **−0.18** |

**The critical findings, stated plainly:**

1. **The benchmark lacks headroom against simple baselines.** Arm B (0.540)
   does not clear the structure-only ML baseline (0.578), which uses no assay
   information. A second-generation pipeline with better descriptions or
   structured metadata fields may change this; this generation does not.

2. **The false-merge rate increased with metadata (0.737 → 0.833).** The
   operationally important metric went the wrong direction. Assay descriptions
   made the model *more* confident that divergent pairs are commensurable,
   not less. This is a safety-relevant finding: a curation pipeline relying on
   Arm B calls would pool 83% of discordant pairs.

3. **Metadata helped for COMMENSURABLE (+16 pp) and hurt for NOT_COMMENSURABLE
   (−11 pp).** The model reads similar-sounding descriptions and infers
   commensurability regardless of the specific methodology differences that
   cause divergence.

**Description quality caveat.** An alternative explanation is that ChEMBL
descriptions are too terse (median 14 words) to carry the signal, and the model's
failure is information-limited rather than reasoning-limited. Analysis in
`src/describe_metadata.py` argues against this: accuracy is flat (Δ bacc = 0.004)
regardless of whether the two assay descriptions differ on detectable methodology
categories (detection technology, cell system, substrate, concentration). The
signal is present but ignored. Qualitative evidence in `results/FAILURE_CASES.md`
shows the same: in 9 of the 10 worst false merges, the model explicitly notices
the methodological difference and then invokes a generic prior to dismiss it.
Only 1 of 10 cases (p076, HIV integrase with identical descriptions) is a genuine
information gap.

**Multi-model replication.** GPT-5.6-Sol (OpenAI) was subsequently evaluated on
both arms. The description-induced false-merge increase is shared by both models,
despite opposite Arm A priors. See [FINDINGS.md](results/FINDINGS.md) and
[MODEL_COMPARISON.md](results/MODEL_COMPARISON.md) for the full comparison.
GPT flip analysis with mechanism breakdown: [GPT_FLIPS.md](results/GPT_FLIPS.md).
Description similarity analysis: [GPT_FLIPS_SIMILARITY.md](results/GPT_FLIPS_SIMILARITY.md).

## Layout

```
src/build_sample.py     build the balanced pair set
src/fetch_metadata.py   pull assay descriptions from the ChEMBL API
src/prompts.py          prompt construction + leakage guards
src/run_arm.py          run one arm against one model, cached and resumable
src/score.py            metrics, calibration, preregistered decision rules
src/baselines.py        non-LLM baselines and headroom analysis
src/null_models.py      chance-rate calibration for the contamination probe
PREREGISTRATION.md      hypotheses and decision rules, fixed before any run
ATTRIBUTION.md          data provenance and pipeline validation
```

## Running it

```bash
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...

python -m src.build_sample
python -m src.baselines

python -m src.run_arm --arm recall_v2      --model claude
python -m src.run_arm --arm control_forced --model claude
python -m src.score   --arm control_forced

python -m src.fetch_metadata
pytest tests/test_no_leakage.py            # gate: descriptions may embed values
python -m src.run_arm --arm metadata --model claude
python -m src.score   --arm metadata
```

Order matters. Each step gates the next, and the gates are in
`PREREGISTRATION.md` so they cannot be adjusted after seeing results.

Stdlib plus numpy, scikit-learn, and RDKit. No SDKs, nothing to break.

## Known limitations

The divergent pool contains 99 unique compounds, capping this export near 200
balanced items. Cross-validation standard deviations of 0.07 to 0.11 follow from
that, so any LLM result within ~8 points of baseline will not be separable at
this n.

Excluding the [0.3, 1.0] band inflates every number here, baselines included.
Both get harder when it is reinstated, though the gap between them may survive.

Single activity type. Cross-domain generalization is untested until a second
loader is added; BRENDA enzyme kinetics is the intended contrast, since the
method should transfer to any domain where the same quantity is measured
repeatedly under varying protocols.

**Two model families.** The pilot covers Anthropic (Claude Opus 4-6) and OpenAI
(GPT-5.6-Sol) with one within-model replication (Claude at two temperature
settings). Two families cannot distinguish a pattern from a coincidence; a third
family is the natural next step. `src/run_arm.py` uses a provider registry;
adding a new model is two config lines and an API key.

The method does not extend to categorical labels such as gene function or
variant pathogenicity. Those have no delta, so ground truth stops being free,
which is the entire reason this approach is cheap.
