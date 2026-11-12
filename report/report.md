---
title: "Pre-filling Canada's Algorithmic Impact Assessment"
subtitle: "A corpus of 39 published assessments, version-aware score reproduction, and a pre-specified evaluation protocol"
author:
  - name: Jonathas Wilbur Ferreira
    affiliation: Independent Researcher
date: 2026-11-05
version: "Technical report, v1.0.0"
abstract: |
  Canada's Directive on Automated Decision-Making requires federal institutions to complete, approve and publish an
  Algorithmic Impact Assessment (AIA) questionnaire before deploying an automated decision system.
  Tools that pre-fill this questionnaire from system documentation could reduce the effort of the
  assessment, but we found no public benchmark to test them. This report describes three
  contributions toward such a benchmark and a pre-specified evaluation protocol. First, a corpus
  of 39 published AIAs from 11 federal departments and agencies, collected from open.canada.ca
  with provenance and SHA-256 pins; 32 of them carry machine-readable answers. Second, a
  version-aware re-implementation of the AIA scoring rule. Applied to the 32 machine-readable
  AIAs, it reproduces the published raw score and impact level for 31 (96.9 %), against 11 raw
  scores and 24 levels out of 32 with the current questionnaire alone. Third, a rule that builds
  model inputs without the AIA's own justification text, and a leakage probe showing that no
  single input feature separates level I from level II above an AUC of 0.9 (on the 6-AIA
  external-document pool three features reach 0.875, so that result is weak). Finally, the
  evaluation protocol is fixed before any model output exists. No model has been trained or
  evaluated. This report contains no accuracy figures.
keywords:
  - algorithmic impact assessment
  - automated decision-making
  - public sector AI governance
  - benchmark
  - pre-specified protocol
  - Canada
lang: en-CA
numbersections: true
geometry: margin=2.5cm
fontsize: 11pt
linkcolor: blue
urlcolor: blue
# licence of this report: CC BY 4.0
---

# Introduction

## The Directive and the AIA

The Treasury Board of Canada's *Directive on Automated Decision-Making* applies to automated
decision systems in production that are used to make an administrative decision, or a related
assessment, about a client (§5.1) [1]. It requires
an Algorithmic Impact Assessment (AIA) before such a system is put into production. The AIA is a
questionnaire published as an open-source web tool [2, 3]. Its answers produce a raw impact score,
a mitigation score and an impact level from I to IV. The impact level determines which requirements of the
Directive apply (§6.1.2, Appendix C). One of them is peer review (§6.3.7). Appendix C requires none
at level I. At levels II and III it requires consulting at least one qualified expert from a listed
category and publishing the complete review or a plain-language summary on a Government of Canada
website; level IV requires at least two [1]. This is the Directive as modified on 2025-06-24; most
AIAs in the corpus were filed under earlier versions, whose peer-review rules were not checked here.


Departments publish completed AIAs on the Open Government Portal (open.canada.ca) under the Open
Government Licence – Canada [4]. A published AIA usually contains the questionnaire export in JSON,
a PDF rendering of the results, and sometimes supporting documents.

## Why pre-filling matters

The current questionnaire has 295 answerable questions (`catalog/README.md`). A single filing sees
224 of them, because design-phase and implementation-phase pages are alternatives. Many questions ask
for facts that already exist in system documentation: what data the system uses, whether it uses
personal information, which other systems it connects to. A tool that reads the documentation and
proposes an answer, an evidence sentence and a confidence, or abstains, could shorten the work. A
human would still validate every answer.

Before such a tool can be judged, three things are needed: labelled data, a way to check that the
labels are consistent with the published scores, and inputs that do not leak the answers. This report
provides all three and fixes the evaluation method in advance.

## Contributions

- **A corpus of 39 published AIAs** from 11 departments and agencies, with file-level provenance,
  licence and SHA-256 hashes (Section 3). 32 AIAs have machine-readable answers.
- **A questionnaire catalogue** of the current AIA tool: 295 questions with choices, weights,
  phase, kind (risk, mitigation, not scored) and section, plus the canonical survey of each tool
  version found in the corpus (Section 4).
- **A version-aware scorer** that reproduces the published raw score and level for 31 of 32
  machine-readable AIAs, and an analysis of the one remaining mismatch (Section 4).
- **A leakage-free input rule** and a **leakage probe** for the impact level (Section 5).
- **A pre-specified evaluation protocol** (v1.1b) with hypotheses, gates, metrics, sample sizes and
  a table of what each outcome would allow anyone to claim (Section 6).

What this report does not contain: no trained model, no teacher or student predictions, and no
accuracy, calibration or level-agreement result. Model evaluation is future work.

# Background and related work

**The AIA tool.** The questionnaire and its scoring code are maintained in the public repository
`canada-ca/aia-eia-js` under the MIT licence [3]. The Government of Canada's guidance page describes
the tool and its purpose [2]. The scoring rule is implemented in the tool's `store.ts`;
`catalog/scoring.md` documents it with line references.

