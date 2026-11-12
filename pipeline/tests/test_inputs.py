"""Level-leakage filtering of model inputs (pipeline/build_inputs.py, audit round 2 M-A) and probe."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_inputs as B  # noqa: E402
import leak_probe as P  # noqa: E402
import redact_pii as R  # noqa: E402

# Synthetic text with the wrapped-line shape of a published peer-review summary (EN and FR PDF extractions).
C088_EN = ("Why we did a peer review assessment\n"
           "The EXAMPLE program completed an Algorithmic Impact Assessment, and scored 2 out 4 for impact\n"
           "level. Because of this, the program had to carry out a peer review of the system’s use of\n"
           "AI.\n\n"
           "The system ranks incoming files for officer review.\n")
C088_FR = ("Le programme EXEMPLE a fait l’objet d’une Évaluation d’incidence algorithmique, et a obtenu une cote de\n"
           "2 sur 4 pour le niveau d’incidence. Pour cette raison, le programme devait mener un\n"
           "examen par les pairs de l’utilisation de l’IA par le système.\n")


class SentenceFilter(unittest.TestCase):
    def test_c088f841_pattern_removed(self):
        out = B.redact(C088_EN)
        for s in ("impact", "level", "Because of this", "required", "peer review", "scored"):
            self.assertNotIn(s, out)
        self.assertEqual(out, "The system ranks incoming files for officer review.")
        self.assertEqual(B.redact(C088_FR), "")

    def test_wrapped_line_split_across_newline(self):
        # The old line-based regex stopped at "\n" and left "level. ..." fragments behind.
        t = ("The tool supports officers. Based on the results, the system was assessed\n"
             "at a moderate\nlevel and peer review applied.\nIt sorts files by complexity.")
        out = B.redact(t)
        self.assertNotIn("moderate", out)
        self.assertNotIn("level", out)
        self.assertEqual(out, "The tool supports officers. It sorts files by complexity.")

    def test_french_qualifiers(self):
        for t in ("Le système a une cote d'incidence de 2 (modéré).", "À un niveau modéré, un avis est publié.",
                  "Le niveau d’incidence est II.", "This is a Level II system.", "Impact Level: 2"):
            self.assertEqual(B.redact(t), "", t)

    def test_notice_or_hitl_required(self):
        self.assertEqual(B.redact("A notice must be published before the system goes live."), "")
        self.assertEqual(B.redact("Human-in-the-loop review is required for every decision."), "")

    def test_ordinary_sentences_kept(self):
        for t in ("Files are grouped into tiers according to their level of difficulty.",
                  "Officers are required to review every document on file.",
                  "Les demandeurs ont l'intention d'étudier au niveau postsecondaire."):
            self.assertEqual(B.redact(t), t)

    def test_idempotent(self):
        t = C088_EN + "\n\nSecond para line one\ncontinues here. Done."
        self.assertEqual(B.redact(B.redact(t)), B.redact(t))


class DocumentType(unittest.TestCase):
    def test_peer_review_files_excluded(self):
        for f in ("data/raw/x/acfe70cb_peer-review-assessment-report-summary_for-publication.pdf",
                  "data/raw/x/60d4bb68_examen-par-les-pairs-du-modele.pdf",
                  "data/raw/x/a02ae14f_outil-resume-analytique-dexamen-par-les-pai.pdf",
                  "data/raw/x/d431e4bf_srec-jemepresente-evaluation-et-reponse-par-les-pairs-final.pdf"):
            self.assertTrue(B.is_level_revealing(f, ""), f)

    def test_title_in_text_detected_and_gba_kept(self):
        self.assertTrue(B.is_level_revealing("data/raw/x/annex-a.pdf", "Annex A\nPeer Review Summary\n..."))
        self.assertFalse(B.is_level_revealing("data/raw/x/gba-plus-summary-en_final.pdf", "GBA Plus summary"))

    def test_built_inputs_have_no_peer_review_document(self):
        files = sorted((B.OUT_DIR).glob("*.json"))
        if not files:
            self.skipTest("inputs not built")
        for p in files:
            rec = json.loads(p.read_text(encoding="utf-8"))
            for d in rec["documents"]:
                if d["source"] == "supporting_doc":
                    self.assertFalse(B.is_level_revealing(d["file"], d["text"]), d["file"])
                self.assertNotRegex(d["text"], r"(?i)peer[\s-]*review|impact\s+level")
            self.assertNotIn("excluded_documents", rec)  # L-1: level-revealing metadata lives in the sidecar
            self.assertNotRegex(json.dumps(rec, ensure_ascii=False), r"(?i)peer[\s-]*review|examen[\s-]*par[\s-]*les[\s-]*pairs|impact\s+level")

    def test_excluded_sidecar_outside_model_input_dir(self):
        if not B.EXCLUDED_PATH.exists():
            self.skipTest("inputs not built")
        self.assertNotEqual(B.EXCLUDED_PATH.parent, B.OUT_DIR)
        side = json.loads(B.EXCLUDED_PATH.read_text(encoding="utf-8"))["excluded"]
        self.assertEqual(list(side), sorted(side))
        for aid, items in side.items():
            self.assertTrue((B.OUT_DIR / f"{aid}.json").exists(), aid)
            for it in items:
                self.assertEqual(it["reason"], B.LEVEL_DOC_REASON, it["file"])


class RawNames(unittest.TestCase):
    def test_names_recovered_from_raw_after_interim_redaction(self):
        with tempfile.TemporaryDirectory() as td:
            ds = Path(td) / "ds1"
            ds.mkdir()
            (ds / "package.json").write_text("{}", encoding="utf-8")
            (ds / "aia.json").write_text(json.dumps({"data": {"projectDetailsRespondent": "Jane Q Doe"},
                                                     "translationsOnResult": {"ADMresponsible": "Smith, John"}}),
                                         encoding="utf-8")
            interim = {"answers": {"projectDetailsRespondent": R.NAME_TOKEN}}
            names = R.collect_names([interim] + R.raw_records(Path(td)))
            self.assertIn("Jane Q Doe", names)
            self.assertIn("John Smith", names)


class Probe(unittest.TestCase):
    def test_auc(self):
        self.assertEqual(P.auc([1, 1, 0, 0], [1, 1, 0, 0]), 1.0)
        self.assertEqual(P.auc([1, 0, 1, 0], [1, 1, 0, 0]), 0.5)
        self.assertEqual(P.auc([0, 0, 0], [1, 0, 0]), 0.5)


if __name__ == "__main__":
    unittest.main()
