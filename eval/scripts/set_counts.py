"""Recount AIAs, departments and scorable items per evaluation set (eval-plan.md v1.1, H2/H4).

Re-run: python3 -I eval/scripts/set_counts.py
Read-only: reads data/interim/aia, data/interim/inputs, catalog/requirements.jsonl,
catalog/versions/<v>/survey-enfr.json. Writes nothing.

Per-item inclusion rule (v1.1): an item (AIA, question) is scorable when
  1. the question is a select question (radiogroup / dropdown / checkbox) of kind risk or
     mitigation in the current catalogue,
  2. the department answered it in the published JSON export,
  3. the same id exists in the export's own questionnaire version with the same question type
     and the same set of choice values, and every answered value is one of those values.
"""
import json, math, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELECT = {"radiogroup", "dropdown", "checkbox"}
LOCKBOX_FRAC, LOCKBOX_MIN, MIN_CHARS = 0.20, 5, 2000


def walk(elements):
    for el in elements:
        if el.get("type") == "panel":
            yield from walk(el.get("elements", []))
        elif el.get("type") != "html":
            yield el


def version_index(version):
    p = ROOT / "catalog" / "versions" / version / "survey-enfr.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for page in s["pages"]:
        for q in walk(page.get("elements", [])):
            vals = {c["value"] if isinstance(c, dict) else c for c in q.get("choices", []) or []}
            out[q.get("name")] = (q.get("type"), frozenset(vals))
    return out


def main():
    cat = {}
    for line in open(ROOT / "catalog" / "requirements.jsonl", encoding="utf-8"):
        q = json.loads(line)
        if q["question_type"] in SELECT and q["kind"] in ("risk", "mitigation"):
            cat[q["id"]] = (q["question_type"], frozenset(c["value"] for c in q["choices"]))
    aias = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "data/interim/aia").glob("*.json"))]
    inputs = {json.loads(p.read_text(encoding="utf-8"))["id"]: json.loads(p.read_text(encoding="utf-8"))
              for p in (ROOT / "data/interim/inputs").glob("*.json")}
    vcache, rows = {}, []
    for a in aias:
        n_items, qids = 0, set()
        if a["answers_source"] == "json":
            v = a["tool_version"]
            vi = vcache.setdefault(v, version_index(v))
            for qid, val in a["answers"].items():
                if qid not in cat or val in (None, "", []):
                    continue
                if vi.get(qid) != cat[qid]:
                    continue
                vals = val if isinstance(val, list) else [val]
                if all(isinstance(x, str) and x in cat[qid][1] for x in vals):
                    n_items += 1
                    qids.add(qid)
        inp = inputs.get(a["id"], {})
        rows.append(dict(id=a["id"][:8], dept=a["department_code"], date=a["date"], json=a["answers_source"] == "json",
                         lang=a["language"], level=a["impact_level"], items=n_items, qids=qids,
                         narr=inp.get("chars_aia_fields_a", 0), ext=inp.get("chars_documents", 0),
                         tot=inp.get("chars_total", 0)))

    js = [r for r in rows if r["json"]]
    k = max(LOCKBOX_MIN, math.ceil(LOCKBOX_FRAC * len(js)))
    lock = set(r["id"] for r in sorted(js, key=lambda r: (r["date"], r["id"]))[-k:])

    def show(name, rs):
        d = Counter(r["dept"] for r in rs)
        d2 = sum(1 for c in d.values() if c >= 2)
        items = sum(r["items"] for r in rs)
        print(f"{name:52s} AIAs={len(rs):2d} depts={len(d):2d} (>=2 AIAs: {d2}) items={items:5d} "
              f"levels={dict(sorted(Counter(r['level'] for r in rs).items()))} {dict(d.most_common())}")

    print("== sets (lock-box = most recent", k, "JSON AIAs by dataset date) ==")
    show("all published", rows)
    show("JSON (question-level labels)", js)
    show("lock-box", [r for r in js if r["id"] in lock])
    cv = [r for r in js if r["id"] not in lock]
    show("CV pool (JSON minus lock-box)", cv)
    show("CV, any input text (C-narr, all)", cv)
    show("CV, (a) fields >= 2000 chars (C-narr strict)", [r for r in cv if r["narr"] >= MIN_CHARS])
    show("CV, documents >= 2000 chars (C-ext)", [r for r in cv if r["ext"] >= MIN_CHARS])
    show("CV, (a)+documents >= 2000 chars", [r for r in cv if r["tot"] >= MIN_CHARS])
    show("lock-box, documents >= 2000 chars (C-ext)", [r for r in js if r["id"] in lock and r["ext"] >= MIN_CHARS])
    show("lock-box, (a)+documents >= 2000 chars", [r for r in js if r["id"] in lock and r["tot"] >= MIN_CHARS])
    print("JSON AIAs with (a)+docs >= 2000 chars:", sum(r["tot"] >= MIN_CHARS for r in js),
          "| all AIAs:", sum(r["tot"] >= MIN_CHARS for r in rows))
    print("languages (JSON):", dict(Counter(r["lang"] for r in js)), "| French in CV:", sum(r["lang"] == "fr" for r in cv),
          "| French in lock-box:", sum(r["lang"] == "fr" for r in js if r["id"] in lock))
    print("post-June-2026 AIAs:", [(r["id"], r["date"], "json" if r["json"] else "pdf") for r in rows if r["date"] > "2026-06-30"])
    it = sorted(r["items"] for r in js)
    print("scorable items per JSON AIA: min", it[0], "median", it[len(it) // 2], "max", it[-1], "total", sum(it))
    by_v = Counter()
    for a, r in zip(aias, rows):
        if r["json"]:
            by_v[a["tool_version"]] += r["items"]
    print("scorable items by tool version:", dict(by_v))
    qcov = Counter(q for r in cv for q in r["qids"])
    thr = math.ceil(0.8 * len(cv))
    print(f"questions scorable in >= 80% of CV AIAs (>= {thr}/{len(cv)}):", sum(c >= thr for c in qcov.values()),
          "| in >= 50%:", sum(c >= math.ceil(0.5 * len(cv)) for c in qcov.values()), "| in >= 1:", len(qcov))
    lv = Counter(r["level"] for r in js)
    print("level majority share (JSON):", f"{max(lv.values())}/{len(js)} = {max(lv.values()) / len(js):.3f}",
          "| all 39:", f"{max(Counter(r['level'] for r in rows).values())}/{len(rows)}")
    lvcv = Counter(r["level"] for r in cv)
    print("level majority share (CV):", f"{max(lvcv.values())}/{len(cv)} = {max(lvcv.values()) / len(cv):.3f}")


if __name__ == "__main__":
    sys.exit(main())
