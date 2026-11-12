"""Parse downloaded published AIAs (data/raw/<dataset-id>/) into data/interim/aia/<id>.json.

Inputs are untrusted data: only read (json, zip/xml) or converted with the system `pdftotext`
binary. Nothing from them is executed. Run: python3 -I pipeline/parse_aia.py

Output per dataset:
  id, department, system_name, title, date, language, answers_source,
  answers            {question_id: value}  (ids that exist in vendor/aia-eia-js/src/survey-enfr.json)
  answers_unmapped   {key: value}          (keys in the published JSON with no survey id)
  free_text_answers  {question_id_or_key: text}   (written inside the AIA itself)
  free_text_fr       {key: text}           (translationsOnResult, when present)
  ckan_notes         dataset description from open.canada.ca
  supporting_docs    [{file, chars}]       (non-AIA PDFs/DOCX: GBA+, peer review, model docs)
  supporting_text    text of those documents
  aia_pdf_text_files [files]               (the AIA rendered as PDF; contains the answers, so it is
                                            NOT model input; used only for score/level)
  description_text   free_text_answers + ckan_notes + supporting_text (spec field)
  raw_score, impact_level, score_source
  primary_json, alternate_jsons
"""
from pathlib import Path
import glob, json, os, re, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "interim", "aia")
TXT = os.path.join(ROOT, "data", "interim", "text")
SURVEY = os.path.join(ROOT, "vendor", "aia-eia-js", "src", "survey-enfr.json")
if not os.path.exists(SURVEY):  # no vendored clone: v1.0.1 is byte-identical (commit b6257338)
    SURVEY = os.path.join(ROOT, "catalog", "versions", "v1.0.1", "survey-enfr.json")

CODE_RE = re.compile(r"^item\d+(-\d+)?$")
# Identity/admin fields: free text, but they describe the respondent, not the system.
ADMIN_FIELDS = {"projectAIAnumber", "projectDetailsRespondent", "projectDetailsJob", "ADMresponsible",
                "projectDetailsBranch", "projectDetailsID", "ServiceID", "consultedTeams",
                "projectDetailsDepartment-NS"}


def load_survey(path=SURVEY):
    """Return {question_name: question_type} for every non-html element in the survey."""
    d = json.load(open(path, encoding="utf-8-sig"))
    out = {}

    def walk(els):
        for el in els:
            if el.get("elements"):
                walk(el["elements"])
            elif el.get("name") and el.get("type") != "html":
                out[el["name"]] = el.get("type")
    for pg in d["pages"]:
        walk(pg.get("elements", []))
    return out


def is_code(v):
    if isinstance(v, list):
        return all(isinstance(x, str) and CODE_RE.match(x) for x in v)
    return isinstance(v, str) and bool(CODE_RE.match(v))


def is_free_text(v):
    return isinstance(v, str) and not CODE_RE.match(v) and len(v.strip()) > 0


def load_result_json(path):
    try:
        d = json.loads(Path(path).read_bytes().decode("utf-8-sig"))
    except Exception:
        return None
    if isinstance(d, dict) and isinstance(d.get("data"), dict):
        return d
    return None


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")) or (0,)


def looks_fr_name(fn):
    b = os.path.basename(fn).lower()
    return bool(re.search(r"(^|[_\-.])(fr|fra|fre|french|francais)([_\-.]|$)", b)) or "french" in b


def doc_lang(doc):
    return detect_lang(" ".join(v for k, v in doc.get("data", {}).items() if is_free_text(v) and k not in ADMIN_FIELDS))


def pick_primary(cands):
    """cands: list of (path, doc). Prefer English free text, non-French filename, newest tool version, name."""
    return max(cands, key=lambda c: (doc_lang(c[1]) == "en", not looks_fr_name(c[0]),
                                     version_tuple(c[1].get("version")), os.path.basename(c[0])))


FR_WORDS = set("le la les des du et est une pour dans que qui sur par au aux ce cette sont avec".split())
EN_WORDS = set("the and is of to in for that this will be are with by on as an".split())


def detect_lang(text):
    w = re.findall(r"[a-zàâçéèêëîïôûùüÿœ]+", text.lower())
    fr = sum(x in FR_WORDS for x in w)
    en = sum(x in EN_WORDS for x in w)
    if fr + en < 5:
        return "unknown"
    return "fr" if fr > en else "en"


SCORE_PATTERNS = [
    ("raw_score", r"Raw (?:Impact )?Score\s*:?\s*(\d+)"),
    ("current_score", r"Current Score\s*:?\s*(\d+)"),
    ("mitigation_score", r"Mitigation Score\s*:?\s*(\d+)"),
    ("raw_score", r"Score d.incidence brut\s*:?\s*(\d+)"),
    ("impact_level", r"Impact Level\s*:\s*([IV]+|\d)\b"),
    ("impact_level", r"Niveau d.incidence\s*:\s*([IV]+|\d)\b"),
]
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


