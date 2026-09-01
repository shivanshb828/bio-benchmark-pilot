"""
Characterise ChEMBL assay descriptions to distinguish two competing
explanations for Arm B's poor performance:

  Hypothesis A (reasoning failure): the descriptions contain enough signal
    and the model fails to act on it.
  Hypothesis B (information gap): the descriptions are too terse to carry
    the signal, so the model's failure is partly information-limited.

For each of the 280 descriptions, we compute:
  - character and word length
  - presence of keywords for four signal categories

For each of the 195 items, we check whether the two descriptions *differ*
on any signal category — that is the actionable signal the model would need
to correctly predict NOT_COMMENSURABLE.

We then cross-tabulate "descriptions differ on at least one category" with
Arm B accuracy to test whether the model extracts the available signal.

Run:  python -m src.describe_metadata [--model claude]
"""
import json, re, statistics
from collections import Counter, defaultdict
from pathlib import Path

from .config import RESULTS, DATA

# ── keyword sets ─────────────────────────────────────────────────────────────
# Detection technology: specific detection method that can differ between labs.
DETECTION_KW = re.compile(
    r'\b(TR[-\s]?FRET|HTRF|AlphaScreen|Alpha[Ll]isa|FRET|fluorimetr\w+|'
    r'fluoresc\w+|luminescen\w+|radiometr\w+|scintillat\w+|'
    r'SPR|surface plasmon|NMR|electrochemiluminescen\w+|ECLIA|'
    r'electrophysiol\w+|patch[- ]clamp|ITC|isothermal|'
    r'LANCE|DELFIA|FLIPR|FP|fluorescence polariz\w+|'
    r'mobility[- ]shift|microfluidic|TR-FRET|time-resolved)\b',
    re.IGNORECASE,
)

# Cell system: whether the assay is cell-based (vs. biochemical/recombinant).
CELL_KW = re.compile(
    r'\b(HEK\d*|CHO|Jurkat|Ba/?F3|MCF\d*|K562|U937|MOLT|THP|'
    r'cell[- ]?based|cellular|whole[- ]cell|live[- ]cell|'
    r'membrane[- ]based|membrane preparation|microsomes|'
    r'cell line|primary cell|PBMC)\b',
    re.IGNORECASE,
)

# Substrate / reporter system: can drive method-specific potency differences.
SUBSTRATE_KW = re.compile(
    r'\b(biotin\w*|coumarin\w*|MCA|AMC|rhodamine\w*|CMNPC|'
    r'fluorogenic\w*|peptide substrate|histone\w*|'
    r'Biotin-\w+|poly-Glu|poly.{1,6}Tyr|'
    r'[Ss]ubstrate[- ]\w+|\w+[- ][Ss]ubstrate)\b',
    re.IGNORECASE,
)

# Explicit concentration / screening condition in the description.
CONC_KW = re.compile(
    r'\b(\d+(?:\.\d+)?\s*(?:pM|nM|[uµ]M|mM))\b',
    re.IGNORECASE,
)

CATEGORIES = {
    "detection":   DETECTION_KW,
    "cell_system": CELL_KW,
    "substrate":   SUBSTRATE_KW,
    "concentration": CONC_KW,
}


def _hits(desc, pattern):
    """Return sorted unique matches (lowercased) in desc."""
    return sorted({m.group(0).lower() for m in pattern.finditer(desc or "")})


def describe_one(assay_id, rec):
    desc = (rec.get("description") or "").strip()
    words = desc.split()
    return {
        "assay_id":    assay_id,
        "n_chars":     len(desc),
        "n_words":     len(words),
        "description": desc,
        **{cat: _hits(desc, pat) for cat, pat in CATEGORIES.items()},
    }


def descriptions_differ(d_a, d_b):
    """
    Return dict of categories where the two descriptions differ.
    Differ means: one mentions a keyword the other does not, OR
    they mention different keywords from the same category.
    """
    diffs = {}
    for cat in CATEGORIES:
        kws_a = set(d_a.get(cat, []))
        kws_b = set(d_b.get(cat, []))
        if kws_a != kws_b:
            diffs[cat] = {"assay_a": sorted(kws_a), "assay_b": sorted(kws_b)}
    return diffs


