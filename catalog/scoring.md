# AIA scoring rule (as implemented by the tool)

> Derived from canada-ca/aia-eia-js, MIT licence, © 2019 Government of Canada; see NOTICE.md.

Source: `vendor/aia-eia-js/src/store.ts`, canada-ca/aia-eia-js commit `b6257338` (2026-10-28),
survey-vue `^1.7.23`. Reproduced in `pipeline/aia_score.py`. `pipeline/tests/test_catalog.py`
cuts the functions out of `store.ts` itself, runs them under Node against 29 synthetic answer sets
and checks that the Python output is identical. It also checks the scored-question list and the
section tables.

Maxima for the current survey (printed by `build_catalog.py`, see `README.md`): raw impact **167**,
mitigation **154** (both phase copies), so the mitigation threshold is **61.6**.

## 1. Which questions count (`store.ts:321-329`, `37-47`, `81-111`)
- At the first update the tool builds `questionNames` from `result.getAllQuestions()` called without
  arguments. In survey-vue 1.7 that returns **every** question, including those hidden by a
  `visibleIf` on the question or its page.
- A question is kept if it is a `radiogroup`, `checkbox` or `dropdown` **and** its score type is > 1.
- Score type comes from the name suffix: `-RS` raw impact (2), `-MS` mitigation (3), `-NS` not scored (1).
  It checks the question's own name first, then its direct parent (the panel). No suffix means not scored.
  In the current survey every panel carries a suffix, so: Project Details are not scored, all
  "Reasons for Automation" through "About the Data" select questions are **raw impact**, and the
  Consultation / Data quality / Procedural fairness / Privacy pages are **mitigation**.
- Free-text (`text`, `comment`) questions never score.

## 2. Value of an answer (`store.ts:25-35`, `49-79`)
- Choice values carry their weight after the **last hyphen**: `"item3-4"` is 4. No hyphen, or a
  non-numeric suffix, is 0 (`"item6"`, department codes `"001"`).
- `radiogroup` / `dropdown`: the weight of the selected value.
- `checkbox`: the **sum** of the weights of all ticked values.
- Unanswered: 0.

## 3. Maximum per question (`store.ts:113-132`)
- `radiogroup` / `dropdown`: the largest choice weight (floored at 0).
- `checkbox`: the sum of all choice weights.

## 4. Final score and impact level (`calculateFinalScore`, `store.ts:147-208`)
```
raw        = Σ value(q)  over raw-impact questions          (store.ts:167-173)
max_raw    = Σ max(q)    over raw-impact questions
mitigation = Σ value(q)  over mitigation questions          (store.ts:174-181)
max_mit    = Σ max(q)    over mitigation questions (Design + Implementation pages)

if mitigation >= 0.8 * (max_mit / 2):                         (store.ts:184-185)
    current = Math.round(0.85 * raw)                          (store.ts:186; JS rounding, .5 goes up)
else:
    current = raw                                             (store.ts:188)

level I   if current <= 0.25 * max_raw                        (store.ts:191-192)
level II  if current <= 0.50 * max_raw                        (store.ts:193-197)
level III if current <= 0.75 * max_raw                        (store.ts:198-202)
level IV  otherwise                                           (store.ts:203-204)
```
The getter returns `[raw, mitigation, current, level]`. The UI labels these "Raw Impact Score",
"Mitigation Score", "Current Score" and the level (`Score.vue:15-18`, `55-64`). With max_raw = 167
the cut-offs are 41.75, 83.5 and 125.25. The mitigation threshold is 0.8 × 154 / 2 = 61.6, so
mitigation ≥ 62 (scores are integers) triggers the 15 % reduction.

## 5. Section tables on the results page (`calculateSectionScore`, `store.ts:210-231`; `Results.vue:327-398`)
These tables are for display only and do not affect the level. For each section header the tool takes
the first answered question's name minus digits and sums the value and maximum of every scored question
whose name **contains** that string. The risk table strips all digits (`replace(/\d/g, "")`,
`Results.vue:335`). The mitigation table strips only the first digit (`replace(/\d/, "")`, `Results.vue:371`).
`aia_score.section_score(survey, data, section)` reproduces the function itself.

## Quirks to keep in mind (reproduced, not fixed)
1. **Hidden questions count in the maxima.** Because `getAllQuestions()` includes invisible questions,
   `max_raw` includes conditional follow-ups such as `aboutAlgorithm8A`, both `riskProfile9` and
   `riskProfile10`, and all of the `aboutDataSource9-14` block, whether or not they can be shown.
   So the level cut-offs are fixed numbers for every project.
2. **Mitigation maximum is halved by hand.** Both the Design and Implementation copies of the mitigation
   pages are in `questionNames`, and only one copy can be shown. The code divides `max_mit` by 2
   (comment at `store.ts:184`). This works because the two copies have identical weights (77 each).
3. **Stale answers.** The store reads `survey.data` as it is, and the score updates on every value change.
   An answer given before a controlling question changed (for example after switching phase) can stay in
   `data` and still count until survey-vue clears invisible values (its default is on completion).
   `aia_score.score` likewise scores whatever is in `data`. Callers should drop answers to hidden
   questions if they want the "clean" score.
4. Some checkbox questions (`businessDrivers1`, `aboutSystem1`, `consultation*2/4/8`) are in
   `questionNames`, but their values have no numeric suffix, so they always add 0.
5. The mitigation section table in the results UI can under-count when a section's first answered
   question has a two-digit number, because only the first digit is stripped. This is display only.
