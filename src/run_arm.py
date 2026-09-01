"""
Run one experimental arm against one model.

Every raw response is cached to results/raw/{arm}/{model}/{id}.json BEFORE
parsing, so a crash never costs you API spend and reruns resume for free.

IMPORTANT: error responses are NEVER written to cache. A missing file = not
yet attempted; a cached file always contains a successful API response.

Provider registry:
  Anthropic uses a custom request format. All other providers (OpenAI, Google,
  xAI) speak the OpenAI chat-completions protocol and share one factory.
  Adding a provider = one line in config.PROVIDER_ENDPOINTS.

Temperature policy:
  The model spec in config.MODELS may include a "temperature" key. If present,
  that value is sent to the API. If absent, no temperature parameter is sent
  (API default). This is the canonical policy for new runs.
  claude (temperature=0) is the pre-policy reference run.

Rate-limit handling (429):
  - Reads Retry-After header and sleeps exactly that long.
  - 429s never count against --retries; retried separately up to 8 times.
  - After 8 consecutive 429s without Retry-After: run stops (hard daily cap).
  - --rps throttles request rate; defaults: 1.0 anthropic, 0.5 others.

Run:
  python -m src.run_arm --arm control_forced --model claude_default
  python -m src.run_arm --arm metadata       --model gemini --dry-run
  python -m src.run_arm --arm metadata       --model grok   --rps 0.5
"""
import argparse, json, os, sys, time
import urllib.request, urllib.error

from .config import RESULTS, RAW, MODELS, PROVIDER_ENDPOINTS
from .prompts import (SYSTEM, control_prompt, control_prompt_forced,
                      metadata_prompt, metadata_prompt_forced,
                      recall_prompt, assert_clean)

# ── provider implementations ─────────────────────────────────────────────────

def _call_anthropic(model, system, user, temperature=None):
    body = {
        "model": model, "max_tokens": 512,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if temperature is not None:
        body["temperature"] = temperature
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode())
        return "".join(b.get("text", "") for b in d.get("content", []))
    except urllib.error.HTTPError as e:
        e._response_body = e.read().decode(errors="replace")
        raise


