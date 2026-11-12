"""Build the leakage-free model input for each AIA: data/interim/inputs/<id>.json.

Rule (see docs/inputs.md). A free-text field of the AIA export is class (a)
"system documentation" only if ALL hold:
  1. it is not on a mitigation page (consultation, dataQuality, fairness, privacy);
  2. its visibleIf (or its panel's) does not reference any select question
     (so it is not a follow-up that exists only because of a chosen option);
  3. its title does not ask to justify a selection ("as per selected option",
     "as selected", "why you have chosen", "please describe"/"specify" alone);
  4. it is not in MANUAL_B (admin fields, or content that states an answer outright).
MANUAL_A lists the one override the other way (impact4, see below).
Everything else is class (b) and is dropped. Every kept text, including the separate
documents, is normalised (PDF line wraps joined) and split into sentences; a sentence that
names an impact level or score, mentions a peer review, or says a notice / human-in-the-loop
was required, is removed. Peer-review documents are excluded whole (their presence reveals level
II+) and listed in `data/interim/inputs_excluded.json`, a sidecar that is not model input. PII redaction
(redact_pii.py) runs automatically at the end; re-running the whole script is idempotent.

    python3 -I pipeline/build_inputs.py            # build + PII redaction
    python3 -I pipeline/build_inputs.py --no-pii   # build only (tests/debug)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aia_score as A  # noqa: E402

ROOT = A.ROOT
OUT_DIR = ROOT / "data" / "interim" / "inputs"
# Sidecar for excluded (level-revealing) documents: outside OUT_DIR, never read as model input
# (audit round 3, L-1). Keyed by AIA id, sorted, rewritten whole on every build (idempotent).
EXCLUDED_PATH = ROOT / "data" / "interim" / "inputs_excluded.json"
MITIGATION_PAGES = ("consultation", "dataQuality", "fairness", "privacy")
JUSTIFY = re.compile(r"as per selected|as selected|why you have chosen|^\s*(please )?(describe|specify)\.?\s*$|"
                     r"^\s*if (yes|no)\b|why .* not\b", re.I)
MANUAL_B = {
    "aboutDataSource12": "PIB bank numbers: states that personal information is used (aboutDataSource1).",
    "projectDetailsRespondent": "admin, not about the system",
    "projectDetailsJob": "admin", "projectDetailsBranch": "admin", "projectDetailsID": "admin",
    "ADMresponsible": "admin (person's name)", "ServiceID": "admin", "projectAIAnumber": "admin (AIA version)",
    "consultedTeams": "about completing the AIA, not the system",
}
MANUAL_A = {
    "impact4": "old-version location of 'describe the decision(s) that will be automated'; the tool itself moves it "
               "to decisionSector3 (class a) on load (ActionButtonBar.vue)",
}
# A "supporting document" that is really the AIA itself (e.g. the French AIA PDF filed as a
# separate resource) carries the answers and points: drop it whole.
AIA_RENDERING = re.compile(r"Raw Impact Score|Score d['’]incidence brut|Points\s*:\s*\+|Section 1\s*:\s*(Impact Level|Niveau d['’]impact)", re.I)
# A supporting document whose mere PRESENCE reveals the impact level (audit round 2, M-A): the
# Directive on Automated Decision-Making requires a peer review from level II up, so a peer-review
# report or summary exists only in level II+ AIAs (10/10 in this corpus, 0 in level I). Such files
# are recorded in the sidecar EXCLUDED_PATH (metadata only) and never enter the model input.
LEVEL_REVEALING_DOC = re.compile(
    r"peer[\s_-]*review|examen[\s_-]*par[\s_-]*les[\s_-]*pai|(?:[ée]|e)valuation[\s_-]*(?:et[\s_-]*r[ée]ponse[\s_-]*)?"
    r"par[\s_-]*les[\s_-]*pairs|evaluation-et-reponse-par-les-pairs", re.I)
LEVEL_DOC_REASON = "peer review: required by the Directive only from impact level II, so its presence reveals the level"

# Sentence-level redaction over normalised text (wrapped lines joined first). A sentence is dropped
# when it names an impact level or score, or says a requirement (peer review, notice, human in the
# loop) applied/was required, which in an AIA context is a consequence of the level.
_Q = r"(?:faible|mod[ée]r[ée]e?|[ée]lev[ée]e?|tr[eè]s\s+[ée]lev[ée]e?)"
LEVEL_TERMS = re.compile(
    r"\bimpact[\s-]+levels?\b|\blevels?\s+of\s+impact\b|\blevels?\s+(?:I{1,3}|IV|[1-4])\b"
    r"|\b(?:low|moderate|medium|high|very\s+high|little(?:\s+to\s+no)?)[\s-]+(?:impact[\s-]+)?level\b"
    r"|\b[1-4]\s*(?:out\s+of|out|sur|/)\s*4\b"
    r"|\bniveaux?\s+d\W{0,2}\s*(?:incidence|impact)s?\b|\bniveaux?\s+(?:I{1,3}|IV|[1-4])\b"
    r"|\bniveaux?\s+(?:d\W{0,2}\s*(?:incidence|impact)\s+)?" + _Q + r"\b|\(\s*" + _Q + r"\s*\)"
    r"|\bincidences?\s+(?:de\s+)?(?:[1-4]\b|" + _Q + r"\b)"
    r"|raw\s+impact\s+score|impact\s+score|current\s+score|mitigation\s+score|\bscores?\b|\bscored\b"
    r"|\bpointage\b|\bcote\s+(?:d\W{0,2}\s*(?:incidence|att[ée]nuation)|actuelle)", re.I)
REQ_OBJECT = re.compile(r"peer[\s-]*review|examen\s+par\s+les\s+pairs|par\s+les\s+pairs|\bnotice\b|"
                        r"human[\s-]*in[\s-]*the[\s-]*loop|humain\s+dans\s+la\s+boucle|intervention\s+humaine|"
                        r"avis\s+(?:pr[ée]alable|public)", re.I)
REQ_WORD = re.compile(r"\brequired?\b|\brequires\b|\brequirements?\b|\bmandatory\b|\bobligatory\b|\bhad\s+to\b|"
                      r"\bmust\b|\bobligatoire|\brequise?s?\b|\bexig|\ba\s+d[ûu]\b|\bdoi(?:t|vent)\b|\bdevai(?:t|ent)\b|"
                      r"\bn[ée]cessaire", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def normalise(text: str) -> list[list[str]]:
    """Paragraphs (split on blank lines) of sentences, with PDF line wraps joined."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    paras = []
    for para in re.split(r"\n[ \t]*\n", t):
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        joined = lines[0]
        for ln in lines[1:]:
            joined += ln if joined.endswith("-") else " " + ln
        joined = re.sub(r"[ \t]+", " ", joined)
        paras.append([x for x in SENT_SPLIT.split(joined) if x.strip()])
    return paras


