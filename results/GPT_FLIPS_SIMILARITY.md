# GPT Arm-flip (b) — Assay Description Similarity Analysis

**Question:** Among the 63 category-(b) flips (GPT asserts similarity without engaging with differences), how many had *identical or near-identical* descriptions — making the failure an information gap rather than a reasoning failure?

---

## Method

Normalised token Jaccard similarity between Assay A and Assay B descriptions:

> Jaccard(A, B) = |tokens(A) ∩ tokens(B)| / |tokens(A) ∪ tokens(B)|

Tokenisation: whitespace-split, lowercase, punctuation stripped. A score of 1.0 means every token is shared; 0.0 means no overlap.

---

## Distribution across 63 (b) cases

| Jaccard range | Count | Share |
|---|---|---|
| = 1.0 (exact match) | 1 | 2% |
| (0.9, 1.0) near-identical | 2 | 3% |
| [0.7, 0.9] similar | 12 | 19% |
| [0.5, 0.7) moderate | 12 | 19% |
| < 0.5 substantially different | **36** | **57%** |

**Summary thresholds (as requested):**

| Threshold | Count |
|---|---|
| Jaccard > 0.9 (identical or near-identical) | **3** |
| Jaccard < 0.5 (substantially different) | **36** |

---

## Identical or near-identical (Jaccard > 0.9)

| id | Jaccard | True label | True delta | Notes |
|---|---|---|---|---|
| p076 | 1.0000 | NOT\_COMMENSURABLE | 3.70 | Descriptions word-for-word identical |
| p129 | 0.9524 | COMMENSURABLE | 0.18 | "c-Met" vs "c-MET" — trivial capitalisation |
| p152 | 0.9231 | COMMENSURABLE | 0.05 | "recombinant NA transporter" vs "NA transporter" |

**p076 is the only harmful misclassification in this group.** Its descriptions are word-for-word identical ("Inhibition of HIV1 integrase strand transfer activity"), yet the true delta is 3.70 — the largest in the entire flip set. GPT's COMMENSURABLE call was unavoidable given that description quality: the underlying assay protocols differed (metal-ion regime, strand-transfer conditions), but ChEMBL captured none of it. This is an **information gap**, not a reasoning failure.

p129 and p152 are both correctly labelled COMMENSURABLE; GPT's call was right, even if reached by surface matching.

---

## Substantially different (Jaccard < 0.5) — selected examples

36 cases had descriptions differing enough that GPT could in principle have engaged with them.

| id | Jaccard | True label | True delta | Key visible difference |
|---|---|---|---|---|
| p041 | 0.389 | NOT\_COMMENSURABLE | 2.23 | BD1 construct named in A; generic BRD4 in B |
| p043 | 0.104 | NOT\_COMMENSURABLE | 2.33 | Detailed 33P-ATP protocol vs generic JAK multi-kinase description |
| p061 | 0.104 | NOT\_COMMENSURABLE | 2.99 | Same contrast (JAK3 detail vs generic) |
| p069 | 0.104 | NOT\_COMMENSURABLE | 3.01 | Same contrast |
| p114 | 0.100 | COMMENSURABLE | 0.11 | "Binding affinity to human ERalpha" vs full displacement SPA description |
| p088 | 0.135 | COMMENSURABLE | 0.02 | Patent-prose protocol vs standard SPA description |

Nine JAK3 pairs (p043, p054, p061, p069, p085, p090, p115, p144, p187) all share Jaccard ≈ 0.10 — one description is a 40-word detailed protocol, the other a 15-word generic assay note. All nine are NOT\_COMMENSURABLE with deltas of 2.33–3.01. GPT called them all COMMENSURABLE.

---

## Two-way split

| Category | Count | Definition |
|---|---|---|
| **Surface matching despite visible differences** | **60** | Jaccard ≤ 0.9; descriptions differed but GPT did not engage |
| **No visible differences available** | **3** | Jaccard > 0.9; descriptions were effectively identical |

**60 of 63 (b) cases (95%) are genuine reasoning failures.** The model had visible protocol differences available and ignored them.

The 3 information-gap cases do not weaken the surface-matching claim. Of the three, only p076 was a harmful misclassification; the other two (p129, p152) were correctly labelled COMMENSURABLE anyway.

---

## Implication for the mechanism claim

The counter-argument that "GPT failed because descriptions were too terse to distinguish" applies to at most 3 of 63 (b) cases, and only to 1 case (p076) where it caused a harmful wrong call. For 60 cases, the descriptions differed on detectable features — enzyme construct, detection method, incubation protocol, substrate — and GPT anchored on target-name and assay-type label rather than reading them.

p076 is best framed as illustrating **both** failure modes: surface matching is the dominant failure (60/63 cases), but it co-exists with a genuine description-quality ceiling that no amount of better reasoning can overcome. Improving ChEMBL description depth is a complementary fix, not an alternative explanation.
