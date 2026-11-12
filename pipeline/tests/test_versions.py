"""Version-aware scoring (catalog/versions/, exported from the tool's git history)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import aia_score as A  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
HAS_VENDOR = (_ROOT / "vendor" / "aia-eia-js" / "src" / "store.ts").exists()
HAS_DATA = any((_ROOT / "data" / "interim" / "aia").glob("*.json"))
NEEDS_VENDOR = unittest.skipUnless(HAS_VENDOR, "needs vendor/aia-eia-js (git clone, see README)")
NEEDS_DATA = unittest.skipUnless(HAS_DATA, "needs the re-downloaded corpus (make data)")


@NEEDS_DATA
class VersionedScoring(unittest.TestCase):
    def test_default_unchanged(self):
        s = A.load_survey()
        self.assertEqual(A.score(s, {})["max_raw_impact_score"], 167)
        self.assertIsNone(A.score(s, {})["version"])

    def test_version_maxima(self):
        manifest = json.loads((A.VERSIONS_DIR / "manifest.json").read_text())
        for v, m in manifest.items():
            r = A.score(None, {}, version=v)
            self.assertEqual(r["max_raw_impact_score"], m["max_raw_impact_score"], v)
            self.assertEqual(r["max_mitigation_score"], m["max_mitigation_score"], v)
        self.assertEqual(manifest["v0.9.1"]["max_raw_impact_score"], 107)
        self.assertEqual(manifest["v0.10.0"]["max_raw_impact_score"], 126)

    def test_v101_equals_vendor(self):
        data = {"riskProfile1-RS": "item1-3"}
        self.assertEqual(A.score(A.load_survey(), data)["raw_impact_score"],
                         A.score(None, data, version="v1.0.1")["raw_impact_score"])

    def test_published_old_aia_reproduced(self):
        # 24d2cab2 (export v0.9.1): published raw 27, level II. The current survey
        # gives level I (27 <= 41.75); v0.9.1 (max 107, cut 26.75) gives level II.
        root = A.ROOT / "data" / "raw" / "24d2cab2-6a0d-4234-9239-b6ce102ebabd"
        f = next(root.glob("*.json"), None)
        if f is None or f.name == "package.json":
            f = next(p for p in root.glob("*.json") if p.name != "package.json")
        data = json.loads(f.read_text())["data"]
        r = A.score(None, data, version="v0.9.1")
        self.assertEqual((r["raw_impact_score"], r["level"]), (27, 2))

    def test_unknown_version(self):
        with self.assertRaises(ValueError):
            A.score(None, {}, version="v9.9")

    def test_load_conversions(self):
        d = {"aboutSystem1": ["item6-1", "item1"], "impact4": "x"}
        out = A.convert_loaded_file(d, "v0.10.0")
        self.assertEqual(out["aboutSystem1"], ["item6", "item1"])
        self.assertEqual(out["decisionSector3"], "x")
        self.assertNotIn("impact4", out)
        self.assertIn("impact4", d)  # input untouched
        self.assertEqual(A.convert_loaded_file(d, "v0.9"), d)

    def test_g0_rate(self):
        import g0_check
        s = g0_check.main(write=False)
        self.assertGreaterEqual(s["after_level"] / s["n"], 0.9)


if __name__ == "__main__":
    unittest.main()
