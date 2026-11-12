"""Unit tests for eval/metrics.py on synthetic data with known answers.
Run: python3 -I -m unittest discover -s eval/tests -v   (from the project root)
"""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import metrics as M  # noqa: E402


def rec(aia, q, t, p, c=0.9, dept="D"):
    return {"aia_id": aia, "department": dept, "question_id": q, "y_true": t, "y_pred": p, "confidence": c}


class TestCI(unittest.TestCase):
    def test_wilson_known(self):
        lo, hi = M.wilson_ci(8, 10)  # textbook value 0.490-0.943
        self.assertAlmostEqual(lo, 0.4902, places=3)
        self.assertAlmostEqual(hi, 0.9433, places=3)

    def test_wilson_edges(self):
        lo, hi = M.wilson_ci(0, 20)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.1611, places=3)
        self.assertEqual(M.wilson_ci(0, 0), (0.0, 1.0))

    def test_cluster_bootstrap_wider_than_iid_when_clustered(self):
        # 20 AIAs x 50 items; whole AIAs are right or wrong -> effective n = 20
        rs = [rec(f"a{i}", f"q{j}", "y", "y" if i % 2 else "n") for i in range(20) for j in range(50)]
        est, lo, hi = M.cluster_bootstrap(rs, M.accuracy, B=1000, seed=1)
        self.assertAlmostEqual(est, 0.5)
        wlo, whi = M.wilson_ci(500, 1000)
        self.assertGreater(hi - lo, 3 * (whi - wlo))
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)

    def test_paired_diff_identical_systems_is_zero(self):
        rs = [rec(f"a{i}", "q", "y", "y" if i % 3 else "n") for i in range(30)]
        est, lo, hi = M.paired_cluster_bootstrap_diff(rs, rs, M.accuracy, B=200)
        self.assertEqual((est, lo, hi), (0.0, 0.0, 0.0))


class TestClassification(unittest.TestCase):
    def test_accuracy_and_abstain(self):
        rs = [rec("a", "q", "y", "y"), rec("b", "q", "y", "n"), rec("c", "q", "y", None), rec("d", "q", "n", "n")]
        self.assertAlmostEqual(M.accuracy(rs), 0.5)
        self.assertAlmostEqual(M.accuracy(rs, answered_only=True), 2 / 3)
        self.assertAlmostEqual(M.coverage(rs), 0.75)

    def test_checkbox_order_insensitive(self):
        self.assertTrue(M.is_correct(rec("a", "q", ("x", "y"), ["y", "x"])))

    def test_macro_f1_hand_computed(self):
        yt = ["a", "a", "a", "b"]
        yp = ["a", "a", "b", "b"]
        # F1(a)=2*2/(4+0+1)=0.8 ; F1(b)=2*1/(2+1+0)=0.6667 ; mean=0.7333
        self.assertAlmostEqual(M.macro_f1(yt, yp), (0.8 + 2 / 3) / 2)

    def test_macro_f1_abstain_costs_recall_only(self):
        self.assertAlmostEqual(M.macro_f1(["a", "a"], ["a", None]), 2 / 3)

    def test_majority_baseline_uses_train_only(self):
        train = [rec(f"t{i}", "q", "no", None) for i in range(7)] + [rec(f"u{i}", "q", "yes", None) for i in range(3)]
        test = [rec("x", "q", "yes", None), rec("y", "q2", "no", None)]
        out = M.majority_baseline(train, test)
        self.assertEqual(out[0]["y_pred"], "no")
        self.assertAlmostEqual(out[0]["confidence"], 0.7)
        self.assertIsNone(out[1]["y_pred"])

    def test_per_question(self):
        rs = [rec("a", "q1", "y", "y"), rec("b", "q1", "n", "y"), rec("a", "q2", "n", "n")]
        pq = M.per_question(rs)
        self.assertAlmostEqual(pq["q1"]["accuracy"], 0.5)
        self.assertAlmostEqual(pq["q2"]["accuracy"], 1.0)


