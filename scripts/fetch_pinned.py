#!/usr/bin/env python3
"""Re-download the exact corpus of this release from open.canada.ca, following the pins in
data/SOURCES.csv (one row per file: dataset id, URL, relative path, SHA-256).

    python3 -I scripts/fetch_pinned.py

Writes data/raw/<dataset>/<file> and data/raw/<dataset>/package.json (CKAN metadata, needed by
pipeline/parse_aia.py). Files are untrusted data: only hashed, never executed. Prints every file
whose SHA-256 differs from the pin (a department may have replaced a file since the release) and exits
with status 2, which stops `make`; set ALLOW_CHANGED=1 to continue anyway.
Content is (c) the Government of Canada, Open Government Licence - Canada.
"""
import csv
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://open.canada.ca/data/api/action/package_show?"


def curl(url, out=None):
    cmd = ["curl", "-sSL", "--fail", "--max-time", "180", "--max-filesize", str(50 * 1024 * 1024), url]
    if os.environ.get("CURL_IPV4"):
        cmd.insert(1, "-4")
    if out:
        cmd += ["-o", out]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl exit {r.returncode}: {url}")
    return r.stdout


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "data", "SOURCES.csv"), encoding="utf-8"))
            if r["status"] == "ok" and r["file"]]
    done_pkg, bad, missing = set(), [], []
    for r in rows:
        out = os.path.join(ROOT, r["file"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        d = os.path.dirname(out)
        if d not in done_pkg:
            pkg = json.loads(curl(API + urllib.parse.urlencode({"id": r["dataset_id"]})))["result"]
            with open(os.path.join(d, "package.json"), "w", encoding="utf-8") as f:
                json.dump(pkg, f, ensure_ascii=False, indent=1)
            done_pkg.add(d)
        if not os.path.exists(out):
            try:
                curl(r["url"], out)
            except RuntimeError as e:
                missing.append((r["file"], str(e)))
                continue
        if sha256(out) != r["sha256"]:
            bad.append(r["file"])
    print(f"files pinned {len(rows)}, downloaded or present {len(rows) - len(missing)}, "
          f"hash mismatches {len(bad)}, missing {len(missing)}")
    for f in bad:
        print("  CHANGED since release:", f)
    for f, e in missing:
        print("  MISSING:", f, e)
    if missing:
        return 1
    return 2 if bad and not os.environ.get("ALLOW_CHANGED") else 0


if __name__ == "__main__":
    sys.exit(main())
