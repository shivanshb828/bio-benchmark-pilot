"""
Prompt construction for both arms.

LEAKAGE IS THE WHOLE BALLGAME. If p_a, p_b, or delta reach the model, the
result is worthless. assert_clean() is called on every prompt before it is
sent and will raise rather than let a contaminated prompt through.
"""
import json

SYSTEM = (
    "You are an expert in assay biophysics and bioactivity data curation. "
    "You judge whether two independently reported measurements are "
    "commensurable, meaning they could legitimately be pooled into a single "
    "dataset for training a quantitative model. Answer only with JSON."
)

SCHEMA = """Respond with exactly this JSON and nothing else:
{"call": "COMMENSURABLE" | "NOT_COMMENSURABLE" | "INSUFFICIENT_INFO",
 "confidence": <float 0-1>,
 "error_class": "assay_method" | "buffer_conditions" | "construct_mutant" | "organism" | "readout_type" | "potency_range" | "none" | "other",
 "reason": "<one sentence>"}

"COMMENSURABLE" means you expect the two reported values to agree closely.
"NOT_COMMENSURABLE" means you expect them to differ substantially.
error_class is your primary reason for a NOT_COMMENSURABLE call, else "none"."""

SCHEMA_FORCED = """Respond with exactly this JSON and nothing else:
{"call": "COMMENSURABLE" | "NOT_COMMENSURABLE",
 "confidence": <float 0-1>,
 "error_class": "assay_method" | "buffer_conditions" | "construct_mutant" | "organism" | "readout_type" | "potency_range" | "none" | "other",
 "reason": "<one sentence>"}

"COMMENSURABLE" means you expect the two reported values to agree closely.
"NOT_COMMENSURABLE" means you expect them to differ substantially.
error_class is your primary reason for a NOT_COMMENSURABLE call, else "none".
INSUFFICIENT_INFO is not a valid response. You must commit to COMMENSURABLE or NOT_COMMENSURABLE.
If you lack direct evidence, make your best guess based on compound structure and target identity."""


def control_prompt(item):
    """Arm A: no assay metadata. The null model.

    If a model scores well here, the task is solvable from structure and
    potency priors alone and the metadata arm is confounded.
    """
    return f"""A single compound was assayed by IC50 against a single protein target in two different assays, reported in the literature.

Compound SMILES: {item['smiles']}
Target (ChEMBL): {item['target']}

You are given no information about either assay protocol.

Will the two reported IC50 values agree closely (within 0.3 log units), or differ substantially (more than 1.0 log units)?

{SCHEMA}"""


def control_prompt_forced(item):
    """Arm A (forced-choice): identical to control_prompt but INSUFFICIENT_INFO forbidden.

    Forces the model to commit so results are comparable to ML baselines,
    which cannot abstain. The confidence field is retained for calibration.
    """
    return f"""A single compound was assayed by IC50 against a single protein target in two different assays, reported in the literature.

Compound SMILES: {item['smiles']}
Target (ChEMBL): {item['target']}

You are given no information about either assay protocol.

Will the two reported IC50 values agree closely (within 0.3 log units), or differ substantially (more than 1.0 log units)?

{SCHEMA_FORCED}"""


def metadata_prompt(item, meta):
    """Arm B: full assay descriptions. The real question."""
    a, b = meta.get(item["assay_a"], {}), meta.get(item["assay_b"], {})

    def block(m, tag):
        fields = [
            ("Description", m.get("description")),
            ("Assay type", m.get("assay_type")),
            ("Category", m.get("assay_category")),
            ("ChEMBL confidence score", m.get("confidence_score")),
            ("Organism", m.get("assay_organism")),
            ("Cell type", m.get("assay_cell_type")),
            ("Tissue", m.get("assay_tissue")),
            ("Test type", m.get("assay_test_type")),
        ]
        body = "\n".join(f"  {k}: {v}" for k, v in fields if v not in (None, "", "None"))
        return f"Assay {tag}:\n{body}"

    return f"""A single compound was assayed by IC50 against a single protein target in two different assays, reported in the literature.

Compound SMILES: {item['smiles']}
Target (ChEMBL): {item['target']}

{block(a, 'A')}

{block(b, 'B')}

Will the two reported IC50 values agree closely (within 0.3 log units), or differ substantially (more than 1.0 log units)?

{SCHEMA}"""


def recall_prompt(item):
    """Contamination check v1 (deprecated): keyed on assay_chembl_id.

    Models do not memorize assay IDs, so 0% recall here is uninformative.
    Use recall_prompt_v2_id / recall_prompt_v2_potency instead.
    """
    return f"""What IC50 value was reported for this compound against this target in ChEMBL assay {item['assay_a']}?

Compound SMILES: {item['smiles']}
Target (ChEMBL): {item['target']}

If you genuinely recall the specific reported value, state it in nM. If you do not, say exactly: NO RECALL.
Respond with JSON: {{"value_nM": <float or null>, "recalled": true|false}}"""


def recall_prompt_v2_id(item):
    """Probe 1 (identification): SMILES only — does the model recognize the compound?"""
    return f"""You are given the SMILES string of a chemical compound. If you recognize this compound and know a common name for it, return that name. If you do not recognize it or are uncertain, return null.

Compound SMILES: {item['smiles']}

Respond with exactly this JSON and nothing else:
{{"name": "<common name, IUPAC name, or trade name — or null>", "recognized": true|false, "confidence": <float 0-1>}}"""


def recall_prompt_v2_potency(item, target_name):
    """Probe 2 (potency): SMILES + target — does the model know a reported IC50?"""
    return f"""You are given a chemical compound and a protein target. If you know of a specific IC50 value reported for this compound against this target in the literature or a public database (e.g. ChEMBL, BindingDB), state the value in nM. If you do not know a specific reported value, return null.

Compound SMILES: {item['smiles']}
Target (ChEMBL): {item['target']}
Target name: {target_name}

Respond with exactly this JSON and nothing else:
{{"value_nM": <float or null>, "known": true|false, "confidence": <float 0-1>}}"""


# "label" is intentionally excluded: "COMMENSURABLE" / "NOT_COMMENSURABLE"
# appear in every prompt as the valid JSON response values in SCHEMA. They are
# the task vocabulary, not leaked ground truth.
FORBIDDEN_FLOAT_KEYS = ("p_a", "p_b", "delta")

# SCHEMA contains "within 0.3 log units" and "more than 1.0 log units".
# Delta values close to those thresholds round to "0.3" or "1.0" at 1dp,
# producing false positives. We skip 1dp for delta only; p_a / p_b values
# (typically 4–11 pchembl) don't coincide with any fixed prompt text.
_DELTA_ROUNDINGS = (2, 3, 4)
_PA_PB_ROUNDINGS = (1, 2, 3, 4)


def assert_clean(prompt, item):
    """Raise if any numeric label-bearing value appears in the prompt."""
    for k in ("p_a", "p_b"):
        v = item.get(k)
        if v is None:
            continue
        for s in {str(v)} | {f"{v:.{n}f}" for n in _PA_PB_ROUNDINGS}:
            if s in prompt:
                raise ValueError(
                    f"LEAK: {k}={v} appears in prompt for {item['id']}")
    v = item.get("delta")
    if v is not None:
        for s in {str(v)} | {f"{v:.{n}f}" for n in _DELTA_ROUNDINGS}:
            if s in prompt:
                raise ValueError(
                    f"LEAK: delta={v} appears in prompt for {item['id']}")
    return prompt