class TestSelective(unittest.TestCase):
    def setUp(self):
        # 10 items: confidences 1.0..0.1; first 6 correct, last 4 wrong -> perfect ranking
        self.good = [rec(f"a{i}", "q", "y", "y" if i < 6 else "n", c=1 - i / 10) for i in range(10)]
        self.bad = [rec(f"a{i}", "q", "y", "y" if i < 6 else "n", c=i / 10) for i in range(10)]

    def test_selective_accuracy_at(self):
        self.assertAlmostEqual(M.selective_accuracy_at(self.good, 0.5), 1.0)
        self.assertAlmostEqual(M.selective_accuracy_at(self.good, 1.0), 0.6)
        self.assertAlmostEqual(M.selective_accuracy_at(self.bad, 0.4), 0.0)

    def test_aurc_ordering(self):
        self.assertLess(M.aurc(self.good), M.aurc(self.bad))
        # perfect ranking: risks = 0 x6, then 1/7,2/8,3/9,4/10 -> mean
        expect = (1 / 7 + 2 / 8 + 3 / 9 + 4 / 10) / 10
        self.assertAlmostEqual(M.aurc(self.good), expect)

    def test_unreachable_coverage_is_nan(self):
        rs = [rec("a", "q", "y", "y", 0.9), rec("b", "q", "y", None), rec("c", "q", "y", None)]
        self.assertTrue(math.isnan(M.selective_accuracy_at(rs, 0.5)))
        self.assertAlmostEqual(M.selective_accuracy_at(rs, 0.3), 1.0)

    def test_abstention_not_rewarded_in_aurc(self):
        all_abstain = [rec("a", "q", "y", None), rec("b", "q", "y", None)]
        self.assertEqual(M.aurc(all_abstain), 1.0)


class TestCalibration(unittest.TestCase):
    def test_calibrated_large_n(self):
        rng = np.random.default_rng(0)
        c = rng.uniform(0.3, 1.0, 20000)
        y = rng.random(20000) < c
        self.assertLess(M.adaptive_ece(c, y, 10), 0.02)
        a, b = M.calibration_slope_intercept(c, y)
        self.assertAlmostEqual(b, 1.0, delta=0.08)
        self.assertAlmostEqual(a, 0.0, delta=0.08)

    def test_overconfident_detected(self):
        rng = np.random.default_rng(1)
        true_p = rng.uniform(0.5, 0.8, 5000)
        y = rng.random(5000) < true_p
        conf = np.clip(true_p + 0.15, 0, 0.99)  # claims 15 pp more than reality
        self.assertGreater(M.adaptive_ece(conf, y, 10), 0.12)
        a, b = M.calibration_slope_intercept(conf, y)
        self.assertLess(a, 0.0)  # intercept < 0 = predicted confidence too high
        self.assertLess(M.brier(true_p, y), M.brier(conf, y))

    def test_null_ece_positive_at_small_n(self):
        c = np.full(40, 0.8)
        q95 = M.null_ece_quantile(c, n_bins=2, n_sim=2000, seed=3)
        self.assertGreater(q95, 0.05)  # ECE of a perfect model at n=40 is not ~0
        self.assertLess(q95, 0.30)

    def test_default_bins(self):
        self.assertEqual(M.default_n_bins(40), 2)
        self.assertEqual(M.default_n_bins(150), 5)
        self.assertEqual(M.default_n_bins(5000), 10)

    def test_reliability_bins_mass(self):
        rows = M.reliability_table(np.linspace(0, 1, 90), np.ones(90), 3)
        self.assertEqual([r["n"] for r in rows], [30, 30, 30])


