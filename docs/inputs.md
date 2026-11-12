# Leakage-free model input

Built by `python3 -I pipeline/build_inputs.py` → `data/interim/inputs/<id>.json` (39 files).
`--fields` prints the classification of every free-text field in every questionnaire version
(catalog/versions/), with the reason. Numbers below come from that script.

## Rule
A free-text (`text`/`comment`) field of the AIA export is

- **(a) system documentation** a department would have before doing the AIA (what the system is,
  its data, model, decision, outputs, business purpose), **only if** it is not on a mitigation
  page, it is not a follow-up shown only for a chosen option (no `visibleIf` on a select
  question, on the field or its panel), and its prompt does not ask to justify the selection;
- **(b) AIA justification**: everything else. These reveal the selected answer and are dropped.

### (a) kept
| field | prompt |
|---|---|
| projectDetailsTitle, projectDetailsProgram, projectDetailsDescription | title, departmental program, project description |
| businessDrivers3 | client needs the system addresses and how |
| businessDrivers4 | expected public benefits |
| businessDrivers6, 6A–6D | expected improvements; program indicators, current performance, expected change |
| businessDrivers7 | how the system stays confined to the client need |
| businessDrivers8 | trade-offs between client interests and program objectives |
| decisionSector3 (and its old location impact4*) | the decision(s) being automated |
| impact20 | criteria used to evaluate client data and operations applied |
| impact21 | output produced by the system |
| impact31 | role of the system in the decision process |
| aboutAlgorithm6, aboutAlgorithm7 | the model used; why it was chosen |
| aboutDataSource13 | input data, its source and collection method |

*impact4 is a follow-up of impact3 in old versions, but the tool itself moves it to decisionSector3
on load, so it is treated as the same field (manual override, `MANUAL_A`).

### (b) dropped
- Every "Please describe why the impacts … are as per selected option" field (impact8, 10, 12, 14,
  16, 25 …), `projectAuthority2` ("why you have chosen"), `businessDrivers5B`, `impact28A`, etc.
- Every conditional follow-up of a scored/select question (`…-other`, `…A/B/Y/N` "Describe",
  "Specify", "If yes/no …": e.g. businessDrivers10/12, motivation-other, decisionSector2,
  aboutAlgorithm9A/11A/11B, aboutDataSource15Y–17Y, aboutSystem2/3C/4C/8A/12, impact3A/18A/18C/19I*/23/23N/27YN, riskProfile4B/8A).
- All fields on the Consultation, Data quality, Procedural fairness and Privacy pages
  (they document mitigation answers; e.g. privacyImplementation5 = the PIA title proves a PIA exists).
- Manual: aboutDataSource12 (PIB numbers state that personal information is used),
  admin fields (respondent, job, branch, ID, ADM name, Service ID, AIA number, consulted teams).

### Separate documents
Each input also carries `documents`: the open.canada.ca dataset description (`ckan_notes`) and each
supporting document that is not the AIA (GBA+ summaries, model descriptions), one entry per file
with provenance. A "supporting" file that is actually an AIA rendering (contains "Raw Impact Score" /
"Points: +" / "Section 1: Impact Level|Niveau d'impact") is dropped whole: 1 found (b8a34d1b, French
AIA PDF). The 2 DOCX "supporting" files of f77faef4 are AIA annexes; they have no file in
`data/interim/text`, so `build_inputs.py` skips them, **but `parse_aia.py` did extract them into the
interim `supporting_text` field** (143,602 chars). They never reach `inputs/`; never use interim
`supporting_text` as model input. (This corrects the earlier "no extracted text" wording; audit round 2, L-b.)

### Documents whose presence reveals the level (audit round 2, M-A)
The Directive on Automated Decision-Making requires a peer review from impact level II, so a
peer-review report or summary is published only for level II systems: **10 of 39 AIAs have one,
all 10 level II, 0 of 16 level I**. In the old C-ext CV pool, "peer-review file present ⇒ level II"
scored 12/12. Every peer-review file (matched by file name, EN/FR, or a title in the first 300 chars)
is now **excluded whole** and recorded in the sidecar `data/interim/inputs_excluded.json` (file, reason,
raw length; no text), outside `data/interim/inputs/` (audit round 3, L-1). The sidecar is metadata, **never model input**. 20 files from 10 AIAs are excluded.

### Level sentences
Every kept text (fields and documents) is normalised first (PDF line wraps joined into one line per
paragraph, paragraphs split on blank lines), then split into sentences. A sentence is dropped if it
- names an impact level or score: "impact level", "level of impact", "level I–IV / 1–4",
  "low/moderate/high/very high (impact) level", "N out of 4 / N sur 4", "niveau d'incidence/d'impact",
  "niveau I–IV / 1–4", "niveau faible/modéré/élevé", "(modéré)", "incidence de 2", any "score",
  "pointage", "cote d'incidence/d'atténuation/actuelle";
- mentions a peer review at all ("peer review", "examen/évaluation par les pairs"; e.g. dataset
  descriptions that list "the Peer Review Summary"), since that also reveals level II;
