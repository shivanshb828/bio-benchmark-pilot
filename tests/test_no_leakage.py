"""
Guard against label leakage in control prompts.

This is the single most important test in the repo. If p_a, p_b, or delta
reaches the model, every result from the control arm is confounded.

For every item in the 195-item pilot sample, we build the control prompt and
assert that none of the three label-bearing floats appear in the text at
roundings of 1 to 4 decimal places or as Python's str() representation.

NOTE ON DELTA AT 1dp
--------------------
The control prompt contains "within 0.3 log units" and "more than 1.0 log
units" as part of the task description. Delta values close to those boundaries
(e.g. 0.26, 0.27, 0.28, 1.01, 1.02 …) round to "0.3" or "1.0" at 1dp —
strings that are always present in the prompt as structural text, not as data.
Checking 1dp for delta would produce false positives without catching real
leakage. Roundings 2–4dp and the raw str() representation are checked instead;
2dp precision is sufficient to detect any genuine injection of the delta value.

p_a and p_b are checked at all four roundings: their values (pchembl units,
typically 4–11) never coincide with any float in the fixed prompt text.
"""
import json
from pathlib import Path

import pytest

from src.prompts import control_prompt

SAMPLE = Path(__file__).resolve().parent.parent / "results" / "pilot_sample_v0.json"


@pytest.fixture(scope="module")
def items():
    assert SAMPLE.exists(), (
        f"Sample not found at {SAMPLE}. Run `python -m src.build_sample` first."
    )
    return json.loads(SAMPLE.read_text())["items"]


def test_sample_size(items):
    assert len(items) == 195, f"Expected 195 items, got {len(items)}"


def _leak_check(prompt, key, value, roundings):
    """Return list of (key, value, offending_string) for any match found."""
    hits = []
    candidates = {str(value)} | {f"{value:.{n}f}" for n in roundings}
    for s in candidates:
        if s in prompt:
            hits.append((key, value, s))
    return hits


@pytest.mark.parametrize("item_index", range(195))
def test_no_leakage_pa(items, item_index):
    item = items[item_index]
    prompt = control_prompt(item)
    hits = _leak_check(prompt, "p_a", item["p_a"], (1, 2, 3, 4))
    assert not hits, (
        f"p_a leakage in item {item['id']}: {hits}"
    )


@pytest.mark.parametrize("item_index", range(195))
def test_no_leakage_pb(items, item_index):
    item = items[item_index]
    prompt = control_prompt(item)
    hits = _leak_check(prompt, "p_b", item["p_b"], (1, 2, 3, 4))
    assert not hits, (
        f"p_b leakage in item {item['id']}: {hits}"
    )


@pytest.mark.parametrize("item_index", range(195))
def test_no_leakage_delta(items, item_index):
    item = items[item_index]
    prompt = control_prompt(item)
    # 1dp omitted for delta: see module docstring
    hits = _leak_check(prompt, "delta", item["delta"], (2, 3, 4))
    assert not hits, (
        f"delta leakage in item {item['id']}: {hits}"
    )
