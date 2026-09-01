"""
Fetch assay descriptions from the ChEMBL API for every assay in the sample.

Uses the bulk assay endpoint to minimise round-trips, with per-ID fallback
for batches that fail after retries.

Design rules:
  - NEVER cache a failed fetch. Only write to data/assay_cache/{id}.json on
    a successful HTTP 200 response. This prevents the poisoned-cache failure
    mode where a cached error silently blocks future retries.
  - 404 is recorded as _absent=true (distinct from a fetch error) so we can
    tell "ChEMBL says this assay does not exist" from "request failed".
  - Exponential backoff on 5xx and timeouts: 1 2 4 8 16 s, up to 5 attempts
    per batch, then fall back to per-ID requests for that batch only.
  - Inter-request delay 0.5 s; batch size 20.

Run:  python -m src.fetch_metadata
"""
import json, time, urllib.request, urllib.error, urllib.parse
from pathlib import Path

from .config import RESULTS, DATA, CHEMBL_API, ASSAY_FIELDS

CACHE = DATA / "assay_cache"
DELAY = 0.5          # seconds between requests
BATCH = 20           # assay IDs per bulk call
MAX_ATTEMPTS = 5
USER_AGENT = (
    "commensurability-pilot/0.2 "
    "(benchmark research; github.com/shivanshb828/bio-benchmark-pilot)"
)
BACKOFF = [1, 2, 4, 8, 16]   # seconds


