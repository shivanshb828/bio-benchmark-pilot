"""
Fetch assay descriptions from the ChEMBL API for every assay in the sample.

Needs network access to www.ebi.ac.uk. Cached per assay, so reruns are cheap
and interruptions are harmless.

The metadata arm is only viable if description coverage is high. This script
reports coverage; check it before building that arm.

Run:  python -m src.fetch_metadata
"""
import json, time, urllib.request, urllib.error

from .config import RESULTS, DATA, CHEMBL_API, ASSAY_FIELDS

CACHE = DATA / "assay_cache"
DELAY = 0.25   # be polite to EBI


def fetch_one(assay_id):
    cached = CACHE / f"{assay_id}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    url = f"{CHEMBL_API}/assay/{assay_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "commensurability-pilot/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        payload = {"_error": f"HTTP {e.code}"}
    except Exception as e:                       # noqa: BLE001
        payload = {"_error": repr(e)}
    rec = {k: payload.get(k) for k in ASSAY_FIELDS}
    rec["_error"] = payload.get("_error")
    cached.write_text(json.dumps(rec, indent=1))
    time.sleep(DELAY)
    return rec


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    sample = json.loads((RESULTS / "pilot_sample_v0.json").read_text())
    assay_ids = sorted({a for it in sample["items"]
                        for a in (it["assay_a"], it["assay_b"])})
    print(f"{len(assay_ids)} unique assays to fetch")

    meta = {}
    for i, aid in enumerate(assay_ids, 1):
        meta[aid] = fetch_one(aid)
        if i % 25 == 0 or i == len(assay_ids):
            print(f"  {i}/{len(assay_ids)}")

    out = RESULTS / "assay_metadata.json"
    json.dump(meta, open(out, "w"), indent=1)

    have_desc = sum(1 for m in meta.values()
                    if m.get("description") and len(m["description"].strip()) > 10)
    errors = sum(1 for m in meta.values() if m.get("_error"))
    print(f"\ndescription coverage : {have_desc}/{len(meta)} = {have_desc/len(meta):.1%}")
    print(f"fetch errors         : {errors}")
    if have_desc / len(meta) < 0.9:
        print("\nWARNING: coverage below 90%. The metadata arm will be "
              "confounded by missing descriptions. Fix before proceeding.")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
