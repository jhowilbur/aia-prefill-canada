"""Questionnaire versions of the AIA tool, taken from the tool's git history.

The tool writes `version` (store.ts `state.version`) into every JSON export.
That string was bumped in these commits of canada-ca/aia-eia-js:

    c33b74d 2021-03-11  v0.9
    8cc9b5f 2021-11-30  v0.9.1
    aca5ce7 2023-01-28  v0.10.0
    4489fa9 2024-12-04  v1.0.0
    b900dc7 2025-10-03  v1.0.1

The scoring code in store.ts (hasScore, getValue, getMaxScoreForQuestion,
calculateFinalScore, questionNames = getAllQuestions().filter(hasScore)) is the
same in every one of these versions; only survey-enfr.json (questions, -RS/-MS
suffixes, choice weights) changes. So a version is fully described by its
survey file.

Canonical survey of a version = the last revision of src/survey-enfr.json
before the next version bump (the state the tool was in when it last wrote
that version string). For v1.0.1 it is the vendored commit.

Run once to (re)export the per-version surveys into catalog/versions/:

    python3 -I pipeline/aia_versions.py export   # needs data/interim/aia-history/repo
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT / "catalog" / "versions"
HISTORY_REPO = ROOT / "data" / "interim" / "aia-history" / "repo"

# version string -> (bump commit, next bump commit or None)
VERSION_RANGES = {
    "v0.9": ("c33b74d", "8cc9b5f"),
    "v0.9.1": ("8cc9b5f", "aca5ce7"),
    "v0.10.0": ("aca5ce7", "4489fa9"),
    "v1.0.0": ("4489fa9", "b900dc7"),
    "v1.0.1": ("b900dc7", None),
}

NOTES = {
    "v1.0.0": "Ambiguous: the 2025 questionnaire rewrite (issues #1127-#1153) was made under the "
              "v1.0.0 string, so a v1.0.0 export can come from the Dec 2024 survey (= v0.10.0 final) "
              "or the Sept 2025 one exported here. No published AIA uses v1.0.0.",
}


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(HISTORY_REPO), *args],
                          capture_output=True, text=True, check=True).stdout


def survey_revisions(version: str) -> list[str]:
    """All revisions of survey-enfr.json reachable inside a version's range (oldest first)."""
    start, end = VERSION_RANGES[version]
    end_ref = f"{end}^" if end else "HEAD"
    revs = _git("log", "--format=%h", f"{start}..{end_ref}", "--", "src/survey-enfr.json").split()[::-1]
    return [start] + revs


def canonical_revision(version: str) -> str:
    _start, end = VERSION_RANGES[version]
    ref = f"{end}^" if end else "HEAD"
    return _git("log", "-1", "--format=%h", ref, "--", "src/survey-enfr.json").strip()


def survey_at(rev: str) -> dict:
    return json.loads(_git("show", f"{rev}:src/survey-enfr.json"))


def export() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import aia_score as A

    manifest = {}
    for version in VERSION_RANGES:
        rev = canonical_revision(version)
        date = _git("log", "-1", "--format=%cI", rev).strip()
        text = _git("show", f"{rev}:src/survey-enfr.json")
        out = VERSIONS_DIR / version / "survey-enfr.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        r = A.score(json.loads(text), {})
        manifest[version] = {
            "survey_commit": rev,
            "survey_commit_date": date,
            "bump_commit": VERSION_RANGES[version][0],
            "next_bump_commit": VERSION_RANGES[version][1],
            "max_raw_impact_score": r["max_raw_impact_score"],
            "max_mitigation_score": r["max_mitigation_score"],
            "scored_questions": len(A.scored_questions(json.loads(text))),
            "note": NOTES.get(version, ""),
        }
    (VERSIONS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    if sys.argv[1:] == ["export"]:
        print(json.dumps(export(), indent=2))
    else:
        print(__doc__)
