# Findings — Commensurability Benchmark Pilot

**Models:** claude-opus-4-6 (temperature 0), gpt-5.6-sol (temperature 1, API-enforced)  
**Date:** 2026-09-01  
**Sample:** 195 items, 168 unique assay pairs. 1 item (p122) excluded from scoring
(indirect leakage gate: assay description contained "200 nM" within 0.051 log
units of p\_b). Scoring denominators are **n=194** throughout.  
All figures cluster-weighted (168 unique pairs weighted equally; two repeated
assay pairs account for 27/195 items and inflate as-is false-merge by 3–4 pp).

---

## Corrections

Two earlier versions of this document presented incorrect headline figures.
Both errors were caught in review and are recorded here.

**Error 1 (abstention scoring).** An initial scoring pass counted abstentions
(INSUFFICIENT\_INFO) as wrong in Arm B but there were no abstentions in
Arm A (where abstention was forbidden). This inflated the apparent Arm A→B
improvement for metrics computed over the full sample.

**Error 2 (schema mismatch).** Arm A used `SCHEMA_FORCED` (INSUFFICIENT\_INFO
forbidden). Arm B used the free-choice `SCHEMA` (INSUFFICIENT\_INFO permitted).
Comparing the two produced a spurious denominator asymmetry: GPT abstained on
52/195 Arm B items; Claude on 13. The published Δfm figures (+0.100 Claude,
+0.455 GPT) were computed over different effective denominators and are not
comparable. The McNemar pairing was also affected.

**Fix.** A new arm, `metadata_forced`, uses `SCHEMA_FORCED` for Arm B. All
findings below use `control_forced` vs `metadata_forced`, matching schemas
exactly. The free-choice metadata arm results are retained in the data as a
secondary finding on abstention behaviour; they are not used to support any
claim in this document.

---

## Finding 1 — Neither model beats simple non-LLM baselines

| Predictor | Balanced accuracy |
|---|---|
| Chance | 0.500 |
| Claude metadata\_forced | 0.561 [0.506, 0.613] |
| GPT metadata\_forced | 0.549 [0.504, 0.598] |
| Structure-only ML (CV) | **0.578** |
| Assay/target history (CV) | **0.648** |

Both models fall below the structure-only ML baseline (0.578) and well below
the history baseline (0.648). The benchmark is not solved with full assay
descriptions. This result is unaffected by the schema correction.

Neither McNemar test on the Arm A→B comparison is significant at p < 0.05
after correction for multiple comparisons across the pilot. Claude's nominal
p=0.031 (see Finding 2) is reported uncorrected; with even a simple two-test
Bonferroni correction the threshold would be 0.025, and this result falls
outside it. GPT's p=0.474 is clearly non-significant regardless of correction.

---

## Finding 2 — The models fail in different kinds, not degrees

**Matched-schema comparison (control\_forced vs metadata\_forced):**

| Model | Arm A bacc | Arm B bacc | Δ bacc | p (uncorr.) |
|---|---|---|---|---|
| Claude | 0.490 | **0.561** | +0.071 | 0.031 |
| GPT | 0.514 | **0.549** | +0.035 | 0.474 |

| Model | Arm A fm | Arm B fm | Δ fm | Arm A fs | Arm B fs |
|---|---|---|---|---|---|
| Claude | 0.694 | 0.715 | **+0.021** | 0.326 | 0.115 |
| GPT | 0.267 | 0.782 | **+0.515** | 0.705 | 0.082 |

The ratio of Δfm is approximately 25×. These are not the same phenomenon at
different magnitudes; they are mechanistically distinct.

**Claude** shows a modest, nominally significant improvement in balanced
accuracy (+0.071, p=0.031 uncorrected) with descriptions. Its false-merge
rate is essentially flat (+0.021). The improvement comes from correctly
identifying commensurable pairs rather than from shifting between error types.

**GPT** shows no significant improvement (p=0.474). Its errors migrate almost
completely: false-merge rises from 0.267 to 0.782; false-split falls from
0.705 to 0.082. Descriptions converted GPT's NOT\_COMMENSURABLE default into
a COMMENSURABLE default without meaningfully increasing accuracy. 40 items
improved, 31 worsened under the schema-corrected pairing.

**Do not average or aggregate these two numbers.** The Δfm values describe
opposite failure modes with opposite downstream consequences: false merges
inject noise into training data; false splits discard usable measurements.
A single aggregate figure would hide this difference.

The "shared direction" claim (both Δfm positive) is technically true but
numerically vacuous at a 25× ratio. It is dropped from this version.

---

## Limitations

**Headline result changed twice under methodological correction.** The initial
Δfm for Claude was +0.100 (abstention artefact), then revised to +0.021 after
fixing the schema mismatch. This sensitivity is itself evidence that protocol
details — specifically which response options are available and how abstentions
are counted — materially affect measured commensurability performance. Future
work should pre-register the exact schema before running.

**Two model families.** Anthropic (Claude) and OpenAI (GPT-5.6-Sol). Two
families cannot distinguish a pattern from a coincidence; either direction
of Δfm could reverse on a third model.

**p=0.031 is nominal and uncorrected.** With two models and two arms,
even a Bonferroni correction raises the threshold to 0.025. Claude's
Arm A→B improvement should be treated as a directional signal, not an
established result.

**n=194 scored items.** Excluding p122 reduces the sample by 0.5%.
McNemar has reliable power only for ~15 pp swings at this n; the Claude
shift (+7.1 pp) is near the detection limit.

**IC50 only; [0.3, 1.0] gap excluded.** Both baselines and LLM results
will degrade when the ambiguous band is reinstated in v1.