**Risk frameworks in other jurisdictions.** The NIST AI Risk Management Framework 1.0 organises AI
risk work into four functions (Govern, Map, Measure, Manage) [5]. The U.S. Office of Management and
Budget memorandum M-25-21 (3 April 2025) sets direction for federal agency use of AI [6]. Both are
relevant because a pre-filled AIA answer may also serve as evidence under these frameworks. Section 8.4
points to a crosswalk.

**Data documentation.** We follow the spirit of datasheets for datasets [7]: Section 3 states how
the data were collected, what they contain, and their known gaps.

**Extraction models.** The project plans a small local extraction model of the GLiNER family [8] as
the student, trained from teacher labels. This is a design intention only; no model has been built.

We did not find a public benchmark that pairs published AIAs with their question-level answers for the
purpose of evaluating pre-filling tools. This statement reflects our search, not an exhaustive review.

# Corpus

## Collection

The fetch script `pipeline/fetch_aia.py` queries the CKAN API of open.canada.ca with
`package_search q="Algorithmic Impact"` [9] (`docs/data-notes.md`). Two kinds of result are excluded
because they are not system AIAs: the blank AIA tool dataset and the Government of Canada AI Register.
Every downloaded file is recorded in `data/SOURCES.csv` with its dataset id, department, date,
resource id, format, URL, licence, language tag, SHA-256 hash and size.

## Counts

All figures in Table 1 come from `docs/data-notes.md`, generated by `pipeline/aia_stats.py`.

Table: Table 1. Corpus summary.

| Item | Value |
|---|---|
| Published AIA datasets | 39 |
| Departments and agencies | 11 |
| Files downloaded | 165 (26.4 MB, 0 download errors) |
| File formats | PDF 112, JSON 42, DOCX 4, HTML 4, CSV 3 |
| Licence | Open Government Licence – Canada on all 165 files |
| AIAs with machine-readable answers (tool JSON export) | 32 of 39 |
| AIAs published only as PDF/DOCX | 7 |
| Impact level found | 39 of 39: level I 16, level II 23 |
| Raw impact score found | 39 of 39 (min 25, median 39, max 63) |
| Tool versions of the JSON exports | v0.10.0 20, v0.9.1 9, v1.0.1 2, v0.9 1 |
| Primary language of JSON free text | English 30, French 2 |

Publication years (dataset metadata): 2018: 1, 2020: 1, 2021: 3, 2022: 7, 2023: 3, 2024: 10,
2025: 11, 2026: 3.

Departments: Immigration, Refugees and Citizenship Canada (IRCC) 13; Employment and Social
Development Canada (ESDC) 9; Canada Border Services Agency 4; Veterans Affairs Canada 3; Public
Services and Procurement Canada 2; Treasury Board of Canada Secretariat 2; Royal Canadian Mounted
Police 2; Public Health Agency of Canada 1; Transport Canada 1; Innovation, Science and Economic
Development Canada 1; Canadian Food Inspection Agency 1. IRCC and ESDC together hold 22 of 39 AIAs
[derived: 13 + 9 = 22].

The seven PDF/DOCX-only AIAs are 44fe9b0d, 7612202f, 89898244, b8a34d1b, c839bedc, eed746a8 and
f77faef4. For these, only the score and level are read; their answers are not parsed into question
ids.

Among the 32 machine-readable AIAs, 13 are level I and 19 are level II [derived from the
`published_level` column of `reports/g0_score_check.csv`].

## Answer coverage

Answered means a non-empty value in the published JSON (`docs/data-notes.md`). Each AIA answers
between 72 and 175 of the 295 questions (median 92). Many questions are conditional, so an empty
answer is often correct. By coverage band, 33 questions are answered in every AIA, 34 in
90–99 %, 27 in 50–89 %, 134 in 1–49 %, and 67 never. Design-phase pages are rarely filled: for example,
`fairnessDesign` has a mean coverage of 2.7 % against 43.4 % for `fairnessImplementation`. Most
published AIAs were filed at the implementation phase.

Seventeen answer keys in the published JSON files do not exist in the current questionnaire (for
example `aboutDataType1`, present in 30 files). They are kept apart as unmapped answers. This is a
first sign of questionnaire drift, treated in Section 4.

## Three kinds of free text

The corpus contains three kinds of text, and they are not equivalent as model input
(`docs/data-notes.md`):

1. **Free-text answers inside the AIA.** Present in all 32 JSON AIAs (length min 379, median 8,375,
   max 44,928 characters). These were written by the same team in the same form, and often justify
   the selected option. They leak answers.
2. **Text outside the AIA questionnaire**: the dataset description on open.canada.ca (39 of 39) and
   supporting documents such as GBA Plus summaries or model descriptions (14 of 39). Some of these
   files are themselves AIA annexes or peer-review reports, which leak the level (Section 5).
3. **The AIA rendered as PDF.** It contains the questions and the answers. It is used only to read
   the published score and level, never as input.

# Questionnaire versions and score reproduction

## The scoring rule

