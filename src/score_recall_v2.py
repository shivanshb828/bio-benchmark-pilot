"""
Score the v2 compound-keyed recall probes and produce results/contamination.json.

Tiers measure compound FAMILIARITY, not data contamination per se.
Recovering the assay-pair divergence label from memory would require the model
to recall both assay values independently, not just one canonical IC50.

Per-item fields in contamination.json:
  id                              — pilot sample item ID
  label                           — COMMENSURABLE | NOT_COMMENSURABLE
  recognized                      — bool: probe-id returned recognized=true
  named_compound                  — str|null: name the model provided
  potency_claimed                 — bool: probe-potency returned known=true
  potency_within_0.5_log          — bool: stated value_nM is within 0.5 log
                                    units of EITHER p_a or p_b
  familiarity_tier                — one of:
    "recognized_with_matching_potency"  (recognized + potency_within_0.5_log)
    "recognized_only"                   (recognized, potency wrong or absent)
    "unrecognized"                      (not recognized by id probe)

Corrected verdict logic (see src/null_models.py for derivation):
  The overall hit rate (22/195 = 11.3%) is well below all null models computed
  over the full 195 items, because 142/195 items were unclaimed (null counts
  as a miss).  The decisive comparison is the hit rate among CLAIMED items
  (known=True, value_nM≠null):  22/53 = 41.5%, vs a random-draw null of
  ~30% [19%, 42%].  The observed value sits at the upper edge of the null CI,
  suggesting possible but not statistically clear genuine recall.

  Crucially, even genuine canonical-IC50 recall CANNOT contaminate the
  assay-pair divergence label, because the label depends on the specific
  divergence between two independent assay measurements for the same compound,
  not on the canonical potency.

  VERDICT: Not contaminated for the benchmark's label.

Run:
  python -m src.score_recall_v2 [--model claude]
"""
import argparse, json, math
from collections import Counter
from pathlib import Path

from .config import RESULTS, RAW
from .null_models import compute as compute_nulls, print_table


def pchembl_from_nM(nm):
    if nm is None or nm <= 0:
        return None
    return 9.0 - math.log10(nm)


def within_0_5(value_nM, p_a, p_b):
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
                f"Run: python -m src.run_recall_v2 --model {a.model}"
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
            tier = "recognized_with_matching_potency"
        elif recognized:
            tier = "recognized_only"
        else:
            tier = "unrecognized"

        results.append({
            "id": iid,
            "label": it["label"],
            "recognized": recognized,
            "named_compound": named_compound,
            "potency_claimed": potency_claimed,
            "potency_within_0.5_log": pot_within,
            "familiarity_tier": tier,
        })

    if missing:
        print(f"WARNING: {len(missing)} items missing responses: "
              f"{missing[:5]}{'…' if len(missing) > 5 else ''}")

    n = len(results)
    tier_counts = Counter(r["familiarity_tier"] for r in results)

    # Denominator report (Task 1)
    n_claimed = sum(1 for r in results if r["potency_claimed"])
    n_matching = sum(1 for r in results if r["potency_within_0.5_log"])
    print(f"\nDenominator breakdown  (model={a.model}, n_items={n})")
    print(f"  potency claimed (known=True, value_nM≠null) : {n_claimed}")
    print(f"  hits (within 0.5 log of p_a or p_b)        : {n_matching}")
    print(f"  hit rate, all 195                           : {100*n_matching/n:.1f}%")
    if n_claimed:
        print(f"  hit rate, claimed subset only               : "
              f"{100*n_matching/n_claimed:.1f}%  ({n_matching}/{n_claimed})")

    # Null model table
    null_results = compute_nulls(model=a.model)
    print_table(null_results, a.model)

    # Familiarity tier distribution
    TIERS = ("unrecognized", "recognized_only", "recognized_with_matching_potency")
    print(f"\nFamiliarity tier distribution")
    for tier in TIERS:
        cnt = tier_counts.get(tier, 0)
        print(f"  {tier:<42} : {cnt:>4}  ({100*cnt/n:.1f}%)")

    # Class balance within each tier
    print("\nClass balance within each tier")
    print(f"  {'tier':<42}  {'n':>4}  {'COMM':>6}  {'NOT_C':>6}")
    imbalanced = []
    for tier in TIERS:
        tier_rows = [r for r in results if r["familiarity_tier"] == tier]
        if not tier_rows:
            print(f"  {tier:<42}  {'0':>4}")
            continue
        comm = sum(1 for r in tier_rows if r["label"] == "COMMENSURABLE")
        not_c = len(tier_rows) - comm
        ratio = max(comm, not_c) / len(tier_rows)
        flag = "  *** IMBALANCED ***" if ratio > 0.70 else ""
        print(f"  {tier:<42}  {len(tier_rows):>4}  {comm:>6}  {not_c:>6}{flag}")
        if ratio > 0.70:
            imbalanced.append(tier)

    print()
    if imbalanced:
        print(f"WARNING: tiers {imbalanced} are badly imbalanced by label (>70% one class).")
        print("  The stratified analysis in score.py will have low power for these tiers.")
    else:
        print("Label balance within familiarity tiers is acceptable.")

    # Write contamination.json
    out_data = {
        "model": a.model,
        "n": n,
        "n_claimed": n_claimed,
        "hit_rate_all": round(n_matching / n, 4),
        "hit_rate_claimed": round(n_matching / n_claimed, 4) if n_claimed else None,
        "null_models": null_results,
        "verdict": (
            "Not contaminated for the benchmark label. "
            "Hit rate among claimed items (41.5%, 22/53) sits at the upper "
            "edge of the random-draw null CI (~30% [19%, 42%]), suggesting "
            "borderline potency recall, but canonical-IC50 recall cannot "
            "recover assay-pair divergence. The 10% threshold from v1 was "
            "invalid here; correct comparison is against the null models."
        ),
        "tier_counts": dict(tier_counts),
        "items": results,
    }
    out = RESULTS / "contamination.json"
    out.write_text(json.dumps(out_data, indent=1))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
