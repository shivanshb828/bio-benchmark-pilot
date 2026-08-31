"""
Run the compound-keyed contamination probes over all 195 pilot items.

Two probes per item:
  id      — SMILES only; asks the model to name the compound
  potency — SMILES + target name; asks for a reported IC50 in nM

Responses are cached to results/raw/recall_v2/{probe}/{model}/{id}.json.
A crashed run resumes for free; existing files are skipped.

Run:
  python -m src.run_recall_v2 --model claude
  python -m src.run_recall_v2 --model claude --probe id      # one probe only
"""
import argparse, json, time
from pathlib import Path

from .config import RESULTS, RAW, DATA, MODELS
from .prompts import SYSTEM, recall_prompt_v2_id, recall_prompt_v2_potency
from .run_arm import CALLERS, parse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--probe", choices=["id", "potency"], default=None,
                    help="Run one probe only (default: both)")
    ap.add_argument("--retries", type=int, default=3)
    a = ap.parse_args()

    spec = MODELS[a.model]
    caller = CALLERS[spec["provider"]]

    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    items = sample["items"]

    target_names = json.loads((DATA / "target_names.json").read_text())

    probes = [a.probe] if a.probe else ["id", "potency"]

    for probe in probes:
        outdir = RAW / "recall_v2" / probe / a.model
        outdir.mkdir(parents=True, exist_ok=True)

        if probe == "id":
            def build(it):
                return recall_prompt_v2_id(it)
        else:
            def build(it):
                return recall_prompt_v2_potency(it, target_names[it["target"]])

        done = 0
        total = len(items)
        print(f"\nProbe '{probe}' ({a.model}, {total} items)")
        for n, it in enumerate(items, 1):
            dest = outdir / f"{it['id']}.json"
            if dest.exists():
                done += 1
                continue

            prompt = build(it)

            for attempt in range(a.retries):
                try:
                    text = caller(spec["model"], SYSTEM, prompt)
                    break
                except Exception as e:                       # noqa: BLE001
                    if attempt == a.retries - 1:
                        text = json.dumps({"_api_error": repr(e)})
                    else:
                        time.sleep(2 ** attempt)

            dest.write_text(json.dumps({
                "id": it["id"], "probe": probe, "model": spec["model"],
                "prompt": prompt, "raw": text, "parsed": parse(text),
            }, indent=1))
            done += 1
            if n % 50 == 0 or n == total:
                print(f"  {n}/{total}")

        print(f"  cached {done} responses in {outdir}")


if __name__ == "__main__":
    main()
