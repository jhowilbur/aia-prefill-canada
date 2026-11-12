import json, os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parse_aia as pa  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
HAS_VENDOR = (_ROOT / "vendor" / "aia-eia-js" / "src" / "store.ts").exists()
HAS_DATA = any((_ROOT / "data" / "interim" / "aia").glob("*.json"))
NEEDS_VENDOR = unittest.skipUnless(HAS_VENDOR, "needs vendor/aia-eia-js (git clone, see README)")
NEEDS_DATA = unittest.skipUnless(HAS_DATA, "needs the re-downloaded corpus (make data)")


class TestHelpers(unittest.TestCase):
    def test_codes(self):
        self.assertTrue(pa.is_code("item1-3"))
        self.assertTrue(pa.is_code(["item1", "item5-2"]))
        self.assertFalse(pa.is_code("item1 is great"))
        self.assertTrue(pa.is_free_text("A system that triages."))
        self.assertFalse(pa.is_free_text("item2-0"))
        self.assertFalse(pa.is_free_text("   "))

    def test_scores_en_fr(self):
        en = "Section 1: Impact Level : 2\nCurrent Score: 41\n\nRaw Impact Score: 41\n\nMitigation Score: 35"
        self.assertEqual(pa.parse_scores(en), {"impact_level": 2, "raw_score": 41, "current_score": 41, "mitigation_score": 35})
        self.assertEqual(pa.parse_scores("Section 1: Impact Level: 1\nRaw Score: 28")["raw_score"], 28)
        self.assertEqual(pa.parse_scores("Section 1 : Niveau d’incidence : 2")["impact_level"], 2)
        self.assertEqual(pa.parse_scores("Impact Level: III")["impact_level"], 3)
        self.assertTrue(pa.is_aia_render(en))
        self.assertFalse(pa.is_aia_render("GBA+ summary of the model"))

    def test_lang(self):
        self.assertEqual(pa.detect_lang("The system will be used to sort the applications and it is fast."), "en")
        self.assertEqual(pa.detect_lang("Le système est utilisé pour trier les demandes dans une file et pour les agents."), "fr")
        self.assertEqual(pa.detect_lang("ok"), "unknown")

    def test_pick_primary_prefers_english_and_newer(self):
        en = {"version": "v0.10.0", "data": {"projectDetailsDescription": "The tool is used by the officers to sort the files and it is fast."}}
        fr = {"version": "v0.11.0", "data": {"projectDetailsDescription": "Le outil est utilisé par les agents pour trier les dossiers dans une file."}}
        self.assertIs(pa.pick_primary([("x/srec.json", fr), ("x/cres.json", en)])[1], en)
        en2 = dict(en, version="v0.12.1")
        self.assertIs(pa.pick_primary([("a.json", en), ("b.json", en2)])[1], en2)

    def test_split_and_dataset(self):
        survey = {"projectDetailsTitle": "text", "impact8": "comment", "impact7": "radiogroup"}
        a, u = pa.split_answers({"projectDetailsTitle": "T", "impact7": "item2-2", "oldKey": "item1"}, survey)
        self.assertEqual(set(a), {"projectDetailsTitle", "impact7"})
        self.assertEqual(u, {"oldKey": "item1"})
        with tempfile.TemporaryDirectory() as d:
            json.dump({"id": "abc", "title": "AIA - X", "notes": "About X.", "organization": {"name": "tbs-sct", "title": "Treasury Board | Conseil"}},
                      open(os.path.join(d, "package.json"), "w"))
            json.dump({"version": "v0.10.0", "data": {"projectDetailsTitle": "X tool", "projectDetailsRespondent": "Jane",
                                                       "impact7": "item2-2", "impact8": "The system is used for triage of the files and it is fast."}},
                      open(os.path.join(d, "r.json"), "w"))
            rec = pa.parse_dataset(d, survey)
        self.assertEqual(rec["system_name"], "X tool")
        self.assertEqual(rec["department"], "Treasury Board")
        self.assertEqual(rec["answers"]["impact7"], "item2-2")
        self.assertNotIn("projectDetailsRespondent", rec["free_text_answers"])  # admin field, not system text
        self.assertIn("triage", rec["description_text"])
        self.assertIn("About X.", rec["description_text"])
        self.assertEqual(rec["answers_source"], "json")
        self.assertIsNone(rec["raw_score"])

    @NEEDS_VENDOR
    def test_real_survey_loads(self):
        s = pa.load_survey()
        self.assertIn("projectDetailsDescription", s)
        self.assertNotIn("welcome1", s)


if __name__ == "__main__":
    unittest.main()
