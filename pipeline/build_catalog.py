"""Build catalog/requirements.jsonl and catalog/README.md from the AIA survey.

Source: vendor/aia-eia-js/src/survey-enfr.json (canada-ca/aia-eia-js, MIT).
One row per answerable question (every SurveyJS element that is not a panel
or an html block). Scoring fields follow store.ts via pipeline/aia_score.py.
The doc-answerability labels are the builder's judgement (see JUDGE below);
everything else is read from the survey file. Run:

    python3 pipeline/build_catalog.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aia_score as A  # noqa: E402

ROOT = A.ROOT
OUT_JSONL = ROOT / "catalog" / "requirements.jsonl"
OUT_README = ROOT / "catalog" / "README.md"

SCORE_TYPE_NAME = {A.NOT_SCORED: "not_scored", A.RAW: "risk", A.MITIGATION: "mitigation"}

# --------------------------------------------------------------------------
# Doc-answerability judgement (builder's call, 2026-11-05).
#   doc           answer is a fact about the system that technical / program
#                 documentation normally states (architecture, model, data,
#                 decision, automation level, published policies).
#   partly        documentation can give evidence, but the answer also needs
#                 an assessment, plan or internal fact the docs may omit.
#   internal-only depends on internal administration (names, IDs, governance
#                 intent, consultations held) rarely written in system docs.
# Keys are question names on the Design side; Implementation twins reuse the
# Design judgement (same wording, past tense). Free-text follow-ups without
# an explicit entry get DEFAULT_FOLLOWUP.
# --------------------------------------------------------------------------
D, P, I = "doc", "partly", "internal-only"
DEFAULT_FOLLOWUP = (P, "free-text justification; docs may supply facts but the wording is the department's own")

JUDGE: dict[str, tuple[str, str]] = {
    # Project details
    "projectAIAnumber": (I, "administrative AIA version number"),
    "projectDetailsRespondent": (I, "person filling the form"),
    "projectDetailsJob": (I, "respondent's job title"),
    "ADMresponsible": (P, "program owner sometimes named in program docs"),
    "projectDetailsDepartment-NS": (D, "owning department is stated on any program/system document"),
    "projectDetailsBranch": (P, "branch often but not always named"),
    "consultedTeams": (I, "who helped fill the AIA"),
    "projectDetailsTitle": (D, "system/project name is in the documentation"),
    "projectDetailsID": (I, "IT-plan identifier is internal"),
    "ServiceID": (I, "service inventory ID is internal"),
    "projectDetailsProgram": (P, "program sometimes named; DRF wording internal"),
    "projectDetailsPhase": (P, "docs show whether the system is live, but AIA phase is a filing choice"),
    "projectDetailsDescription": (D, "project description is core documentation content"),
    # Reasons for automation
    "businessDrivers1": (D, "motivations (backlog, quality, cost) are usually stated in project docs"),
    "businessDrivers3": (D, "client needs addressed are typically described"),
    "businessDrivers4": (D, "expected benefits are typically described"),
    "businessDrivers5": (P, "effectiveness rating is a self-assessment"),
    "businessDrivers7": (P, "scope-confinement measures sometimes described"),
    "businessDrivers8": (P, "trade-off analysis rarely written outside the AIA"),
    "businessDrivers6A": (D, "expected improvements are typically described"),
    "businessDrivers6B": (P, "service standards may be public, link to system not always"),
    "businessDrivers6C": (I, "current performance figures are internal"),
    "businessDrivers6D": (P, "expected performance change sometimes projected"),
    "businessDrivers9": (P, "options analysis appears in business cases, not always in system docs"),
    "businessDrivers11": (P, "consequence of not deploying is a judgement"),
    # Risk profile
    "riskProfile1": (P, "public scrutiny / litigation is context, not a system fact"),
    "riskProfile2": (P, "client population may be described; equity-group framing is a judgement"),
    "riskProfile3": (P, "exclusions sometimes stated as scope limits"),
    "riskProfile4": (P, "accessibility assessment status needs internal confirmation"),
    "riskProfile7": (P, "fraud/exploitation exposure inferable from domain, still a judgement"),
    "riskProfile8": (P, "audits/media issues may be public but linking them is a judgement"),
    "riskProfile9": (I, "TBS concept case / GC EARB plan is internal governance"),
    "riskProfile10": (I, "TBS concept case / GC EARB submission is internal governance"),
    # Project authority
    "projectAuthority1": (P, "legal authority usually cited; need for new authority is a legal call"),
    "projectAuthority2": DEFAULT_FOLLOWUP,
    # About the system
    "aboutSystem1": (D, "capabilities (image, text, risk scoring, generation, workflow) are core system facts"),
    "aboutSystem3": (D, "developer (in-house, vendor, other government) is usually stated"),
    "aboutSystem3A": (D, "name of the developing institution/vendor"),
    "aboutSystem3B": (D, "name of the developing government"),
    "aboutSystem3C": (D, "name of the third-party developer"),
    "aboutSystem4": (D, "who configured the system is usually stated with the developer"),
    "aboutSystem4A": (D, "name of configuring institution"),
    "aboutSystem4B": (D, "name of configuring government"),
    "aboutSystem4C": (D, "name of configuring third party"),
    "aboutSystem5": (D, "open source / custom / COTS is a basic architecture fact"),
    "aboutSystem5A": (D, "licence is stated for open-source components"),
    "aboutSystem5B": (D, "customisation beyond off-the-shelf is described in architecture docs"),
    "aboutSystem5C": (D, "what was customised and by whom"),
    "aboutSystem6": (P, "accountability assignment sometimes named (system owner)"),
    "aboutSystem7": (I, "continuous-improvement group is internal organisation"),
    "aboutSystem8": (P, "EN 301 549 conformance may be in accessibility statements"),
    "aboutSystem9": (P, "fallback / manual process sometimes in continuity docs"),
    "aboutSystem10A": (P, "access-control process often in security docs"),
    "aboutSystem11": (P, "environmental impact rating is a self-assessment"),
    "aboutSystem12": DEFAULT_FOLLOWUP,
    # About the algorithm
    "aboutAlgorithm1": (P, "trade-secret status sometimes stated (vendor IP)"),
    "aboutAlgorithm2": (P, "interpretability is partly technical, partly a judgement"),
    "aboutAlgorithm3": (D, "rules-based vs data-pattern (ML) is a basic model fact"),
    "aboutAlgorithm4": (D, "deterministic vs probabilistic inference is a basic model fact"),
    "aboutAlgorithm5": (D, "discriminative vs generative model type is a basic model fact"),
    "aboutAlgorithm6": (D, "model description is core technical documentation"),
    "aboutAlgorithm7": (P, "model-selection rationale sometimes documented"),
    "aboutAlgorithm8": (P, "continuous learning is a design fact, but published texts rarely say it (audit M4: 1/15 texts mention retraining)"),
    "aboutAlgorithm8A": (P, "monitoring of model changes sometimes described"),
    "aboutAlgorithm9": (D, "input features (incl. protected characteristics) are listed in model docs"),
    "aboutAlgorithm9A": DEFAULT_FOLLOWUP,
    "aboutAlgorithm11": (P, "proxy-variable evaluation is an assessment, may be reported"),
    # About the decision
    "decisionSector3": (D, "the administrative decision supported is core documentation content"),
    "decisionSector1": (D, "decision domain (health, benefits, licensing, immigration...) follows from the program"),
    "decisionSector2": (D, "other decision category description"),
    # Impact assessment
    "impact30": (D, "full vs partial automation (human in the loop) is a stated design fact"),
    "impact31": (D, "role of the system in the decision process is usually described"),
    "impact3": (D, "whether the system makes discretionary assessments is described with its role"),
    "impact3A": (D, "description of the discretionary element"),
    "impact4A": (P, "staff impact sometimes in business case"),
    "impact20": (D, "criteria and operations on client data are technical documentation"),
    "impact21": (D, "system output and how to interpret it is technical documentation"),
    "impact22": (P, "whether it replaces a human task is often but not always stated"),
    "impact22A": (D, "description of the new function"),
    "impact5": (P, "user vs developer organisation sometimes stated"),
    "impact6": (P, "reversibility rating is a self-assessment informed by recourse docs"),
    "impact7": (P, "duration rating is a self-assessment"),
    "impact9": (P, "rights/freedoms impact rating is a self-assessment"),
    "impact24": (P, "equality/dignity/privacy impact rating is a self-assessment"),
    "impact11": (P, "health impact rating is a self-assessment"),
    "impact13": (P, "economic impact rating is a self-assessment"),
    "impact15": (P, "environmental impact rating is a self-assessment"),
    "impact18": (P, "subgroup performance testing may be reported in evaluation docs"),
    "impact19I": (P, "disability performance testing may be reported in evaluation docs"),
    "impact23": (P, "most-affected groups is a judgement"),
    "impact26": (P, "share of clients covered sometimes stated as volume/coverage"),
    "impact27": (P, "impact of exclusion from the tool is a judgement"),
    "impact28": (P, "false positive/negative impact rating is a self-assessment"),
    # About the data
    "aboutDataSource1": (D, "use of personal information as input is stated in data / privacy docs"),
    "aboutDataSource9": (P, "collection-limitation verification is a privacy assessment"),
    "aboutDataSource10": (D, "personal information used in decisions about the same person is a data-flow fact"),
    "aboutDataSource11": (P, "PIB consistency check is a privacy assessment"),
    "aboutDataSource12": (P, "PIB numbers sometimes cited in privacy notices"),
    "aboutDataSource14": (D, "who the data is shared with is a documented data flow"),
    "aboutDataSource14A": (D, "other sharing recipients"),
    "aboutDataSource15": (P, "representativeness of training data needs an assessment"),
    "aboutDataSource16": (P, "known biases in training data need an assessment"),
    "aboutDataSource2": (D, "security classification (Protected A/B...) is stated in security / data docs"),
    "aboutDataSource2A": (D, "other classification"),
    "aboutDataSource17": (P, "accuracy measures for personal information sometimes described"),
    "aboutDataSource3": (D, "who controls the data is a documented data fact"),
    "aboutDataSource4": (D, "number of data sources is a documented data fact"),
    "aboutDataSource5": (P, "IoT / sensor input is an architecture fact, but published texts never state its absence (audit M4: 0/15 texts); answerable only from priors"),
    "aboutDataSource6": (D, "interfaces with other IT systems are an architecture fact"),
    "aboutDataSource7": (P, "training-data provenance rarely stated in published texts (spot-check 2026-11-05: 11/32 weak keyword hits)"),
    "aboutDataSource8": (D, "who collected the input data is a documented data fact"),
    "aboutDataSource13": (D, "description of input data, source and collection is documentation content"),
    "aboutDataSourceType1": (D, "use of unstructured data (text, images, audio) is a data fact"),
    "aboutDataSourceType2": (D, "type of unstructured data is a data fact"),
    "aboutDataSourceType3": (P, "deliberate data exclusions sometimes documented"),
    # Consultations (mitigation)
    "consultationDesign1": (I, "internal consultations held are process records"),
    "consultationDesign2": (P, "internal partners engaged are sometimes listed in published texts (audit M4: 6b429c8e, 94d9dd91 list Privacy, IT Security, Legal, Data Governance)"),
    "consultationDesign3": (I, "external consultations held are process records"),
    "consultationDesign4": (I, "which external partners were engaged"),
    "consultationDesign5": (I, "consultees per lifecycle stage"),
    "consultationDesign6": (I, "consultation of most-impacted clients"),
    "consultationDesign7": (I, "consultation of adversely impacted communities"),
    "consultationDesign8": (I, "concerns raised by consultees"),
    "consultationDesign9": (I, "how feedback was handled"),
    # Data quality (mitigation)
    "dataQualityDesign1": (P, "bias-testing process may be described in evaluation docs"),
    "dataQualityDesign2": (P, "publication status of the process is checkable only if published"),
    "dataQualityDesign3": (P, "data-quality issue log rarely in public docs"),
    "dataQualityDesign4": (P, "publication status of the process"),
    "dataQualityDesign5": (P, "GBA Plus may be mentioned in program docs"),
    "dataQualityDesign7": (P, "publication of GBA Plus findings"),
    "dataQualityDesign8": (P, "data-quality risk process sometimes in data governance docs"),
    "dataQualityDesign9": (P, "publication status of the process"),
    "dataQualityDesign10": (D, "posting on the Open Government Portal is verifiable from the docs/portal"),
    # Procedural fairness (mitigation)
    "fairnessDesign1": (P, "audit-trail content sometimes described in technical docs"),
    "fairnessDesign1A": (P, "traceability of decision points to legislation sometimes described"),
    "fairnessDesign2": (D, "logging of every recommendation/decision is a technical design fact"),
    "fairnessDesign3": (P, "audit-trail granularity sometimes described"),
    "fairnessDesign4": (P, "override logging is a design fact absent from published texts (spot-check: 0/32 mention overrides)"),
    "fairnessDesign5": (D, "model/system change log is a technical design fact"),
    "fairnessDesign7": (P, "explanation data in audit trail sometimes described"),
    "fairnessDesign10": (D, "ability to produce reasons/explanations is a stated system feature"),
    "fairnessDesign8": (P, "version-per-decision logging is absent from published texts (spot-check: 0/32 mention it)"),
    "fairnessDesign9": (P, "decision-maker in audit trail sometimes described"),
    "fairnessDesign12": (P, "user feedback mechanism sometimes described"),
    "fairnessDesign13": (P, "recourse is often published by the program, but only 4/32 AIA texts mention it (spot-check)"),
    "fairnessDesign13A": (P, "description or link of the recourse process (follows fairnessDesign13)"),
    "fairnessDesign16": (P, "change-control process sometimes in ops docs"),
    "fairnessDesign17": (P, "use of all client information is a design detail rarely stated"),
    "fairnessDesign18": (P, "bias mitigations in model testing may be reported"),
    "fairnessDesign19": (P, "relevance of inputs is a judgement on documented features"),
    "fairnessDesign20": (P, "relevance of rules is a judgement on documented rules"),
    "fairnessDesign21": (P, "client-facing protections partly published (service standards, notices)"),
    "fairnessDesign22": (I, "impartiality / ethics processes for decision-makers are internal"),
    "fairnessDesign22A": (I, "automation-bias training is internal HR practice"),
    "fairnessDesign23": (P, "retraining / rule-review cadence sometimes described"),
    "fairnessDesign24": (P, "performance monitoring sometimes described"),
    "fairnessDesign24A": (P, "update-on-monitoring process sometimes described"),
    # Privacy (mitigation)
    "privacyDesign1": (P, "PIA existence is sometimes public (PIA summaries)"),
    "privacyDesign5": (P, "PIA title/scope/date if a summary is published"),
    "privacyDesign2": (P, "security-by-design sometimes claimed in docs"),
    "privacyDesign9": (P, "privacy-by-design sometimes claimed in docs"),
    "privacyDesign3": (P, "closed-system status is rarely stated in published texts (spot-check: 2/32 mention hosting/cloud)"),
    "privacyDesign4": (P, "information-sharing agreements sometimes cited"),
    "privacyDesign7": (P, "de-identification is a data-processing fact, but published texts rarely state it (audit M4: 1/15; spot-check 1/32)"),
    "privacyDesign8": (D, "de-identification method is a data-processing fact"),
}

# Shortlist for the first test (audit H3): rebuilt from data, not by hand.
# A question is shortlisted when ALL hold:
#   1. it has closed choices and is scored by the tool, on the common path
#      (phase "both"), or a phase-forked question whose Design/Implementation
#      twins are merged into one item (a filing answers exactly one twin);
#   2. coverage: answered in >= SL_MIN_COVERAGE of the JSON AIAs, counted with
#      the version mapping (an export counts only if its own questionnaire
#      version, catalog/versions/, has the question and every choice item id it
#      offers exists in the current survey with compatible wording);
#   3. not near-constant: majority answer share <= SL_MAX_MAJORITY among the
#      answered AIAs (multi-select: the whole selected set is one answer);
#   4. answerable from documentation: labelled "doc", or labelled "partly" and
#      the topic is mentioned in >= SL_MIN_EVIDENCE leakage-free inputs
#      (data/interim/inputs, keyword patterns in EVIDENCE below).
SL_MIN_COVERAGE = 20
SL_MAX_MAJORITY = 0.85
SL_MIN_EVIDENCE = 6
AIA_DIR = ROOT / "data" / "interim" / "aia"
INPUTS_DIR = ROOT / "data" / "interim" / "inputs"
EVIDENCE: dict[str, str] = {
    "aboutDataSource1": r"personal information|renseignements personnels",
    "aboutDataSource2": r"protected [abc]\b|protégé [abc]|classified|\bsecret\b",
    "aboutDataSource6": r"interface|integrat\w+ with|(connect|link)\w* (to|with)|\bapi\b|gcms|existing system",
    "aboutDataSource7": r"train(ed|ing)? (data|set|on)|historical (data|cases|decisions)",
    "aboutDataSource8": r"(collect|obtain|receiv|provided by|supplied by)\w*.{0,60}(data|information)",
    "impact3": r"discretion|judg(e)?ment",
    "impact5": r"in-house|developed by|built by|vendor|contractor|third[- ]party|centre of (excellence|expertise)|data science",
    "riskProfile3": r"(not|never) (be )?(applied|used) (to|for)|does not apply to|(are|were|is) excluded (from|because)",
    "aboutAlgorithm1": r"trade secret|proprietary",
    "dataQualityImplementation5": r"GBA ?(\+|plus)|gender[- ]based analysis|ACS ?\+",
    "privacyImplementation1": r"privacy impact assessment|\bPIA\b|EFVP",
    "privacyImplementation4": r"(sharing|service) agreement|memorandum of understanding|\bMOU\b",
    "privacyImplementation7": r"de-?identif|anonymi[sz]|pseudonymi[sz]|dépersonnalis",
    "privacyImplementation3": r"closed system|no (internet|external) connection|cloud",
}
_SL_CACHE: dict = {}


def _norm_text(t) -> str:
    return re.sub(r"\W+", " ", loc(t, "en").lower()).strip()


def _choice_items(q: dict) -> dict[str, str]:
    return {str(c["value"]).split("-")[0]: _norm_text(c.get("text")) for c in q.get("choices", [])}


def _same_wording(a: str, b: str) -> bool:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return a == b
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.6


def version_compatible(old_q: dict, cur_q: dict) -> bool:
    """Every choice item of the old version exists in the current one with compatible wording."""
    old, cur = _choice_items(old_q), _choice_items(cur_q)
    return all(k in cur and _same_wording(cur[k], t) for k, t in old.items())


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _label(v):
    if isinstance(v, list):
        return tuple(sorted(str(x).split("-")[0] for x in v))
    return str(v).split("-")[0]


def coverage_stats(rows: list[dict]) -> dict[str, dict]:
    """Per question: version-mapped coverage, majority share and evidence count over the JSON AIAs."""
    if "stats" in _SL_CACHE:
        return _SL_CACHE["stats"]
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(AIA_DIR.glob("*.json"))]
    js = [r for r in recs if r.get("answers_source") == "json"]
    cur_survey = {q["name"]: q for q, _p, _pg in A.iter_questions(A.load_survey())}
    ver_surveys = {v: {q["name"]: q for q, _p, _pg in A.iter_questions(A.load_survey(version=v))}
                   for v in A.available_versions()}
    texts = {}
    for r in js:
        f = INPUTS_DIR / f"{r['id']}.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            texts[r["id"]] = " ".join(str(v) for v in d.get("aia_fields_a", {}).values()) + " " + \
                " ".join(str(x.get("text", "")) for x in d.get("documents", []))
    stats = {}
    for row in rows:
        if not row["choices"] or not row["scored"] or row["phase"] == "design":
            continue
        names = [row["id"]] + ([row["twin_id"]] if row["twin_id"] else [])
        vals, compatible = [], 0
        for r in js:
            data = dict(r["answers"])
            data.update(r["answers_unmapped"])
            vsurvey = ver_surveys.get(r.get("tool_version"), cur_survey)
            ok = False
            for nm in names:
                q = vsurvey.get(nm)
                if q is None or nm not in cur_survey or not version_compatible(q, cur_survey[nm]):
                    continue
                ok = True
                if not _empty(data.get(nm)):
                    vals.append(_label(data[nm]))
                    break
            compatible += ok
        c = collections.Counter(vals)
        pat = EVIDENCE.get(row["id"])
        evidence = sum(bool(re.search(pat, t, re.I)) for t in texts.values()) if pat else None
        stats[row["id"]] = {
            "answered": len(vals), "compatible": compatible, "of": len(js),
            "majority_share": round(c.most_common(1)[0][1] / len(vals), 3) if vals else None,
            "majority_answer": c.most_common(1)[0][0] if vals else None,
            "evidence": evidence, "evidence_of": len(texts),
        }
    _SL_CACHE["stats"] = stats
    return stats


def shortlist(rows: list[dict]) -> list[str]:
    stats = coverage_stats(rows)
    out = []
    for row in rows:
        st = stats.get(row["id"])
        if st is None or st["answered"] < SL_MIN_COVERAGE or st["majority_share"] > SL_MAX_MAJORITY:
            continue
        if row["phase"] == "implementation" and not row["twin_id"]:
            continue
        lab = row["doc_answerability"]
        if lab == D or (lab == P and (st["evidence"] or 0) >= SL_MIN_EVIDENCE):
            out.append(row["id"])
    return out


def strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def loc(value, lang: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return strip_html(value)
    key = "default" if lang == "en" else lang
    return strip_html(value.get(key) or value.get("default") or "")


def phase_of(page: dict) -> str:
    vif = page.get("visibleIf", "")
    if '"item1"' in vif and "projectDetailsPhase" in vif:
        return "design"
    if '"item2"' in vif and "projectDetailsPhase" in vif:
        return "implementation"
    return "both"


def twin_name(name: str) -> str | None:
    if "Implementation" in name:
        return name.replace("Implementation", "Design")
    if "Design" in name:
        return name.replace("Design", "Implementation")
    return None


def judge(name: str, visible_if: str | None = None) -> tuple[str, str]:
    if name in JUDGE:
        return JUDGE[name]
    if "Implementation" in name:
        design = name.replace("Implementation", "Design")
        if design in JUDGE:
            return JUDGE[design]
    # Follow-up to an internal-only question stays internal-only.
    if visible_if:
        m = re.search(r"\{([^}]+)\}", visible_if)
        if m and m.group(1) != name and judge(m.group(1))[0] == I:
            return I, f"follow-up to internal-only question {m.group(1)}"
    return DEFAULT_FOLLOWUP


def build_rows(survey: dict) -> list[dict]:
    names = {q["name"] for q, _p, _pg in A.iter_questions(survey)}
    rows = []
    for order, (q, parent, page) in enumerate(A.iter_questions(survey)):
        name = q["name"]
        stype = A.score_type(q, parent)
        scored = A.has_score(q, parent)
        label, reason = judge(name, q.get("visibleIf"))
        twin = twin_name(name)
        choices = [
            {
                "value": c["value"],
                "weight": A.choice_weight(c),
                "text_en": loc(c.get("text"), "en"),
                "text_fr": loc(c.get("text"), "fr"),
            }
            for c in q.get("choices", [])
        ]
        rows.append({
            "id": name,
            "order": order,
            "page": page["name"],
            "page_title_en": loc(page.get("title"), "en"),
            "page_title_fr": loc(page.get("title"), "fr"),
            "panel": parent["name"] if parent is not page else None,
            "phase": phase_of(page),
            "twin_id": twin if twin in names else None,
            "question_type": q["type"],
            "kind": SCORE_TYPE_NAME[stype],
            "scored": scored,
            "multi_select": q["type"] == "checkbox",
            "text_en": loc(q.get("title"), "en"),
            "text_fr": loc(q.get("title"), "fr"),
            "help_en": loc(q.get("help") or q.get("description"), "en"),
            "help_fr": loc(q.get("help") or q.get("description"), "fr"),
            "choices": choices,
            "max_score": A.max_score_for_question(q) if scored else 0,
            "visible_if": q.get("visibleIf"),
            "page_visible_if": page.get("visibleIf"),
            "doc_answerability": label,
            "doc_reason": reason,
            "doc_reason_source": (
                "explicit" if (name in JUDGE or name.replace("Implementation", "Design") in JUDGE)
                else "inherited-followup" if reason.startswith("follow-up to") else "default-followup"
            ),
            "shortlist": False,
        })
    chosen = set(shortlist(rows))
    for r in rows:
        r["shortlist"] = r["id"] in chosen
    return rows


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def write_readme(rows: list[dict], survey: dict) -> str:
    totals = A.score(survey, {})
    by_page = collections.OrderedDict()
    for r in rows:
        by_page.setdefault(r["page"], []).append(r)

    n = len(rows)
    n_scored = sum(r["scored"] for r in rows)
    n_choice = sum(bool(r["choices"]) for r in rows)
    n_free = n - n_choice
    kind_c = collections.Counter(r["kind"] for r in rows)
    scored_kind = collections.Counter(r["kind"] for r in rows if r["scored"])
    doc_c = collections.Counter(r["doc_answerability"] for r in rows)
    doc_scored = collections.Counter(r["doc_answerability"] for r in rows if r["scored"])
    phase_c = collections.Counter(r["phase"] for r in rows)
    cond = sum(1 for r in rows if r["visible_if"])
    defaulted = sum(1 for r in rows if r["doc_reason_source"] == "default-followup")
    inherited = sum(1 for r in rows if r["doc_reason_source"] == "inherited-followup")
    # One filing: Design OR Implementation pages, never both.
    one_filing = [r for r in rows if r["phase"] in ("both", "design")]
    one_filing_scored = [r for r in one_filing if r["scored"]]

    page_rows = []
    for page, rs in by_page.items():
        c = collections.Counter(r["doc_answerability"] for r in rs)
        page_rows.append([
            f"`{page}`", rs[0]["page_title_en"] or "-", rs[0]["phase"], len(rs),
            sum(r["scored"] for r in rs), c.get(D, 0), c.get(P, 0), c.get(I, 0),
            sum(r["max_score"] for r in rs),
        ])

    sl = [r for r in rows if r["shortlist"]]
    stats = coverage_stats(rows)

    def ev(st):
        return "-" if st["evidence"] is None else f"{st['evidence']}/{st['evidence_of']}"

    sl_rows = [[
        f"`{r['id']}`" + (f" (+`{r['twin_id']}`)" if r["phase"] != "both" else ""), r["kind"],
        "multi" if r["multi_select"] else "single", len(r["choices"]), r["max_score"],
        f"{stats[r['id']]['answered']}/{stats[r['id']]['of']}", f"{stats[r['id']]['majority_share']:.2f}",
        r["doc_answerability"], ev(stats[r["id"]]),
        r["text_en"][:90] + ("…" if len(r["text_en"]) > 90 else ""),
    ] for r in sl]
    sl_doc = sum(r["doc_answerability"] == D for r in sl)
    short_note = (f" (the result is {len(sl)}, below the 12 aimed for: no other question passes all four "
                  "filters, and lowering a threshold would admit near-constant or undocumented questions)"
                  if len(sl) < 12 else "")
    by_id = {r["id"]: r for r in rows}
    near = [(i, st) for i, st in stats.items() if i not in {r["id"] for r in sl}
            and st["answered"] >= SL_MIN_COVERAGE and by_id[i]["doc_answerability"] in (D, P)
            and (by_id[i]["doc_answerability"] == D or (st["evidence"] or 0) >= SL_MIN_EVIDENCE)]
    near_rows = [[f"`{i}`", f"{st['answered']}/{st['of']}", f"{st['majority_share']:.2f}",
                  by_id[i]["doc_answerability"], ev(st)] for i, st in sorted(near)]
    old_sl = ["impact30", "impact3", "decisionSector1", "aboutAlgorithm3", "aboutAlgorithm4",
              "aboutAlgorithm5", "aboutAlgorithm8", "aboutAlgorithm9", "aboutSystem3", "aboutSystem5",
              "aboutDataSource1", "aboutDataSource2", "aboutDataSource4", "aboutDataSource5", "aboutDataSource6"]
    old_rows = [[f"`{i}`", f"{stats[i]['answered']}/{stats[i]['of']}",
                 f"{stats[i]['majority_share']:.2f}" if stats[i]["majority_share"] is not None else "-",
                 "kept" if by_id[i]["shortlist"] else "dropped"] for i in old_sl]

    text = f"""# AIA requirement catalogue

