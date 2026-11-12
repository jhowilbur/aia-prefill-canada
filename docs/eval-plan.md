# Evaluation plan (pre-specified) — local AIA pre-fill

> Release note: this is the frozen protocol as written. References to `docs/audit-*.md` point to internal
> review notes that are not part of this release. TRL wording follows the standard Technology Readiness
> Level scale; no gate has been run and no TRL is claimed.

> **Frozen 2026-11-05 (v1.1b) by the author before any model output was seen.** The teacher pilot and hand-labelling have not been run.

Status: **v1.1b, 2026-11-05** (amends v1.0 and v1.1 of the same day), written before any teacher or
student output exists. **No model result of any kind had been produced when v1.1 was written**
(no teacher pilot, no student run, no baseline scored), nor when v1.1a/v1.1b were written; see
"Changelog v1.0 → v1.1" at the end. v1.1b was frozen on 2026-11-05.
Author: Jonathas Wilbur Ferreira. Any change after the first
result is seen must be logged in "Amendments" at the end, with the date and the reason, and
reported next to the results. Results that use an amended threshold are labelled *post hoc*.

Claim labels used below: **[measured]** = computed here by a script; **[derived]** = follows
by arithmetic or logic from stated inputs; **[read]** = read from a file or source named in
the line; **[assumption]** = my design call, open to overrule.

---

## 1. What is being evaluated

For every AIA question (catalogue `catalog/requirements.jsonl`, built from
`vendor/aia-eia-js/src/survey-enfr.json`), a system reads one government AI system's
documentation and returns: chosen answer (one choice, or a set for checkbox questions),
one evidence sentence, a confidence in [0, 1], or `ABSTAIN` ("unable to determine").

Systems compared (all see the same retrieved chunks unless stated):

| ID | System | Notes |
|---|---|---|
| S | Student: GLiNER2.5-small fine-tuned on teacher labels + top-k retrieved chunks | the thing we want to prove |
| T | Teacher: Claude Opus labels, same chunks | upper reference, not ground truth |
| T-full | Teacher with the whole document (optional, credits permitting) | ceiling of retrieval loss |
| B-maj | Majority answer per question, learned on training folds only; confidence = training frequency | strong for skewed questions |
| B-bm25 | BM25 retrieval (query = question + choice text) + rule: choice with the highest BM25 score in top-k chunks; confidence = softmax of score margin; abstain below a threshold tuned on inner folds | "no ML" baseline |
| B-abst | Always abstain | sanity floor for the level metric |

**Item set (v1.1, per-item inclusion) [assumption].** An item = (AIA, question). It is
scored when all hold: (1) the question is a `radiogroup`, `dropdown` or `checkbox` of kind
`risk` or `mitigation` in `catalog/requirements.jsonl`; (2) the department answered it in the
published JSON export; (3) the same id exists in the export's *own* questionnaire version
(`catalog/versions/<version>/survey-enfr.json`) with the same question type and the same set
of choice values, and every answered value is one of them. `comment` and `text` fields are not
scored. Unanswered conditional questions are not items (no truth). Rule implemented and counted
by `eval/scripts/set_counts.py` **[measured]**: 1,451 items over the 32 JSON AIAs (min 35 /
median 44 / max 110 per AIA); by version v0.10.0 867, v0.9.1 329, v1.0.1 218, v0.9 37; 64
distinct questions occur at least once in the CV pool, **37 "core questions"** are scorable in
≥ 80 % (≥ 20/25) of CV AIAs. Per-question summaries (mean macro-F1, per-question tables) use
the 37 core questions; pooled item metrics use all items. Item counts are reported per version
stratum.

## 2. Ground truth and its known weaknesses

- Truth = the department's answers in published AIAs (open.canada.ca). These are
  **self-reported, unaudited** answers. The plan measures agreement with the department,
  not correctness. A human audit (Section 7) estimates how often the department answer is
  itself unsupported by the documents.
- **Questionnaire versions (v1.1).** The AIA questions and weights changed across tool
  versions v0.9, v0.9.1, v0.10.0, v1.0.1 (the scoring code did not; only the survey did,
  `docs/g0.md` **[read]**). Inclusion is per item (above), not per AIA.
  **Gate G0 (per tool version):** the version-aware scorer `pipeline/aia_score.score(survey,
  data, version=v)`, where v = the version printed on the score PDF when known, else the
  export's `version`, with that version's survey from `catalog/versions/`, must reproduce the
  published impact level for **≥ 90 % of the 32 JSON AIAs overall and ≥ 90 % within every
  version stratum with ≥ 5 AIAs**; smaller strata are reported, not gated. Status
  **[read, docs/g0.md, reports/g0_score_check.csv]**: 31/32 overall; by the scoring version v (PDF rule above, v1.1b round-3 L-e) v0.9 1/1,
  v0.9.1 8/8, v0.10.0 20/21, v1.0.1 2/2 (aafdfbcd: export v0.9.1, PDF v0.10.0; by export version
  the strata read 9/9 and 19/20) **[measured, `reports/g0_score_check.csv` column `version`]** → **G0 passes**, pending re-run by the independent reviewer.
  **Truth for the level metric = the published level**, never a recomputation. The one
  mismatch, 6b429c8e (PDF and JSON are different edits: published 30/level I vs 35/level II
  from the JSON), keeps its published level and is flagged in every per-question analysis
  (its item answers come from the JSON, which may not be the edit that was scored).
