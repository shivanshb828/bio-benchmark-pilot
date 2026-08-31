"""
Guard against label leakage in control AND metadata prompts.

This is the single most important test in the repo. If p_a, p_b, or delta
reaches the model, every result from the affected arm is confounded.

CONTROL ARM CHECKS (always run)
--------------------------------
For every item in the 195-item pilot sample, build the control prompt and
assert that none of the three label-bearing floats appear in the text at
roundings 1–4 decimal places or as Python's str() representation.

NOTE ON DELTA AT 1dp: the control prompt contains "within 0.3 log units" and
"more than 1.0 log units". Delta values close to those boundaries round to
"0.3" or "1.0" at 1dp — strings always present in the prompt as structural
text, not leaked data. Roundings 2–4dp and str() are checked instead.
p_a and p_b are checked at all four roundings.

METADATA ARM CHECKS (skipped when assay_metadata.json absent)
--------------------------------------------------------------
Two independent leakage modes in Arm B:

  1. DIRECT: p_a or p_b appear verbatim (any rounding 1–4dp) in the
     metadata_prompt text.  Hard assertion; any hit fails the test.

  2. INDIRECT (concentration-unit scan): ChEMBL descriptions frequently embed
     potency values ("IC50 = 45 nM", "inhibition at 10 uM").  We scan every
     description for any numeric value followed by a concentration unit
     (pM, nM, uM/µM, mM) and convert to pChEMBL.  If any converted value
     falls within 0.1 log units of p_a OR p_b for the item in question,
     the item is flagged.

     Flagged items are written to results/arm_b_exclusions.json and must
     be excluded from Arm B scoring.  The test does NOT fail on these —
     it collects and documents them so they can be excluded explicitly
     rather than silently dropped.

Unit conversions (pchembl = –log10(IC50 in mol/L)):
  pM  → pchembl = 12 – log10(value)
  nM  → pchembl =  9 – log10(value)
  uM  → pchembl =  6 – log10(value)
  mM  → pchembl =  3 – log10(value)
"""
import json, math, re
from pathlib import Path

import pytest

from src.prompts import control_prompt, metadata_prompt

ROOT   = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "results" / "pilot_sample_v0.json"
META   = ROOT / "results" / "assay_metadata.json"
EXCL   = ROOT / "results" / "arm_b_exclusions.json"

# ── concentration-unit regex ──────────────────────────────────────────────────
# matches e.g. "45 nM", "0.5uM", "100 µM", "10mM", "500pM"
_CONC_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(pM|nM|[uµ]M|mM)\b',
    re.IGNORECASE,
)

UNIT_SCALE = {          # converts value in stated unit to pchembl
    "pm": lambda v: 12.0 - math.log10(v),
    "nm": lambda v:  9.0 - math.log10(v),
    "um": lambda v:  6.0 - math.log10(v),
    "µm": lambda v:  6.0 - math.log10(v),
    "mm": lambda v:  3.0 - math.log10(v),
}

INDIRECT_THRESHOLD = 0.1   # log units — tighter than the 0.5 recall threshold


def _to_pchembl(value_str, unit):
    try:
        v = float(value_str)
        if v <= 0:
            return None
        key = unit.lower()
        fn = UNIT_SCALE.get(key)
        return fn(v) if fn else None
    except (ValueError, ZeroDivisionError):
        return None


def _scan_descriptions_for_potency(prompt, item):
    """Return list of hit dicts if any conc value in prompt is within
    INDIRECT_THRESHOLD log units of p_a or p_b."""
    hits = []
    for m in _CONC_RE.finditer(prompt):
        pc = _to_pchembl(m.group(1), m.group(2))
        if pc is None:
            continue
        err_a = abs(pc - item["p_a"])
        err_b = abs(pc - item["p_b"])
        if min(err_a, err_b) <= INDIRECT_THRESHOLD:
            hits.append({
                "matched_text": m.group(0),
                "pchembl_converted": round(pc, 3),
                "p_a": item["p_a"], "err_a": round(err_a, 3),
                "p_b": item["p_b"], "err_b": round(err_b, 3),
            })
    return hits


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def items():
    assert SAMPLE.exists(), (
        f"Sample not found at {SAMPLE}. Run `python -m src.build_sample` first."
    )
    return json.loads(SAMPLE.read_text())["items"]


@pytest.fixture(scope="module")
def meta():
    if not META.exists():
        return None
    return json.loads(META.read_text())


# ── helpers ───────────────────────────────────────────────────────────────────

ROUNDINGS = (1, 2, 3, 4)


def _leak_check(prompt, key, value, roundings):
    hits = []
    candidates = {str(value)} | {f"{value:.{n}f}" for n in roundings}
    for s in candidates:
        if s in prompt:
            hits.append((key, value, s))
    return hits


