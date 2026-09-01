# Findings — Commensurability Benchmark Pilot

**Models:** claude-opus-4-6, gpt-5.6-sol (reasoning mode, temperature fixed at 1)  
**Date:** 2026-09-01 · **n:** 195 items, 168 unique assay pairs

---

## What was measured

A compound measured against the same target in two independent assays will
either yield agreeing IC50s (the assays are *commensurable* — safe to pool) or
diverging ones (not commensurable — merging them injects noise). The observed
divergence is the label; no expert annotation is needed. We show the model the
experimental context — either compound + target only (Arm A), or with full
ChEMBL assay descriptions (Arm B) — and ask it to predict agreement.

---

## Cluster correction

27 items come from just two assay pairs repeated across compounds: HIV-1
integrase CHEMBL1033786/CHEMBL1211287 (10 items) and JAK3
CHEMBL3374009/CHEMBL3705847 (9 items). The as-is metrics count these pairs'
characteristics 9–10 times each. All results below use **cluster-weighted**
figures (variant c: each unique assay pair contributes equal weight regardless
of how many compounds it spans). The as-is figures are shown for reference.

| | As-is | Cluster-weighted |
|---|---|---|
| Claude Arm B false-merge | 0.831 | **0.796** |
| GPT Arm B false-merge | 0.768 | **0.730** |

Cluster correction reduces apparent false-merge by 3–4 pp. It does not change
the conclusions, but 0.796 and 0.730 are the defensible headline numbers.

---

## Arm A → B: did assay metadata help?

**Claude (committed only):**

| | Arm A (control\_forced) | Arm B (metadata) |
|---|---|---|
| Balanced accuracy | 0.490 [0.409, 0.554] | **0.557 [0.499, 0.607]** |
| FALSE MERGE rate | 0.694 | 0.796 |
| False split rate | 0.326 | 0.089 |

McNemar (194 paired items, continuity corrected): +34 wrong→right,
−28 right→wrong. **χ²(1) = 0.403, p = 0.525.** Not significant.

**GPT (committed only):**

| | Arm A (control\_forced) | Arm B (metadata) |
|---|---|---|
| Balanced accuracy | 0.514 [0.442, 0.580] | **0.578 [0.503, 0.637]** |
| FALSE MERGE rate | 0.267 | 0.730 |
| False split rate | 0.705 | 0.113 |

McNemar: +47 wrong→right, −66 right→wrong. **χ²(1) = 2.867, p = 0.090.**
Not significant. Note direction: GPT is net −19 items with metadata; it does
marginally *worse* with descriptions than without.

**Neither model shows a statistically significant improvement from Arm A to
Arm B.** The cluster-weighted Arm B bacc equals the structure-only ML baseline
(0.578) for GPT, and falls 2 pp below it for Claude. Neither model exceeds the
best history-based ML baseline (0.648).

---

## The models diverge sharply on default bias

The two models solved the task differently and got nearly the same wrong answer:

| | Control (no metadata) | | Metadata | |
|---|---|---|---|---|
| Model | FALSE MERGE | False split | FALSE MERGE | False split |
| **Claude** | **0.694** | 0.326 | 0.796 | 0.089 |
| **GPT** | 0.267 | **0.705** | 0.730 | 0.113 |

Claude defaults to COMMENSURABLE: it pools 69% of truly-divergent pairs without
metadata, rising to 80% when descriptions confirm "same target." GPT defaults to
NOT_COMMENSURABLE: it splits 70% of truly-poolable pairs without metadata. Both
biases diminish as metadata is added, converging toward a shared failure on the
harder class.

This divergence is real and should not be averaged. A single aggregate metric
would obscure opposite failure modes that have opposite downstream consequences:
Claude's false merges inject noise into training data; GPT's false splits discard
usable measurements.

---

## The model ignores available signal

When both assay descriptions differ on a detectable methodology category
(detection technology, cell system, substrate, concentration) — 66.7% of item
pairs — Arm B accuracy is flat: **bacc 0.503 (descriptions differ) vs 0.499
(identical categories), Δ = +0.004.** The model reads both descriptions and
converges on the same answer regardless of methodological divergence. Of the 10
worst false merges, 9 were cases where the model explicitly noted the
methodological difference and then dismissed it with a generic prior ("standard
assays typically agree"). One case (p076: identical descriptions, Δ = 3.7 log
units) is a genuine information gap; the rest are reasoning failures.

---

## Limitations

- **99-compound ceiling.** The divergent class draws from only 99 unique
  compounds. Cross-validation SDs of 0.07–0.11 make results within ~8 pp of
  baseline statistically indistinguishable. The McNemar test has power to detect
  ~15 pp swings at n ≈ 190; smaller genuine improvements will not register.

- **Cluster concentration.** 27/195 items (14%) come from two assay pairs. The
  cluster correction partially addresses this, but those pairs may be
  unrepresentative of the general commensurability problem (HIV integrase and
  JAK3 are both known difficult-to-reproduce systems).

- **IC50 only.** Ki pairs contain a 75% exact-zero-delta artifact (repeated
  citations) and were excluded. Results may not generalise to binding assays.

- **Excluded band [0.3, 1.0].** Items in the ambiguous middle zone are not
  scored. Both the ML baselines and LLM results would likely degrade when this
  band is reinstated in v1.

- **GPT reasoning model.** gpt-5.6-sol does not support temperature=0. Its
  responses use the model default (temperature=1), introducing run-to-run
  variance not present in the Claude results. A repeat run would be needed to
  bound this variance before reporting GPT numbers as fixed.

- **1 item excluded** (p122) by the indirect leakage gate: assay description
  contained "200 nM" within 0.051 log units of p_b = 6.75. All metrics above
  exclude this item.