- **Input leakage (the biggest risk).** A published AIA contains the answers *and* the
  department's free-text explanations. If the model reads the AIA's own comment fields it
  is copying, not assessing. Two input conditions, never mixed:
  - **C-narr** (allowed, weaker): the class-(a) system-description fields of the AIA export
    plus the separate documents, exactly as built by `pipeline/build_inputs.py` and defined in
    `docs/inputs.md` **[read]**; never a justification or follow-up field, never the answer
    table. Class-(a) text is written inside the AIA form and can echo answers implicitly, so
    C-narr results are labelled "AIA-narrative input".
  - **C-ext** (target, stronger): documents that are not the AIA (privacy impact
    assessment summary, GBA+ summary, departmental web pages, peer-review reports, system
    documentation), collected by the data job with provenance in `data/SOURCES.csv`. In v1.1
    C-ext = the `documents` part of each input only (dataset description + non-AIA supporting
    files), and an AIA enters a C-ext set only with ≥ 2,000 chars of it.
  Every claim states which condition it rests on. Real counts **[measured, set_counts.py]**:
  C-narr CV pool 25 AIAs / 8 departments / 1,018 items (20 AIAs / 7 departments with
  ≥ 2,000 chars of (a)+documents, reported as a sensitivity stratum); C-ext CV pool **6 AIAs /
  2 departments / 250 items** (cic 3, esdc-edsc 3; levels I:4 / II:2) after the level-leak fix
  (v1.1a; was 12 / 4 / 501); C-ext lock-box 3 AIAs. Gate C, the only C-ext gate, is suspended (§5.3).
- **Answerability.** Many answers are not determinable from any public document. The
  department still answered them. Human label "answerable from the input: yes/no"
  (Section 7) lets us report accuracy on the answerable subset and check that abstentions
  fall mostly on unanswerable items.

## 3. Splits (no leakage)

1. **Unit of independence = the AIA's system**, not the item. Versions or updates of the
   same system (same AIA number, or title similarity ≥ 0.8 after normalisation, checked by
   hand) form one cluster and always land in the same fold **[assumption]**.
2. **Grouped by department (v1.1: leave-one-department-out).** Departments reuse wording
   and answer patterns, so folds are grouped by department. Only 4 CV departments have ≥ 2
   AIAs (cic 11, esdc-edsc 6, tbs-sct 2, vac-acc 2), so the rule of v1.0 already selects
   leave-one-department-out: 8 outer folds on C-narr (IRCC fold = 11 of 25 AIAs); 2 on C-ext (v1.1b: cic 3, esdc-edsc 3),
   descriptive only while Gate C is suspended.
   Per-fold n is reported with every number. Inner selection uses leave-one-department-out
   inside the training part (or leave-one-AIA-out when it has < 3 departments).
3. **Nested selection.** Everything tuned (abstention threshold, temperature scaling,
   retrieval k, BM25 threshold, prompt wording for the teacher) is chosen on inner folds of
   the training part only. The outer fold is touched once per final configuration.