The rule below is taken from `catalog/scoring.md`, which cites the tool's `store.ts` at commit
`b6257338`. A question counts toward the score if it is a single-choice, dropdown or checkbox
question and its name or parent panel carries the suffix `-RS` (raw impact) or `-MS` (mitigation).
The weight of a choice is the number after the last hyphen of its value (`item3-4` weighs 4).
Checkbox questions sum the weights of the ticked choices. Hidden questions count toward the maxima.

Let $R$ be the raw impact score, $R_{\max}$ its maximum, $M$ the mitigation score and $M_{\max}$ the
mitigation maximum over both phase copies. Then

$$
C = \begin{cases} \operatorname{round}(0.85\,R) & \text{if } M \ge 0.8 \cdot M_{\max}/2,\\ R & \text{otherwise,} \end{cases}
$$

and the level is I if $C \le 0.25\,R_{\max}$, II if $C \le 0.50\,R_{\max}$, III if
$C \le 0.75\,R_{\max}$, and IV otherwise. Rounding follows JavaScript, so .5 rounds up.

## Versions

The repository history of the tool has 1,068 commits (`docs/g0.md`). The version string written into
each export changed five times: v0.9 (2021-03-11), v0.9.1 (2021-11-30), v0.10.0 (2023-01-28), v1.0.0
(2024-12-04) and v1.0.1 (2025-10-03). The scoring functions did not change across these versions;
only the survey file did. A version is therefore equivalent to its survey. For each version, the
canonical survey is the last revision before the next version bump. It is exported to
`catalog/versions/<version>/survey-enfr.json`.

Table 2 lists the maxima from `catalog/versions/manifest.json` and the cut-offs derived from them.

Table: Table 2. Score maxima per tool version and derived thresholds.

| Version | Scored questions | $R_{\max}$ | $M_{\max}$ | Level cut-offs I / II / III [derived] | Mitigation threshold [derived] |
|---|---|---|---|---|---|
| v0.9, v0.9.1 | 101 | 107 | 90 | 26.75 / 53.5 / 80.25 | 36 |
| v0.10.0 | 109 | 126 | 92 | 31.5 / 63 / 94.5 | 36.8 |
| v1.0.0, v1.0.1 | 160 | 167 | 154 | 41.75 / 83.5 / 125.25 | 61.6 |

Derivation: cut-offs $= (0.25, 0.50, 0.75) \times R_{\max}$; for example $0.25 \times 107 = 26.75$.
Mitigation threshold $= 0.8 \times M_{\max} / 2$; for example $0.8 \times 92 / 2 = 36.8$. The
v1.0.x values 41.75, 83.5, 125.25 and 61.6 also appear in `catalog/scoring.md`.

