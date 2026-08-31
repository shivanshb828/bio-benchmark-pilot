"""
Score the recall-arm responses: contamination check.

For each item the model was asked whether it could recall the specific IC50
value from ChEMBL assay_a. We report:

  - How many responses claim recall (recalled: true)
  - Of those, how many stated a value_nM within 0.5 log units of the true
    pchembl value (p_a stored in the sample)

Interpretation (fixed in advance, per PREREGISTRATION.md):
  >10% accurate recall  → sample is contaminated; Arms A and B are invalid
  ≤10% accurate recall  → contamination not detected; proceed with main arms

pchembl is defined as  -log10(IC50 in mol/L) = 9 - log10(IC50 in nM).
A recalled value_nM is "accurate" if |p_a - (9 - log10(value_nM))| ≤ 0.5.

Run:
  python -m src.score_recall [--model claude] [--limit N]
"""
import argparse, json, math
from pathlib import Path

from .config import RESULTS, RAW


def pchembl_from_nM(nm):
    """Convert IC50 in nM to pchembl units."""
    if nm is None or nm <= 0:
        return None
    return 9.0 - math.log10(nm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    raw_dir = RAW / "recall" / a.model
    if not raw_dir.exists():
        raise SystemExit(
            f"No recall responses found at {raw_dir}. "
            "Run: python -m src.run_arm --arm recall --model {a.model}"
        )

    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    true_values = {it["id"]: it["p_a"] for it in sample["items"]}

    files = sorted(raw_dir.glob("*.json"))
    if a.limit:
        files = files[: a.limit]

    total = len(files)
    claimed_recall = []
    accurate_recall = []

    for f in files:
        resp = json.loads(f.read_text())
        parsed = resp.get("parsed", {})
        item_id = resp["id"]

        if parsed.get("recalled"):
            claimed_recall.append(item_id)
            value_nM = parsed.get("value_nM")
            recalled_pchembl = pchembl_from_nM(value_nM)
            true_p = true_values.get(item_id)
            if recalled_pchembl is not None and true_p is not None:
                err = abs(true_p - recalled_pchembl)
                if err <= 0.5:
                    accurate_recall.append(
                        dict(id=item_id, true_pchembl=true_p,
                             recalled_nM=value_nM,
                             recalled_pchembl=round(recalled_pchembl, 3),
                             error_log_units=round(err, 3))
                    )

    n_claimed = len(claimed_recall)
    n_accurate = len(accurate_recall)
    pct_claimed = 100 * n_claimed / total if total else 0
    pct_accurate = 100 * n_accurate / total if total else 0

    print(f"Recall contamination check  ({a.model}, n={total})")
    print(f"  Claimed recall (recalled: true) : {n_claimed}/{total}  ({pct_claimed:.1f}%)")
    print(f"  Accurate recall (≤0.5 log units): {n_accurate}/{total}  ({pct_accurate:.1f}%)")

    if accurate_recall:
        print("\n  Accurate recalls:")
        for r in accurate_recall:
            print(f"    {r['id']}  true={r['true_pchembl']:.3f} pchembl  "
                  f"recalled={r['recalled_nM']} nM "
                  f"({r['recalled_pchembl']:.3f} pchembl)  "
                  f"err={r['error_log_units']:.3f}")

    print()
    threshold = 10.0
    if pct_accurate > threshold:
        print(f"CONCLUSION: CONTAMINATED — {pct_accurate:.1f}% accurate recall exceeds "
              f"the {threshold:.0f}% threshold. Arms A and B are invalid on this data.")
    else:
        print(f"CONCLUSION: NOT CONTAMINATED — {pct_accurate:.1f}% accurate recall is at "
              f"or below the {threshold:.0f}% threshold. Proceed with main arms.")


if __name__ == "__main__":
    main()