4. **Lock-box temporal hold-out.** The most recent 20 % of the 32 JSON AIAs by dataset date
   (⌈0.2·32⌉ = 7, minimum 5) are set aside before any work, hashed
   (`docs/lockbox.sha256`, created 2026-11-05 before any model output), and evaluated **once** at the end **[measured]**: 7 AIAs,
   4 departments (esdc-edsc 3, cic 2, pwgsc-tpsgc 1, ic 1), 433 items, levels I:5 / II:2
   (CV pool is I:8 / II:17, so the lock-box is also a distribution-shift test). All 7 have
   ≥ 2,000 chars of C-narr input; only 3 have ≥ 2,000 chars of C-ext text.
   **Memorisation (v1.1).** Only one AIA is dated after the teacher's June 2026 cutoff
   (b8a34d1b, 2026-08-14) and it is PDF-only with no question-level labels **[measured]**, so
   no labelled AIA is guaranteed unseen by the teacher, and the lock-box cannot guard against
   memorisation. Replacement guard, all run on the pilot and on the CV folds, prompts frozen
   first:
   - **M-a, no-input probe:** teacher given only the question, choices, AIA title and
     department, no document. If its accuracy beats B-maj (paired, lower bound > 0), recall of
     public AIAs is shown and every T number is labelled "may include memorisation".
   - **M-b, input gain:** T(with input) − T(no input) on the same items, paired cluster
     bootstrap. Gate A requires a positive point gain on the pilot and lower bound > 0 on the
     full teacher run: a teacher that does not gain from reading is not reading.
   - **M-c, counterfactual perturbation:** ≥ 40 items (≥ 8 AIAs) where a rule-based edit of a
     decisive input sentence should flip the answer (for example "personal information is
     used" → "no personal information is used"; "fully automated decision" → "a human makes
     the final decision"), edits written and checked by the author before any model sees them.
     Report flip rate for T and S with Wilson CI; a memorising model keeps its answer.
   - **M-d, paraphrase invariance:** the same ≥ 40 inputs paraphrased without changing
     meaning (rule-based reordering and synonym edits, or a non-Claude model, checked by
     the author). Report answer stability for T and S. M-c and M-d apply to S too (its base model
     may also have seen public AIAs).
   T stays "an upper reference that may include memorisation" in every report.
5. **Teacher labels only for training folds.** The teacher labels documents of training
   folds for student training. Teacher predictions on test folds are made only to score T
   as a baseline and are never fed back into training.
6. Majority baseline frequencies are computed on the training folds only (unit-tested:
   `test_majority_baseline_uses_train_only`).

## 4. Metrics (implemented in `eval/metrics.py`)

| Metric | Definition | Unit of CI |
|---|---|---|
| Accuracy (full coverage) | correct / all items, abstain = wrong | cluster bootstrap over AIAs |
| Per-question accuracy + macro-F1 | per question across AIAs; macro-F1 averages per-choice F1 over choices present; abstain costs recall, not precision | Wilson (one item per AIA, so items are independent) — **descriptive only** |
| Mean macro-F1 over questions | the above averaged over questions | cluster bootstrap |
| Coverage | answered / all items | — |
| Risk-coverage curve, AURC | sort answered items by confidence; abstentions never covered and count as risk 1 in AURC so abstaining is not rewarded | cluster bootstrap |
| Selective accuracy @ c | accuracy on the ⌈c·n⌉ most confident answered items; NaN if coverage c is not reached | cluster bootstrap |
| Calibration | adaptive (equal-mass) ECE with ⌊n/30⌋ bins, clamped to 2–10; Brier score; Cox logistic calibration slope and intercept (no binning, best suited to small n); reliability table with Wilson CI per bin | cluster bootstrap |
| Null-ECE | 95th percentile of the ECE a *perfectly calibrated* model would show at the same n and confidences (simulation) | — |
| Evidence verbatim rate | the quoted sentence occurs in the input text (automatic hallucination check) | cluster bootstrap |
| Evidence correctness | human: supports / partial / no; strict = supports, lenient = supports+partial | Wilson |
| Impact-level agreement (v1.1) | level from the pre-filled questionnaire vs the **published** level; truth has levels I and II only, so this is binary: exact agreement, under-classification rate (II predicted as I), Cohen's κ, all next to the majority-level baseline ("always II": 17/25 = 0.68 in CV, 2/7 in the lock-box) | Wilson (one per AIA) |
| Lift over B-maj (v1.1) | per question and pooled: Δ = acc_S − acc_maj and error reduction (acc_S − acc_maj)/(1 − acc_maj), at matched coverage; published next to each question's training-fold majority share | paired cluster bootstrap (pooled); descriptive per question |
| Paired difference S − baseline | same items, same bootstrap draws | paired cluster bootstrap |

**Why these calibration choices.** ECE is biased upward at small n. With confidences
spread over 0.6–1.0, a perfectly calibrated model shows a 95th-percentile ECE of
0.126 at n = 40, 0.094 at n = 100, 0.081 at n = 150, 0.077 at n = 300 and 0.042 at
n = 1000 **[measured, `eval/scripts/sample_size.py`, seed 0/1]**. A fixed "ECE ≤ 0.05" rule
would fail a perfect model at our sample sizes, so thresholds are stated relative to the
null-ECE, and the calibration slope (which uses every point) carries the main weight.

**Level computation (v1.1).** The pre-filled level is scored with the AIA's own tool version
(G0 scorer): model answers replace the department's on scored items; scored questions outside
the item set keep the department's answer, and the share of the raw score they carry is
reported per AIA.
**Abstentions in the level metric.** A pre-filled questionnaire with gaps has no level.
Two fill policies, both reported: **conservative** (abstained raw-risk items take their
highest-risk choice, abstained mitigation items take their lowest; needs no oracle) =
primary; **oracle** (a human fills the gaps with the department's answer) = secondary,
it measures how much the answered part distorts the level.

**Bootstrap settings.** B = 10 000 for reported numbers (2 000 in tests), percentile
intervals, seed 20261105, resampling AIAs (clusters). Items inside one AIA are correlated.
With the real ~40 items per AIA and an intra-AIA correlation of 0.05–0.2, the design effect
is 3.0–8.8, so the 25 C-narr CV AIAs (~1,000 items) behave like ≈ 114–339 independent items
and the 6 C-ext AIAs (v1.1b; 250 items, m ≈ 42) like ≈ 28–81 **[derived, `sample_size.py`, scaled to 6 AIAs]**. With 25 or 6 clusters
the percentile bootstrap is itself optimistic; intervals are also reported as BCa, and a gate
passes only if both bounds pass. The AIA count limits every claim.

**Multiplicity.** Exactly four primary endpoints (P1–P4 below), Holm-adjusted at
family-wise α = 0.05 for the "beats baseline" tests (v1.1: the three tests S − B-maj
macro-F1, S − B-maj selective accuracy @ 0.5, S − B-bm25 AURC). Per-question results are descriptive;
no claim of the form "question X works" is made from them.

## 5. Pre-specified thresholds

Primary endpoints (all on outer folds, condition stated):
- **P1** selective accuracy of S at coverage 0.5 (and the coverage reached at 0.9), and its
  lift over B-maj at the same coverage.
- **P2** S − B-maj on mean macro-F1 over the 37 core questions (paired cluster bootstrap);
  also S − B-bm25 on AURC.
- **P3** impact-level agreement (conservative fill) next to the majority-level baseline.
  **Reported, never gating** (v1.1): truth has levels I–II only.
- **P4** evidence correctness (human, strict).

**Interval rule.** "Lower bound" = lower end of the 95 % interval. Gates pass on interval
bounds, never on point estimates alone. Declared exceptions (v1.1): (i) the lock-box checks in
Gate C, which are a one-shot confirmation on 7 AIAs (Wilson half-width ≈ ±0.24) and are
labelled as such; (ii) the 50-item pilot KILL rules, which can only stop work, never support a
claim.

**Majority baseline (v1.1).** B-maj is fitted per question on the training folds. Training
majority shares are high on many questions (for example aboutDataSource5 0.91, impact30 0.90,
aboutDataSource1 0.81 among JSON AIAs, `docs/audit-phase0.md` M3 **[read]**), so a high
absolute accuracy means little. Every accuracy claim is stated as lift over B-maj, and each
question's majority share is published beside its result. Per-question lift is descriptive
(n = 25 per question, Wilson half-width ≈ ±0.15 at p = 0.8 **[measured]**); the gating tests
are pooled. The number of core questions where S's point lift is > 0, = 0, < 0 is reported.

### 5.1 Gate A — "worth continuing" (after the 50-item teacher pilot, then after the first student CV run)

Pilot (teacher only, 50 items from ≥ 5 CV AIAs, C-narr):
- **KILL** if teacher selective accuracy at 0.5 is not above B-maj's at 0.5 (point lift ≤ 0),
  **or** the input gain M-b is ≤ 0 (point), **or** teacher selective accuracy at 0.5 < 0.75,
  **or** evidence verbatim rate < 0.80. 50 items give a Wilson half-width ≈ ±0.11 at p = 0.8
  **[measured]**, so the pilot can only catch a clear failure, not prove success.
- **CONTINUE** to the full teacher run otherwise. The full run repeats M-a and M-b with
  intervals; M-b lower bound ≤ 0 is a KILL.

First student CV run (C-narr CV pool, lock-box untouched):
- **KILL** if the lower bound of S − B-maj mean macro-F1 ≤ 0, **or** the upper bound of
  S − B-bm25 AURC ≥ 0, **or** S selective accuracy at 0.5 is more than 15 pp below T's (point).
- **CONTINUE** otherwise.

**Gate A allows claiming:** nothing outside the project. It only decides whether to spend more.

### 5.2 Gate B — TRL 3 evidence (proof of concept), condition C-narr

Reset to the real counts **[measured, set_counts.py]**. All must hold on outer folds:
| # | Criterion | Threshold |
|---|---|---|
| B1 | Data size | C-narr CV pool ≥ 20 AIAs from ≥ 6 departments and ≥ 800 scored items (available: 25 / 8 / 1,018); H1 ≥ 100 human-judged S evidence items **from C-narr inputs only** (v1.1b), ≤ 8 per AIA (capacity 25 × 8 = 200) |
| B2 | P1 | S selective accuracy @ 0.5: lower bound ≥ 0.75 |
| B3 | P1 + P2 vs majority | lower bound of S − B-maj > 0 on **both** mean macro-F1 (core questions) and selective accuracy @ 0.5, Holm-adjusted; lift and error reduction reported |
| B4 | P4 | evidence strict: Wilson lower bound ≥ 0.60 |
| B5 | Calibration (v1.1, interval-based) | calibration-slope lower bound ≥ 0.5 (confidence carries signal, not grossly over-confident) **and** upper bound of adaptive ECE ≤ null-ECE₉₅ + 0.05; point slope and ECE reported |
| B6 | Hallucination | evidence verbatim rate: lower bound ≥ 0.90 |
| B7 | P3 | level agreement and κ with Wilson CI next to "always level II"; reported, not gating |
| B8 | Memorisation | M-a, M-b, M-c, M-d reported for T and S |

**Gate B allows claiming:** "On 25 published federal AIAs from 8 departments (levels I–II,
English, mostly IRCC and ESDC triage systems), with input taken from the AIA's own
system-description fields and supporting documents, the tool answered AIA questions with
evidence and calibrated abstention: selective accuracy X [CI] at coverage 0.5, a lift of
Δ [CI] over the per-question majority baseline (Z [CI])." That is **TRL 3 (proof of concept)**.
It does not allow "validated", "accurate on AIAs in general", or any statement about levels
III–IV or French.

### 5.3 Gate C — limited TRL 4 evidence, condition C-ext plus the lock-box

> **v1.1a (2026-11-05, before any result): Gate C is SUSPENDED.** After the level-leak fix (`docs/audit-round2.md` M-A, `docs/inputs.md`), the C-ext CV pool is **6 AIAs / 2 departments / 250 items**, below C1. No TRL 4 claim of any kind is allowed on the current data. Gate C may be reinstated only in a v1.2 that adds C-ext data (e.g. departmental pages, PIA/GBA+ summaries), uses the corrected scope wording in `docs/inputs.md` ("not independent of the AIA team"), and adds the document-type baseline — all **before** any C-ext result is seen. Until then the highest claimable result is Gate B (TRL 3, C-narr).


Reset to the real counts. v1.0's Gate C (≥ 30 C-ext AIAs from ≥ 8 departments, ≥ 150 C-ext
evidence items, level agreement ≥ 0.80, French within 10 pp) is **unreachable with published
data** (C-ext had 12 CV AIAs from 4 departments in v1.1, 6 from 2 since v1.1a) and is withdrawn. The reset gate
below is kept as text for a possible v1.2 and is **SUSPENDED** (note above):

