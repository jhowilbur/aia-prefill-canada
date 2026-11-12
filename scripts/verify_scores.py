#!/usr/bin/env python3
"""Offline check: recompute every published AIA's raw score and impact level from the
derived answers in data/aia_answers.jsonl, with the questionnaire version that produced it.

    python3 -I scripts/verify_scores.py        # prints the per-AIA table and the summary

Expected result for this release: 31 of 32 match on raw score and level (see docs/g0.md;
the mismatch is 6b429c8e, whose score PDF and JSON export disagree).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import aia_score as A  # noqa: E402


def main() -> int:
    n = ok = 0
    for line in open(ROOT / "data" / "aia_answers.jsonl", encoding="utf-8"):
        r = json.loads(line)
        s = A.score(None, r["answers"], version=r["version"])
        match = s["raw_impact_score"] == r["published_raw"] and s["level"] == r["published_level"]
        n += 1
        ok += match
        print(f"{r['aia_id'][:8]}  {r['version']:8}  published raw {r['published_raw']:>3} level {r['published_level']}"
              f"  recomputed raw {s['raw_impact_score']:>3} level {s['level']}  {'OK' if match else 'MISMATCH'}")
    print(f"\n{ok}/{n} match on raw score and impact level")
    return 0


if __name__ == "__main__":
    sys.exit(main())