Generated by `pipeline/build_catalog.py` from `vendor/aia-eia-js/src/survey-enfr.json`
(canada-ca/aia-eia-js, commit b6257338, 2026-10-28). Do not edit by hand: every number
below is printed by the script. Scoring rule: [`scoring.md`](scoring.md).

## Files
- `requirements.jsonl`: one row per answerable question ({n} rows).
- `scoring.md`: exact scoring rule with `store.ts` line references; reproduced by `pipeline/aia_score.py`.

Row fields: `id` (SurveyJS name), `order`, `page`, `page_title_en/fr`, `panel`, `phase`
(both / design / implementation), `twin_id` (Design↔Implementation counterpart), `question_type`,
`kind` (risk / mitigation / not_scored, from the panel suffix `-RS` / `-MS` / `-NS`), `scored`
(counts toward the score in the tool), `multi_select`, `text_en/fr`, `help_en/fr`,
`choices` [{{value, weight, text_en, text_fr}}], `max_score`, `visible_if`, `page_visible_if`,
`doc_answerability` (doc / partly / internal-only), `doc_reason`, `doc_reason_source`
(explicit judgement, inherited from an internal-only parent, or the default rule for free-text follow-ups), `shortlist`.

## Counts
- Answerable questions: **{n}** ({n_choice} with choices, {n_free} free-text).
- Scored by the tool: **{n_scored}** (risk {scored_kind.get('risk', 0)}, mitigation {scored_kind.get('mitigation', 0)}).
- By kind (all rows): risk {kind_c.get('risk', 0)}, mitigation {kind_c.get('mitigation', 0)}, not_scored {kind_c.get('not_scored', 0)}.
- By phase: both {phase_c.get('both', 0)}, design-only {phase_c.get('design', 0)}, implementation-only {phase_c.get('implementation', 0)}.
  A single filing sees the common pages plus one phase: **{len(one_filing)}** questions, {len(one_filing_scored)} scored.
