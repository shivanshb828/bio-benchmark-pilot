"""
Score the v2 compound-keyed contamination probes and produce
results/contamination.json.

Per-item fields in the output:
  id                    — pilot sample item ID
  recognized            — bool: probe-id returned recognized=true
  named_compound        — str|null: the name the model provided
  potency_claimed       — bool: probe-potency returned known=true
  potency_within_0.5_log — bool: stated value_nM is within 0.5 log units
                           of EITHER p_a or p_b (both are the true values;
                           we use the min distance to be conservative)
  contamination_risk    — "high"   if potency_within_0.5_log
                          "medium" if recognized but potency wrong or unclaimed
                          "low"    otherwise

Contamination rule (fixed in advance):
  Any item with contamination_risk="high" is flagged. If the high-risk
  fraction exceeds 10%, the sample is considered contaminated and Arms A/B
  results must be interpreted with that caveat.

pchembl ↔ nM: pchembl = 9 - log10(IC50_nM)
A match requires |p_true - (9 - log10(value_nM))| ≤ 0.5 for either p_a or p_b.

Run:
  python -m src.score_recall_v2 [--model claude]
"""
import argparse, json, math
from collections import Counter
from pathlib import Path

from .config import RESULTS, RAW


def pchembl_from_nM(nm):
    if nm is None or nm <= 0:
        return None
    return 9.0 - math.log10(nm)


def within_0_5(value_nM, p_a, p_b):
    """True if value_nM is within 0.5 log units of p_a OR p_b."""
    pc = pchembl_from_nM(value_nM)
    if pc is None:
        return False
    return min(abs(pc - p_a), abs(pc - p_b)) <= 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude")
    a = ap.parse_args()

    id_dir = RAW / "recall_v2" / "id" / a.model
    pot_dir = RAW / "recall_v2" / "potency" / a.model
    for d in (id_dir, pot_dir):
        if not d.exists():
            raise SystemExit(
                f"Missing recall_v2 responses at {d}.\n"
                "Run: python -m src.run_recall_v2 --model {a.model}"
            )

    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    item_meta = {it["id"]: it for it in sample["items"]}

    results = []
    missing = []

    for it in sample["items"]:
        iid = it["id"]
        id_file = id_dir / f"{iid}.json"
        pot_file = pot_dir / f"{iid}.json"

        if not id_file.exists() or not pot_file.exists():
            missing.append(iid)
            continue

        id_resp = json.loads(id_file.read_text())["parsed"]
        pot_resp = json.loads(pot_file.read_text())["parsed"]

        recognized = bool(id_resp.get("recognized"))
        named_compound = id_resp.get("name") if recognized else None

        potency_claimed = bool(pot_resp.get("known"))
        value_nM = pot_resp.get("value_nM") if potency_claimed else None
        pot_within = within_0_5(value_nM, it["p_a"], it["p_b"])

        if pot_within:
            risk = "high"
        elif recognized:
            risk = "medium"
        else:
            risk = "low"

        results.append({
            "id": iid,
            "label": it["label"],
            "recognized": recognized,
            "named_compound": named_compound,
            "potency_claimed": potency_claimed,
            "potency_within_0.5_log": pot_within,
            "contamination_risk": risk,
        })

    if missing:
        print(f"WARNING: {len(missing)} items missing responses: {missing[:5]}{'…' if len(missing)>5 else ''}")

    n = len(results)
    risk_counts = Counter(r["contamination_risk"] for r in results)
    high_pct = 100 * risk_counts["high"] / n if n else 0

    print(f"\nContamination risk distribution  (model={a.model}, n={n})")
    print(f"  low    : {risk_counts['low']:>4}  ({100*risk_counts['low']/n:.1f}%)")
    print(f"  medium : {risk_counts['medium']:>4}  ({100*risk_counts['medium']/n:.1f}%)")
    print(f"  high   : {risk_counts['high']:>4}  ({100*risk_counts['high']/n:.1f}%)")

    print("\nClass balance within each risk tier")
    print(f"  {'tier':<8}  {'n':>4}  {'COMM':>6}  {'NOT_C':>6}  {'imbalance?'}")
    for tier in ("low", "medium", "high"):
        tier_rows = [r for r in results if r["contamination_risk"] == tier]
        if not tier_rows:
            print(f"  {tier:<8}  {'0':>4}")
            continue
        comm = sum(1 for r in tier_rows if r["label"] == "COMMENSURABLE")
        not_c = len(tier_rows) - comm
        ratio = max(comm, not_c) / len(tier_rows) if tier_rows else 0
        flag = "  *** IMBALANCED ***" if ratio > 0.70 else ""
        print(f"  {tier:<8}  {len(tier_rows):>4}  {comm:>6}  {not_c:>6}{flag}")

    imbalanced_tiers = []
    for tier in ("low", "medium", "high"):
        tier_rows = [r for r in results if r["contamination_risk"] == tier]
        if tier_rows:
            comm = sum(1 for r in tier_rows if r["label"] == "COMMENSURABLE")
            ratio = max(comm, len(tier_rows) - comm) / len(tier_rows)
            if ratio > 0.70:
                imbalanced_tiers.append(tier)

    print()
    if imbalanced_tiers:
        print(f"WARNING: tiers {imbalanced_tiers} are badly imbalanced by label (>70% one class).")
        print("  The stratified analysis in score.py will have low statistical power for these tiers.")
        print("  Consider collapsing medium+low before reporting.")
    else:
        print("Label balance within risk tiers looks acceptable.")

    print()
    if high_pct > 10.0:
        print(f"CONCLUSION: CONTAMINATED — {high_pct:.1f}% of items at high risk (>10% threshold).")
        print("  Arm A and Arm B results must be reported with a contamination caveat.")
    else:
        print(f"CONCLUSION: NOT CONTAMINATED — {high_pct:.1f}% high-risk items (≤10% threshold).")

    out = RESULTS / "contamination.json"
    out.write_text(json.dumps({
        "model": a.model,
        "n": n,
        "risk_counts": dict(risk_counts),
        "high_pct": round(high_pct, 2),
        "items": results,
    }, indent=1))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