def main():
    meta = json.loads((RESULTS / "assay_metadata.json").read_text())
    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    excl = {f["id"] for f in
            json.loads((RESULTS / "arm_b_exclusions.json").read_text())["excluded_items"]}

    # Per-assay stats
    assay_stats = {aid: describe_one(aid, rec or {}) for aid, rec in meta.items()}

    # Token-length distribution
    lengths_chars = [s["n_chars"] for s in assay_stats.values()]
    lengths_words = [s["n_words"] for s in assay_stats.values()]

    print("=== Description length ===")
    print(f"  n = {len(lengths_chars)}")
    for name, vals in [("chars", lengths_chars), ("words", lengths_words)]:
        vs = sorted(vals)
        q1 = vs[len(vs)//4]
        q3 = vs[3*len(vs)//4]
        print(f"  {name}: median={statistics.median(vs):.0f}  "
              f"IQR=[{q1}, {q3}]  min={min(vs)}  max={max(vs)}")

    # Category coverage across all 280 descriptions
    print("\n=== Category keyword coverage (n=280 assays) ===")
    for cat, pat in CATEGORIES.items():
        n_hit = sum(1 for s in assay_stats.values() if s[cat])
        print(f"  {cat:<14}: {n_hit:>4}/{len(assay_stats)}  ({100*n_hit/len(assay_stats):.1f}%)")
        # Most common keywords
        kw_counts = Counter(kw for s in assay_stats.values() for kw in s[cat])
        for kw, cnt in kw_counts.most_common(5):
            print(f"               {kw!r:<35} {cnt}")

    # Per-item: do descriptions differ?
    print("\n=== Per-item description divergence (n=195 items) ===")
    items = sample["items"]
    item_diffs = {}
    for it in items:
        da = assay_stats.get(it["assay_a"], {})
        db = assay_stats.get(it["assay_b"], {})
        item_diffs[it["id"]] = descriptions_differ(da, db)

    n_any_diff   = sum(1 for d in item_diffs.values() if d)
    n_no_diff    = len(items) - n_any_diff

    print(f"  Descriptions differ on ≥1 category: {n_any_diff}  ({100*n_any_diff/len(items):.1f}%)")
    print(f"  Descriptions identical on all categories: {n_no_diff}  ({100*n_no_diff/len(items):.1f}%)")

    for cat in CATEGORIES:
        n = sum(1 for d in item_diffs.values() if cat in d)
        print(f"    differ on '{cat}': {n}")

    # Cross-tabulate description divergence with Arm B accuracy
    import os
    from pathlib import Path
    arm_b_dir = RESULTS / "raw" / "metadata" / "claude"
    if not arm_b_dir.exists():
        print("\nArm B responses not found — skipping accuracy cross-tabulation.")
        return

    print("\n=== Arm B accuracy by description divergence (abstentions = wrong) ===")
    label_map = {it["id"]: it["label"] for it in items}

    def accuracy(iids):
        if not iids:
            return float("nan"), 0
        n_right = 0
        pos, neg = [], []
        for iid in iids:
            f = arm_b_dir / f"{iid}.json"
            if not f.exists():
                continue
            call = json.loads(f.read_text())["parsed"].get("call")
            label = label_map[iid]
            correct = (call == label)
            if label == "NOT_COMMENSURABLE":
                pos.append(correct)
            else:
                neg.append(correct)
        if not pos or not neg:
            return float("nan"), len(pos) + len(neg)
        bacc = (sum(pos)/len(pos) + sum(neg)/len(neg)) / 2
        return bacc, len(pos) + len(neg)

    # Split items into "differ" and "same" (excluding excl)
    differ_ids = [it["id"] for it in items if item_diffs[it["id"]] and it["id"] not in excl]
    same_ids   = [it["id"] for it in items if not item_diffs[it["id"]] and it["id"] not in excl]

    ba_differ, n_differ = accuracy(differ_ids)
    ba_same,   n_same   = accuracy(same_ids)

    print(f"  Descriptions differ (n={n_differ}): bacc={ba_differ:.3f}")
    print(f"  Descriptions same   (n={n_same}):   bacc={ba_same:.3f}")

    if ba_differ == ba_differ and ba_same == ba_same:
        delta = ba_differ - ba_same
        print(f"  Δ (differ − same) = {delta:+.3f}")
        if abs(delta) < 0.05:
            print("  VERDICT: accuracy is flat regardless of description divergence.")
            print("  The model does not extract available category-level signal.")
            print("  This supports Hypothesis A (reasoning failure) over B (info gap).")
        elif delta > 0:
            print("  VERDICT: accuracy is higher when descriptions differ —")
            print("  the model partially extracts the signal.")
            print("  The failure is partly information-limited (Hypothesis B).")
        else:
            print("  VERDICT: accuracy is LOWER when descriptions differ —")
            print("  unusual; model may be confused by divergent descriptions.")

    # Also break out by category
    print("\n  By individual category:")
    for cat in CATEGORIES:
        cat_diff_ids = [it["id"] for it in items
                        if cat in item_diffs[it["id"]] and it["id"] not in excl]
        cat_same_ids = [it["id"] for it in items
                        if cat not in item_diffs[it["id"]] and it["id"] not in excl]
        ba_d, n_d = accuracy(cat_diff_ids)
        ba_s, n_s = accuracy(cat_same_ids)
        print(f"    {cat:<14}: differ n={n_d} bacc={ba_d:.3f}  |  "
              f"same n={n_s} bacc={ba_s:.3f}  |  Δ={ba_d-ba_s:+.3f}")

    # Worst-case: items where descriptions look identical but values diverge
    not_comm_same = [it for it in items
                     if it["label"] == "NOT_COMMENSURABLE"
                     and not item_diffs[it["id"]]
                     and it["id"] not in excl]
    print(f"\n=== NOT_COMMENSURABLE items with identical-category descriptions: "
          f"{len(not_comm_same)} ===")
    print("  These are the hardest cases: the model has no category-level signal.")
    for it in sorted(not_comm_same, key=lambda x: -x["delta"])[:10]:
        da = assay_stats[it["assay_a"]].get("description","")[:60]
        db = assay_stats[it["assay_b"]].get("description","")[:60]
        print(f"  {it['id']}  delta={it['delta']:.2f}")
        print(f"    A: {da!r}")
        print(f"    B: {db!r}")


if __name__ == "__main__":
    main()