- Conditional (own `visibleIf`): {cond}.
- Doc-answerability, all rows: doc {doc_c.get(D, 0)}, partly {doc_c.get(P, 0)}, internal-only {doc_c.get(I, 0)}
  ({defaulted} free-text follow-ups use the default rule "partly", {inherited} inherit internal-only from their parent question).
- Doc-answerability, scored rows: doc {doc_scored.get(D, 0)}, partly {doc_scored.get(P, 0)}, internal-only {doc_scored.get(I, 0)}.
- Score maxima (tool logic, all questions incl. hidden ones): raw impact **{totals['max_raw_impact_score']}**,
  mitigation **{totals['max_mitigation_score']}** (both phases; the tool halves it, so the 15 % deduction needs
  mitigation ≥ {totals['mitigation_threshold']:g}).

### By section (page)
{md_table(['page', 'title', 'phase', 'questions', 'scored', 'doc', 'partly', 'internal-only', 'max score'], page_rows)}

## Shortlist for the first test ({len(sl)} questions, {sl_doc} labelled doc)
Rebuilt from data (audit H3, 2026-11-05). A question is kept when all hold{short_note}:
1. closed choices, scored by the tool, on the common path (phase "both"), or a phase-forked
   question with its Design/Implementation twin merged into one item;
2. answered in **≥ {SL_MIN_COVERAGE} of the 32 JSON AIAs**, counted with the version mapping: an export
   counts only if its own questionnaire version (`catalog/versions/`) has the question and every
   choice item id it offers exists in the current survey with compatible wording (≥ 60 % token
   overlap). Weights may differ between versions; labels are compared by item id;
