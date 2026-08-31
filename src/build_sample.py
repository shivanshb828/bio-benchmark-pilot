"""
Build the balanced pair sample from the ChEMBL32 max-curation export.

Ground truth is free: the divergence between two independently reported
values IS the label. The model never sees the values.

Two filters that matter and are easy to get wrong:
  1. IC50 only. 75.7% of Ki pairs in this export have an exactly zero delta,
     which is the repeated-citation artifact Kramer et al. identified: one
     measurement recorded twice, not two measurements agreeing. Including
     them would make the COMMENSURABLE class mostly duplicate rows.
  2. Exact-zero deltas dropped even within IC50 (19.2% of pairs), for the
     same reason.

Run:  python -m src.build_sample
"""
import gzip, csv, json, random, itertools, statistics
from collections import defaultdict

from .config import (SOURCE, RESULTS, SEED, AGREE_MAX, DISAGREE_MIN,
                     N_PER_CLASS, MAX_PER_TARGET)


def load_pairs(act_type="IC50"):
    pairs = []
    for path in sorted(SOURCE.glob(f"*.{act_type}.csv.gz")):
        stem = path.name[: -len(".csv.gz")]
        target = stem.replace("target_", "").split("-")[0]
        by, smiles = defaultdict(dict), {}
        with gzip.open(path, "rt") as f:
            for r in csv.DictReader(f):
                try:
                    v = float(r["pchembl_value"])
                except (TypeError, ValueError):
                    continue
                by[r["compound_chembl_id"]].setdefault(
                    r["assay_chembl_id"], []).append(v)
                smiles[r["compound_chembl_id"]] = r["canonical_smiles"]

        for cmpd, assays in by.items():
            if len(assays) < 2:
                continue
            med = {a: statistics.median(vs) for a, vs in assays.items()}
            for a1, a2 in itertools.combinations(sorted(med), 2):
                d = abs(med[a1] - med[a2])
                if d == 0.0:
                    continue          # non-independent duplicate
                pairs.append(dict(
                    target=target, dataset=stem, act_type=act_type,
                    compound=cmpd, smiles=smiles[cmpd],
                    assay_a=a1, assay_b=a2,
                    p_a=med[a1], p_b=med[a2], delta=round(d, 4),
                ))
    return pairs


def stratified(pool, n, cap, rng):
    rng.shuffle(pool)
    seen, per_target, out = set(), defaultdict(int), []
    for p in pool:
        if p["compound"] in seen or per_target[p["target"]] >= cap:
            continue
        seen.add(p["compound"])
        per_target[p["target"]] += 1
        out.append(p)
        if len(out) == n:
            break
    return out


def main():
    rng = random.Random(SEED)
    pairs = load_pairs("IC50")

    agree = [p for p in pairs if p["delta"] < AGREE_MAX]
    disagree = [p for p in pairs if p["delta"] > DISAGREE_MIN]

    print(f"nonzero IC50 pairs      : {len(pairs):,}")
    print(f"  agree  (0, {AGREE_MAX}) : {len(agree):,} "
          f"over {len({p['compound'] for p in agree}):,} compounds")
    print(f"  disagree (> {DISAGREE_MIN}) : {len(disagree):,} "
          f"over {len({p['compound'] for p in disagree}):,} compounds")

    A = stratified(agree, N_PER_CLASS, MAX_PER_TARGET, rng)
    D = stratified(disagree, N_PER_CLASS, MAX_PER_TARGET, rng)

    items = ([dict(p, label="COMMENSURABLE") for p in A] +
             [dict(p, label="NOT_COMMENSURABLE") for p in D])
    rng.shuffle(items)
    for i, it in enumerate(items):
        it["id"] = f"p{i:03d}"

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "pilot_sample_v0.json"
    json.dump({
        "seed": SEED,
        "source": ("rinikerlab/overlapping_assays, ChEMBL32 max-curation export; "
                   "IC50 only; exact-duplicate deltas excluded"),
        "thresholds": {"agree_max": AGREE_MAX, "disagree_min": DISAGREE_MIN},
        "n": len(items),
        "items": items,
    }, open(out, "w"), indent=1)

    print(f"\nsampled {len(A)} agree / {len(D)} disagree "
          f"across {len({i['target'] for i in items})} targets")
    print(f"median delta  agree={statistics.median([p['delta'] for p in A]):.3f}  "
          f"disagree={statistics.median([p['delta'] for p in D]):.3f}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