All of Gate B, plus:
| # | Criterion | Threshold |
|---|---|---|
| C1 | Data size | C-ext CV pool ≥ 12 AIAs from ≥ 4 departments (v1.1 had exactly 12 / 4; **available now 6 / 2 / 250 → C1 fails, Gate C suspended**); lock-box 7 AIAs hashed and untouched until the end; ≥ 90 human-judged evidence items from C-ext inputs (cap 8 per AIA; now 6 × 8 = 48 possible, so this also needs v1.2 data) |
| C2 | P1 on C-ext | S selective accuracy @ 0.5 lower bound ≥ 0.75 **and** lower bound of S − B-maj (selective accuracy @ 0.5) > 0 |
| C3 | P2 on C-ext | lower bound of S − B-maj mean macro-F1 > 0 and upper bound of S − B-bm25 AURC < 0 |
| C4 | Lock-box (C-narr, 7 AIAs, one shot, declared exception) | S selective accuracy @ 0.5 within 10 pp of its CV point estimate **and** point lift over B-maj > 0; CI reported; the 3 lock-box AIAs with C-ext text reported separately |
| C5 | P4 on C-ext | evidence strict point ≥ 0.85 and Wilson lower bound ≥ 0.75 (n = 90: ≥ 77/90 gives [0.77, 0.91] **[measured]**) |
| C6 | Abstention is meaningful | if ≥ 30 H1 items are labelled unanswerable: S abstains on them with Wilson lower bound ≥ 0.50 (≥ 21/30 gives 0.52 **[measured]**); if fewer than 30, "not tested" |
| C7 | Memorisation | M-c flip rate of S: Wilson lower bound ≥ 0.50; M-d stability of S ≥ 0.85 point |
| — | Level | not gating (levels I–II only) |
| — | French | **not testable**: only 2 JSON AIAs have French primary text (b4a417f7, f95dbd40, both IRCC; since v1.1a only b4a417f7 is in the C-ext CV pool), none in the lock-box; 2 AIAs from 1 department cannot support any comparison. v1.0's C7 is withdrawn; every claim says "English only; French not tested" and the 2 French AIAs are reported individually |