# ── CONTROL ARM tests (always run) ───────────────────────────────────────────

def test_sample_size(items):
    assert len(items) == 195, f"Expected 195 items, got {len(items)}"


@pytest.mark.parametrize("item_index", range(195))
def test_no_leakage_pa(items, item_index):
    item = items[item_index]
    prompt = control_prompt(item)
    hits = _leak_check(prompt, "p_a", item["p_a"], (1, 2, 3, 4))
    assert not hits, f"p_a leakage in item {item['id']}: {hits}"


@pytest.mark.parametrize("item_index", range(195))
def test_no_leakage_pb(items, item_index):
    item = items[item_index]
    prompt = control_prompt(item)
    hits = _leak_check(prompt, "p_b", item["p_b"], (1, 2, 3, 4))
    assert not hits, f"p_b leakage in item {item['id']}: {hits}"


@pytest.mark.parametrize("item_index", range(195))
def test_no_leakage_delta(items, item_index):
    item = items[item_index]
    prompt = control_prompt(item)
    # 1dp omitted for delta: threshold strings "0.3"/"1.0" appear in every prompt
    hits = _leak_check(prompt, "delta", item["delta"], (2, 3, 4))
    assert not hits, f"delta leakage in item {item['id']}: {hits}"


# ── METADATA ARM tests (skipped when metadata absent) ────────────────────────

def _require_meta(meta):
    if meta is None:
        pytest.skip("assay_metadata.json not present — run src.fetch_metadata first")


@pytest.mark.parametrize("item_index", range(195))
def test_metadata_no_direct_leakage_pa(items, meta, item_index):
    """p_a must not appear verbatim in metadata_prompt at any rounding 1–4dp."""
    _require_meta(meta)
    item = items[item_index]
    prompt = metadata_prompt(item, meta)
    hits = _leak_check(prompt, "p_a", item["p_a"], (1, 2, 3, 4))
    assert not hits, (
        f"p_a DIRECT LEAKAGE in metadata_prompt for {item['id']}: {hits}\n"
        f"  p_a={item['p_a']}  assay_a={item['assay_a']}"
    )


@pytest.mark.parametrize("item_index", range(195))
def test_metadata_no_direct_leakage_pb(items, meta, item_index):
    """p_b must not appear verbatim in metadata_prompt at any rounding 1–4dp."""
    _require_meta(meta)
    item = items[item_index]
    prompt = metadata_prompt(item, meta)
    hits = _leak_check(prompt, "p_b", item["p_b"], (1, 2, 3, 4))
    assert not hits, (
        f"p_b DIRECT LEAKAGE in metadata_prompt for {item['id']}: {hits}\n"
        f"  p_b={item['p_b']}  assay_b={item['assay_b']}"
    )


def test_metadata_indirect_leakage_scan(items, meta):
    """Scan descriptions for embedded concentration values close to p_a/p_b.

    Items with hits are NOT failed here — they are written to
    results/arm_b_exclusions.json for explicit exclusion from Arm B scoring.
    The test fails only if the exclusion file cannot be written.
    """
    _require_meta(meta)

    flagged = []
    for item in items:
        prompt = metadata_prompt(item, meta)
        desc_hits = _scan_descriptions_for_potency(prompt, item)
        if desc_hits:
            flagged.append({
                "id": item["id"],
                "label": item["label"],
                "assay_a": item["assay_a"],
                "assay_b": item["assay_b"],
                "p_a": item["p_a"],
                "p_b": item["p_b"],
                "delta": item["delta"],
                "hits": desc_hits,
            })

    exclusion_data = {
        "n_total": len(items),
        "n_excluded": len(flagged),
        "threshold_log_units": INDIRECT_THRESHOLD,
        "reason": (
            "Description text contains a concentration value (with unit pM/nM/uM/mM) "
            f"within {INDIRECT_THRESHOLD} log units of p_a or p_b. "
            "These items may give the model indirect access to a true IC50 value."
        ),
        "excluded_items": flagged,
    }
    EXCL.write_text(json.dumps(exclusion_data, indent=1))

    # Print a summary to make pytest output informative
    if flagged:
        ids = [f["id"] for f in flagged]
        labels = {f["label"] for f in flagged}
        print(f"\n  Indirect leakage flagged: {len(flagged)} items → {EXCL.name}")
        print(f"  IDs: {ids}")
        print(f"  Labels: {labels}")
        comm = sum(1 for f in flagged if f["label"] == "COMMENSURABLE")
        print(f"  Class balance: {comm} COMMENSURABLE, {len(flagged)-comm} NOT_COMMENSURABLE")
    else:
        print(f"\n  No indirect leakage found — arm_b_exclusions.json written with 0 items")
