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
    """Contamination check: can the model simply recall the values?"""
    return f"""What IC50 value was reported for this compound against this target in ChEMBL assay {item['assay_a']}?

Compound SMILES: {item['smiles']}
Target (ChEMBL): {item['target']}

If you genuinely recall the specific reported value, state it in nM. If you do not, say exactly: NO RECALL.
Respond with JSON: {{"value_nM": <float or null>, "recalled": true|false}}"""


FORBIDDEN_KEYS = ("p_a", "p_b", "delta", "label")


def assert_clean(prompt, item):
    """Raise if any label-bearing value appears in the prompt."""
    for k in FORBIDDEN_KEYS:
        v = item.get(k)
        if v is None:
            continue
        if isinstance(v, float):
            # catch the value at several roundings
            for s in {f"{v:.1f}", f"{v:.2f}", f"{v:.3f}", f"{v:.4f}", str(v)}:
                if s in prompt:
                    raise ValueError(f"LEAK: {k}={v} appears in prompt for {item['id']}")
        elif str(v) in prompt:
            raise ValueError(f"LEAK: {k}={v} appears in prompt for {item['id']}")
    return prompt