def parse_scores(text):
    out = {}
    for key, pat in SCORE_PATTERNS:
        if key in out:
            continue
        m = re.search(pat, text)
        if m:
            v = m.group(1)
            out[key] = ROMAN.get(v, None) if v in ROMAN else int(v)
    return out


def is_aia_render(text):
    return bool(re.search(r"Raw Impact Score|Impact Level\s*:|Niveau d.incidence\s*:|Score d.incidence brut", text))


def pdf_text(path, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    out = os.path.join(cache_dir, os.path.basename(path) + ".txt")
    if not os.path.exists(out):
        r = subprocess.run(["pdftotext", "-q", "-layout", path, out], capture_output=True, timeout=120)
        if r.returncode != 0 or not os.path.exists(out):
            return ""
    return open(out, encoding="utf-8", errors="replace").read()


def docx_text(path):
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception:
        return ""
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def split_answers(data, survey):
    answers, unmapped = {}, {}
    for k, v in data.items():
        (answers if k in survey else unmapped)[k] = v
    return answers, unmapped


def parse_dataset(d, survey):
    pkg = json.load(open(os.path.join(d, "package.json"), encoding="utf-8"))
    did = pkg["id"]
    org = pkg.get("organization") or {}
    cands = []
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        if os.path.basename(f) == "package.json":
            continue
        doc = load_result_json(f)
        if doc is not None:
            cands.append((f, doc))
    rec = {"id": did, "department": (org.get("title") or org.get("name") or "").split("|")[0].strip(),
           "department_code": org.get("name", ""), "title": pkg.get("title", "").strip(),
           "date": (pkg.get("date_published") or pkg.get("metadata_created") or "")[:10]}
    answers, unmapped, free, free_fr, primary, alts, tool_version = {}, {}, {}, {}, None, [], None
    if cands:
        p = pick_primary(cands)
        primary = os.path.relpath(p[0], ROOT)
        alts = [os.path.relpath(c[0], ROOT) for c in cands if c[0] != p[0]]
        tool_version = p[1].get("version")
        answers, unmapped = split_answers(p[1]["data"], survey)
        for k, v in p[1]["data"].items():
            if is_free_text(v) and k not in ADMIN_FIELDS:
                free[k] = v.strip()
        tr = p[1].get("translationsOnResult") or {}
        if isinstance(tr, dict):
            free_fr = {k: v.strip() for k, v in tr.items() if is_free_text(v) and k not in ADMIN_FIELDS}
    rec["system_name"] = (answers.get("projectDetailsTitle") or unmapped.get("projectDetailsTitle") or rec["title"]).strip()
    # documents
    tcache = os.path.join(TXT, did)
    aia_pdfs, supp, supp_texts, scores, score_src = [], [], [], {}, None
    for f in sorted(glob.glob(os.path.join(d, "*"))):
        low = f.lower()
        if low.endswith(".pdf"):
            t = pdf_text(f, tcache)
        elif low.endswith(".docx"):
            t = docx_text(f)
        else:
            continue
        rel = os.path.relpath(f, ROOT)
        if is_aia_render(t):
            aia_pdfs.append(rel)
            s = parse_scores(t)
            # prefer an English render for the score (FR renders often omit the numbers)
            if s and (not scores or ("raw_score" in s and "raw_score" not in scores)):
                scores, score_src = s, rel
        elif t.strip():
            supp.append({"file": rel, "chars": len(t)})
            supp_texts.append(t)
    notes = (pkg.get("notes") or "").strip()
    en_text = "\n\n".join(free.values())
    rec.update({
        "language": detect_lang(en_text) if en_text else "none",
        "answers_source": "json" if cands else ("pdf_only" if aia_pdfs else "none"),
        "tool_version": tool_version,
        "answers": answers, "answers_unmapped": unmapped,
        "free_text_answers": free, "free_text_fr": free_fr,
        "ckan_notes": notes,
        "supporting_docs": supp, "supporting_text": "\n\n".join(supp_texts),
        "aia_pdf_text_files": aia_pdfs,
        "description_text": "\n\n".join(x for x in [en_text, notes, "\n\n".join(supp_texts)] if x),
        "raw_score": scores.get("raw_score"), "impact_level": scores.get("impact_level"),
        "current_score": scores.get("current_score"), "mitigation_score": scores.get("mitigation_score"),
        "score_source": score_src,
        "primary_json": primary, "alternate_jsons": alts,
    })
    return rec


def main():
    survey = load_survey()
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for d in sorted(glob.glob(os.path.join(RAW, "*"))):
        if not os.path.isfile(os.path.join(d, "package.json")):
            continue
        rec = parse_dataset(d, survey)
        with open(os.path.join(OUT, rec["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        n += 1
        print(rec["id"][:8], rec["answers_source"], len(rec["answers"]), len(rec["answers_unmapped"]),
              rec["raw_score"], rec["impact_level"], rec["language"])
    print("parsed", n)


if __name__ == "__main__":
    main()
