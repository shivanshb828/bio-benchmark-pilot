# Findings — Commensurability Benchmark Pilot

**Models:** claude-opus-4-6 (temperature 0), gpt-5.6-sol (temperature 1, API-enforced)  
**Date:** 2026-09-01  
**Sample:** 195 items, 168 unique assay pairs. 1 item (p122) excluded from scoring
by the indirect leakage gate (assay description contained "200 nM" within 0.051
log units of p\_b). All scoring denominators are **n=194**; p122 is excluded
from both McNemar pairings and cluster-weighted metrics throughout.

---

## What was measured

The same compound in two independent assays either yields agreeing IC50s
(*commensurable*) or diverging ones (*not commensurable*). Observed divergence
is the label; no annotation required. We value-blind the model and ask it to
predict agreement from experimental context.

**Arm A (control\_forced):** SMILES + target ID only. INSUFFICIENT\_INFO
forbidden; model must commit.  
**Arm B (metadata\_forced):** same plus full ChEMBL assay descriptions.
INSUFFICIENT\_INFO also forbidden, matching Arm A exactly.

All figures are **cluster-weighted** (168 unique assay pairs; 27/195 items
from two repeated pairs inflate as-is false-merge by 3–4 pp).

**Schema correction.** An earlier run used `metadata` (free-choice schema,
INSUFFICIENT\_INFO permitted) against `control_forced` (forced schema). That
comparison was invalid: GPT abstained on 52/195 Arm B items; Claude on 13.
The corrected comparison uses `metadata_forced` for Arm B throughout.
Earlier free-choice metadata figures are kept as a secondary finding on
abstention behaviour.

---

## Finding 1 — Claude improves with descriptions; GPT does not

**Primary (matched schemas, cluster-weighted):**

| Model | Arm A bacc | Arm B bacc | Δ | McNemar χ²(1) | p |
|---|---|---|---|---|---|
| Claude | 0.490 [0.422, 0.559] | **0.585** [0.523, 0.644] | +0.095 | 4.661 | **0.031** |
| GPT | 0.514 [0.449, 0.584] | 0.568 [0.516, 0.623] | +0.054 | 0.512 | 0.474 |

Claude shows a statistically significant improvement (p=0.031): 40 items
flipped wrong→right, 22 right→wrong. GPT does not (p=0.474): 67 flipped
right, 58 wrong, net +9.

Claude's Arm B (0.585) clears the structure-only ML baseline (0.578) and
approaches the lower bound of the best history baseline CI (0.648 ± 0.070).
GPT's Arm B (0.568) stays below the structure-only baseline.

The improvement is real in the sense that it is not purely a false-merge
increase: Claude's false-merge changes by only +0.021 (see Finding 2).

---

## Finding 2 — Models shift toward merging, but magnitudes differ by 25×

| Model | Arm A fm | Arm B fm | Δfm | Arm A fs | Arm B fs |
|---|---|---|---|---|---|
| Claude | 0.694 | **0.715** | +0.021 | 0.326 | 0.115 |
| GPT | 0.267 | **0.782** | **+0.514** | 0.705 | 0.082 |

Both false-merge rates rose. Claude's increase is negligible (+0.021); GPT's is
+0.514 — nearly complete error migration. GPT converted its NOT\_COMMENSURABLE
default into a COMMENSURABLE default when given descriptions. False-split fell
from 0.705 to 0.082; false-merge rose from 0.267 to 0.782. The distribution
of errors nearly flipped; accuracy barely changed.

**Do not average 0.715 and 0.782.** They describe different mechanisms:
Claude's errors remain distributed across classes; GPT's errors migrated
almost entirely to false merges. A single number would hide this difference.

The shared direction (both Δfm positive) is present but misleading as a
summary: +0.021 and +0.514 are not the same phenomenon. Claude used the
descriptions productively; GPT redistributed its errors.

---

## Temperature is not a confound

gpt-5.6-sol rejects temperature=0 (HTTP 400). Claude ran at temp=0 and also
at API default, to verify the asymmetry is immaterial:

| | Arm B bacc | Arm B fm |
|---|---|---|
| Claude temp=0 | 0.585 | 0.715 |
| Claude temp=default | 0.556 | 0.789 |
| Δ | −0.029 | +0.074 |

The differences are inside the bootstrap CI width (~0.14). Temperature is not
a material confound; the Claude–GPT comparison needs no asterisk.

---

## Abstention as secondary finding

Under the free-choice schema (`metadata`, INSUFFICIENT\_INFO permitted),
GPT abstained on 52/195 items (26.7%); Claude on 13 (6.7%). The items GPT
abstained on were predominantly NOT\_COMMENSURABLE items it would have
merged when forced to commit — exactly what metadata\_forced reveals.
GPT's abstention is a meaningful signal: given the option, it declines on
the items it would otherwise get wrong.

---

## Limitations

**Two model families.** Anthropic (Claude) and OpenAI (GPT-5.6-Sol). Two
families cannot distinguish a pattern from a coincidence. The directions may
differ or reverse on a third model. `src/run_arm.py` uses a provider registry;
extending to Gemini or Grok is two config lines and an API key.

**n=194 scored items.** Excluding p122 reduces the sample by 0.5%. The impact
on all reported metrics is negligible; it is noted for reproducibility.

**GPT abstention asymmetry.** In the free-choice arm GPT abstained 4× more
than Claude. Forced-choice metrics (used in Findings 1 and 2) are the primary
comparison; free-choice abstention rates are reported separately.

**IC50 only; [0.3, 1.0] gap excluded.** Both baselines and LLM results will
degrade when the ambiguous band is reinstated in v1.

**Small n.** 99 unique divergent compounds caps total items near 200.
McNemar requires ~15 pp swings for reliable detection at this n; Claude's
+9.5 pp Arm A→B shift is near that threshold.