3. majority answer share **≤ {SL_MAX_MAJORITY}** among answered AIAs (multi-select: the selected set);
4. answerable from documentation: labelled `doc`, or `partly` with the topic mentioned in
   ≥ {SL_MIN_EVIDENCE} leakage-free inputs (`EVIDENCE` keyword patterns over `data/interim/inputs`).

"evidence" = inputs whose text matches the topic pattern (a keyword hit, not proof the answer is
stated; `-` = no pattern). `businessDrivers1` and `aboutSystem1` weigh 0 in the tool: they test
answer extraction only and do not move the score. `aboutDataSource2` is coarser in v0.9.x/v0.10.0
exports (Protected B/C and Secret/Top secret were one choice each), so it is scored on item ids.
{md_table(['id', 'kind', 'select', 'choices', 'max', 'coverage', 'majority', 'label', 'evidence', 'question (EN)'], sl_rows)}

Excluded only because majority share > {SL_MAX_MAJORITY} (covered and answerable; B-maj would be near-perfect):
{md_table(['id', 'coverage', 'majority', 'label', 'evidence'], near_rows)}

Previous hand-picked shortlist (15) against the data:
{md_table(['id', 'coverage', 'majority', 'now'], old_rows)}

## Label changes (audit M4 + spot-check, 2026-11-05)
Audit M4 flagged three labels as wrong for published text; a further 10 explicit labels were
spot-checked by keyword search over the 32 JSON AIAs' leakage-free inputs against the
department's own answers (`doc` kept only if the topic is commonly stated in published text).
| id (twin follows) | was | now | evidence |
|---|---|---|---|
| `aboutDataSource5` | doc | partly | audit: 0/15 texts mention sensors/IoT, all answered |
| `aboutAlgorithm8` | doc | partly | audit: 1/15 texts mention retraining |
| `consultationDesign2` / `consultationImplementation2` | internal-only | partly | audit: 6b429c8e, 94d9dd91 list the internal consultees |
| `aboutDataSource7` | doc | partly | 11/32 weak hits on training data |
| `privacyDesign3` | doc | partly | 2/32 mention hosting / cloud |
| `fairnessDesign4` | doc | partly | 0/32 mention overrides |
| `fairnessDesign8` | doc | partly | 0/32 mention version-per-decision logging |
| `fairnessDesign13` (+13A) | doc | partly | 4/32 mention recourse / reconsideration |
| `privacyDesign7` | doc | partly | 1/32 mention de-identification (audit M4: 1/15) |