The same raw score can therefore give different levels in different versions. Without the
mitigation reduction, a raw score of 30 is level I in v0.10.0 ($30 \le 31.5$) but level II in v0.9.1 ($30 > 26.75$). The mitigation reduction
also matters. For 52b8574d (Treasury Board of Canada Secretariat, *Using artificial intelligence
(AI) to automate candidate evaluations in the staffing process's assessment phase*, v0.10.0),
$R = 33$ and $M = 37 \ge 36.8$, so $C = \operatorname{round}(0.85 \times 33) = \operatorname{round}(28.05) = 28 \le 31.5$:
level I, as published [derived from `reports/g0_score_check.csv`].

v1.0.0 is ambiguous: the 2025 questionnaire rewrite was made under that string. No published AIA
uses v1.0.0 (`catalog/versions/manifest.json`).

## Which version scored the published number

The score PDF prints `Version: x.y.z`. The check uses that version when it is known, and the
export's version otherwise (`docs/g0.md`). The two differ for two AIAs:

- **aafdfbcd** (Veterans Affairs Canada, *Automation Development to Support Disability Benefit
  Decision Making*): JSON v0.9.1, PDF v0.10.0. Scoring with v0.9.1 gives 56, level III; scoring with
  v0.10.0 gives the published 55, level II. The file was re-opened in v0.10.0 before printing.
- **cea9985f** (Treasury Board of Canada Secretariat, *ATIP Online Request Service*): the PDF prints
  "0.8", for which no survey snapshot was exported. The JSON version v0.9.1 is used, and it matches.

The scorer also reproduces two conversions the tool applies when an old file is re-opened: the
`aboutSystem1` value `item6-1` becomes `item6` from v0.9.1, and `impact4` moves to `decisionSector3`
from v0.10.0.

## Result

Truth is the published raw score and level read from the AIA PDF. Table 3 is computed by
`pipeline/g0_check.py --history` and summarised in `docs/g0.md`.

Table: Table 3. Score reproduction on the 32 machine-readable AIAs.

| Scorer | Raw score match | Level match |
|---|---|---|
| Current questionnaire (v1.0.1) applied to every AIA | 11/32 (34.4 %) | 24/32 (75.0 %) |
| Version-aware | **31/32 (96.9 %)** | **31/32 (96.9 %)** |

The mitigation score also matches in 32 of 32 AIAs with the version-aware scorer. Percentages:
$11/32 = 0.344$, $24/32 = 0.750$, $31/32 = 0.969$.

Table 4 breaks the version-aware result down by version. The stratum depends on which version label
is used; both views are shown.

Table: Table 4. Raw score and level both matched, by version stratum (version-aware scorer).

| Version | By scoring (PDF) version | By export (JSON) version |
|---|---|---|
| v0.9 | 1/1 | 1/1 |
| v0.9.1 | 8/8 | 9/9 |
| v0.10.0 | 20/21 | 19/20 |
| v1.0.1 | 2/2 | 2/2 |

Sources: `docs/eval-plan.md` §2 (scoring-version strata), `docs/g0.md` (export-version strata), both
re-tallied from `reports/g0_score_check.csv` (columns `version` and `json_version`).


The protocol in Section 6 sets a gate, G0, that requires the scorer to reproduce at least 90 % of
published levels overall and in every version stratum with at least 5 AIAs. On the figures above,
G0 passes. The protocol records this as pending a re-run by an independent reviewer
(`docs/eval-plan.md` §2).

## The remaining mismatch

**6b429c8e** (Employment and Social Development Canada, *Employment Insurance Machine Learning
Workload*, v0.10.0) is published as 30, level I. The JSON answers give 35, level II. The five points
come from `businessDrivers5` (+1), `businessDrivers11` (+2) and `impact30` (+2) (`docs/g0.md`).

The PDF's own answer table disagrees with the JSON. For the question "How effective will the system
likely be", the PDF shows *Very effective [Points: +0]*, while the JSON holds `item2-1` (+1). The PDF
and the JSON are therefore different edits of the assessment. A search over the survey history finds a
raw score of 30 only with survey revisions from March 2023, after the version string was set (2023-01-28) but
before the v0.10.0 release tag (2023-04-13); in those revisions the questions had other names.
The JSON uses the later names, so such an interim build does not explain the gap. We keep
the published level as truth and flag this AIA in every per-question analysis.

## What the reproduction shows

The low agreement of the current questionnaire (11 of 32 raw scores) is explained by questionnaire
drift between versions, not by errors in the published scores. Once each AIA is scored with its own
version, only one AIA differs, and for that AIA the published files disagree with each other. The
department answers in the JSON exports are therefore consistent with the published levels, which is a
precondition for using them as labels.

# Leakage-free inputs and the leak probe

## The problem

A published AIA contains its answers, and its free-text fields often explain the selected option. A
model that reads those fields copies the answer rather than assessing the system. A second leak is
less obvious: some documents are published only for certain impact levels.

## The input rule

`pipeline/build_inputs.py` builds one input per AIA (39 files) under `data/interim/inputs/`
(`docs/inputs.md`). A free-text field of the AIA export is kept as system documentation only if all
of the following hold: it is not on a mitigation page; it is not a follow-up shown only for a chosen
option; and its prompt does not ask to justify a selection. Kept fields include the project title,
program and description, the client needs and public benefits, the decision being automated, the
criteria and output of the system, its role in the decision, the model used and why, and the input
data and its source. Everything else is dropped. This includes every "please describe why the impacts
are as per selected option" field, every conditional follow-up, all fields on the consultation, data
quality, procedural fairness and privacy pages, and administrative fields.

Each input also carries separate documents: the dataset description and each supporting file that is
not the AIA. A supporting file that is itself an AIA rendering is dropped whole; one was found
(b8a34d1b, a French AIA PDF).

## Documents whose presence reveals the level

A peer-review report or summary is published only for level II systems in this corpus: 10 of 39 AIAs
have one, all 10 at level II, and none of the 16 level I AIAs (`docs/inputs.md`). The mere presence of
such a file predicts the level. Every peer-review file is therefore excluded whole; 20 files from 10
AIAs are recorded in a metadata sidecar that is never model input.

Kept text is also filtered at sentence level. A sentence is dropped if it names an impact level or a
score, mentions a peer review, or states that a notice, human review or peer review was required.
After the filter, no input contains "peer review", "impact level" or "niveau d'incidence".
Personal-information redaction runs at the end of the build.

## Input sizes after the fix

From `docs/inputs.md`:

- Inputs of at least 2,000 characters (kept fields plus documents): 27 of 39 AIAs, and 27 of the 32
  JSON AIAs. All seven PDF-only AIAs fall below the threshold.
- Kept fields alone of at least 2,000 characters: 23 of 32 JSON AIAs.
- Documents alone of at least 2,000 characters: 9 of 39 AIAs (17 before the peer-review exclusion).

## The leak probe

`pipeline/leak_probe.py` computes, for each candidate feature of the model input, the area under the
ROC curve (AUC) for separating level II (positive) from level I. Separation is
$\max(\mathrm{AUC}, 1-\mathrm{AUC})$. A feature is flagged if separation exceeds 0.9. For a binary
feature, AUC $= (\mathrm{TPR} + \mathrm{TNR})/2$ for the rule "present implies level II"
(`reports/leak_probe.md`). The probe runs on the two cross-validation pools of the protocol
(Section 6).

Table: Table 5. Leak probe, selected features (`reports/leak_probe.md`).

| Feature | C-narr pool (25 AIAs; I: 8, II: 17) | C-ext pool (6 AIAs; I: 4, II: 2) |
|---|---|---|
| Supporting document present | 0.504 (1/8 vs 2/17) | 0.875 (1/4 vs 2/2) |
| GBA Plus document present | 0.504 (1/8 vs 2/17) | 0.875 (1/4 vs 2/2) |
| Peer-review document in input | 0.500 (0/8 vs 0/17) | 0.500 (0/4 vs 0/2) |
| Input length (characters) | 0.706 | 0.875 |
| Keyword "level" | 0.511 | 0.625 |
| Keyword "impact level" / "niveau d'incidence" | 0.500 | 0.500 |
| *Reference, not input: peer-review file published* | *0.735 (0/8 vs 8/17)* | *1.000 (0/4 vs 2/2)* |

Values are separation; "present in I vs II" counts in brackets.

Example of the binary formula, C-ext, "supporting document present": TPR $= 2/2 = 1$, TNR
$= 3/4 = 0.75$, AUC $= (1 + 0.75)/2 = 0.875$ [derived; matches the table].

No feature of the model input is flagged in either pool. Before the fix, the presence of a published
peer-review file separated the C-ext pool perfectly (1.000) and the C-narr pool at 0.735.

The C-ext result is weak evidence of safety. With 6 AIAs, three features reach 0.875, one AIA away
from 1.0. A single AIA moves a binary AUC by up to $1/(2\,n_{\text{level}})$; with $n = 2$ level II
AIAs that is $1/4 = 0.25$ [derived from the formula in `reports/leak_probe.md`]. The protocol therefore
requires a "document present implies level II" baseline next to any level result on that pool.

## Limits of the rule

Kept fields are still written by the AIA team inside the AIA form and can echo answers implicitly,
for example a data description that says "personal information". Results on these inputs measure
reading an AIA narrative, not reading independent system documentation. The rule is mechanical; a
human spot-check of 10 inputs is advised before any model is run (`docs/inputs.md`).

# Pre-specified evaluation protocol

The protocol is `docs/eval-plan.md`, version 1.1b, dated 2026-11-05. It was written and amended
before any teacher, student or baseline output existed. Changes after the first result must be logged
with a date and reason and labelled *post hoc*. The freeze rests on the author's statement; no third-party registry was
used, so the public deposit of this report is the protocol's first external timestamp.


## Task

For each AIA question, a system reads one government AI system's documentation and returns a chosen
answer (one choice, or a set for checkbox questions), one evidence sentence, a confidence in [0, 1],
or ABSTAIN.

## Systems compared

The student (S) is a small fine-tuned extraction model trained on teacher labels over retrieved text
chunks. The teacher (T) is a large language model that labels the same chunks; it is an upper
reference, never ground truth. Baselines are the per-question majority answer learned on training
folds only (B-maj), a BM25 retrieval rule (B-bm25), and "always abstain" (B-abst).

## Items and input conditions

An item is one (AIA, question) pair. It is scored when the question is a closed-choice risk or
mitigation question, the department answered it, and the same question with the same choices exists
in the export's own questionnaire version. Counted by `eval/scripts/set_counts.py`: 1,451 items over
the 32 JSON AIAs (min 35, median 44, max 110 per AIA); by version v0.10.0 867, v0.9.1 329, v1.0.1 218,
v0.9 37. Sixty-four distinct questions occur; 37 "core questions" are scorable in at least 20 of the
25 cross-validation AIAs.

Two input conditions are never mixed:

- **C-narr** (allowed, weaker): the kept AIA fields plus separate documents (Section 5). Results are
  labelled "AIA-narrative input".
- **C-ext** (target, stronger): only the documents outside the AIA, and only for AIAs with at least
  2,000 characters of them.

Table: Table 6. Evaluation sets (`docs/eval-plan.md` §2–3, from `set_counts.py`).

| Set | AIAs | Departments | Items | Levels I / II |
|---|---|---|---|---|
| C-narr cross-validation pool | 25 | 8 | 1,018 | 8 / 17 |
| C-narr pool, inputs ≥ 2,000 characters (sensitivity stratum) | 20 | 7 | 837 | — |
| C-ext cross-validation pool | 6 | 2 | 250 | 4 / 2 |
| Lock-box (temporal hold-out) | 7 | 4 | 433 | 5 / 2 |

Consistency check [derived]: $25 + 7 = 32$ AIAs and $1{,}018 + 433 = 1{,}451$ items.

## Splits

The unit of independence is the system: versions of the same system share a fold. Folds are
leave-one-department-out, which gives 8 outer folds on C-narr (the IRCC fold holds 11 of 25 AIAs).
Everything tuned is chosen on inner folds. The most recent 20 % of the JSON AIAs by dataset date,
$\lceil 0.2 \times 32 \rceil = 7$, form a lock-box. Its label lines are hashed in `docs/lockbox.sha256` (created 2026-11-05, before any
model output) and it is evaluated once.

The lock-box cannot guard against memorisation. Only one AIA is dated after the planned teacher model's
stated knowledge cutoff (June 2026) (b8a34d1b, 2026-08-14), and it has no question-level labels. Four replacement checks
are pre-specified: a no-input probe (M-a), the gain from reading the input (M-b), a counterfactual
edit that should flip the answer (M-c, at least 40 items from at least 8 AIAs), and paraphrase
invariance (M-d).

## Metrics

All metrics are implemented in `eval/metrics.py` (NumPy only, 28 unit tests on synthetic data). They
include accuracy at full coverage, per-question macro-F1, the risk–coverage curve and its area
(AURC), selective accuracy at a coverage level, calibration (adaptive ECE, Brier score, calibration
slope and intercept), the evidence verbatim rate, human-judged evidence correctness, impact-level
agreement, and lift over the majority baseline.

Confidence intervals use a cluster bootstrap over AIAs, $B = 10{,}000$, seed 20261105, with both
percentile and BCa intervals; a gate passes only if both bounds pass. With about 40 items per AIA and
an intra-AIA correlation of 0.05–0.2, the design effect is 3.0–8.8 (assuming equal cluster sizes; real clusters hold 35–110 items, which
raises it), so the 25 C-narr AIAs behave like about 114–339 independent items.

Calibration thresholds are stated relative to a null-ECE, because ECE is biased upward at small $n$.
A perfectly calibrated model shows a 95th-percentile ECE of 0.126 at $n = 40$, 0.094 at $n = 100$ and
0.042 at $n = 1{,}000$ (`eval/scripts/sample_size.py`; simulated with confidences uniform on [0.6, 1]
and $\lfloor n/30 \rfloor$ equal-mass bins clamped to 2–10; about 0.13 at $n = 40$ depending on the draw).

The level metric is reported, never gating. Truth has levels I and II only, and "always level II"
already scores 17/25 = 0.68 [0.48, 0.83] on the C-narr pool and 19/32 = 0.59 [0.42, 0.75] on all
JSON AIAs.

## Primary endpoints and gates

Four primary endpoints are fixed: P1, selective accuracy of S at coverage 0.5 and its lift over
B-maj; P2, S minus B-maj on mean macro-F1 over the 37 core questions, and S minus B-bm25 on AURC; P3,
level agreement (reported only); P4, human-judged evidence correctness. The three "beats baseline"
tests are Holm-adjusted at family-wise $\alpha = 0.05$.

- **Gate G0** (scorer): at least 90 % level reproduction overall and per version stratum with at
  least 5 AIAs. Passes on current data (Section 4), pending independent re-run.
- **Gate A** ("worth continuing", internal only): KILL rules after a 50-item teacher pilot and after
  the first student run. For example, the pilot stops if teacher selective accuracy at 0.5 is below
  0.75, does not beat B-maj, does not gain from reading the input, or quotes evidence verbatim less
  than 80 % of the time.
- **Gate B** (proof-of-concept gate, C-narr): all of B1–B8 on outer folds. Among them: at least 20
  AIAs from at least 6 departments and 800 items (available 25 / 8 / 1,018); S selective accuracy at
  0.5 with a lower bound of at least 0.75; a positive lower bound on S minus B-maj for both macro-F1
  and selective accuracy; human-judged evidence correctness with a Wilson lower bound of at least
  0.60 on at least 100 items; a calibration-slope lower bound of at least 0.5; and a verbatim-evidence
  lower bound of at least 0.90.
- **Gate C** (C-ext plus lock-box): **suspended**. After the peer-review exclusion, the C-ext pool has
  6 AIAs from 2 departments, below its own minimum of 12 AIAs from 4 departments. It may return only
  through a v1.2 amendment that adds external documents, before any C-ext result is seen.

## Human labels and the circularity guard

Ground truth is only the department's published answers and the author's own labels. Teacher outputs
are training data, never truth. No model from the teacher's family is used as a judge. Human
labelling is blind to the system that produced each item. The plan requires 195 judged items
(evidence correctness, answerability, an intra-rater repeat, and a truth audit) plus 80 prepared
perturbation inputs, estimated at about 7 hours in sessions of at most one hour. A fresh reviewer must
reproduce every reported number to the third decimal from saved predictions.

## What each outcome allows anyone to claim

The protocol fixes the wording of claims before results exist (`docs/eval-plan.md` §5.3–5.4).

Table: Table 7. Claims table (abridged from `docs/eval-plan.md` §5.3).

| Outcome | What may be said |
|---|---|
| G0 only (current state) | "Our scorer reproduces the published impact level of 31 of 32 published AIAs across 4 tool versions." Nothing about models. |
| Gate A passes | Nothing external. Internally: worth continuing. |
| Gate B passes | A scoped proof-of-concept sentence: C-narr input, 25 AIAs from 8 departments, levels I–II, English only (French not tested; 2 French AIAs reported individually), with selective accuracy and lift over the majority baseline and their intervals. |
| Gate B fails | "Proof of concept not demonstrated", with every number reported. |
| Gate C | Not claimable: suspended on current data. |
| Any outcome | Never "compliant", never "correct", never French, never levels III–IV. |

The current state of this work is the first row.

# Limitations

- **No model results.** This report evaluates data, a scorer and an input rule. It says nothing about
  how well any model pre-fills an AIA.
- **Small sample.** 32 AIAs carry question-level labels. Per-question results will be descriptive
  only: at $n = 25$ and $\hat p = 0.8$ the Wilson half-width is about ±0.15 (`docs/eval-plan.md` §8).
- **No high-impact systems.** All 39 AIAs are level I (16) or II (23). The highest published raw score
  is 63, which equals $0.50 \times 126$, the level II upper cut-off of its version [derived:
  eaeb269c, Canada Border Services Agency, *Client Reporting and Engagement System (CRES)/ReportIn*,
  v0.10.0, `reports/g0_score_check.csv`]. Nothing can be said about levels III–IV.
- **Selection bias.** Only published AIAs are seen; systems whose AIA is not (yet) published, or that
  fall outside the Directive's scope, are absent. IRCC and ESDC hold
  22 of 39 AIAs and 17 of the 25 cross-validation AIAs.
- **Labels are self-reported.** Department answers are unaudited. One example is noted in
  `catalog/README.md`: 1257e5c1 (IRCC, *Passport Program Facial Recognition System*) states that
  children under 16 were excluded but answered `riskProfile3` "No". The protocol measures agreement
  with departments, not correctness.
- **Questionnaire drift.** Four tool versions are present; 17 answer keys are absent from the
  current questionnaire; per-question labels for older AIAs are partial.
- **One unresolved mismatch.** 6b429c8e's published PDF and JSON are different edits.
- **Input leakage is reduced, not eliminated.** C-narr text is written inside the AIA form. The C-ext
  pool is too small for a reliable leak probe.
- **Language.** Only 2 JSON AIAs have French primary text. French performance is untestable.
- **Text extraction.** PDF text comes from `pdftotext -layout` and can lose table order; DOCX text is
  raw XML text.
- **No real system documentation.** Departments do not publish design documents or model cards; the
  external text is short summaries.

# Data, code and licences

## What the repository redistributes

The repository redistributes **derived tables only**:

- `data/aia_answers.jsonl`: one row per machine-readable AIA (32 rows) with the structured choice
  answers keyed by question id;
- scores and levels (published and recomputed) and per-AIA metadata;
- the questionnaire catalogue (`catalog/`), including each version's survey;
- `data/SOURCES.csv`: provenance for each source file, with URL and SHA-256 hash;
- reports (`reports/`) and this document.

Raw files (PDF, DOCX, JSON exports, CSV, HTML) and free text are **not redistributed**. This avoids
re-publishing personal information that may appear in the records; such information is not covered by
the Open Government Licence (`NOTICE.md`). The scripts re-download every raw file from open.canada.ca
and check it against its SHA-256 pin; `make` stops if any file differs from its pin.


## Licences

- **AIA data**: contains information licensed under the Open Government Licence – Canada [4]. Use of
  the data does not imply endorsement by the Government of Canada.
- **AIA questionnaire and scoring logic**: derived from `canada-ca/aia-eia-js` [3], MIT licence,
  Copyright (c) 2019 Government of Canada. The full licence text is in `NOTICE.md`.
- **Repository code**: MIT licence (`LICENSE`). **This report, the crosswalk and the docs**: CC BY 4.0.

## Reproducibility

The released repository is laid out as `pipeline/`, `eval/`, `catalog/`, `data/` (derived tables
only), `reports/`, `crosswalk/`, `report/` and `scripts/`. All Python is run with `python3 -I`.

Offline check of the score reproduction, from the released derived table only:

```sh
python3 -I scripts/verify_scores.py
# expected: raw score and level match for 31 of 32 AIAs; mismatch 6b429c8e
```


Main pipeline: it clones the official tool at the pinned commit, re-downloads every source file and
checks the SHA-256 pins, then runs the G0 check, the input build, the leak probe, the corpus counts and
the evaluation-set counts (tested from scratch on 2026-11-05: all 165 pins matched and the outputs were
identical to the released ones):

```sh
make reproduce
```

Individual steps, in order:

```sh
make vendor                               # official tool at the pinned commit
python3 -I scripts/fetch_pinned.py        # re-download the pinned files, check SHA-256
python3 -I pipeline/parse_aia.py          # parse JSON/PDF/DOCX (needs pdftotext)
python3 -I pipeline/redact_pii.py         # PII redaction of the parsed files
python3 -I pipeline/aia_versions.py export  # optional; needs the tool's full git history
python3 -I pipeline/aia_stats.py          # corpus counts
python3 -I pipeline/g0_check.py           # score reproduction -> reports/g0_score_check.csv
python3 -I pipeline/build_catalog.py      # questionnaire catalogue
python3 -I pipeline/build_inputs.py       # leakage-free inputs (+ PII redaction)
python3 -I pipeline/leak_probe.py         # -> reports/leak_probe.md
python3 -I eval/scripts/set_counts.py     # evaluation set counts
python3 -I eval/scripts/sample_size.py    # sample-size and null-ECE figures
```

Tests:

```sh
python3 -I -m unittest discover -s pipeline/tests
python3 -I -m unittest discover -s eval/tests
```

Offline, 19 of the 46 pipeline tests are skipped until `make vendor data` has run. `eval/` needs numpy.
`pipeline/aia_versions.py export` and `g0_check.py --history` (the released CSV's last column) need a full,
non-shallow clone of canada-ca/aia-eia-js at `data/interim/aia-history/repo`; no script creates it.
The catalogue test cuts the scoring functions out of the tool's `store.ts`, runs them under Node.js on
29 synthetic answer sets (after `make vendor`, with Node.js installed), and checks that the Python scorer gives identical output
(`catalog/scoring.md`).

## Crosswalk to NIST AI RMF 1.0 and OMB M-25-21

The crosswalk has 57 rows (`crosswalk/aia_nist_omb_crosswalk.csv`): 43 rows for AIA questionnaire
sections, 13 rows for U.S. practices with no direct AIA question, and 1 row for an AIA-only item.
Each row cites AIA question ids and short exact quotes from both U.S. documents, and grades the match
as strong (the same obligation), partial (the same topic) or none. Against NIST AI RMF 1.0 there are
5 strong, 35 partial and 17 none; against M-25-21 there are 2 strong, 32 partial and 23 none. The six
rows with a strong match are purpose and benefit, scope confinement, environmental sustainability,
performance across identity factors, monitoring (all NIST) and open-data disclosure (OMB). An
independent check of 30 rows led to corrections in seven rows before release. The mapping also shows differences in kind. M-25-21 does not grade risk by
degree of automation, while the AIA scores full automation as riskier; whether the memo's practices
apply at all depends on the AI output being a "principal basis" for the decision. M-25-21 has no counterpart for notice and explanations to affected people, and
it leaves the privacy, security and confidentiality of training and input data out of its
definition of AI-use risk, while still asking for privacy impacts to be documented. Neither U.S. document has a general
opt-out to a human alternative; that practice was in M-24-10, which M-25-21 rescinded. The mapping
covers the questionnaire only, not the Directive. As of 2026-11-05, NIST states that AI RMF 1.0 is
being revised, and M-25-21 remains in force.

The directory `crosswalk/` maps sections of the AIA questionnaire to the functions and categories of
the NIST AI Risk Management Framework 1.0 [5] and to the requirements of OMB memorandum M-25-21 [6].
The mapping is a reading aid. It does not state that a completed AIA satisfies either framework.

# Provenance of the numbers

Every number in this report was either produced by a repository script (Section 8.3) or derived by
hand from such output and marked [derived]. Figures about the tool's git history (commit count,
version dates, survey-revision search) require a full clone of canada-ca/aia-eia-js, which the
release does not automate. The protocol's circularity guard (Section 6) forbids using a model from
the same family as the teacher to judge model outputs.

# References

[1] Treasury Board of Canada Secretariat. *Directive on Automated Decision-Making*.
<https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=32592> (accessed 2026-11-05).

[2] Government of Canada. *Algorithmic Impact Assessment*. Canada.ca.
<https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/automated-decision-making/algorithmic-impact-assessment.html>
(accessed 2026-11-05).

[3] Government of Canada. *aia-eia-js: Algorithmic Impact Assessment tool* (source code, MIT
licence). <https://github.com/canada-ca/aia-eia-js> (vendored at commit b6257338, accessed
2026-11-05).