**Gate C allows claiming (only if reinstated by a v1.2 and passed; suspended now):** "TRL 4, retrospective laboratory validation, limited scope": the
component was validated on non-AIA documents (dataset descriptions and supporting files; not
independent of the AIA team, `docs/inputs.md`) for N published AIAs from M departments (v1.2 counts; 6 / 2 today, below C1), and confirmed once on a temporal hold-out of 7 later AIAs, levels I–II, English
only. The scope sentence is mandatory every time TRL 4 is written. Whether a given funder's TRL 4
definition accepts this scope is **unverified**; quote the definition being applied and have an
independent reviewer check the match. More C-ext data
(departmental web pages, PIA and GBA+ summaries per system) would widen the scope; it would
need a v1.2 amendment *before* it is scored.

**TRL 5 is not claimable from this project [derived].** TRL 5 asks for validation in a
relevant (simulated or real) environment. Retrospective scoring of published AIAs is a
laboratory test however good the numbers are. TRL 5 needs, in addition: a prospective trial on
documents of systems whose AIA is *not yet published*, run by people who really fill AIAs
(ATIP/AI governance staff), measuring time saved and error rate of the human-validated
questionnaire against an unaided group. That trial is a future step, not part of this plan.
At most say "TRL 3 (Gate B); TRL 5 trial designed" while Gate C is suspended; "TRL 4 (limited
scope)" only if a v1.2 reinstates Gate C and it passes.

| Outcome | What the author may say |
|---|---|
| G0 only | "Our scorer reproduces the published impact level of 31 of 32 published AIAs across 4 tool versions." Nothing about models. |
| Gate A passes | Nothing external. Internal: worth continuing. |
| Gate B passes | TRL 3 sentence above (C-narr, 25 AIAs / 8 departments, lift over majority). |
| Gate B fails | "Proof of concept not demonstrated"; report every number anyway. |
| Gate C passes | **Not claimable: Gate C is suspended on current data (v1.1a).** Highest claimable now: TRL 3 (Gate B). TRL 4 wording returns only if a v1.2 reinstates Gate C before any C-ext result and it passes. |
| any | Never TRL 5, never "compliant", never "correct", never French, never levels III–IV. |

