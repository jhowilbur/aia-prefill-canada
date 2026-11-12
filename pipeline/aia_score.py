"""Reproduce the scoring of the Government of Canada AIA tool (canada-ca/aia-eia-js).

Derived from canada-ca/aia-eia-js, MIT licence, (c) 2019 Government of Canada; see NOTICE.md.

Source of truth: vendor/aia-eia-js/src/store.ts (commit b6257338, 2026-10-28).
Every rule below names the store.ts line it mirrors. See catalog/scoring.md.

Usage:
    from aia_score import load_survey, score
    survey = load_survey()
    result = score(survey, {"impact30": "item1-4", "aboutAlgorithm3": ["item2-1"]})
    result["level"]  # 1..4  (impact level I..IV)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Per-version surveys exported from the tool's git history by aia_versions.py.
VERSIONS_DIR = ROOT / "catalog" / "versions"
SURVEY_PATH = ROOT / "vendor" / "aia-eia-js" / "src" / "survey-enfr.json"
if not SURVEY_PATH.exists():  # no vendored clone: v1.0.1 is byte-identical to it (commit b6257338)
    SURVEY_PATH = VERSIONS_DIR / "v1.0.1" / "survey-enfr.json"
DEFAULT_VERSION = None  # None = the vendored (current, v1.0.1) survey

SELECT_TYPES = ("radiogroup", "checkbox", "dropdown")  # store.ts:39-41
NOT_SCORED, RAW, MITIGATION = 1, 2, 3                  # store.ts:82

# Constants of calculateFinalScore, store.ts:156-161
PERCENTAGE = 0.8
DEDUCTION = 0.15
THRESHOLD1, THRESHOLD2, THRESHOLD3 = 0.25, 0.5, 0.75


_VERSION_CACHE: dict[str, dict] = {}


def available_versions() -> list[str]:
    return sorted(p.parent.name for p in VERSIONS_DIR.glob("*/survey-enfr.json"))


VERSION_ORDER = ("v0.9", "v0.9.1", "v0.10.0", "v1.0.0", "v1.0.1")


def convert_loaded_file(data: dict, to_version: str) -> dict:
    """Conversions the tool applies when an exported file is LOADED
    (src/components/ActionButtonBar.vue, loadSurvey), for a file that is
    re-opened in a newer tool version before its score is printed.

    - from v0.9.1 (commit b98fbf8, 2022-02-18, #622): aboutSystem1 "item6-1" -> "item6"
    - from v0.10.0 (commit 604a669, 2023-04-01): impact4 moved to decisionSector3
    Returns a new dict; the input is not modified.
    """
    out = dict(data)
    rank = VERSION_ORDER.index(to_version) if to_version in VERSION_ORDER else -1
    if rank >= VERSION_ORDER.index("v0.9.1"):
        a = out.get("aboutSystem1")
        if isinstance(a, list) and "item6-1" in a:
            a = list(a)
            a[a.index("item6-1")] = "item6"
            out["aboutSystem1"] = a
    if rank >= VERSION_ORDER.index("v0.10.0") and "impact4" in out:
        out["decisionSector3"] = out.pop("impact4")
    return out


def load_survey(path: Path | str = SURVEY_PATH, version: str | None = None) -> dict:
    """Load a survey. With `version` (an export's "version" string such as
    "v0.9.1"), load that questionnaire version from catalog/versions/ instead."""
    if version is not None:
        if version not in _VERSION_CACHE:
            vpath = VERSIONS_DIR / version / "survey-enfr.json"
            if not vpath.exists():
                raise ValueError(f"unknown AIA tool version {version!r}; known: {available_versions()}")
            with open(vpath, encoding="utf-8") as fh:
                _VERSION_CACHE[version] = json.load(fh)
        return _VERSION_CACHE[version]
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- traversal
def iter_questions(survey: dict):
    """Yield (question, parent, page) in SurveyJS getAllQuestions() order.

    getAllQuestions() is called without arguments at store.ts:323, so in
    survey-vue 1.7 it returns ALL questions, including those hidden by a
    visibleIf on the question or on its page (visibleOnly defaults to false).
    Panels and html blocks are containers / static content, not questions.
    """
    def walk(elements, parent, page):
        for el in elements:
            if el.get("type") == "panel":
                yield from walk(el.get("elements", []), el, page)
            elif el.get("type") == "html":
                continue
            else:
                yield el, parent, page

    for page in survey["pages"]:
        yield from walk(page.get("elements", []), page, page)


def _score_type_helper(name: str | None) -> int:  # store.ts:81-94
    if name:
        if name.endswith("-RS"):
            return RAW
        if name.endswith("-MS"):
            return MITIGATION
        if name.endswith("-NS"):
            return NOT_SCORED
    return 0


def score_type(question: dict, parent: dict) -> int:  # store.ts:96-111
    result = _score_type_helper(question.get("name"))
    if result > 0:
        return result
    result = _score_type_helper(parent.get("name"))
    return NOT_SCORED if result == 0 else result


def has_score(question: dict, parent: dict) -> bool:  # store.ts:37-47
    return question.get("type") in SELECT_TYPES and score_type(question, parent) > 1


# ------------------------------------------------------------------- values
def parse_embedded_value(val: str) -> float:  # store.ts:49-59
    idx = val.rfind("-")
    if idx == -1:
        return 0
    suffix = val[idx + 1:]
    try:
        num = float(suffix) if suffix.strip() else 0.0  # JS Number("") === 0
    except ValueError:
        return 0
    if math.isnan(num):
        return 0
    return int(num) if num.is_integer() else num


def get_value(val) -> float:  # store.ts:61-79 (+ addItemsInArray 25-35)
    if val is None:
        return 0
    if isinstance(val, list):
        total = 0
        for item in val:
            if isinstance(item, bool):
                continue
            if isinstance(item, (int, float)):
                total += item
            elif isinstance(item, str):
                total += parse_embedded_value(item)
        return total
    if isinstance(val, str):
        return parse_embedded_value(val)
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return 0
    return val


def choice_weight(choice: dict) -> float:
    return get_value(choice.get("value"))


def max_score_for_question(question: dict) -> float:  # store.ts:113-132
    qtype = question.get("type")
    weights = [choice_weight(c) for c in question.get("choices", [])]
    if qtype in ("radiogroup", "dropdown"):
        return max([0] + weights)  # max starts at 0
    if qtype == "checkbox":
        return sum(weights)
    return 0


def scored_questions(survey: dict):
    """questionNames of store.ts:321-329, with their score type."""
    return [(q, p, score_type(q, p)) for q, p, _ in iter_questions(survey) if has_score(q, p)]


def js_round(x: float) -> int:
    """JavaScript Math.round: halves round toward +infinity."""
    return math.floor(x + 0.5)


# -------------------------------------------------------------------- score
def score(survey: dict | None, data: dict, version: str | None = DEFAULT_VERSION) -> dict:
    """calculateFinalScore, store.ts:147-208.

    `version`: None (default) scores with `survey` as given (unchanged
    behaviour). A version string ("v0.9", "v0.9.1", "v0.10.0", "v1.0.0",
    "v1.0.1") scores with that questionnaire version instead; `survey` may then
    be None. The scoring code is identical in all versions, only the survey
    (scored questions, weights, maxima) differs; see catalog/versions/.

    `data` is the SurveyJS data object ({question name: value}); radiogroup and
    dropdown values are strings such as "item1-3", checkbox values are lists.
    Like the tool, values are scored as given: an answer left on a question
    that is currently hidden still counts (see scoring.md, quirk 3).
    """
    if version is not None:
        survey = load_survey(version=version)
    raw = mitigation = max_raw = max_mitigation = 0
    for q, _parent, stype in scored_questions(survey):
        name = q["name"]
        if stype == RAW:
            raw += get_value(data.get(name))
            max_raw += max_score_for_question(q)
        elif stype == MITIGATION:
            mitigation += get_value(data.get(name))
            max_mitigation += max_score_for_question(q)

    # store.ts:184-189 — maxMitigationScore halved because of the Design /
    # Implementation fork (both copies are counted in the maximum).
    deduction_applied = mitigation >= PERCENTAGE * (max_mitigation / 2)
    total = js_round((1 - DEDUCTION) * raw) if deduction_applied else raw

    # store.ts:191-205
    if total <= max_raw * THRESHOLD1:
        level = 1
    elif total <= max_raw * THRESHOLD2:
        level = 2
    elif total <= max_raw * THRESHOLD3:
        level = 3
    else:
        level = 4

    return {
        "raw_impact_score": raw,
        "mitigation_score": mitigation,
        "current_score": total,
        "level": level,
        "level_roman": ["I", "II", "III", "IV"][level - 1],
        "max_raw_impact_score": max_raw,
        "max_mitigation_score": max_mitigation,
        "mitigation_threshold": PERCENTAGE * (max_mitigation / 2),
        "deduction_applied": deduction_applied,
        "version": version,
    }


def section_score(survey: dict, data: dict, section: str) -> tuple[int, float, float]:
    """calculateSectionScore, store.ts:210-231 (results-page tables only).

    Filters scored question names by substring `section`, returns
    (number of questions, project score, maximum score).
    """
    qs = [q for q, _p, _t in scored_questions(survey) if section in q["name"]]
    return (
        len(qs),
        sum(get_value(data.get(q["name"])) for q in qs),
        sum(max_score_for_question(q) for q in qs),
    )


if __name__ == "__main__":
    s = load_survey()
    r = score(s, {})
    print(json.dumps({k: r[k] for k in ("max_raw_impact_score", "max_mitigation_score", "mitigation_threshold")}))