[4] Government of Canada. *Open Government Licence – Canada*.
<https://open.canada.ca/en/open-government-licence-canada> (accessed 2026-11-05).

[5] National Institute of Standards and Technology. *Artificial Intelligence Risk Management
Framework (AI RMF 1.0)*. NIST AI 100-1, January 2023. <https://doi.org/10.6028/NIST.AI.100-1>

[6] Executive Office of the President, Office of Management and Budget. *M-25-21: Accelerating
Federal Use of AI through Innovation, Governance, and Public Trust*. 3 April 2025.
<https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf>

[7] Gebru, T., Morgenstern, J., Vecchione, B., Wortman Vaughan, J., Wallach, H., Daumé III, H., and Crawford, K. *Datasheets for Datasets*. Communications of the ACM 64(12), 2021. arXiv:1803.09010. <https://arxiv.org/abs/1803.09010>

[8] Zaratiana, U., Tomeh, N., Holat, P., and Charnois, T. *GLiNER: Generalist Model for Named Entity
Recognition using Bidirectional Transformer*. NAACL 2024. arXiv:2311.08526. <https://arxiv.org/abs/2311.08526>

[9] Government of Canada. Open Government Portal, search "Algorithmic Impact".
<https://open.canada.ca/data/en/dataset?q=Algorithmic+Impact> (accessed 2026-11-05).

