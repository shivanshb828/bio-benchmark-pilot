"""
Score a completed arm.

Headline metric is balanced accuracy against a 0.5 baseline. The metric that
actually decides the benchmark's value is the FALSE MERGE RATE: how often the
model says COMMENSURABLE on a pair that diverges by more than a log unit.
False merges poison training data. False splits only cost sample size.

Run:  python -m src.score --arm control
      python -m src.score --arm control --model claude
"""
import argparse, json, random, statistics
from collections import Counter, defaultdict

from .config import RESULTS, RAW, SEED, MODELS


def load(arm, model):
    d = RAW / arm / model
    if not d.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]


def bacc(rows):
    """Balanced accuracy, abstentions counted as wrong."""
    per = defaultdict(lambda: [0, 0])
    for r in rows:
        per[r["label"]][1] += 1
        if r["call"] == r["label"]:
            per[r["label"]][0] += 1
    if len(per) < 2:
        return float("nan")
    return statistics.mean(c / n for c, n in per.values() if n)


def boot(rows, fn, n=2000):
    rng = random.Random(SEED)
    vals = []
    for _ in range(n):
        s = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
        v = fn(s)
        if v == v:
            vals.append(v)
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]


def report(arm, model):
    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    labels = {i["id"]: i for i in sample["items"]}

    rows, bad = [], 0
    for rec in load(arm, model):
        p = rec.get("parsed", {})
        call = p.get("call")
        if call not in ("COMMENSURABLE", "NOT_COMMENSURABLE", "INSUFFICIENT_INFO"):
            bad += 1
            continue
        it = labels[rec["id"]]
        rows.append({
            "id": rec["id"], "call": call, "label": it["label"],
            "delta": it["delta"], "target": it["target"],
            "conf": p.get("confidence"), "error_class": p.get("error_class"),
        })

    if not rows:
        print(f"  {model}: no parsable responses ({bad} unparsable)")
        return None

    n = len(rows)
    pos = [r for r in rows if r["label"] == "NOT_COMMENSURABLE"]
    neg = [r for r in rows if r["label"] == "COMMENSURABLE"]
    false_merge = sum(r["call"] == "COMMENSURABLE" for r in pos) / len(pos) if pos else float("nan")
    false_split = sum(r["call"] == "NOT_COMMENSURABLE" for r in neg) / len(neg) if neg else float("nan")
    abstain = sum(r["call"] == "INSUFFICIENT_INFO" for r in rows) / n
    ba = bacc(rows)
    lo, hi = boot(rows, bacc)

    print(f"\n=== {arm} / {model} ===")
    print(f"n scored            : {n}  ({bad} unparsable)")
    print(f"balanced accuracy   : {ba:.3f}   95% CI [{lo:.3f}, {hi:.3f}]   baseline 0.500")
    print(f"FALSE MERGE rate    : {false_merge:.3f}   <- the one that matters")
    print(f"false split rate    : {false_split:.3f}")
    print(f"abstention rate     : {abstain:.3f}")

    # calibration
    buckets = defaultdict(lambda: [0, 0])
    for r in rows:
        c = r["conf"]
        if not isinstance(c, (int, float)):
            continue
        b = min(int(c * 5), 4)
        buckets[b][1] += 1
        buckets[b][0] += (r["call"] == r["label"])
    if buckets:
        print("\ncalibration (stated confidence vs actual accuracy)")
        for b in sorted(buckets):
            c, t = buckets[b]
            print(f"  {b*0.2:.1f}-{(b+1)*0.2:.1f}   n={t:>4}   acc={c/t:.2f}")

    # what the model blames when it splits
    ec = Counter(r["error_class"] for r in rows if r["call"] == "NOT_COMMENSURABLE")
    if ec:
        print("\nstated error_class on NOT_COMMENSURABLE calls")
        for k, v in ec.most_common():
            print(f"  {str(k):<20} {v}")

    # does accuracy track how extreme the divergence is?
    print("\naccuracy by true delta band")
    bands = [(0, .1), (.1, .3), (1.0, 1.5), (1.5, 2.5), (2.5, 99)]
    for lo_, hi_ in bands:
        sub = [r for r in rows if lo_ <= r["delta"] < hi_]
        if sub:
            acc = sum(r["call"] == r["label"] for r in sub) / len(sub)
            print(f"  [{lo_:.1f},{hi_:.1f})  n={len(sub):>4}  acc={acc:.2f}")

    return {"arm": arm, "model": model, "n": n, "balanced_accuracy": ba,
            "ci": [lo, hi], "false_merge": false_merge,
            "false_split": false_split, "abstention": abstain}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--model", default=None)
    a = ap.parse_args()

    models = [a.model] if a.model else list(MODELS)
    out = [r for m in models if (r := report(a.arm, m))]

    if a.arm == "control" and out:
        print("\n" + "=" * 62)
        print("PREREGISTERED DECISION RULE (control arm)")
        best = max(r["balanced_accuracy"] for r in out)
        print(f"  best balanced accuracy = {best:.3f}")
        if best > 0.65:
            print("  >0.65 -> the task is largely solvable from structure and")
            print("  potency priors alone. The metadata arm would be CONFOUNDED.")
            print("  Do not proceed to Arm B without redesign.")
        else:
            print("  <=0.65 -> structure priors do not solve the task.")
            print("  Arm B is clean to run. Proceed.")
        print("=" * 62)

    if out:
        p = RESULTS / f"scores_{a.arm}.json"
        json.dump(out, open(p, "w"), indent=1)
        print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
