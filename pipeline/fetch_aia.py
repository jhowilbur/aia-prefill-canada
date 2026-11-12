"""Download published AIA datasets from open.canada.ca (CKAN) into data/raw/<dataset-id>/.

Read-only HTTP GETs via `curl -4` (IPv4 only). Files are untrusted data:
never executed, only hashed here. Writes data/raw/<id>/package.json (CKAN metadata) and
data/SOURCES.csv. Usage: python3 -I pipeline/fetch_aia.py  (live CKAN search; new AIAs may appear.
For the exact corpus of a release use scripts/fetch_pinned.py, which follows data/SOURCES.csv.)
"""
import csv, hashlib, json, os, re, subprocess, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
API = "https://open.canada.ca/data/api/action/"
MAX_FILE = 50 * 1024 * 1024
# CKAN hits for q="Algorithmic Impact" that are NOT an individual system's AIA.
EXCLUDE = {"5423054a-093c-4239-85be-fa0b36ae0b2e",  # TBS: the blank AIA tool/questionnaire itself
           "fcbc0200"}  # prefix: GC AI Register (MVP) – a register, not an AIA


def get(url, out=None, timeout=120):
    cmd = ["curl", "-4", "-sSL", "--fail", "--max-time", str(timeout), "--max-filesize", str(MAX_FILE), url]
    if out:
        cmd += ["-o", out]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl {r.returncode} {url}: {r.stderr.decode()[:200]}")
    return r.stdout


def api(action, **params):
    d = json.loads(get(API + action + "?" + urllib.parse.urlencode(params)))
    if not d.get("success"):
        raise RuntimeError(d)
    return d["result"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[:120] or "file"


def main():
    res = api("package_search", q='"Algorithmic Impact"', rows=1000)
    pkgs = [p for p in res["results"] if p["id"] not in EXCLUDE and not any(p["id"].startswith(e) for e in EXCLUDE)]
    print(f"search count={res['count']} kept={len(pkgs)}")
    rows = []
    for p in pkgs:
        d = os.path.join(RAW, p["name"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "package.json"), "w") as f:
            json.dump(p, f, ensure_ascii=False, indent=1)
        org = (p.get("organization") or {})
        date = (p.get("date_published") or p.get("metadata_created") or "")[:10]
        lic = p.get("license_title") or p.get("license_id")
        for r in p.get("resources", []):
            url = r.get("url") or ""
            if url.startswith("/"):
                url = "https://open.canada.ca" + url
            fmt = (r.get("format") or "").upper()
            lang = "/".join(r.get("language") or [])
            base = os.path.basename(urllib.parse.urlparse(url).path) or r["id"]
            fn = safe_name(r["id"][:8] + "_" + base)
            if fmt == "HTML" and not fn.lower().endswith((".html", ".htm")):
                fn += ".html"
            out = os.path.join(d, fn)
            status = "ok"
            if not os.path.exists(out):
                try:
                    get(url, out)
                except Exception as e:
                    status = "error: " + str(e)[:120]
                    if os.path.exists(out):
                        os.remove(out)
            rows.append({
                "dataset_id": p["id"], "title": p.get("title", "").strip(), "department": org.get("name", ""),
                "department_title": (org.get("title") or "").split("|")[0].strip(), "date": date,
                "resource_id": r["id"], "resource_name": (r.get("name") or "").strip(), "format": fmt,
                "file": os.path.relpath(out, ROOT) if status == "ok" else "", "url": url, "licence": lic,
                "language": lang, "sha256": sha256(out) if status == "ok" else "", "bytes": os.path.getsize(out) if status == "ok" else "",
                "status": status})
            print(status[:40], fmt, p["id"][:8], fn)
    with open(os.path.join(ROOT, "data", "SOURCES.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("rows", len(rows), "errors", sum(r["status"] != "ok" for r in rows))


if __name__ == "__main__":
    main()
