"""Remove personal information from the interim corpus (audit M5).

Targets every string in data/interim/aia/*.json and data/interim/inputs/*.json:
  - personal names of public servants, taken from the admin name fields
    (projectDetailsRespondent, ADMresponsible) of every AIA and then replaced
    wherever they occur in free text (full name, "Last, First" and "First Last");
    values that are a team, branch, department or role ("Various Stakeholders at
    IRCC", "Example Directorate - Data Office") are kept;
  - e-mail addresses (all, including functional mailboxes);
  - telephone numbers (North American formats, optional extension).
Department and role words (projectDetailsJob, branch, etc.) are kept.

data/raw is never touched (see data/raw/README.md). The script is idempotent and
runs automatically at the end of build_inputs.py; re-run it by hand after parse_aia.py.
Names are collected from the raw exports as well, so a re-run on already-redacted interim
files still finds them.
Writes the count report to reports/pii_redaction.md.

    python3 -I pipeline/redact_pii.py            # redact in place + report
    python3 -I pipeline/redact_pii.py --dry-run  # report only
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = [ROOT / "data" / "interim" / "aia", ROOT / "data" / "interim" / "inputs"]
REPORT = ROOT / "reports" / "pii_redaction.md"
RAW_DIR = ROOT / "data" / "raw"

NAME_FIELDS = ("projectDetailsRespondent", "ADMresponsible")
ANSWER_DICTS = ("answers", "answers_unmapped", "free_text_answers", "free_text_fr", "aia_fields_a")
NAME_TOKEN = "[REDACTED-NAME]"
EMAIL_TOKEN = "[REDACTED-EMAIL]"
PHONE_TOKEN = "[REDACTED-PHONE]"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PHONE_RE = re.compile(
    r"(?<![\w-])(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}"
    r"(?:\s?(?:x|ext\.?|poste)\s?\d{1,6})?(?![\w-])", re.I)
# Words that mark a value as an organisation, team or role rather than a person.
NON_PERSON = re.compile(
    r"\b(various|stakeholders?|divers|intervenants?|team|teams|équipe|branch|direction|division|"
    r"management|modernization|department|ministère|canada|ircc|esdc|cbsa|cra|tbs|pspc|unit|office|"
    r"program|programme|services?|centre|center|sector|secteur|n/?a|s\.?o\.?)\b", re.I)
NAME_PART = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’.-]*"
PERSON_RE = re.compile(rf"^{NAME_PART}(?:\s+{NAME_PART}){{0,3}}$")


def split_people(value: str) -> list[str]:
    """Turn an admin name field into person names; [] if it is an organisation/role."""
    value = re.sub(r"\s+", " ", str(value)).strip()
    if not value or NON_PERSON.search(value):
        return []
    # "Last, First" (exactly one comma, single words both sides) is one person.
    m = re.fullmatch(rf"({NAME_PART}), ({NAME_PART})", value)
    if m:
        return [f"{m.group(2)} {m.group(1)}", f"{m.group(1)}, {m.group(2)}"]
    people = []
    for part in re.split(r",|;| and | et |&|/", value):
        part = part.strip()
        if part and PERSON_RE.match(part) and len(part.split()) >= 2:
            people.append(part)
    return people


def collect_names(records: list[dict]) -> list[str]:
    names = set()
    for rec in records:
        for d in ANSWER_DICTS:
            sub = rec.get(d)
            if not isinstance(sub, dict):
                continue
            for f in NAME_FIELDS:
                v = sub.get(f)
                if isinstance(v, str):
                    names.update(split_people(v))
    # Longest first so "Alex Martin" goes before any shorter overlap.
    return sorted(names, key=lambda s: (-len(s), s))


def raw_records(raw_dir: Path | None = None) -> list[dict]:
    """Answer dicts of every published tool JSON in data/raw (read-only).

    Interim admin fields are already `[REDACTED-NAME]` after a first run, so names are always
    re-read from the untouched raw exports; that keeps a re-run complete and nothing persists
    the name list (audit round 2, L-a)."""
    out = []
    for p in sorted((raw_dir or RAW_DIR).glob("*/*.json")):
        if p.name == "package.json":
            continue
        try:
            d = json.loads(p.read_bytes().decode("utf-8-sig"))
        except Exception:
            continue
        if isinstance(d, dict) and isinstance(d.get("data"), dict):
            rec = {"answers": d["data"]}
            tr = d.get("translationsOnResult")
            if isinstance(tr, dict):
                rec["answers_unmapped"] = {k: (v.get("fr") or v.get("en") if isinstance(v, dict) else v)
                                           for k, v in tr.items()}
            out.append(rec)
    return out


def name_pattern(names: list[str]) -> re.Pattern | None:
    if not names:
        return None
    alts = [r"\s+".join(re.escape(w) for w in n.split()) for n in names]
    return re.compile(r"(?<![\w])(?:" + "|".join(alts) + r")(?![\w])", re.I)


def redact_text(s: str, name_re: re.Pattern | None, counts: collections.Counter) -> str:
    s, n = EMAIL_RE.subn(EMAIL_TOKEN, s)
    counts["email"] += n
    s, n = PHONE_RE.subn(PHONE_TOKEN, s)
    counts["phone"] += n
    if name_re is not None:
        s, n = name_re.subn(NAME_TOKEN, s)
        counts["name"] += n
    return s


def redact_obj(obj, name_re, counts):
    if isinstance(obj, str):
        return redact_text(obj, name_re, counts)
    if isinstance(obj, list):
        return [redact_obj(x, name_re, counts) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_obj(v, name_re, counts) for k, v in obj.items()}
    return obj


def main(argv: list[str]) -> dict:
    dry = "--dry-run" in argv
    files = [p for d in TARGET_DIRS for p in sorted(d.glob("*.json"))]
    loaded = {p: json.loads(p.read_text(encoding="utf-8")) for p in files}
    names = collect_names([r for r in loaded.values() if isinstance(r, dict)] + raw_records())
    name_re = name_pattern(names)
    per_file, total = {}, collections.Counter()
    for p, rec in loaded.items():
        c = collections.Counter()
        new = redact_obj(rec, name_re, c)
        if sum(c.values()):
            per_file[p] = c
            total.update(c)
            if not dry:
                p.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [
        "# PII redaction report",
        "",
        "Generated by `python3 -I pipeline/redact_pii.py`" + (" --dry-run" if dry else "") +
        ". Counts are replacements made in this run (a second run finds 0).",
        f"Scope: {len(files)} files in data/interim/aia and data/interim/inputs. data/raw untouched.",
        f"Distinct person names found in admin fields: {len(names)} (not listed here on purpose).",
        "",
        f"- Names replaced with `{NAME_TOKEN}`: **{total['name']}**",
        f"- E-mail addresses replaced with `{EMAIL_TOKEN}`: **{total['email']}**",
        f"- Phone numbers replaced with `{PHONE_TOKEN}`: **{total['phone']}**",
        f"- Files changed: **{len(per_file)}**",
        "",
        "| file | names | e-mails | phones |",
        "|---|---|---|---|",
    ]
    for p, c in per_file.items():
        lines.append(f"| `{p.relative_to(ROOT)}` | {c['name']} | {c['email']} | {c['phone']} |")
    lines += ["", "Limits: names are found only from the admin name fields; a person named only inside",
              "free text or in data/interim/text (PDF/DOCX extractions) is not caught. Review before sharing."]
    if total or not REPORT.exists():
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"names {total['name']}, emails {total['email']}, phones {total['phone']}, "
          f"files {len(per_file)}{' (dry run)' if dry else ''}")
    return {"names": names, "total": total, "files": len(per_file)}


if __name__ == "__main__":
    main(sys.argv[1:])
