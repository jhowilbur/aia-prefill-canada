"""PII redaction (pipeline/redact_pii.py, audit M5)."""
from __future__ import annotations

import collections
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import redact_pii as R  # noqa: E402


def _rec():
    return {
        "department": "Immigration, Refugees and Citizenship Canada",
        "answers": {
            "projectDetailsRespondent": "Jane Q Doe",
            "projectDetailsJob": "Example Analyst",
            "projectDetailsBranch": "Example Operations Branch",
            "projectDetailsDescription": "Contact Jane Q Doe at jane.doe@example.gc.ca or 613-555-0199 ext 12.",
        },
        "answers_unmapped": {"ADMresponsible": "Smith, John"},
        "free_text_fr": {"projectDetailsRespondent": "Divers intervenants de l'agence"},
        "ckan_notes": "Reviewed by John Smith; call (819) 555-0100.",
    }


class Redact(unittest.TestCase):
    def setUp(self):
        self.rec = _rec()
        names = R.collect_names([self.rec])
        self.counts = collections.Counter()
        self.out = R.redact_obj(self.rec, R.name_pattern(names), self.counts)
        self.flat = json.dumps(self.out, ensure_ascii=False)

    def test_names_emails_phones_removed(self):
        for s in ("Jane Q Doe", "John Smith", "Smith, John", "jane.doe@", "613-555-0199", "555-0100"):
            self.assertNotIn(s, self.flat)
        self.assertEqual(self.counts["email"], 1)
        self.assertEqual(self.counts["phone"], 2)
        self.assertEqual(self.counts["name"], 4)

    def test_roles_and_departments_kept(self):
        a = self.out["answers"]
        self.assertEqual(a["projectDetailsJob"], "Example Analyst")
        self.assertEqual(a["projectDetailsBranch"], "Example Operations Branch")
        self.assertEqual(self.out["department"], self.rec["department"])
        self.assertEqual(self.out["free_text_fr"]["projectDetailsRespondent"], "Divers intervenants de l'agence")

    def test_org_values_are_not_people(self):
        self.assertEqual(R.split_people("Various Stakeholders at Example Agency"), [])
        self.assertEqual(R.split_people("Example Directorate – Data Office"), [])
        self.assertEqual(R.split_people("Alex Martin, Sam Lee"), ["Alex Martin", "Sam Lee"])

    def test_idempotent(self):
        c = collections.Counter()
        again = R.redact_obj(self.out, R.name_pattern(R.collect_names([self.rec])), c)
        self.assertEqual(again, self.out)
        self.assertEqual(sum(c.values()), 0)

    def test_numbers_that_are_not_phones_survive(self):
        c = collections.Counter()
        s = "Score 2024-12-10, PPU 116, 1,234,567 records, version 0.10.0"
        self.assertEqual(R.redact_text(s, None, c), s)

    def test_interim_corpus_is_clean(self):
        files = [p for d in R.TARGET_DIRS for p in d.glob("*.json")]
        if not files:
            self.skipTest("no interim data")
        recs = [json.loads(p.read_text(encoding="utf-8")) for p in files]
        pat = R.name_pattern(R.collect_names(recs))
        for p, rec in zip(files, recs):
            c = collections.Counter()
            R.redact_obj(rec, pat, c)
            self.assertEqual(sum(c.values()), 0, f"{p.name}: run pipeline/redact_pii.py ({dict(c)})")


if __name__ == "__main__":
    unittest.main()