# Any sentence that says a peer review exists or happened (dataset descriptions list "the Peer
# Review Summary") leaks the level the same way the document itself does.
PEER_REVIEW = re.compile(r"peer[\s-]*review|examen\s+par\s+les\s+pairs|[ée]valuation\s+par\s+les\s+pairs|"
                         r"revue\s+par\s+les\s+pairs|examen\s+des\s+pairs", re.I)


def leaks_level(sentence: str) -> bool:
    return bool(LEVEL_TERMS.search(sentence) or PEER_REVIEW.search(sentence) or (REQ_OBJECT.search(sentence) and REQ_WORD.search(sentence)))


def _title(q):
    t = q.get("title")
    return (t.get("default") if isinstance(t, dict) else t) or ""


def field_catalogue() -> dict:
    """name -> (class, reason, title, page) over the union of all versions' free-text fields."""
    cat = {}
    for v in A.available_versions():
        s = A.load_survey(version=v)
        select_names = {q["name"] for q, _p, _g in A.iter_questions(s) if q.get("type") in A.SELECT_TYPES}
        for q, parent, page in A.iter_questions(s):
            if q.get("type") not in ("text", "comment") or q["name"] in cat:
                continue
            name, title, pname = q["name"], _title(q), page.get("name", "")
            vis = " ".join(x.get("visibleIf") or "" for x in (q, parent, page) if x is not page or True)
            refs = set(re.findall(r"\{([^}]+)\}", vis))
            if name in MANUAL_A:
                c, why = "a", MANUAL_A[name]
            elif name in MANUAL_B:
                c, why = "b", MANUAL_B[name]
            elif pname.startswith(MITIGATION_PAGES):
                c, why = "b", "mitigation page: documents a mitigation answer"
            elif refs & select_names:
                c, why = "b", "follow-up shown only for a selected option: " + ",".join(sorted(refs & select_names))
            elif JUSTIFY.search(title):
                c, why = "b", "asks to justify the selected option"
            else:
                c, why = "a", "describes the system, its data, model, decision or business purpose"
            cat[name] = (c, why, title.strip().replace("\n", " ")[:140], pname, v)
    return cat


