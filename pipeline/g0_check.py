"""Gate G0: recompute each published AIA's score from its JSON answers and compare.

Writes reports/g0_score_check.csv and prints the summary used in docs/g0.md.

    python3 -I pipeline/g0_check.py            # uses catalog/versions/ only
    python3 -I pipeline/g0_check.py --history  # also searches every survey revision
                                               # inside the version's range (needs
                                               # data/interim/aia-history/repo)

Truth = published raw score and level read from the AIA PDF (data/interim/aia/*.json,
fields raw_score / impact_level). Answers = the export's `data` object in the primary JSON.
"before" = current vendored survey for every AIA (old behaviour).
"after"  = version-aware: the survey of the tool version that produced the published
           score. That is the "Version: x.y.z" line printed on the score PDF when it
           names a known version (catalog/versions/), else the export's `version` field.
           When the PDF version is newer than the export, the export was re-opened in the
           newer tool, so the tool's load-time conversions are applied first
           (aia_score.convert_loaded_file).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aia_score as A  # noqa: E402

ROOT = A.ROOT
OUT = ROOT / "reports" / "g0_score_check.csv"


def load_aias():
    for f in sorted((ROOT / "data" / "interim" / "aia").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("answers_source") != "json" or not d.get("primary_json"):
            continue
        export = json.loads((ROOT / d["primary_json"]).read_text(encoding="utf-8"))
        yield d, export


def pdf_version(d: dict) -> str | None:
    src = d.get("score_source") or ""
    txt_path = ROOT / (src.replace("data/raw", "data/interim/text", 1) + ".txt")
    if not src or not txt_path.exists():
        return None
    head = txt_path.read_text(encoding="utf-8", errors="replace")[:3000]
    m = re.search(r"Version\s*:?\s*v?(\d+\.\d+(?:\.\d+)?)", head)
    return "v" + m.group(1) if m else None


def main(history: bool = False, write: bool = True) -> dict:
    current = A.load_survey()
    rows = []
    for d, export in load_aias():
        data = export.get("data", {})
        json_version = export.get("version")
        pdf_v = pdf_version(d)
        known = A.available_versions()
        version = pdf_v if pdf_v in known else json_version
        scored_data = data
        if version != json_version:
            scored_data = A.convert_loaded_file(data, version)
        before = A.score(current, data)
        after = A.score(None, scored_data, version=version)
        row = {
            "aia_id": d["id"],
            "version": version,
            "json_version": json_version,
            "pdf_version": pdf_v,
            "published_raw": d["raw_score"],
            "published_level": d["impact_level"],
            "published_mitigation": d.get("mitigation_score"),
            "recomputed_raw": after["raw_impact_score"],
            "recomputed_level": after["level"],
            "recomputed_mitigation": after["mitigation_score"],
            "max_raw": after["max_raw_impact_score"],
            "raw_match": after["raw_impact_score"] == d["raw_score"],
            "level_match": after["level"] == d["impact_level"],
            "before_raw": before["raw_impact_score"],
            "before_level": before["level"],
            "before_raw_match": before["raw_impact_score"] == d["raw_score"],
            "before_level_match": before["level"] == d["impact_level"],
            "primary_json": d["primary_json"],
        }
        row["match"] = row["raw_match"] and row["level_match"]
        if history:
            import aia_versions as V
            hits = [rev for rev in V.survey_revisions(version)
                    if A.score(V.survey_at(rev), scored_data)["raw_impact_score"] == d["raw_score"]]
            row["history_revisions_matching_raw"] = " ".join(hits)
        rows.append(row)

    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    n = len(rows)
    summ = {
        "n": n,
        "before_raw": sum(r["before_raw_match"] for r in rows),
        "before_level": sum(r["before_level_match"] for r in rows),
        "after_raw": sum(r["raw_match"] for r in rows),
        "after_level": sum(r["level_match"] for r in rows),
        "after_both": sum(r["match"] for r in rows),
        "by_version": {},
        "mismatches": [(r["aia_id"], r["version"], r["published_raw"], r["recomputed_raw"],
                        r["published_level"], r["recomputed_level"]) for r in rows if not r["match"]],
    }
    byv = defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        b = byv[r["version"]]
        b[0] += 1
        b[1] += r["before_raw_match"]
        b[2] += r["raw_match"]
        b[3] += r["level_match"]
    summ["by_version"] = {v: {"n": b[0], "before_raw": b[1], "after_raw": b[2], "after_level": b[3]}
                          for v, b in sorted(byv.items())}
    return summ


if __name__ == "__main__":
    s = main(history="--history" in sys.argv)
    print(json.dumps(s, indent=2))
    print(f"G0 before: raw {s['before_raw']}/{s['n']} = {s['before_raw']/s['n']:.1%}, "
          f"level {s['before_level']}/{s['n']} = {s['before_level']/s['n']:.1%}")
    print(f"G0 after:  raw {s['after_raw']}/{s['n']} = {s['after_raw']/s['n']:.1%}, "
          f"level {s['after_level']}/{s['n']} = {s['after_level']/s['n']:.1%}, "
          f"both {s['after_both']}/{s['n']} = {s['after_both']/s['n']:.1%}")
