# Arm B Failure Cases — 10 Worst False Merges

**Selection criteria:** NOT_COMMENSURABLE items called `COMMENSURABLE` by
claude-opus-4-6 in Arm B, ranked by delta (descending), ties broken by
stated confidence. Excludes p122 (leakage exclusion).

These are what a domain reviewer will actually read. Two structural patterns
dominate: (1) descriptions that are literally identical but values that diverge
enormously, and (2) descriptions that differ on detectable methodology but
the model explains away the difference.

---

## Case 1 — p142

**True delta: 4.45 log units (×28,000 fold divergence)**  
**Model call: COMMENSURABLE (confidence 0.78)**  
**Target:** CHEMBL2039 (MAO-B)

**Assay A** (CHEMBL4686672):
> Inhibition of recombinant human MAO-B

**Assay B** (CHEMBL965567):
> Inhibition of human recombinant MAOB by fluorimetric method

**True values:** p_a = 8.66 | p_b = 4.21  
**Model reason:**
> Both assays measure IC50 inhibition of the same recombinant human MAO-B target
> with confidence score 9, and while the detection method (fluorimetric vs.
> unspecified) may differ slightly, IC50 values for the same compound against the
> same recombinant enzyme typically agree within 0.3 log units when assay
> conditions are standard.

**What went wrong:** The model noticed the detection difference ("fluorimetric vs.
unspecified") but immediately discounted it with a generic prior ("typically agree
when conditions are standard"). A 28,000-fold divergence between two MAO-B assays
with nominally identical substrates is the entire phenomenon this benchmark
is designed to detect. The model's prior overwhelmed the description-level evidence.

---

## Case 2 — p001

**True delta: 4.04 log units (×11,000 fold)**  
**Model call: COMMENSURABLE (confidence 0.60)**  
**Target:** CHEMBL3267 (PI3Kγ)

**Assay A** (CHEMBL3366680):
> Inhibition of PI3Kgamma (unknown origin) assessed as decrease in fluorescence
> intensity using phosphorylated substrate

**Assay B** (CHEMBL871582):
> Inhibition of human PI3Kgamma

**True values:** p_a = 4.26 | p_b = 8.30  
**Model reason:**
> Both assays measure IC50 inhibition of human PI3Kgamma (same target, same
> organism, same confidence score, both binding/functional assays), and while the
> detection method details differ slightly, standard biochemical PI3K kinase assays
> typically yield comparable IC50 values for the same compound.

**What went wrong:** Assay A specifies "unknown origin" for the protein and uses
fluorescence with a phosphorylated substrate. Assay B has no such details. The
signals — source organism ambiguity and different detection readouts — are present
in the text. The model sees them and explicitly notes the detection difference,
then invokes "typically yield comparable values" to override the concern.

---

## Case 3 — p076

**True delta: 3.70 log units (×5,000 fold)**  
**Model call: COMMENSURABLE (confidence 0.85)**  
**Target:** CHEMBL3471 (HIV-1 integrase)

**Assay A** (CHEMBL1111323):
> Inhibition of HIV1 integrase strand transfer activity

**Assay B** (CHEMBL890063):
> Inhibition of HIV1 integrase strand transfer activity

**True values:** p_a = 8.0 | p_b = 4.3  
**Model reason:**
> Both assays have identical descriptions, assay types, confidence scores, and
> organism, suggesting highly similar or identical protocols that should yield
> closely agreeing values.

**What went wrong:** The descriptions are literally identical. The model's
inference is correct given the available information. This is a genuine
information-gap case: whatever caused the 5,000-fold divergence is completely
invisible in the ChEMBL description. The model cannot be faulted for failing here.
This case belongs in Hypothesis B (information-limited), not Hypothesis A
(reasoning failure). See `describe_metadata.py` results: 33 NOT_COMMENSURABLE
items have identical-category descriptions; p076 is the worst of them.

---

## Case 4 — p086

**True delta: 3.69 log units (×4,900 fold)**  
**Model call: COMMENSURABLE (confidence 0.62)**  
**Target:** CHEMBL240 (hERG)

**Assay A** (CHEMBL1225864):
> Inhibition of human ERG by electrophysiology assay

**Assay B** (CHEMBL1259359):
> Inhibition of human ERG

**True values:** p_a = 5.52 | p_b = 9.21  
**Model reason:**
> Both assays measure IC50 inhibition of human ERG (CHEMBL240) with confidence
> score 9 and the same organism, and while Assay A specifies electrophysiology,
> both are binding/functional assays against the same target, so IC50 values are
> likely to agree within 0.3 log units.

**What went wrong:** This is a pure reasoning failure. Electrophysiology (patch
clamp) and biochemical IC50 assays for hERG are known to produce systematically
different values because the electrophysiology assay measures functional channel
block while the biochemical assay measures binding. A domain-aware reader would
flag this as a methodological mismatch. The model acknowledges the difference and
concludes the opposite of what an expert would conclude. This is Hypothesis A.

---

## Case 5 — p069

**True delta: 3.01 log units**  
**Model call: COMMENSURABLE (confidence 0.72)**  
**Target:** CHEMBL2148 (JAK3)

**Assay A** (CHEMBL3374009):
> Inhibition of JAK3 (unknown origin)-mediated phosphorylation of
> Biotin-KAIETDKEYYTVKD incubated for 10 mins prior to substrate addition
> measured after 1 hr in presence of [gamma-33P]ATP by scintillation counting

**Assay B** (CHEMBL3705847):
> Inhibition Assay: The kinase activity of all three JAK kinases is measured
> using a radioactive, end-point assay and with trace amounts of 33P-ATP.

**True values:** p_a = 7.43 | p_b = 10.44  
**Model reason:**
> Both assays measure JAK3 inhibition using radioactive 33P-ATP-based kinase
> activity assays with the same endpoint type (IC50), same organism, same
> confidence score, and very similar methodologies, so the reported IC50 values
> are expected to agree closely.

**What went wrong:** Assay A measures JAK3 specifically with a defined peptide
substrate (Biotin-KAIETDKEYYTVKD). Assay B measures "all three JAK kinases"
— i.e., JAK1, JAK2, and JAK3 together in an unresolved mixture. A selectivity
difference of 1000-fold between JAK-family assays is plausible when one assay
is isoform-specific and the other is not. The model reads "same methodology"
and misses the specificity difference. Three other items (p043, p045, p085)
use this same assay pair and repeat the same error.

---

## Cases 6–8 — p008, p025, p045 (HIV-1 integrase cluster)

**True delta: 3.00 log units each**  
**Model call: COMMENSURABLE (confidence 0.72 each)**  
**Target:** CHEMBL3471 (HIV-1 integrase)

**Assay A** (CHEMBL1033786):
> Inhibition of HIV1 integrase strand transfer activity

**Assay B** (CHEMBL1211287):
> Inhibition of HIV-1 integrase

**True values (examples):** p_a ≈ 4.8–5.2, p_b ≈ 7.8–8.2

**What went wrong:** Assay A specifies "strand transfer activity" — a specific step
in the HIV integrase catalytic mechanism. Assay B describes generic "integrase
inhibition," which could measure a different step (e.g., 3′-processing) or the
same step under different conditions. The model treats the specificity difference
as minor wording variation. The systematic 3-log divergence across multiple
structurally distinct compounds on this assay pair strongly suggests a
protocol-level difference, not measurement noise.

This cluster (p008, p025, p045, p089, p112, p121, p125, p135, p150 — nine items
total) all use the same two assays. A single assay-pair discordance creates nine
false merges.

---

## Case 9 — p043

**True delta: 3.00 log units**  
**Model call: COMMENSURABLE (confidence 0.72)**  
**Target:** CHEMBL2148 (JAK3) — same assay pair as Case 5 above (p069)

Different compound, same systematic error. The model applies the same "same
methodology → agree" reasoning regardless of compound. JAK3 specificity vs.
pan-JAK assay produces a consistent 1000-fold offset across the series.

---

## Case 10 — p085

**True delta: 3.00 log units**  
**Model call: COMMENSURABLE (confidence 0.72)**  
**Target:** CHEMBL2148 (JAK3) — same assay pair as Cases 5 and 9

Third instance. The model's confidence is identical (0.72) across all three
JAK3 compounds. It has not updated on the first error; it cannot, since each
item is presented independently. This is a design feature of the benchmark
(no cross-item learning), but it also means systematic assay-level errors
produce clusters of false merges that inflate the false-merge rate.

---

## Summary

| Case | Target | delta | Conf | Pattern |
|---|---|---|---|---|
| p142 | MAO-B | 4.45 | 0.78 | Prior overrides detection difference (H-A) |
| p001 | PI3Kγ | 4.04 | 0.60 | Prior overrides source + detection signals (H-A) |
| p076 | HIV-IN | 3.70 | 0.85 | **Identical descriptions — no available signal (H-B)** |
| p086 | hERG | 3.69 | 0.62 | Electrophysiology vs biochemical, wrong inference (H-A) |
| p069 | JAK3 | 3.01 | 0.72 | Isoform-specific vs pan-JAK, ignored (H-A) |
| p008 | HIV-IN | 3.00 | 0.72 | Strand-transfer vs generic — cluster of 9 (H-A) |
| p025 | HIV-IN | 3.00 | 0.72 | Same assay pair (H-A) |
| p045 | HIV-IN | 3.00 | 0.72 | Same assay pair (H-A) |
| p043 | JAK3 | 3.00 | 0.72 | Same assay pair as p069 (H-A) |
| p085 | JAK3 | 3.00 | 0.72 | Same assay pair as p069 (H-A) |

**H-A = reasoning failure (information available, wrong inference)**  
**H-B = information gap (descriptions genuinely uninformative)**

9 of 10 worst cases are Hypothesis A. Only p076 is a genuine information gap.
The descriptions are not too terse; the model is not extracting the available
signal. This is consistent with the `describe_metadata.py` finding that
accuracy is flat (Δ bacc = 0.004) regardless of whether descriptions differ
on detectable methodology categories.

The practical consequence: fixing the description gap (e.g., enriching ChEMBL
descriptions) would resolve 1 of the 10 worst cases. The remaining 9 require
improved methodological reasoning, not better information.
