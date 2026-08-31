# Arm B — BLOCKED: assay metadata coverage below 90% gate

**Date:** 2026-08-31  
**Gate:** description coverage ≥ 90% of all assay IDs in the sample  
**Observed:** 117 / 280 assays = **41.8%**  
**Decision: Do not run Arm B.**

---

## Coverage breakdown

| Level | n | % |
|---|---|---|
| Assays with description | 117 / 280 | 41.8% |
| Assays with fetch error | 163 / 280 | 58.2% |

| Error type | Count |
|---|---|
| HTTP 500 (Internal Server Error) | 105 |
| Timeout | 58 |

Errors are persistent: the 163 failed assays returned the same errors on a
second pass with the cache cleared. Timeouts with a 60 s window also failed.
This is not a transient network issue.

### Item-level impact (n = 195)

| Situation | Items | % |
|---|---|---|
| Both assay descriptions available | 52 | 26.7% |
| One assay described, one missing | 65 | 33.3% |
| Neither assay described | 78 | 40.0% |

Running Arm B would leave 78/195 items (40%) with *no* assay metadata —
identical to the control prompt — and 65/195 with only half the information.
Results would be confounded by mixed-metadata composition.

---

## Why the 90% gate exists

The metadata arm tests whether *assay descriptions* drive better
commensurability judgements. If 40% of items have no descriptions at all, the
arm measures a mixture of "model uses descriptions" and "model guesses without
descriptions". The two signals cannot be separated post-hoc, and any
comparison to Arm A (control) would be meaningless: Arm B would be partially
identical to Arm A by construction.

---

## Root cause hypothesis

The 105 HTTP 500 errors are concentrated in assay IDs of the form
`CHEMBL3xxxxxx` and `CHEMBL4xxxxxx` — higher-numbered assays that appear in
the ChEMBL32 max-curation export but may have been deprecated, merged, or
superseded in the current ChEMBL API (which serves a later release). The
source data was downloaded from the ChEMBL32 snapshot; the live API is not
guaranteed to serve all ChEMBL32 assay IDs.

The 58 timeout errors may be retrievable with a dedicated retry strategy
(exponential backoff, higher timeout), but the 105 HTTP 500 errors require
a different resolution.

---

## Required before Arm B can run

**Option A (preferred):** Use the ChEMBL32-specific data download.
The ChEMBL32 assay descriptions are available in the ChEMBL FTP archive
(`ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_32/`).
Replace `fetch_metadata.py` with a local-file reader that extracts
descriptions from the `chembl_32_sqlite.tar.gz` or the assay TSV export.

**Option B:** Restrict Arm B to the 52 items where both assay descriptions
were successfully fetched. Pre-register this restriction before running.
Note: the 52 items are class-imbalanced (21 COMMENSURABLE / 31 NOT_COMMENSURABLE)
and represent only 26.7% of the pilot sample; power will be limited.

**Option C:** Substitute document-level metadata (paper titles, journal,
year) for the 163 missing assay descriptions, and recheck whether the
resulting Arm B prompt still tests the intended question.

---

## Leakage gate status (Task 2)

Even though Arm B is blocked, the leakage test infrastructure is complete
and was exercised against the 117 available descriptions:

- **Direct leakage (p_a / p_b verbatim in metadata_prompt):** 0 items flagged.  
- **Indirect leakage (concentration value within 0.1 log of p_a or p_b):**
  1 assay description contains a concentration value (`10 uM ATP` — a substrate
  concentration), but it is not close to any item's p_a or p_b. 0 items excluded.
- `results/arm_b_exclusions.json` written with `n_excluded = 0`.

When Option A or B above is resolved, re-run
`pytest tests/test_no_leakage.py -k metadata` before executing Arm B.
