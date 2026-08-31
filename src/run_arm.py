"""
Run one experimental arm against one model.

Every raw response is cached to results/raw/{arm}/{model}/{id}.json BEFORE
parsing, so a crash never costs you API spend and reruns resume for free.

Run:
  python -m src.run_arm --arm control  --model claude
  python -m src.run_arm --arm metadata --model claude
  python -m src.run_arm --arm recall   --model claude --limit 30
"""
import argparse, json, os, sys, time
import urllib.request, urllib.error

from .config import RESULTS, RAW, MODELS
from .prompts import (SYSTEM, control_prompt, control_prompt_forced,
                      metadata_prompt, recall_prompt, assert_clean)


def call_anthropic(model, system, user):
    body = json.dumps({
        "model": model, "max_tokens": 512, "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json",
                 "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode())
    return "".join(b.get("text", "") for b in d.get("content", []))


def call_openai(model, system, user):
    body = json.dumps({
        "model": model, "temperature": 0,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"content-type": "application/json",
                 "authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode())
    return d["choices"][0]["message"]["content"]


CALLERS = {"anthropic": call_anthropic, "openai": call_openai}


def parse(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        t = t[4:] if t.startswith("json") else t
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1:
        return {"_parse_error": text[:400]}
    try:
        return json.loads(t[i:j + 1])
    except json.JSONDecodeError:
        return {"_parse_error": text[:400]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True,
                    choices=["control", "control_forced", "metadata", "recall"])
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--retries", type=int, default=3)
    a = ap.parse_args()

    spec = MODELS[a.model]
    caller = CALLERS[spec["provider"]]

    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    items = sample["items"][: a.limit]

    meta = {}
    if a.arm == "metadata":
        p = RESULTS / "assay_metadata.json"
        if not p.exists():
            sys.exit("assay_metadata.json missing. Run src.fetch_metadata first.")
        meta = json.loads(p.read_text())

    outdir = RAW / a.arm / a.model
    outdir.mkdir(parents=True, exist_ok=True)

    builders = {"control":        lambda it: control_prompt(it),
                "control_forced": lambda it: control_prompt_forced(it),
                "metadata":       lambda it: metadata_prompt(it, meta),
                "recall":         lambda it: recall_prompt(it)}

    done = 0
    for n, it in enumerate(items, 1):
        dest = outdir / f"{it['id']}.json"
        if dest.exists():
            done += 1
            continue

        prompt = assert_clean(builders[a.arm](it), it)

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
            "id": it["id"], "arm": a.arm, "model": spec["model"],
            "prompt": prompt, "raw": text, "parsed": parse(text),
        }, indent=1))
        done += 1
        if n % 20 == 0 or n == len(items):
            print(f"  {n}/{len(items)}")

    print(f"{a.arm}/{a.model}: {done} cached in {outdir}")


if __name__ == "__main__":
    main()
