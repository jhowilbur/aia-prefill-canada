"""Tests for the AIA catalogue and the score reproduction.

The reference is the tool's own code: the scoring functions are cut out of
vendor/aia-eia-js/src/store.ts at test time (lines from `function
addItemsInArray` up to the `//Toggles` comment), the only change being the
removal of the `<QuestionSelectBase>` angle-bracket casts that Node's type
stripping refuses. They run under Node against a small stand-in for the
survey-vue model, and their output is compared with pipeline/aia_score.py.

    python3 -m unittest discover -s pipeline/tests -v
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import aia_score as A  # noqa: E402
import build_catalog as B  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
HAS_VENDOR = (_ROOT / "vendor" / "aia-eia-js" / "src" / "store.ts").exists()
HAS_DATA = any((_ROOT / "data" / "interim" / "aia").glob("*.json"))
NEEDS_VENDOR = unittest.skipUnless(HAS_VENDOR, "needs vendor/aia-eia-js (git clone, see README)")
NEEDS_DATA = unittest.skipUnless(HAS_DATA, "needs the re-downloaded corpus (make data)")

STORE_TS = A.ROOT / "vendor" / "aia-eia-js" / "src" / "store.ts"
NODE = shutil.which("node")

HARNESS = r"""
const fs = require("fs");
const { survey, answerSets } = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
// --- stand-in for survey-vue: only what store.ts touches ---
function makeQuestion(el, parent) {
  return {
    name: el.name,
    parent: { name: parent.name },
    choices: (el.choices || []).map(c => ({ itemValue: c.value })),
    getType() { return el.type; },
  };
}
const all = [];
function walk(elements, parent) {
  for (const el of elements) {
    if (el.type === "panel") walk(el.elements || [], el);
    else if (el.type !== "html") all.push(makeQuestion(el, parent));
  }
}
for (const page of survey.pages) walk(page.elements || [], page);
const byName = Object.fromEntries(all.map(q => [q.name, q]));
// store.ts:321-329
const questionNames = all.filter(q => hasScore(q)).map(q => q.name);
const out = answerSets.map(data => {
  const model = { data, getQuestionByName: n => byName[n] };
  return {
    final: calculateFinalScore(model, questionNames),
    sections: Object.fromEntries(
      ["riskProfile", "aboutAlgorithm", "impact", "fairnessDesign"].map(s => [s, calculateSectionScore(model, questionNames, s)])
    ),
  };
});
console.log(JSON.stringify({ questionNames, out }));
"""


def extract_store_functions() -> str:
    src = STORE_TS.read_text(encoding="utf-8")
    start = src.index("function addItemsInArray")
    end = src.index("//Toggles wheather")
    body = src[start:end]
    body = body.replace("<QuestionSelectBase>", "")
    body = body.replace("export function", "function")
    return body


def run_tool(survey: dict, answer_sets: list[dict]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        script = tmp / "harness.ts"
        script.write_text(extract_store_functions() + "\n" + HARNESS, encoding="utf-8")
        payload = tmp / "payload.json"
        payload.write_text(json.dumps({"survey": survey, "answerSets": answer_sets}), encoding="utf-8")
        res = subprocess.run([NODE, str(script), str(payload)], capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            raise RuntimeError(res.stderr)
        return json.loads(res.stdout)


def answer_all(survey: dict, pick, phase: str | None = None) -> dict:
    """Answer every scored question with `pick(choices) -> value or list`."""
    data = {}
    for q, _p, page in A.iter_questions(survey):
        if not A.has_score(q, _p):
            continue
        if phase and B.phase_of(page) not in ("both", phase):
            continue
        choices = [c["value"] for c in q["choices"]]
        v = pick(choices, q)
        if v is not None:
            data[q["name"]] = v
    return data


def highest(choices, q):
    if q["type"] == "checkbox":
        return list(choices)
    return max(choices, key=lambda v: A.get_value(v))


def lowest(choices, q):
    if q["type"] == "checkbox":
        return []
    return min(choices, key=lambda v: A.get_value(v))


class SyntheticSets:
    @staticmethod
    def build(survey):
        sets = {
            # 1. Nothing answered.
            "empty": {},
            # 2. Worst case: every risk answer at its max, no mitigation.
            "max_risk_no_mitigation": {
                k: v for k, v in answer_all(survey, highest).items()
                if B.SCORE_TYPE_NAME[A.score_type(*_lookup(survey, k))] == "risk"
            },
            # 3. Max risk + full Design-phase mitigation -> 15 % deduction.
            "max_risk_full_design_mitigation": answer_all(survey, highest, phase="design"),
            # 4. Lowest answers everywhere (design phase).
            "all_lowest": answer_all(survey, lowest, phase="design"),
        }
        rng = random.Random(20261105)
        for i in range(25):
            def pick(choices, q, rng=rng):
                if rng.random() < 0.15:
                    return None
                if q["type"] == "checkbox":
                    return [c for c in choices if rng.random() < 0.5]
                return rng.choice(choices)
            sets[f"random_{i:02d}"] = answer_all(survey, pick, phase=rng.choice(["design", "implementation"]))
        return sets


def _lookup(survey, name):
    for q, p, _pg in A.iter_questions(survey):
        if q["name"] == name:
            return q, p
    raise KeyError(name)


@NEEDS_VENDOR
class TestScoreMatchesTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not NODE:
            raise unittest.SkipTest("node not installed")
        cls.survey = A.load_survey()
        cls.sets = SyntheticSets.build(cls.survey)
        cls.names = list(cls.sets)
        cls.tool = run_tool(cls.survey, [cls.sets[n] for n in cls.names])

    def test_same_scored_question_list(self):
        mine = [q["name"] for q, _p, _t in A.scored_questions(self.survey)]
        self.assertEqual(mine, self.tool["questionNames"])

    def test_final_scores_match(self):
        for name, tool_out in zip(self.names, self.tool["out"]):
            with self.subTest(set=name):
                r = A.score(self.survey, self.sets[name])
                self.assertEqual(
                    [r["raw_impact_score"], r["mitigation_score"], r["current_score"], r["level"]],
                    tool_out["final"],
                )

    def test_section_scores_match(self):
        for name, tool_out in zip(self.names, self.tool["out"]):
            for section, vals in tool_out["sections"].items():
                with self.subTest(set=name, section=section):
                    self.assertEqual(list(A.section_score(self.survey, self.sets[name], section)), vals)

    def test_named_sets_hit_expected_levels(self):
        lv = {n: A.score(self.survey, self.sets[n])["level"] for n in self.names}
        self.assertEqual(lv["empty"], 1)
        self.assertEqual(lv["max_risk_no_mitigation"], 4)
        self.assertEqual(lv["all_lowest"], 1)
        r = A.score(self.survey, self.sets["max_risk_full_design_mitigation"])
        self.assertTrue(r["deduction_applied"])
        self.assertEqual(r["current_score"], A.js_round(0.85 * r["raw_impact_score"]))
        # Random sets should cover more than one level, or the test is weak.
        self.assertGreater(len({lv[n] for n in self.names}), 1)

    def test_max_raw_reached_by_max_answers(self):
        r = A.score(self.survey, self.sets["max_risk_no_mitigation"])
        self.assertEqual(r["raw_impact_score"], r["max_raw_impact_score"])


class TestScoringRules(unittest.TestCase):
    def test_parse_embedded_value(self):
        self.assertEqual(A.get_value("item1-3"), 3)
        self.assertEqual(A.get_value("item6"), 0)
        self.assertEqual(A.get_value("001"), 0)
        self.assertEqual(A.get_value(["item1-1", "item2-4", "item3"]), 5)
        self.assertEqual(A.get_value(None), 0)

    def test_js_round_half_up(self):
        self.assertEqual(A.js_round(2.5), 3)
        self.assertEqual(A.js_round(3.5), 4)

    def test_level_boundaries(self):
        # Hand-built mini survey: max raw 8, max mitigation 4 (halved -> 2, threshold 1.6).
        survey = {"pages": [
            {"name": "p", "elements": [{"type": "panel", "name": "x-RS", "elements": [
                {"type": "dropdown", "name": "r1", "choices": [{"value": "a-0"}, {"value": "b-4"}]},
                {"type": "checkbox", "name": "r2", "choices": [{"value": "a-2"}, {"value": "b-2"}]},
            ]}]},
            {"name": "m", "elements": [{"type": "panel", "name": "y-MS", "elements": [
                {"type": "radiogroup", "name": "m1", "choices": [{"value": "a-2"}, {"value": "b-0"}]},
                {"type": "radiogroup", "name": "m2", "choices": [{"value": "a-2"}, {"value": "b-0"}]},
            ]}]},
        ]}
        cases = [
            ({}, 0, 1),
            ({"r2": ["a-2"]}, 2, 1),                  # 2 <= 8*0.25
            ({"r2": ["a-2", "b-2"]}, 4, 2),           # 4 <= 4
            ({"r1": "b-4", "r2": ["a-2"]}, 6, 3),     # 6 <= 6
            ({"r1": "b-4", "r2": ["a-2", "b-2"]}, 8, 4),
            ({"r1": "b-4", "r2": ["a-2", "b-2"], "m1": "a-2"}, 7, 4),  # round(0.85*8)=7 > 6
        ]
        for data, total, level in cases:
            with self.subTest(data=data):
                r = A.score(survey, data)
                self.assertEqual((r["current_score"], r["level"]), (total, level))
        self.assertEqual(A.score(survey, {})["max_raw_impact_score"], 8)
        self.assertEqual(A.score(survey, {})["mitigation_threshold"], 1.6)


class TestCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.survey = A.load_survey()
        cls.rows = B.build_rows(cls.survey)

    def test_one_row_per_survey_question(self):
        names = [q["name"] for q, _p, _pg in A.iter_questions(self.survey)]
        self.assertEqual([r["id"] for r in self.rows], names)
        self.assertEqual(len(names), len(set(names)), "duplicate SurveyJS names")

    def test_choices_and_weights_from_source(self):
        for r in self.rows:
            q, _p = _lookup(self.survey, r["id"])
            self.assertEqual([c["value"] for c in r["choices"]], [c["value"] for c in q.get("choices", [])])
            for c in r["choices"]:
                self.assertEqual(c["weight"], A.get_value(c["value"]))
                self.assertTrue(c["text_en"] and c["text_fr"], (r["id"], c["value"]))

    def test_scored_max_sum_equals_tool_max(self):
        tot = A.score(self.survey, {})
        self.assertEqual(sum(r["max_score"] for r in self.rows if r["kind"] == "risk"), tot["max_raw_impact_score"])
        self.assertEqual(sum(r["max_score"] for r in self.rows if r["kind"] == "mitigation"), tot["max_mitigation_score"])

    def test_every_row_judged(self):
        for r in self.rows:
            self.assertIn(r["doc_answerability"], ("doc", "partly", "internal-only"))
            self.assertTrue(r["doc_reason"])

    @NEEDS_DATA
    def test_jsonl_on_disk_is_current(self):
        on_disk = [json.loads(line) for line in B.OUT_JSONL.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(on_disk, json.loads(json.dumps(self.rows, ensure_ascii=False)))

    @NEEDS_DATA
    def test_shortlist(self):
        sl = [r for r in self.rows if r["shortlist"]]
        self.assertEqual([r["id"] for r in sl], B.shortlist(self.rows))
        self.assertTrue(10 <= len(sl) <= 20, len(sl))
        stats = B.coverage_stats(self.rows)
        for r in sl:
            st = stats[r["id"]]
            self.assertTrue(r["scored"] and r["choices"])
            self.assertIn(r["phase"], ("both", "implementation"))
            self.assertGreaterEqual(st["answered"], B.SL_MIN_COVERAGE)
            self.assertLessEqual(st["majority_share"], B.SL_MAX_MAJORITY)
            self.assertTrue(r["doc_answerability"] == "doc" or (st["evidence"] or 0) >= B.SL_MIN_EVIDENCE)

    @NEEDS_DATA
    def test_version_mapping(self):
        # aboutSystem3 exists only from v1.0.0: just the two v1.0.1 exports count.
        self.assertEqual(B.coverage_stats(self.rows)["aboutSystem3"]["answered"], 2)
        # Weight change only (item1-4 -> item1-2) still maps.
        self.assertEqual(B.coverage_stats(self.rows)["aboutDataSource1"]["answered"], 32)


if __name__ == "__main__":
    unittest.main()
