# Licences and notices

| Part | Licence |
|---|---|
| Code (`pipeline/`, `eval/`, `scripts/`) | MIT, © 2026 Jonathas Wilbur Ferreira (`LICENSE`) |
| Report (`report/`), crosswalk (`crosswalk/`), docs (`docs/`) | CC BY 4.0, © 2026 Jonathas Wilbur Ferreira <https://creativecommons.org/licenses/by/4.0/> |
| Derived AIA tables (`data/`, `reports/`) | Contain information licensed under the Open Government Licence – Canada (see below); the selection, compilation and derived columns (`g0_*`, `leakage_free_input_chars`, `n_supporting_docs`, recomputed scores) © 2026 Jonathas Wilbur Ferreira, CC BY 4.0 |
| Questionnaire catalogue (`catalog/`) | MIT, © 2019 Government of Canada (see below) |

## Published AIAs: Open Government Licence – Canada
Contains information licensed under the Open Government Licence – Canada.
<https://open.canada.ca/en/open-government-licence-canada>

`data/aia_catalogue.csv`, `data/aia_answers.jsonl`, `data/SOURCES.csv` and `reports/` are derived
from the Algorithmic Impact Assessments published on open.canada.ca (each source file is listed
with its URL and SHA-256 in `data/SOURCES.csv`). This repository does **not** redistribute the
source files or any free-text answers: it keeps only the multiple-choice answers to questionnaire
questions, published scores, and public record metadata (department, system title, date). No
personal information is included; the administrative fields (respondent, job title, branch,
responsible executive) are dropped before export. `scripts/fetch_pinned.py` re-downloads the
originals from the Government of Canada. Use of the data does not imply endorsement by the
Government of Canada.

## AIA questionnaire: MIT, canada-ca/aia-eia-js
`catalog/requirements.jsonl`, `catalog/versions/*/survey-enfr.json`, `catalog/scoring.md`, the AIA
question ids and wording in `crosswalk/` and `reports/aia_question_coverage.csv`, and the
scoring logic in `pipeline/aia_score.py` copy or derive from the questionnaire and scoring code of
<https://github.com/canada-ca/aia-eia-js> (commit b62573389db4946b4d70b7fa62c4ca8d9990dba3), distributed under this licence:

```
MIT License

Copyright (c) 2019 Government of Canada - Gouvernement du Canada

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

This project is independent research. It is not affiliated with, funded by or endorsed by the
Government of Canada, the Treasury Board of Canada Secretariat, NIST or OMB.
