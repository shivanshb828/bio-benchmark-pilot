# Findings — Commensurability Benchmark Pilot

**Models:** claude-opus-4-6 (temperature 0), gpt-5.6-sol (temperature 1, API-enforced)  
**Date:** 2026-09-01 · **n:** 195 items, 168 unique assay pairs · **1 item excluded** (p122, leakage gate)

---

## What was measured

The same compound in two independent assays either yields agreeing IC50s (*commensurable*) or diverging ones (*not commensurable*). Observed divergence is the label; no annotation required. We value-blind the model and ask it to predict agreement from experimental context.

**Arm A:** SMILES + target ID only, forced choice.  
**Arm B:** same plus full ChEMBL assay descriptions.

All figures are **cluster-weighted** (168 unique assay pairs; repeated pairs inflate false-merge by 3–4 pp as-is).

---

## Finding 1 — Descriptions add no measurable signal in either model

| Model | Arm A bacc | Arm B bacc | McNemar p |
|---|---|---|---|
| Claude | 0.490 [0.409, 0.554] | 0.557 [0.499, 0.607] | 0.525 |
| GPT | 0.514 [0.442, 0.580] | 0.578 [0.503, 0.637] | 0.090 |

Neither improvement is significant. For GPT, descriptions are net harmful (−19 items net correct). Neither model clears the structure-only ML baseline (0.578) or the history baseline (0.648).

The failure is not information poverty. Descriptions differ on a detectable methodology category (detection technology, cell system, substrate) in 66.7% of pairs. Accuracy is flat regardless: bacc 0.503 (differ) vs 0.499 (identical), **Δ = 0.004**. The signal is present; neither model extracts it.

---

## Finding 2 — Descriptions push both models toward merging

| Model | Arm A false-merge | Arm B false-merge | Δ |
|---|---|---|---|
| Claude | 0.694 | **0.795** | +0.100 |
| GPT | 0.267 | **0.722** | **+0.455** |

Both false-merge rates rose. GPT's shift is 4.5× larger (+0.455 vs +0.100) because it started from a NOT\_COMMENSURABLE default and had more room to move. GPT migrated from splitting poolable pairs to merging divergent ones: errors redistributed, not resolved.

The shared direction is the stronger claim: descriptions induce a COMMENSURABLE bias regardless of starting prior. Do not average the two false-merge rates — the gap reflects different baselines, not different sensitivity.

**Within-model replication:** Claude at temp=0 shifts +0.100; at API default it shifts +0.081. Both runs agree within bootstrap CI, confirming the effect is stable within a model, not a sampling artefact.

---

## Mechanism: surface matching and its limits

GPT's 86 Arm A→B flips (see `GPT_FLIPS.md`) split as:

- **73% (63/86):** Anchors on target-name and assay-type label without engaging with protocol differences present in the descriptions.
- **27% (23/86):** Notices a visible difference and then underestimates its magnitude.

The 73% pattern dominates. To test whether it reflects reasoning failure rather than terse descriptions, normalised token Jaccard similarity was computed for all 63 cases (see `GPT_FLIPS_SIMILARITY.md`):

| Category | Count |
|---|---|
| Surface matching despite visible differences (Jaccard ≤ 0.9) | **60** |
| No visible differences available (Jaccard > 0.9) | **3** |

**60 of 63 cases (95%) had descriptions differing on detectable features.** GPT ignored them.

**p076** is the headline case: both descriptions read *"Inhibition of HIV1 integrase strand transfer activity"* — word-for-word identical — yet the true delta is 3.70 log units, the largest in the flip set. It illustrates both failure modes at once: surface matching (the model had nothing else to go on) and the description-quality ceiling that better reasoning alone cannot overcome. Improving ChEMBL description depth is a complementary fix, not an alternative explanation.

The "notices then dismisses" pattern is Claude-dominant and the minority mode for GPT (27%). The models fail differently even while shifting the same direction.

---

## Temperature: not a confound

gpt-5.6-sol rejects temperature=0; Claude ran at temp=0. To check whether this asymmetry matters, Claude was re-run at its API default:

| | Arm B bacc | Arm B false-merge |
|---|---|---|
| Claude temp=0 | 0.558 | 0.795 |
| Claude temp=default | 0.556 | 0.789 |
| Δ | −0.002 | −0.006 |

Both differences are far inside the ~0.14 CI width. Temperature is not a material confound; the Claude–GPT comparison needs no asterisk.

---

## Limitations

**Two model families.** The pilot covers Anthropic (two Claude runs) and OpenAI (GPT-5.6-Sol). Two families cannot distinguish a pattern from a coincidence. A third family sharing the direction would substantially strengthen the claim; a reversal would reopen it. Extending to additional providers is the natural next step — `src/run_arm.py` uses a provider registry, so adding a model is two config lines and an API key.

**Small n.** 99 unique divergent compounds caps total items near 200. McNemar detects ~15 pp swings; the 6–7 pp Arm A→B shifts are below detection threshold by design.

**GPT abstention.** GPT abstained on 26.7% of Arm B items (52/195) vs 6.7% for Claude (13/195). Committed-only metrics may not represent the full distribution.

**IC50 only; [0.3, 1.0] gap excluded.** Both baselines and LLM results will degrade when the ambiguous band is reinstated in v1.