### 5.4 What cannot be claimed at all with this data

- That a pre-filled AIA is **compliant** with the Directive on Automated Decision-Making,
  or that the tool performs any legal assessment.
- That the model is **correct**: only agreement with self-reported department answers is
  measured (plus a small human audit).
- Performance on **impact level III–IV** systems: all 39 published AIAs are level I (16) or
  II (23) **[read, data-notes.md; measured, set_counts.py]**, so no claim beyond levels I–II.
- Any level-agreement claim that does not show the "always level II" baseline beside it.
- Performance on **French** inputs (2 AIAs, untestable) or on departments other than the
  8 (C-narr) / 2 (C-ext) present; IRCC and ESDC are 17 of the 25 CV AIAs.
- Performance on **unpublished, internal or non-federal** systems (selection bias: only
  systems a department chose to publish are seen).
- Any **per-question** reliability statement (n per question ≤ 25 CV AIAs, Wilson
  half-width ≈ ±0.15 at p = 0.8 **[measured]**).
- **TRL 5**, or TRL 4 without the scope sentence of Gate C.
- **Time saved** or replacement of a human assessor (not measured here).
- Anything about the teacher's absolute quality: every labelled AIA predates its cutoff
  (possible memorisation, guarded only indirectly by M-a to M-d).

## 6. Circularity guard (Claude must not grade Claude)

1. Ground truth is only (a) the department's published answers and (b) the author's labels.
   Teacher outputs are **training data**, never truth, never an evaluation target for S
   (S is scored against department answers, not against T).
2. Evidence correctness, answerability and truth audits are judged by **the author only**. No
   LLM-as-judge from the Claude family. If a second rater is ever needed, use a human; a
   non-Claude model may be reported only as a separate, clearly labelled extra.
3. Human labelling is **blind to system**: S and T items are interleaved in random order
   with the system name hidden (`data/truth/human_batch_*.csv` stores a hashed system id;
   the key is in a separate file the author does not open while labelling).
4. Teacher prompts are frozen (hash recorded) before the outer folds are scored; no prompt
   change after looking at test-fold results.
5. The code that computes the metrics (`eval/metrics.py`) never calls a model.
6. A fresh reviewer (not the author of the pipeline) re-runs `eval/metrics.py` on the saved
   predictions and must reproduce every reported number to the third decimal.

## 7. Human-label protocol (the author)

**What to label** — one CSV row per item, shown: the AIA question (EN), its choices, the
system's chosen answer, the evidence sentence, and ±2 sentences of context from the input.

| Set | Items | Labels |
|---|---|---|
| H1 evidence + answerability | 150 answered items: 100 from S, 50 from T, all from **C-narr CV inputs** (v1.1b), stratified by AIA (≤ 8 per AIA; 25 × 8 = 200 possible) and question section, interleaved, system hidden. Gate B (B1, B4, B6) uses only these. | evidence: `supports` / `partial` / `no`; answerable from the input: `yes` / `no` |
| H1-ext (optional, v1.1b) | up to 48 S items from the 6 C-ext AIAs (≤ 8 each), labelled only if a v1.2 reinstates Gate C; reported separately, no minimum, never pooled into Gate B | same as H1 |
| H2 intra-rater repeat | 15 items of H1 shown again ≥ 1 day later, shuffled | same labels → Cohen's κ |
| H3 truth audit | 30 items where S or T disagrees with the department, with full input available | `department supported` / `model supported` / `neither` / `both possible` |
| H4 perturbation set (v1.1) | 40 counterfactual edits (M-c) written by the author from a list of decisive sentences, and 40 paraphrases (M-d) checked for unchanged meaning, before any model sees them | `answer should flip to …` / `meaning unchanged: yes/no` |
| **Total** | **195 judged items + 80 prepared inputs** | |

**Time estimate [derived].** At 1.0–2.0 min per item, 195 items take 3.3–6.5 h; H4 adds
40 edits at 2–3 min (1.3–2 h) and 40 paraphrase checks at ~1 min (0.7 h). Plan ≈ 7 h in
seven sessions of ≤ 1 h (fatigue degrades labels). v1.1b leaves the total unchanged: the 195
judged items still take ≈ 4.9 h at 1.5 min (3.2–6.5 h), ≈ 7 h with H4; the optional H1-ext adds
48 items, 0.8–1.6 h, only if Gate C is reinstated **[measured, `sample_size.py` v1.1b]**.
Gate B needs H1 ≥ 100 C-narr S items: at n = 100, B4 (Wilson lower ≥ 0.60) passes from 70/100
observed, half-width ≈ ±0.08 at p̂ = 0.8; with ≤ 8 items per AIA and intra-AIA correlation
0.05–0.2 the design effect is 1.35–2.4 (≈ 42–74 effective items), still above the 24 needed at
p̂ = 0.8 (41 at p̂ = 0.75) **[measured, `sample_size.py` v1.1b]**. Gate C (suspended) would need
≥ 90 C-ext items, which 6 AIAs cannot give (48 max).

