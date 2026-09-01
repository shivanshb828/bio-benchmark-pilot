"""
Run one experimental arm against one model.

Every raw response is cached to results/raw/{arm}/{model}/{id}.json BEFORE
parsing, so a crash never costs you API spend and reruns resume for free.

IMPORTANT: error responses are NEVER written to cache. A missing file = not
yet attempted; a cached file always contains a successful API response.

Rate-limit handling (429):
  - Reads the Retry-After header and sleeps exactly that long.
  - 429s do not count against --retries; they are retried separately (up to 8).
  - After 3 consecutive 429s the run stops and prints remaining quota.

Run:
  python -m src.run_arm --arm control_forced --model claude
  python -m src.run_arm --arm metadata       --model gpt --rps 0.3
  python -m src.run_arm --arm control_forced --model gpt --dry-run
"""
import argparse, json, os, sys, time
import urllib.request, urllib.error

from .config import RESULTS, RAW, MODELS
from .prompts import (SYSTEM, control_prompt, control_prompt_forced,
                      metadata_prompt, recall_prompt, assert_clean)

# Models that reject temperature control (reasoning/o-series).
_NO_TEMPERATURE_PREFIXES = ("gpt-5.6", "o1", "o3", "o4")

# Backoff schedule for 429 when Retry-After header is absent (seconds).
# Designed for a ~30-minute rate-limit window: after ~4 attempts the
# cumulative sleep exceeds the window and the quota should have reset.
_429_BACKOFF = [30, 60, 120, 300, 600, 1200, 1800]