- says a notice, human-in-the-loop or peer review was required/mandatory/had to/must/a dû/doit.
Ordinary sentences such as "level of difficulty", "officers are required to review…" and "niveau postsecondaire" are kept
(tested). The old line-based regex stopped at a line break and left fragments of a peer-review summary sentence
that states the impact level and the resulting peer review (c088f841); this sentence and its
French twin are now removed (c088f841's peer-review files are also excluded as a whole).
Re-check after the fix: no input contains "peer review", "impact level" or "niveau d'incidence";
the remaining "level"/"niveau" hits are ordinary uses (complexity, study level, risk level of cargo).

PII redaction (`redact_pii.py`) runs automatically at the end of `build_inputs.py`; names are read
from the untouched raw exports, so a re-run on already-redacted interim files still finds them.
Re-running the build is idempotent.

## Counts after the M-A fix (leakage-free total = (a) fields + documents)
- **≥ 2,000 chars: 27 of 39 AIAs (was 29); 27 of the 32 JSON AIAs (unchanged).** b8a34d1b and
  c839bedc (PDF-only) fall below because their peer-review files are gone.
- (a) fields alone ≥ 2,000 chars: 23 of 32 JSON AIAs (unchanged). **Documents alone ≥ 2,000: 9 of 39
  (was 17)**: 1257e5c1, 452e10be, 6b429c8e, 94d9dd91, b4a417f7, b92cbf7b, d24ae2dd, daa9ca66, f028d40f.
- Below 2,000 chars: JSON AIAs 9addf54a, aafdfbcd, ad4be3b8, cea9985f, d41f9ec2; PDF-only 44fe9b0d,
  7612202f, 89898244, b8a34d1b, c839bedc, eed746a8, f77faef4.
- Evaluation sets (`eval/scripts/set_counts.py`, same rules as eval-plan v1.1):
  - C-narr CV pool unchanged: 25 AIAs / 8 departments / 1,018 items; ≥ 2,000 chars of
    (a)+documents: 20 AIAs / 7 departments / 837 items.
  - **C-ext CV pool: 6 AIAs / 2 departments / 250 items (cic 3, esdc-edsc 3), levels I:4 / II:2**
    (was 12 / 4 / 501). C-ext lock-box: 3 AIAs (unchanged).
  - Consequence: Gate C1 (≥ 12 C-ext CV AIAs from ≥ 4 departments) **fails** on the current data.
- Downstream: the catalogue shortlist is rebuilt from these inputs (`build_catalog.py`): `impact5`
  drops out (evidence in 11/32 → below the threshold), so the shortlist is 10 questions, not 11.

## Leakage probe (`pipeline/leak_probe.py` → `reports/leak_probe.md`)
Single-feature AUC, level II positive, flag if max(AUC, 1−AUC) > 0.9, on exactly what the model reads.
- C-narr (25): nothing flagged; highest is input length 0.71. Keywords "peer review", "impact level":
  0 hits; "level" 0.51, "niveau" 0.50.
- C-ext (6: I 4 / II 2): nothing flagged, but supporting-document present, GBA+ present and input
  length each reach 0.875 (GBA+ file in 1/4 level I and 2/2 level II). With 6 AIAs this is one AIA
  away from 1.0; treat it as an open risk and add a "document present ⇒ II" baseline if C-ext is scored.
- Reference (not input): "peer-review file published" separated C-ext at 1.000 and C-narr at 0.735
  before the fix.

## Wording change Gate C needs (proposed wording for a future v1.2 of the protocol)
`docs/eval-plan.md` §5.3, "Gate C allows claiming" paragraph (lines ~269–272). Replace

> the component was validated on independent non-AIA documents for 12 published AIAs from 4
> departments, and confirmed once on a temporal hold-out of 7 later AIAs, levels I–II, English only.

with

> the component was validated on non-AIA documents published with the AIA (dataset description and
> supporting files other than peer-review reports, after level-sentence redaction; not independent
> of the AIA team) for 6 published AIAs from 2 departments, and confirmed once on a temporal hold-out
> of 7 later AIAs, levels I–II, English only.

and in §2 (C-ext real counts) and C1 replace "C-ext CV pool **12 AIAs / 4 departments / 501 items**
(cic 7, esdc-edsc 3, tc 1, cbsa-asfc 1)" with "C-ext CV pool **6 AIAs / 2 departments / 250 items**
(cic 3, esdc-edsc 3; levels I:4 / II:2) after the M-A fix (peer-review documents excluded)". Because C1
then fails, the plan must either withdraw Gate C (no TRL 4 claim) or amend it in v1.2 **before** any
C-ext result is seen (e.g. add C-ext data from departmental pages, PIA/GBA+ summaries), and add the
document-type baseline (level II iff a supporting document / GBA+ file is present) next to the level
metric and the level-correlated questions.

## Limits
- Class (a) text is still written by the AIA team inside the AIA form, so it can echo answers
  implicitly (e.g. a data description that says "personal information"). It is the C-narr condition
  of eval-plan.md, not C-ext. Only `documents` approximate C-ext.
- The (a)/(b) rule is mechanical; a human spot-check of 10 inputs before the teacher pilot is advised.
- Level confound: peer-review files and peer-review sentences are removed, but on the 6-AIA C-ext pool
  "any supporting document / GBA+ file present" and input length still reach AUC 0.875 against the level
  (`reports/leak_probe.md`). Report a document-type baseline beside every level or level-correlated result.
