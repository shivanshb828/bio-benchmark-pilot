"""
Null models for the v2 potency recall probe.

A "hit" is: stated value_nM converts to pchembl within 0.5 log units of
EITHER p_a or p_b for the item.  The 0.5-log window is wide because the
probe is designed to catch egregious recall, not fine-grained accuracy.

Four null models are computed over two subsets:
  all195   — all 195 pilot items (denominator = 195, claimed + unclaimed)
  claimed  — the subset where the model returned known=True and value_nM≠null

The random-draw null draws ONE pchembl value from the full source pool per
item per bootstrap replicate. Using the full source pool (47 k measurements,
median 6.80) rather than the biased sample pool (median 7.54) is correct
because a contaminated model would recall from the full training distribution,
not from our stratified subsample.

Run:
  python -m src.null_models [--model claude] [--seed N] [--n-boot 5000]
"""
import argparse, gzip, csv, json, math, random, statistics
from pathlib import Path

from .config import SOURCE, RESULTS, RAW, SEED


def load_source_pool():
    """All pchembl values from the IC50 source files."""
    vals = []
    for path in sorted(SOURCE.glob("*.IC50.csv.gz")):
        with gzip.open(path, "rt") as f:
            for r in csv.DictReader(f):
                try:
                    vals.append(float(r["pchembl_value"]))
                except (TypeError, ValueError):
                    continue
    return vals


def hit(guess_pchembl, item):
    return min(abs(guess_pchembl - item["p_a"]),
               abs(guess_pchembl - item["p_b"])) <= 0.5


def hit_rate_const(guess_pchembl, items):
    return sum(hit(guess_pchembl, it) for it in items) / len(items)


def hit_rate_random(items, pool, n_boot, seed):
    """Bootstrap distribution of hit rate under random-draw null."""
    rng = random.Random(seed)
    boot = []
    for _ in range(n_boot):
        hits = sum(hit(rng.choice(pool), it) for it in items)
        boot.append(hits / len(items))
    boot.sort()
    lo = boot[int(0.025 * n_boot)]
    hi = boot[int(0.975 * n_boot)]
    return statistics.mean(boot), lo, hi


def load_claimed(model):
    """Return (claimed_items, claimed_values_nM) for the given model."""
    pot_dir = RAW / "recall_v2" / "potency" / model
    if not pot_dir.exists():
        return [], {}
    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    item_map = {it["id"]: it for it in sample["items"]}
    claimed, vals = [], {}
    for f in sorted(pot_dir.glob("*.json")):
        resp = json.loads(f.read_text())
        p = resp["parsed"]
        if p.get("known") and p.get("value_nM") and p["value_nM"] > 0:
            iid = resp["id"]
            claimed.append(item_map[iid])
            vals[iid] = p["value_nM"]
    return claimed, vals


def observed_hit_rate(items, values_nM):
    """Hit rate of the model's stated values against the true p_a / p_b."""
    if not items:
        return float("nan"), 0, 0
    n_hit = 0
    for it in items:
        v = values_nM.get(it["id"])
        if v:
            rpc = 9.0 - math.log10(v)
            if hit(rpc, it):
                n_hit += 1
    return n_hit / len(items), n_hit, len(items)


def compute(model="claude", n_boot=5000, seed=SEED):
    pool = load_source_pool()
    pool_median = statistics.median(pool)

    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    all_items = sample["items"]
    claimed_items, claimed_vals = load_claimed(model)

    results = {}
    for label, items in [("all195", all_items), ("claimed", claimed_items)]:
        if not items:
            results[label] = None
            continue
        m_rand, lo_rand, hi_rand = hit_rate_random(items, pool, n_boot, seed)
        obs, n_hit, n = observed_hit_rate(items, claimed_vals)
        results[label] = {
            "n": n,
            "null_pool_median": round(hit_rate_const(pool_median, items), 3),
            "null_100nM": round(hit_rate_const(7.0, items), 3),
            "null_random_mean": round(m_rand, 3),
            "null_random_lo95": round(lo_rand, 3),
            "null_random_hi95": round(hi_rand, 3),
            "observed": round(obs, 3) if obs == obs else None,
            "n_hit": n_hit,
        }
    results["pool_median_pchembl"] = round(pool_median, 3)
    results["pool_n"] = len(pool)
    return results


def print_table(results, model):
    pm = results["pool_median_pchembl"]
    print(f"\nNull models for v2 potency probe  (model={model})")
    print(f"Source pool: n={results['pool_n']:,}, median={pm:.2f} pchembl")
    print()
    print(f"{'Null model':<38}  {'all195':>8}  {'claimed':>8}")
    print("-" * 60)
    r_all = results["all195"]
    r_cl = results["claimed"]

    def fmt(val):
        return f"{100*val:.1f}%" if val is not None and val == val else "  n/a"

    print(f"  constant: pool median ({pm:.2f} pchembl)  "
          f"{fmt(r_all['null_pool_median'])}  {fmt(r_cl['null_pool_median'])}")
    print(f"  constant: 100 nM (7.0 pchembl)         "
          f"{fmt(r_all['null_100nM'])}  {fmt(r_cl['null_100nM'])}")
    lo, hi = r_all['null_random_lo95'], r_all['null_random_hi95']
    lo2, hi2 = r_cl['null_random_lo95'], r_cl['null_random_hi95']
    print(f"  random draw from pool                  "
          f"{fmt(r_all['null_random_mean'])} [{100*lo:.1f},{100*hi:.1f}]  "
          f"{fmt(r_cl['null_random_mean'])} [{100*lo2:.1f},{100*hi2:.1f}]")
    print(f"  OBSERVED                               "
          f"{fmt(r_all['observed'])}  {fmt(r_cl['observed'])}")
    print(f"    (n_hit / n)                          "
          f"  {r_all['n_hit']}/{r_all['n']}         {r_cl['n_hit']}/{r_cl['n']}")

    print()
    obs_cl = r_cl["observed"]
    null_mean = r_cl["null_random_mean"]
    null_hi = r_cl["null_random_hi95"]
    print("Verdict (claimed-subset criterion):")
    if obs_cl is None or obs_cl != obs_cl:
        print("  No claimed responses to evaluate.")
    elif obs_cl > null_hi:
        print(f"  Observed ({100*obs_cl:.1f}%) exceeds null 97.5th pct ({100*null_hi:.1f}%).")
        print("  MARGINAL CONTAMINATION SIGNAL — but note that canonical-IC50")
        print("  recall cannot recover the assay-pair divergence label.")
    elif obs_cl > null_mean:
        print(f"  Observed ({100*obs_cl:.1f}%) above null mean ({100*null_mean:.1f}%)")
        print(f"  but within 95% CI [{100*r_cl['null_random_lo95']:.1f}%, {100*null_hi:.1f}%].")
        print("  NOT CONTAMINATED at p<0.05 threshold.")
        print("  Even genuine canonical-IC50 recall cannot recover assay-pair")
        print("  divergence; the relevant label requires knowing both assay")
        print("  values independently.")
    else:
        print(f"  Observed ({100*obs_cl:.1f}%) at or below null mean ({100*null_mean:.1f}%).")
        print("  NOT CONTAMINATED.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude")
    ap.add_argument("--n-boot", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()

    results = compute(model=a.model, n_boot=a.n_boot, seed=a.seed)
    print_table(results, a.model)
    return results


if __name__ == "__main__":
    main()