def _no_temperature(model_id):
    return any(model_id.startswith(p) for p in _NO_TEMPERATURE_PREFIXES)


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
    body_dict = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user",   "content": user}],
    }
    if not _no_temperature(model):
        body_dict["temperature"] = 0
    body = json.dumps(body_dict).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"content-type": "application/json",
                 "authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode())
        return d["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        # Re-raise with body attached so callers can log it
        e._response_body = body_bytes.decode(errors="replace")
        raise


CALLERS = {"anthropic": call_anthropic, "openai": call_openai}

# Default inter-request delay per provider (seconds).
_DEFAULT_RPS = {"anthropic": 1.0, "openai": 0.5}


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


def _call_with_rate_limit(caller, model, system, prompt, retries, item_id):
    """
    Call the model with 429-aware retry logic.
    Returns the response text, or None if all non-429 retries exhausted.
    Returns "QUOTA_EXHAUSTED" sentinel if 8 consecutive 429s with no
    Retry-After header (suggests a daily/hard cap, not a window reset).

    429s never consume the --retries budget; they have a separate counter.
    """
    consecutive_429s = 0
    rate_retry = 0
    attempt = 0

    while attempt < retries:
        try:
            text = caller(model, system, prompt)
            return text
        except urllib.error.HTTPError as e:
            body = getattr(e, "_response_body", "")
            if e.code == 429:
                consecutive_429s += 1
                limit    = e.headers.get("x-ratelimit-limit-requests", "?")
                remaining = e.headers.get("x-ratelimit-remaining-requests", "?")
                reset    = e.headers.get("x-ratelimit-reset-requests", "?")
                retry_after = (e.headers.get("Retry-After")
                               or e.headers.get("retry-after"))

                if retry_after:
                    wait = float(retry_after)
                    consecutive_429s = 0   # Retry-After means window will open; reset streak
                else:
                    wait = _429_BACKOFF[min(rate_retry, len(_429_BACKOFF) - 1)]

                print(f"  429 on {item_id} (#{consecutive_429s}) — "
                      f"limit={limit} remaining={remaining} resets-in={reset} "
                      f"sleeping={wait:.0f}s")

                # Stop if we've hit the limit 8 times without a Retry-After —
                # this indicates a hard daily cap, not a short window, and we
                # should not keep sleeping and burning quota attempts.
                if consecutive_429s >= 8:
                    print(f"\n  QUOTA HARD-LIMITED: 8 consecutive 429s without "
                          f"Retry-After on {item_id}")
                    print(f"  limit={limit}  remaining={remaining}  resets-in={reset}")
                    print("  Stopping run. Rerun after the reset window to resume.")
                    return "QUOTA_EXHAUSTED"

                rate_retry += 1
                time.sleep(wait)
                continue   # do NOT increment attempt

            consecutive_429s = 0
            attempt += 1
            if attempt >= retries:
                print(f"  FAILED {item_id}: HTTP {e.code} — {body[:200]}")
                return None
            time.sleep(2 ** attempt)

        except Exception as e:                    # noqa: BLE001
            consecutive_429s = 0
            attempt += 1
            if attempt >= retries:
                print(f"  FAILED {item_id}: {e}")
                return None
            time.sleep(2 ** attempt)

    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True,
                    choices=["control", "control_forced", "metadata", "recall"])
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap number of items processed (for testing)")
    ap.add_argument("--retries", type=int, default=3,
                    help="Max non-429 error retries per item")
    ap.add_argument("--rps", type=float, default=None,
                    help="Max requests per second (default: 1.0 anthropic, 0.5 openai)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Build and validate every prompt but make no API calls")
    a = ap.parse_args()

    spec = MODELS[a.model]
    provider = spec["provider"]
    caller = CALLERS[provider]
    model_id = spec["model"]

    delay = 1.0 / (a.rps if a.rps else _DEFAULT_RPS.get(provider, 1.0))

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

    # ── dry-run: validate all prompts, count calls needed ──────────────────
    if a.dry_run:
        print(f"DRY RUN: {a.arm} / {a.model}  ({model_id})")
        if _no_temperature(model_id):
            print(f"  NOTE: {model_id} is a reasoning model — temperature will be omitted")
        n_cached = n_pending = n_leak_error = 0
        for it in items:
            dest = outdir / f"{it['id']}.json"
            if dest.exists():
                n_cached += 1
                continue
            try:
                assert_clean(builders[a.arm](it), it)
                n_pending += 1
            except ValueError as e:
                print(f"  LEAK: {e}")
                n_leak_error += 1
        total = n_cached + n_pending
        print(f"  {total} items total  |  {n_cached} already cached  |  "
              f"{n_pending} API calls needed")
        if n_leak_error:
            print(f"  WARNING: {n_leak_error} items would raise a leakage error — "
                  f"fix before running")
        else:
            print("  Leakage check: CLEAN")
        est_min = n_pending * delay / 60
        print(f"  Estimated time at {1/delay:.2f} req/s: {est_min:.1f} min "
              f"(ignoring 429 pauses)")
        return

    # ── live run ────────────────────────────────────────────────────────────
    if _no_temperature(model_id):
        print(f"NOTE: {model_id} does not support temperature — "
              f"responses will use the model default")

    done = failed = 0
    for n, it in enumerate(items, 1):
        dest = outdir / f"{it['id']}.json"
        if dest.exists():
            done += 1
            continue

        prompt = assert_clean(builders[a.arm](it), it)

        text = _call_with_rate_limit(caller, model_id, SYSTEM, prompt,
                                     a.retries, it["id"])

        if text is None:
            failed += 1
            # Do NOT write anything to cache — leave file absent for retry
            continue

        if text == "QUOTA_EXHAUSTED":
            # Run aborted; don't cache anything
            break

        dest.write_text(json.dumps({
            "id": it["id"], "arm": a.arm, "model": model_id,
            "prompt": prompt, "raw": text, "parsed": parse(text),
        }, indent=1))
        done += 1
        if n % 20 == 0 or n == len(items):
            print(f"  {n}/{len(items)}")

        time.sleep(delay)   # throttle between successful requests

    print(f"{a.arm}/{a.model}: {done} cached in {outdir}"
          + (f"  ({failed} failed — rerun to retry)" if failed else ""))


if __name__ == "__main__":
    main()
