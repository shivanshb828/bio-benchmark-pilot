"""Shared configuration. Change SEED only if you intend to break reproducibility."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = DATA / "source_data"
RESULTS = ROOT / "results"
RAW = RESULTS / "raw"

SEED = 20260831

# Label thresholds, in log10 units. Fixed by PREREGISTRATION.md.
AGREE_MAX = 0.3       # |delta| < 0.3  -> COMMENSURABLE
DISAGREE_MIN = 1.0    # |delta| > 1.0  -> NOT_COMMENSURABLE
# Pairs in [0.3, 1.0] are excluded from v0 and reinstated in v1.

N_PER_CLASS = 100
MAX_PER_TARGET = 15   # stops one promiscuous target dominating the sample

MODELS = {
    "claude": {"provider": "anthropic", "model": "claude-opus-4-6"},
    "gpt":    {"provider": "openai",    "model": "gpt-5.2"},
}

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
ASSAY_FIELDS = [
    "assay_chembl_id", "description", "assay_type", "assay_category",
    "confidence_score", "assay_organism", "assay_cell_type",
    "assay_tissue", "assay_test_type", "document_chembl_id",
]