class TestImpactLevel(unittest.TestCase):
    Q = {
        "r1-RS": {"score_type": "RS", "qtype": "radiogroup", "values": {"no": 0, "yes": 4}},
        "r2-RS": {"score_type": "RS", "qtype": "checkbox", "values": {"a": 2, "b": 2}},
        "m1-MS": {"score_type": "MS", "qtype": "radiogroup", "values": {"no": 0, "yes": 2}},
        "m2-MS": {"score_type": "MS", "qtype": "radiogroup", "values": {"no": 0, "yes": 2}},
        "x-NS": {"score_type": "NS", "qtype": "radiogroup", "values": {"a": 9}},
    }

    def test_thresholds(self):
        # max_raw = 8; t1=2, t2=4, t3=6
        lv = lambda ans: M.impact_level(ans, self.Q)["level"]
        self.assertEqual(lv({"r1-RS": "no", "r2-RS": ["a"]}), 1)          # 2 <= 2
        self.assertEqual(lv({"r1-RS": "yes"}), 2)                          # 4
        self.assertEqual(lv({"r1-RS": "yes", "r2-RS": ["a"]}), 3)          # 6
        self.assertEqual(lv({"r1-RS": "yes", "r2-RS": ["a", "b"]}), 4)     # 8

    def test_mitigation_deduction_and_js_round(self):
        # max_mit = 4 -> needs mit >= 0.8*2 = 1.6 ; total = round(0.85*8)=round(6.8)=7 -> level 4
        r = M.impact_level({"r1-RS": "yes", "r2-RS": ["a", "b"], "m1-MS": "yes"}, self.Q)
        self.assertEqual((r["total"], r["level"]), (7, 4))
        # raw 6 with mitigation: round(5.1)=5 -> 5 <= 6 -> level 3 (unchanged)
        r = M.impact_level({"r1-RS": "yes", "r2-RS": ["a"], "m1-MS": "yes"}, self.Q)
        self.assertEqual(r["total"], 5)
        self.assertEqual(M.js_round(2.5), 3)
        self.assertEqual(M.js_round(-2.5), -2)

    def test_ns_ignored(self):
        self.assertEqual(M.impact_level({"x-NS": "a"}, self.Q)["raw"], 0)

    def test_fill_policies(self):
        pred = {"r1-RS": None, "r2-RS": None, "m1-MS": None, "m2-MS": "yes"}
        cons = M.fill_abstentions(pred, self.Q, "conservative")
        self.assertEqual(cons["r1-RS"], "yes")
        self.assertEqual(sorted(cons["r2-RS"]), ["a", "b"])
        self.assertEqual(cons["m1-MS"], "no")
        self.assertEqual(cons["m2-MS"], "yes")
        orc = M.fill_abstentions(pred, self.Q, "oracle", {"r1-RS": "no", "r2-RS": [], "m1-MS": "yes"})
        self.assertEqual(orc["r1-RS"], "no")

    def test_level_agreement(self):
        la = M.level_agreement([1, 2, 2, 3, 4], [1, 2, 1, 3, 2])
        self.assertAlmostEqual(la["exact"], 0.6)
        self.assertAlmostEqual(la["under_rate"], 0.4)
        self.assertEqual(la["under_by_2plus"], 1)


class TestAgreementEvidence(unittest.TestCase):
    def test_kappa_known(self):
        # 2x2: O = [[20,5],[10,15]], n=50: po=0.7, pe=(25*30+25*20)/2500=0.5, kappa=0.4
        a = ["y"] * 25 + ["n"] * 25
        b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
        self.assertAlmostEqual(M.weighted_kappa(a, b, ["y", "n"]), 0.4)

    def test_quadratic_kappa_perfect(self):
        self.assertAlmostEqual(M.weighted_kappa([1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4], "quadratic"), 1.0)

    def test_evidence(self):
        self.assertTrue(M.evidence_verbatim("The system  uses\nML.", "Intro. the system uses ml. End"))
        self.assertFalse(M.evidence_verbatim("invented", "nothing here"))
        e = M.evidence_correctness(["supports"] * 7 + ["partial"] * 2 + ["no"])
        self.assertAlmostEqual(e["strict"], 0.7)
        self.assertAlmostEqual(e["lenient"], 0.9)


class TestFullReport(unittest.TestCase):
    def test_runs_on_synthetic(self):
        rng = np.random.default_rng(7)
        rs = []
        for a in range(15):
            for q in range(40):
                c = rng.uniform(0.4, 1.0)
                ok = rng.random() < c
                p = None if c < 0.5 else ("y" if ok else "n")
                rs.append(rec(f"a{a}", f"q{q}", "y", p, c, dept=f"d{a % 5}"))
        rep = M.full_report(rs, B=200)
        self.assertEqual(rep["n_aia"], 15)
        self.assertEqual(rep["n_departments"], 5)
        est, lo, hi = rep["sel_acc@0.5"]
        self.assertLessEqual(lo, est)
        self.assertLessEqual(est, hi)
        self.assertIn("ece_null95", rep["calibration"])


if __name__ == "__main__":
    unittest.main()
