# aia-prefill-canada

A reproducible corpus of the **Algorithmic Impact Assessments (AIAs)** that Canadian federal institutions have published on open.canada.ca. The repository also contains a scorer that reproduces the official tool's results, a leakage analysis of candidate model inputs, a crosswalk to the **NIST AI RMF 1.0** and **OMB M-25-21**, and a **pre-specified protocol** for testing whether a model can help pre-fill an AIA from a system's documentation.

Author: Jonathas Wilbur Ferreira, Independent Researcher. Technical report: [`report/`](report/).

> **Status (v1.0.0, 2026-11-05).** This release covers data, scoring and protocol only. **No model has been trained or evaluated, and no accuracy is reported.** The evaluation protocol in `docs/eval-plan.md` was frozen before any model output existed.

## What is in it

| Result | Where | Check it yourself |
|---|---|---|
| Corpus: 39 published AIAs from 11 departments and agencies (2018-10-05 to 2026-08-14); 32 have machine-readable answers | `data/aia_catalogue.csv`, `docs/data-notes.md` | `data/SOURCES.csv` (URL + SHA-256 for each of the 165 source files) |
| Score reproduction: the raw score and impact level of **31 of 32** machine-readable AIAs, recomputed with version-aware scoring (11/32 raw and 24/32 level when the current questionnaire is used for every AIA) | `docs/g0.md`, `reports/g0_score_check.csv` | `make verify` (offline, about 1 s) |
| Questionnaire catalogue: all 295 questions of the official tool (EN/FR, choices, weights), plus the five questionnaire versions behind the published scores | `catalog/` | `make test` |
| Leakage-free inputs and a leak probe: no single feature of the model input separates impact level I from II above the 0.9 flag | `docs/inputs.md`, `reports/leak_probe.md` | `make reproduce` |
| Crosswalk: AIA questionnaire ↔ NIST AI RMF 1.0 ↔ OMB M-25-21 | `crosswalk/` | sources and quotes in each row |
| Pre-specified evaluation protocol: hypotheses, metrics, sample sizes, pass/kill gates, allowed claims | `docs/eval-plan.md`, `docs/lockbox.sha256` | frozen by the author 2026-11-05, before any model output; this release is its first external timestamp |

## Quick start

Requires Python ≥ 3.10 and numpy (for `eval/`), plus `git`, `curl` and `pdftotext` (poppler) for `make reproduce`; Node.js runs the optional cross-check of the scorer against the tool's own `store.ts`.

```sh
make verify     # recompute the 32 published scores from the derived answers: expect 31/32
make test       # unit tests; data-dependent tests skip until the corpus is downloaded
make reproduce  # clone the official AIA tool at the pinned commit, re-download the corpus
                # from open.canada.ca (about 27 MB, SHA-256 checked), parse, G0 check,
                # build leakage-free inputs, leak probe, full test suite
```

If IPv6 is broken on your network, run `CURL_IPV4=1 make reproduce`.

A from-scratch `make reproduce` (tested 2026-11-05) re-downloads all 165 files with matching SHA-256 and regenerates `reports/leak_probe.md` byte for byte and `reports/g0_score_check.csv` identically, except for the `history_revisions_matching_raw` column, which needs `pipeline/g0_check.py --history` and a full clone of the tool's git history (see `pipeline/aia_versions.py`).

## Data and privacy

The repository redistributes **only derived tables**:
- the multiple-choice answers to questionnaire questions (`data/aia_answers.jsonl`);
- published scores and levels;
- public record metadata (department, system title, date).

It contains **no source files, no free-text answers and no personal information**. The administrative fields (respondent, job title, branch, responsible executive) are dropped before export. `make data` re-downloads the originals from the Government of Canada into `data/raw/`, which is git-ignored. Those originals can contain the names and work e-mail addresses of public servants: keep them out of any derived work you share. `pipeline/redact_pii.py` removes the ones it can find.

## Layout

| Folder | What |
|---|---|
| `pipeline/` | fetch, parse, questionnaire versions, scorer (`aia_score.py`), G0 check, catalogue, leakage-free inputs, PII redaction, leak probe; `tests/` |
| `eval/` | metrics for the planned evaluation (selective accuracy, calibration, risk–coverage, Wilson and bootstrap CIs); `tests/` |
| `scripts/` | `verify_scores.py` (offline check), `fetch_pinned.py` (exact corpus re-download) |
| `catalog/` | `requirements.jsonl`, `versions/<v>/survey-enfr.json`, `scoring.md` |
| `data/` | derived tables and `SOURCES.csv` |
| `docs/` | data notes, G0, input rule, evaluation protocol |
| `reports/` | outputs of the scripts |
| `crosswalk/` | AIA ↔ NIST AI RMF 1.0 ↔ OMB M-25-21 |
| `report/` | technical report |

Code comments that mention an "audit" or "round N" (for example `M-A`, `L-1`) refer to internal review notes that are not part of this release.

## Licences

Code: MIT. Report, crosswalk and docs: CC BY 4.0. Derived AIA tables: contain information licensed under the Open Government Licence – Canada; the author's additions CC BY 4.0. Questionnaire: MIT, © Government of Canada (canada-ca/aia-eia-js). Details are in [`NOTICE.md`](NOTICE.md). This is independent research, not affiliated with or endorsed by the Government of Canada.

## Citation

See [`CITATION.cff`](CITATION.cff). The DOI will be added on publication.