def _make_request(url):
    """Return parsed JSON payload or raise urllib.error.*."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def _extract_record(payload):
    """Pull the fields we care about from a single assay payload dict."""
    rec = {k: payload.get(k) for k in ASSAY_FIELDS}
    rec["_absent"] = False
    return rec


def fetch_batch(ids):
    """
    Fetch a batch of assay IDs via the bulk endpoint.
    Returns dict {assay_id: record} for every ID that came back successfully.
    Raises on unrecoverable failure so the caller can fall back to per-ID.
    """
    id_str = ",".join(ids)
    url = (
        f"{CHEMBL_API}/assay.json"
        f"?assay_chembl_id__in={urllib.parse.quote(id_str)}"
        f"&limit={len(ids) + 5}"          # slightly above batch size for safety
    )
    for attempt, wait in enumerate(BACKOFF[:MAX_ATTEMPTS]):
        try:
            data = _make_request(url)
            results = {}
            for assay in data.get("assays", []):
                aid = assay.get("assay_chembl_id")
                if aid:
                    results[aid] = _extract_record(assay)
            return results
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}          # bulk 404 → none of these IDs exist
            if e.code < 500:
                raise             # 4xx other than 404: don't retry
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(BACKOFF[attempt])
        except Exception:                  # noqa: BLE001
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(BACKOFF[attempt])
    return {}


def fetch_one_id(assay_id):
    """
    Per-ID fallback. Returns record or None (on failure).
    404 → returns an _absent record (cached).
    5xx/timeout → returns None (NOT cached).
    """
    cached = CACHE / f"{assay_id}.json"
    if cached.exists():
        return json.loads(cached.read_text())

    url = f"{CHEMBL_API}/assay/{assay_id}.json"
    for attempt, wait in enumerate(BACKOFF[:MAX_ATTEMPTS]):
        try:
            payload = _make_request(url)
            rec = _extract_record(payload)
            cached.write_text(json.dumps(rec, indent=1))  # only on success
            time.sleep(DELAY)
            return rec
        except urllib.error.HTTPError as e:
            if e.code == 404:
                rec = {k: None for k in ASSAY_FIELDS}
                rec["_absent"] = True
                cached.write_text(json.dumps(rec, indent=1))  # 404 is definitive
                time.sleep(DELAY)
                return rec
            if e.code < 500:
                time.sleep(DELAY)
                return None         # unexpected 4xx, don't retry
            if attempt == MAX_ATTEMPTS - 1:
                time.sleep(DELAY)
                return None         # give up, do NOT cache
            time.sleep(BACKOFF[attempt])
        except Exception:           # noqa: BLE001
            if attempt == MAX_ATTEMPTS - 1:
                time.sleep(DELAY)
                return None
            time.sleep(BACKOFF[attempt])
    return None


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    assay_ids = sorted({a for it in sample["items"]
                        for a in (it["assay_a"], it["assay_b"])})
    print(f"{len(assay_ids)} unique assays to fetch")

    # Only fetch IDs not already in cache
    to_fetch = [aid for aid in assay_ids
                if not (CACHE / f"{aid}.json").exists()]
    already = len(assay_ids) - len(to_fetch)
    print(f"  {already} already cached, {len(to_fetch)} to fetch")

    # ── batch fetch ──────────────────────────────────────────────────────────
    batch_fetched, batch_failed = 0, []
    batches = [to_fetch[i:i + BATCH] for i in range(0, len(to_fetch), BATCH)]

    for b_idx, batch in enumerate(batches, 1):
        try:
            results = fetch_batch(batch)
            # Write successful results to cache
            for aid, rec in results.items():
                (CACHE / f"{aid}.json").write_text(json.dumps(rec, indent=1))
                batch_fetched += 1
            # IDs that came back missing from the bulk response
            missing_from_bulk = [aid for aid in batch if aid not in results]
            if missing_from_bulk:
                batch_failed.extend(missing_from_bulk)
        except Exception:                  # noqa: BLE001
            batch_failed.extend(batch)
        time.sleep(DELAY)
        if b_idx % 5 == 0 or b_idx == len(batches):
            print(f"  batch {b_idx}/{len(batches)}  "
                  f"fetched={batch_fetched}  fallback_queue={len(batch_failed)}")

    # ── per-ID fallback for anything not returned by bulk ────────────────────
    fallback_ok, fallback_fail = 0, []
    if batch_failed:
        print(f"\nFalling back to per-ID requests for {len(batch_failed)} assays")
        for i, aid in enumerate(batch_failed, 1):
            rec = fetch_one_id(aid)
            if rec is not None:
                fallback_ok += 1
            else:
                fallback_fail.append(aid)
            if i % 25 == 0 or i == len(batch_failed):
                print(f"  {i}/{len(batch_failed)}")

    # ── assemble and write final metadata ────────────────────────────────────
    meta = {}
    for aid in assay_ids:
        cached = CACHE / f"{aid}.json"
        if cached.exists():
            meta[aid] = json.loads(cached.read_text())
        else:
            meta[aid] = None   # fetch failed and wasn't cached

    out = RESULTS / "assay_metadata.json"
    json.dump(meta, open(out, "w"), indent=1)

    # ── coverage report ──────────────────────────────────────────────────────
    def has_desc(m):
        return (m is not None and
                m.get("description") and
                len(m["description"].strip()) > 10)

    have_desc   = sum(1 for m in meta.values() if has_desc(m))
    n_absent    = sum(1 for m in meta.values() if m is not None and m.get("_absent"))
    n_failed    = sum(1 for m in meta.values() if m is None)
    n_total     = len(meta)

    print(f"\n{'='*50}")
    print(f"Assay coverage report")
    print(f"  Total assays       : {n_total}")
    print(f"  With description   : {have_desc}  ({have_desc/n_total:.1%})")
    print(f"  Absent (404)       : {n_absent}")
    print(f"  Fetch failed       : {n_failed}")

    if fallback_fail:
        print(f"\n  Remaining failures ({len(fallback_fail)}):")
        for aid in fallback_fail[:30]:
            print(f"    {aid}")
        if len(fallback_fail) > 30:
            print(f"    ... and {len(fallback_fail)-30} more")

    # Item-level breakdown
    sample_items = sample["items"]
    both = sum(1 for it in sample_items
               if has_desc(meta.get(it["assay_a"]))
               and has_desc(meta.get(it["assay_b"])))
    one  = sum(1 for it in sample_items
               if (has_desc(meta.get(it["assay_a"])) !=
                   has_desc(meta.get(it["assay_b"]))))
    none = len(sample_items) - both - one

    print(f"\nItem-level (n={len(sample_items)}):")
    print(f"  Both described  : {both}  ({both/len(sample_items):.1%})")
    print(f"  One described   : {one}  ({one/len(sample_items):.1%})")
    print(f"  Neither         : {none}  ({none/len(sample_items):.1%})")

    if have_desc / n_total < 0.9:
        print(f"\nWARNING: coverage {have_desc/n_total:.1%} < 90%.")
        print("Arm B cannot run without confounding. See fetch failures above.")
    else:
        print(f"\nCoverage {have_desc/n_total:.1%} >= 90%. Proceed to leakage gate.")

    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
