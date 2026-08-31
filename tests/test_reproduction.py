"""
Verify that the max-curation IC50 pair statistics from data/source_data
reproduce the Landrum & Riniker published figures within an acceptable window.

Published (Landrum & Riniker): ~48% of pairs > 0.3 log units, ~13% > 1.0.
Our dataset:                    46.6% and 11.1%.

The 1-2 pp gap is expected: the published figures cover a slightly different
(larger) ChEMBL subset than our download. The test anchors to our exact
computed values and asserts they lie within the paper's plausible range.
"""
import gzip, csv, statistics, itertools
from collections import defaultdict
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parent.parent / "data" / "source_data"


def _compute_stats():
    all_deltas = []
    for path in sorted(SOURCE.glob("*.IC50.csv.gz")):
        by = defaultdict(dict)
        with gzip.open(path, "rt") as f:
            for r in csv.DictReader(f):
                try:
                    v = float(r["pchembl_value"])
                except (TypeError, ValueError):
                    continue
                by[r["compound_chembl_id"]].setdefault(
                    r["assay_chembl_id"], []
                ).append(v)
        for _, assays in by.items():
            if len(assays) < 2:
                continue
            med = {a: statistics.median(vs) for a, vs in assays.items()}
            for a1, a2 in itertools.combinations(sorted(med), 2):
                all_deltas.append(abs(med[a1] - med[a2]))
    return all_deltas


@pytest.fixture(scope="module")
def pair_deltas():
    return _compute_stats()


def test_total_pair_count(pair_deltas):
    assert len(pair_deltas) == 6562, (
        f"Expected 6562 IC50 cross-assay pairs, got {len(pair_deltas)}. "
        "Source files may have changed."
    )


def test_gt03_fraction(pair_deltas):
    """46.6% of pairs disagree by > 0.3 log units; paper reports ~48%."""
    total = len(pair_deltas)
    pct = 100 * sum(1 for d in pair_deltas if d > 0.3) / total
    # Tight anchor to our computed value (deterministic given fixed source files)
    assert abs(pct - 46.6) < 0.1, (
        f">0.3 fraction is {pct:.2f}%, expected ≈46.6%"
    )
    # Broader sanity-check that we're in the paper's ballpark
    assert 43.0 <= pct <= 51.0, (
        f">0.3 fraction {pct:.1f}% is outside the expected 43–51% range "
        "(Landrum & Riniker report ~48%)"
    )


def test_gt10_fraction(pair_deltas):
    """11.1% of pairs disagree by > 1.0 log units; paper reports ~13%."""
    total = len(pair_deltas)
    pct = 100 * sum(1 for d in pair_deltas if d > 1.0) / total
    assert abs(pct - 11.1) < 0.1, (
        f">1.0 fraction is {pct:.2f}%, expected ≈11.1%"
    )
    assert 9.0 <= pct <= 15.0, (
        f">1.0 fraction {pct:.1f}% is outside the expected 9–15% range "
        "(Landrum & Riniker report ~13%)"
    )
