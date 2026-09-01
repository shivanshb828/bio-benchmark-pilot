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

# ── Temperature policy ────────────────────────────────────────────────────────
# Canonical policy: run every model at its API default temperature, because
# that is the configuration a practitioner would actually deploy.
#
# "temperature" in a model entry overrides the default for that model only.
# Omitting "temperature" means the provider receives no temperature parameter.
#
# claude was additionally run at temperature=0 (entry "claude" below) to test
# sensitivity; "claude_default" is the policy-compliant entry.
# gpt-5.6-sol rejects temperature=0 (HTTP 400); it always runs at default=1.
# ─────────────────────────────────────────────────────────────────────────────

MODELS = {
    # Anthropic — claude-opus-4-6
    "claude":         {"provider": "anthropic", "model": "claude-opus-4-6",
                       "temperature": 0},          # pre-policy run; kept for comparison
    "claude_default": {"provider": "anthropic", "model": "claude-opus-4-6"},

    # OpenAI — gpt-5.6-sol (reasoning model, rejects temperature=0)
    "gpt":            {"provider": "openai",    "model": "gpt-5.6-sol"},

    # Google — gemini-3.5-flash (requires GEMINI_API_KEY).
    # gemini-3.1-pro-preview returned 429 on the first call (quota exhausted on
    # the provided key, which appears to be free-tier). Flash is the highest
    # tier reachable; document this in MODEL_COMPARISON.md.
    "gemini":         {"provider": "google",    "model": "gemini-3.5-flash"},

    # xAI — Grok 3 (requires XAI_API_KEY; OpenAI-compatible endpoint)
    "grok":           {"provider": "xai",       "model": "grok-3"},
}

# Provider → (base_url, api_key_env_var)
# "anthropic" is handled separately (different auth header and request format).
PROVIDER_ENDPOINTS = {
    "openai":  ("https://api.openai.com/v1/chat/completions",           "OPENAI_API_KEY"),
    "google":  ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "GEMINI_API_KEY"),
    "xai":     ("https://api.x.ai/v1/chat/completions",                 "XAI_API_KEY"),
}

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
ASSAY_FIELDS = [
    "assay_chembl_id", "description", "assay_type", "assay_category",
    "confidence_score", "assay_organism", "assay_cell_type",
    "assay_tissue", "assay_test_type", "document_chembl_id",
]