Spot-checked and kept: `aboutDataSource8` doc (21/32 describe who supplies the data),
`aboutDataSource6` doc (15/32 describe interfaces), `impact3` doc (7/32 explicit; usually
inferable from the decision description, weakest of the kept), `riskProfile3` partly,
`aboutAlgorithm1` partly (0/32 mention trade secrets or proprietary models; borderline internal-only).
Note: 1257e5c1 says children under 16 were excluded but answered riskProfile3 "No"; department
answers are not error-free ground truth.

## Caveats
- Doc-answerability is the builder's judgement of what system documentation would state
  (closer to "ideal documentation" than to what is published; audit M4). Only the rows in
  "Label changes" were checked against published text. The human "answerable" labels of the
  eval plan should replace it.
- `businessDrivers1`, `aboutSystem1` and the consultation checklists are "scored" in the tool's
  sense but all their choices weigh 0 (values without a numeric suffix).
"""
    OUT_README.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    survey = A.load_survey()
    rows = build_rows(survey)
    unknown = [k for k in JUDGE if k not in {r["id"] for r in rows}]
    assert not unknown, f"judged ids not in survey: {unknown}"
    for r in rows:
        if r["shortlist"]:
            assert r["scored"] and r["doc_answerability"] in (D, P), r["id"]
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSONL, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_readme(rows, survey)
    print(f"wrote {len(rows)} rows to {OUT_JSONL.relative_to(ROOT)} and {OUT_README.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