def _make_oai_caller(base_url: str, api_key_env: str):
    """Factory for OpenAI-compatible endpoints (OpenAI, Google, xAI)."""
    def caller(model, system, user, temperature=None):
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user",   "content": user}],
        }
        if temperature is not None:
            body["temperature"] = temperature
        req = urllib.request.Request(
            base_url,
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json",
                     "authorization": f"Bearer {os.environ[api_key_env]}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode())
            return d["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            e._response_body = e.read().decode(errors="replace")
            raise
    return caller


def _build_callers():
    callers = {"anthropic": _call_anthropic}
    for provider, (url, key_env) in PROVIDER_ENDPOINTS.items():
        callers[provider] = _make_oai_caller(url, key_env)
    return callers


CALLERS = _build_callers()

# Backoff for 429 without Retry-After (seconds). Long tail covers 30-min windows.
_429_BACKOFF = [30, 60, 120, 300, 600, 1200, 1800]

# Default inter-request delay per provider (seconds, converted to sleep = 1/rps).
_DEFAULT_RPS = {"anthropic": 1.0}   # others default to 0.5 via argparse


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


def _call_with_rate_limit(caller, model, system, prompt, temp, retries, item_id):
    """
    Call with 429-aware retry logic.
    Returns response text, None (non-429 failure), or "QUOTA_EXHAUSTED".
    429s never consume --retries.
    """
    consecutive_429s = rate_retry = attempt = 0
    while attempt < retries:
        try:
            return caller(model, system, prompt, temperature=temp)
        except urllib.error.HTTPError as e:
            body = getattr(e, "_response_body", "")
            if e.code == 429:
                consecutive_429s += 1
                limit     = e.headers.get("x-ratelimit-limit-requests", "?")
                remaining = e.headers.get("x-ratelimit-remaining-requests", "?")
                reset     = e.headers.get("x-ratelimit-reset-requests", "?")
                ra = e.headers.get("Retry-After") or e.headers.get("retry-after")
                if ra:
                    wait = float(ra)
                    consecutive_429s = 0
                else:
                    wait = _429_BACKOFF[min(rate_retry, len(_429_BACKOFF) - 1)]
                print(f"  429 on {item_id} (#{consecutive_429s}) "
                      f"limit={limit} remaining={remaining} resets-in={reset} "
                      f"sleep={wait:.0f}s")
                if consecutive_429s >= 8:
                    print(f"\n  QUOTA HARD-LIMITED on {item_id} — stopping.")
                    return "QUOTA_EXHAUSTED"
                rate_retry += 1
                time.sleep(wait)
                continue
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
                    choices=["control", "control_forced",
                             "metadata", "metadata_forced", "recall"])
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--limit",   type=int,   default=None)
    ap.add_argument("--retries", type=int,   default=3)
    ap.add_argument("--rps",     type=float, default=None,
                    help="Requests/second (default: 1.0 anthropic, 0.5 others)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate prompts, count pending calls, no API requests")
    a = ap.parse_args()

    spec     = MODELS[a.model]
    provider = spec["provider"]
    model_id = spec["model"]
    temp     = spec.get("temperature")          # None = API default
    caller   = CALLERS[provider]

    default_rps = _DEFAULT_RPS.get(provider, 0.5)
    delay = 1.0 / (a.rps if a.rps else default_rps)

    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    items  = sample["items"][: a.limit]

    meta = {}
    if a.arm in ("metadata", "metadata_forced"):
        p = RESULTS / "assay_metadata.json"
        if not p.exists():
            sys.exit("assay_metadata.json missing. Run src.fetch_metadata first.")
        meta = json.loads(p.read_text())

    outdir = RAW / a.arm / a.model
    outdir.mkdir(parents=True, exist_ok=True)

    builders = {
        "control":         lambda it: control_prompt(it),
        "control_forced":  lambda it: control_prompt_forced(it),
        "metadata":        lambda it: metadata_prompt(it, meta),
        "metadata_forced": lambda it: metadata_prompt_forced(it, meta),
        "recall":          lambda it: recall_prompt(it),
    }

    # ── dry-run ──────────────────────────────────────────────────────────────
    if a.dry_run:
        temp_note = f"temperature={temp}" if temp is not None else "temperature=<API default>"
        print(f"DRY RUN: {a.arm} / {a.model}  ({model_id}, {temp_note})")
        key_env = PROVIDER_ENDPOINTS.get(provider, (None, None))[1]
        if key_env and not os.environ.get(key_env):
            print(f"  WARNING: {key_env} not set — live run will fail")
        n_cached = n_pending = n_leak = 0
        for it in items:
            if (outdir / f"{it['id']}.json").exists():
                n_cached += 1
                continue
            try:
                assert_clean(builders[a.arm](it), it)
                n_pending += 1
            except ValueError as e:
                print(f"  LEAK: {e}")
                n_leak += 1
        print(f"  {n_cached + n_pending} items  |  "
              f"{n_cached} cached  |  {n_pending} calls needed")
        if n_leak:
            print(f"  WARNING: {n_leak} items would raise a leakage error")
        else:
            print("  Leakage check: CLEAN")
        print(f"  Estimated time at {1/delay:.1f} req/s: "
              f"{n_pending * delay / 60:.1f} min (ignoring 429 pauses)")
        return

    # ── live run ─────────────────────────────────────────────────────────────
    temp_note = f"temperature={temp}" if temp is not None else "temperature=<API default>"
    print(f"{a.arm} / {a.model}  ({model_id}, {temp_note})")

    done = failed = 0
    for n, it in enumerate(items, 1):
        dest = outdir / f"{it['id']}.json"
        if dest.exists():
            done += 1
            continue

        prompt = assert_clean(builders[a.arm](it), it)
        text   = _call_with_rate_limit(caller, model_id, SYSTEM, prompt,
                                       temp, a.retries, it["id"])

        if text is None:
            failed += 1
            continue
        if text == "QUOTA_EXHAUSTED":
            break

        dest.write_text(json.dumps({
            "id": it["id"], "arm": a.arm, "model": model_id,
            "prompt": prompt, "raw": text, "parsed": parse(text),
        }, indent=1))
        done += 1
        if n % 20 == 0 or n == len(items):
            print(f"  {n}/{len(items)}")
        time.sleep(delay)

    print(f"{a.arm}/{a.model}: {done} cached in {outdir}"
          + (f"  ({failed} failed — rerun to retry)" if failed else ""))


if __name__ == "__main__":
    main()