**Instructions to the author (print on the label sheet).**
1. Judge only what the shown text says. Do not use what you know about the department.
2. `supports`: the sentence alone makes the chosen answer clearly right.
   `partial`: relevant but needs an extra step or assumption. `no`: irrelevant,
   contradicts the answer, or not in the text.
3. Answerable `yes` only if someone reading the input (not the AIA's answer table) could
   choose one option with reasonable confidence.
4. When unsure, choose the stricter label and add a note. Never look at which system
   produced the row.
5. Stop after 60 minutes or 50 items, whichever comes first.

**Quality bar.** Intra-rater κ (H2) ≥ 0.6 for the evidence label; if lower, rewrite the
instructions, relabel H1, and report both. A second human rater for 30 H1 items is
recommended before external use (inter-rater κ); not required for Gate B.

## 8. Minimum n per claim (Wilson 95 %, p̂ = 0.8 unless noted) [measured, `sample_size.py`]

| n | 95 % CI for p̂ = 0.8 | half-width | Allowed use |
|---|---|---|---|
| 10 | 0.49–0.94 | 0.23 | anecdote only |
| 7 | — | ≈ 0.24 (6/7: 0.49–0.97) | lock-box confirmation only (declared exception) |
| 6 | — | — | C-ext AIAs available since v1.1a (below Gate C's 12; Gate C suspended) |
| 25 | 0.61–0.91 | 0.15 | C-narr CV AIAs (Gate B); per-question n, descriptive only |
| 50 | 0.67–0.89 | 0.11 | pilot sanity check |
| 90 | (p̂ = 0.856: 0.77–0.91) | 0.07 | Gate C evidence claim on C-ext (suspended; 48 max today) |
| 100 | 0.71–0.87 | 0.08 | Gate B evidence claim (C-narr S items; B4 passes from 70/100) |
| 150 | 0.73–0.86 | 0.06 | full H1 |
| 245 | — | 0.05 | needed for ±5 pp claims |

Level agreement (one per AIA) is not gated in v1.1. For reference, "always level II" scores
17/25 = 0.68 [0.48, 0.83] on the CV pool and 19/32 = 0.59 [0.42, 0.75] on all JSON AIAs
**[measured]**; a level result is meaningful only against that.

## 9. Run order

1. Data job delivers AIAs → G0 per tool version (passed per `docs/g0.md`; reviewer re-runs)
   → `eval/scripts/set_counts.py` recount → freeze lock-box hash.
2. the author prepares H4 (M-c, M-d inputs); teacher prompts frozen and hashed.
3. Teacher pilot 50 items with and without input (M-a, M-b) → Gate A (pilot).
4. Full teacher labels on training folds → student training (nested CV) → Gate A (student).
5. Human labels H1–H3 (C-narr) → Gate B on CV; M-c, M-d scored. (H1-ext and Gate C only after a v1.2.)
6. Open the lock-box once → reported (C4 suspended with Gate C).
7. Independent reviewer reproduces numbers → report with every gate shown as pass/fail,
   including failures.

## 10. Files

- `eval/metrics.py` — all metrics (NumPy only).
- `eval/tests/test_metrics.py` — 28 unit tests on synthetic data, all passing
  (`python3 -I -m unittest discover -s eval/tests -v`) **[measured 2026-11-05]**.
- `eval/scripts/sample_size.py` — every sample-size and null-ECE number in this file.
- `eval/scripts/set_counts.py` (v1.1) — per-item inclusion rule, AIA / department / item
  counts per set, lock-box composition, French and post-cutoff counts, core questions.

## Changelog v1.0 → v1.1 → v1.1b (2026-11-05, before any result)

Made by the plan's author after the independent audit `docs/audit-phase0.md` (round 1) found
v1.0 infeasible with the real data, and after `docs/g0.md`, `docs/inputs.md`,
`docs/data-notes.md` and `reports/aia_question_coverage.csv` were produced. **At the time of
every change below no teacher, student or baseline output existed**: no model had been run,
no prediction file existed, and no gate had been evaluated. The changes are therefore
pre-specification amendments (made before any result), not *post hoc* changes. The v1.0 text is archived unchanged in
`docs/eval-plan-v1.0.md`, and its thresholds are quoted in this list so the difference is auditable.

| # | Audit item | v1.0 | v1.1 | Why |
|---|---|---|---|---|
| 1 | H1 | G0: current-survey scorer must reproduce ≥ 90 % of levels | G0 per tool version, ≥ 90 % overall and in each stratum with ≥ 5 AIAs; truth = published level; 6b429c8e flagged, keeps published level | survey drift across v0.9–v1.0.1 made the current scorer reproduce only 24/32 levels; the version-aware scorer gives 31/32 (`docs/g0.md`) |
| 2 | H2 | include an AIA only if its questions map 1:1 to the current survey | per-item inclusion (same id, type and choice values in the export's version and the catalogue); 37 core questions for per-question summaries | the 1:1 rule kept 2 of 32 AIAs; per-item gives 1,451 items |
| 3 | H4 | Gate B: ≥ 15 AIAs, ≥ 5 departments, either condition | Gate B on C-narr: ≥ 20 AIAs, ≥ 6 departments, ≥ 800 items (available 25 / 8 / 1,018) | C-ext has 4 departments, so Gate B is only reachable on C-narr |
| 4 | H4 | Gate C: ≥ 30 C-ext AIAs, ≥ 8 departments, ≥ 150 C-ext evidence items | Gate C "limited TRL 4": ≥ 12 C-ext AIAs, ≥ 4 departments, ≥ 90 C-ext evidence items, 7-AIA lock-box confirmation on C-narr | only 12 C-ext CV AIAs from 4 departments exist (`set_counts.py`); v1.0 Gate C was unreachable |
| 5 | M1 | post-June-2026 AIAs in the lock-box guard memorisation | no-input probe, input gain (in Gate A), counterfactual flip and paraphrase stability tests (M-a to M-d); T labelled "may include memorisation" | the only post-cutoff AIA (b8a34d1b) is PDF-only with no question labels |
| 6 | M2 | level gate C4: exact ≥ 0.80, LB ≥ 0.65, under ≤ 0.10, zero under by ≥ 2 levels; quadratic κ | level reported, never gating; binary metrics and κ next to "always level II" | truth has levels I–II only; "always II" already scores 0.68 in CV, and the ≥ 2-level clause was vacuous |
| 7 | M3 | B-maj beaten on mean macro-F1 only | B3/C2/C3 require lower bound of S − B-maj > 0 on macro-F1 and on selective accuracy @ 0.5; lift and error reduction reported per question beside the majority share | majority shares reach 0.78–0.91 on usable questions |
| 8 | L3 | B5: slope in [0.6, 1.4] and ECE ≤ null + 0.05, both point estimates | slope lower bound ≥ 0.5 and ECE upper bound ≤ null-ECE₉₅ + 0.05; B6 verbatim lower bound ≥ 0.90; explicit list of declared point-estimate exceptions | v1.0 contradicted its own "point estimates never pass a gate" rule |
| 9 | L4 | C7: French within 10 pp if ≥ 5 French AIAs | French declared untestable now; withdrawn | only 2 French JSON AIAs, 1 department |
| 10 | L2 | GroupKFold k = min(5, departments) | leave-one-department-out, per-fold n reported | 4 CV departments have ≥ 2 AIAs; the IRCC fold holds 11 of 25 |
| 11 | — | lock-box size and composition not known | 7 AIAs, 4 departments, levels I:5 / II:2, 3 with C-ext text | measured by `set_counts.py` |
| 12 | — | human labels 195 items, ≈ 5 h | + H4 perturbation set (80 prepared inputs), ≈ 7 h | needed by M-c / M-d |
| 13 | — | bootstrap percentile only | percentile and BCa, both bounds must pass | 12–25 clusters make percentile intervals optimistic |
| 14 | — | "what the author may claim" only for Gate B | claim table for every outcome; TRL 5 never; TRL 4 only with scope sentence | exact claim wording needed |
| 15 | round-2 M-A | Gate C at 12 C-ext AIAs / 4 departments | **Gate C suspended** (C-ext is 6 AIAs / 2 departments after the leak fix); highest claim = Gate B, TRL 3 | `docs/inputs.md`, `reports/leak_probe.md` |
| 16 | round-3 M-C (v1.1b) | H1: ≥ 90 of 100 S items from C-ext (96 possible) | H1 = 100 S + 50 T items from C-narr only (≤ 8 per AIA, 200 possible); Gate B rests on C-narr items alone; C-ext labelling optional (H1-ext, ≤ 48 items, Gate C only); time unchanged (≈ 4.9 h judged items, ≈ 7 h with H4) | C-ext has 6 AIAs, so ≤ 48 items; n = 100 gives B4 Wilson lower ≥ 0.60 from 70/100 (`sample_size.py` v1.1b) |
| 17 | round-3 M-C, L-2 (v1.1b) | §2, §3, §4, §5.3, §5.4, §8, §9 quoted 12 C-ext AIAs / 4 departments / 501 items, 4 C-ext folds, TRL 4 ceiling | 6 / 2 / 250 (`set_counts.py` re-run 2026-11-05), 2 C-ext folds, claim table and TRL 5 paragraph say TRL 4 is not claimable while Gate C is suspended; Gate C scope sentence uses the `docs/inputs.md` wording | stale counts after the leak fix; a reader must not read TRL 4 as reachable |
| 18 | round-3 L-e (v1.1b) | G0 strata quoted by export version (v0.9.1 9/9, v0.10.0 19/20) | strata by the stated scoring (PDF) version: v0.9.1 8/8, v0.10.0 20/21; G0 still passes | consistency with the G0 version rule |

Not changed: metrics code (`eval/metrics.py`), the circularity guard (Section 6), the
human-label instructions, the abstention fill policies, the bootstrap seed.

## Amendments after results

(none) — any change from here on is logged with date and reason, and the affected results are
labelled *post hoc*.