def redact(text: str) -> str:
    out = []
    for para in normalise(text):
        kept = [x for x in para if not leaks_level(x)]
        if kept:
            out.append(" ".join(kept))
    return "\n\n".join(out).strip()


def is_level_revealing(file: str, text: str) -> bool:
    """Peer-review documents, by file name or by a title in the first lines of the text."""
    return bool(LEVEL_REVEALING_DOC.search(Path(file).name) or LEVEL_REVEALING_DOC.search((text or "")[:300]))


def main(redact_pii: bool = True) -> dict:
    cat = field_catalogue()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stats = {"n": 0, "ge2000": 0, "lengths": {}, "unknown_fields": set(), "dropped_aia_renderings": [], "skipped_no_text": [],
             "excluded_level_revealing": []}
    excluded_all = {}
    for f in sorted((ROOT / "data" / "interim" / "aia").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        kept = {}
        for k, v in (d.get("free_text_answers") or {}).items():
            c = cat.get(k, ("b", "not in any survey version"))[0]
            if k not in cat:
                stats["unknown_fields"].add(k)
            if c == "a" and str(v).strip():
                kept[k] = redact(str(v))
        docs = [{"source": "ckan_notes", "text": redact(d.get("ckan_notes") or "")}]
        excluded = []
        for sd in d.get("supporting_docs", []):
            tpath = ROOT / (sd["file"].replace("data/raw", "data/interim/text", 1) + ".txt")
            if not tpath.exists():  # DOCX/HTML have no extracted text file
                stats["skipped_no_text"].append(sd["file"])
                continue
            text = tpath.read_text(encoding="utf-8", errors="replace")
            if AIA_RENDERING.search(text):
                stats["dropped_aia_renderings"].append(sd["file"])
                continue
            if is_level_revealing(sd["file"], text):
                excluded.append({"source": "supporting_doc", "file": sd["file"], "reason": LEVEL_DOC_REASON,
                                 "chars_raw": len(text)})
                stats["excluded_level_revealing"].append(sd["file"])
                continue
            docs.append({"source": "supporting_doc", "file": sd["file"], "text": redact(text)})
        total = sum(len(x) for x in kept.values()) + sum(len(x["text"]) for x in docs)
        rec = {"id": d["id"], "answers_source": d.get("answers_source"), "aia_fields_a": kept,
               "documents": docs,
               "chars_aia_fields_a": sum(len(x) for x in kept.values()),
               "chars_documents": sum(len(x["text"]) for x in docs), "chars_total": total,
               "rule": "docs/inputs.md"}
        (OUT_DIR / f"{d['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        if excluded:  # NOT model input: presence alone reveals the level -> sidecar file only
            excluded_all[d["id"]] = excluded
        stats["n"] += 1
        stats["lengths"][d["id"]] = (rec["chars_aia_fields_a"], rec["chars_documents"], total, d.get("answers_source"))
    EXCLUDED_PATH.write_text(json.dumps({"note": "NOT model input (docs/inputs.md); presence reveals impact level II+",
                                         "excluded": dict(sorted(excluded_all.items()))},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
    L = stats["lengths"].values()
    stats["ge2000"] = sum(1 for x in L if x[2] >= 2000)
    stats["ge2000_json"] = sum(1 for x in L if x[2] >= 2000 and x[3] == "json")
    stats["n_json"] = sum(1 for x in L if x[3] == "json")
    stats["ge2000_fields_only_json"] = sum(1 for x in L if x[0] >= 2000 and x[3] == "json")
    stats["ge2000_docs_only"] = sum(1 for x in L if x[1] >= 2000)
    stats["unknown_fields"] = sorted(stats["unknown_fields"])
    stats["catalogue"] = cat
    if redact_pii:
        import redact_pii as R  # PII redaction always runs on the rebuilt inputs (audit round 2, L-a)
        stats["pii"] = {k: v for k, v in R.main([]).items() if k != "names"}
        stats["pii"]["total"] = dict(stats["pii"]["total"])
    return stats


if __name__ == "__main__":
    s = main(redact_pii="--no-pii" not in sys.argv)
    cat = s.pop("catalogue")
    lengths = s.pop("lengths")
    print(json.dumps(s, indent=1))
    if "--fields" in sys.argv:
        for k, (c, why, title, page, v) in sorted(cat.items(), key=lambda x: (x[1][3], x[0])):
            print(f"{c}\t{k}\t{page}\t{title[:70]}\t{why}")
