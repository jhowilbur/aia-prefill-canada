# AIA ↔ NIST AI RMF 1.0 ↔ OMB M-25-21 crosswalk

This crosswalk maps the sections of Canada's Algorithmic Impact Assessment (AIA) questionnaire to two US documents: the NIST AI Risk Management Framework 1.0 (NIST AI 100-1) and OMB Memorandum M-25-21. It also lists the gaps in both directions.

**This is an interpretive mapping by the author, not an official equivalence.** None of the three issuing bodies (Treasury Board of Canada Secretariat, NIST, OMB) has endorsed it. Do not use it as evidence that a system meets either US document.

File: `aia_nist_omb_crosswalk.csv` (UTF-8, comma-separated, RFC 4180 quoting). It has 57 rows: 43 AIA-section rows, 13 rows for US practices with no direct AIA question, and 1 row for an AIA-only item. Four more AIA-only items have their own rows in the first group, all marked `none`.

## Sources

All three were accessed on 2026-11-05.

| Document | Version / status as of 2026-11-05 | URL |
|---|---|---|
| AIA questionnaire | `canada-ca/aia-eia-js` v1.0.1 (MIT licence), as extracted into the local catalogue `catalog/requirements.jsonl` (295 rows, one per question). Context: Treasury Board *Directive on Automated Decision-Making*. | https://github.com/canada-ca/aia-eia-js |
| NIST AI 100-1, *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*, January 26, 2023 | **Current, but under revision.** The NIST AI RMF page says: "The AI RMF 1.0 is being revised as part of the White House AI Action Plan." That page lists no revised version, draft or new document number. Some third-party sites claim an "AI RMF 2.0" was published or drafted in 2026; NIST does not confirm this, so it is not relied on. On April 7, 2026, NIST also released a concept note for a separate AI RMF Profile on Trustworthy AI in Critical Infrastructure. That is a profile, not a replacement. PDF SHA-256: `7576edb5…89f1`. | PDF: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf · status page: https://www.nist.gov/itl/ai-risk-management-framework |
| OMB M-25-21, *Accelerating Federal Use of AI through Innovation, Governance, and Public Trust*, April 3, 2025 | **In force; not rescinded or superseded.** It is still listed on the OMB memoranda index, which runs to M-27-01 (October 23, 2026). No later memo found rescinds it. M-26-04 (December 11, 2025, *Increasing Public Trust in AI Through Unbiased AI Principles*) says it "builds on" M-25-21 and M-25-22 and adds LLM procurement duties; it does not replace M-25-21. M-25-21 itself rescinded M-24-10. PDF SHA-256: `0aab0aa4…9813`. | PDF: https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf · index: https://www.whitehouse.gov/omb/information-resources/guidance/memoranda/ · M-26-04: https://www.whitehouse.gov/wp-content/uploads/2025/12/M-26-04-Increasing-Public-Trust-in-Artificial-Intelligence-Through-Unbiased-AI-Principles-1.pdf |

The companion memo M-25-22 (AI acquisition) is out of scope.

## Method

1. **Unit of mapping.** Each AIA questionnaire page (`page` in the catalogue) is one unit. A page is split into several rows when its questions carry different obligations; for example, Procedural Fairness is split into audit trail, legislative authority, overrides, reasons, feedback, recourse, relevance, mitigation, training and monitoring. Every question id comes from the catalogue, and the builder script checks each id against it. Design-phase and implementation-phase twins (for example `fairnessDesign13` / `fairnessImplementation13`) share a row.
2. **NIST.** Subcategory ids and wording come from Tables 1–4 of NIST AI 100-1 (PDF pages 27–38, printed pages 22–33). No subcategory number was invented.
3. **OMB.** References use the memo's own numbering in its Appendix ("M-25-21 Implementation Guidance for Agencies"). For example, `Appendix 4(b)(vi)` is Section 4(b), minimum practice vi. The high-impact definition is in Section 5 and the presumed high-impact purposes are in Section 6. The minimum risk-management practices (4(b)(i)–(vii)) apply only to *high-impact* use cases. The AIA applies to every automated decision system in scope of the Directive.
4. **Quotes.** Each `nist_quote_short` and `omb_quote_short` is one contiguous excerpt of 25 words or fewer. A script compared every quote with text extracted from the PDFs (`pdftotext`):
   - NIST: eight quotes where the two-column table layout mixes category text into subcategory text during extraction were checked by eye against the layout rendering.
   - OMB: the PDF is a scanned, OCR'd signature copy. Quotes fix only obvious OCR spacing and character errors ("ofthe" → "of the", "AI' s" → "AI's", "0MB" → "OMB", "govemmentwide" → "governmentwide"). Original wording is kept even where it looks odd (for example "as well its justification").
   - Dashes and curly quotes follow the source.
5. **Conservatism.** "Strong" needs the same obligation, not the same topic. Where the obvious mapping is not supported by the text, the row says so in `notes`. The notable cases are listed under *Disagreements with the obvious mapping*.

## Columns

| Column | Meaning |
|---|---|
| `aia_section` | AIA page title and key, plus the sub-topic. Rows starting with `GAP` are gap rows. |
| `aia_question_ids` | Semicolon-separated catalogue ids. In US→AIA gap rows, this lists the *nearest* AIA items, if any. |
| `aia_summary` | Plain-language summary of what the AIA questions ask. |
| `nist_rmf_subcategories` | Matching subcategories; the first listed is the one quoted. |
| `nist_quote_short` | Exact excerpt of the first subcategory, 25 words or fewer. |
| `omb_m2521_ref` | M-25-21 Appendix section and practice. |
| `omb_quote_short` | Exact excerpt, 25 words or fewer. |
| `match` | Overall level: the stronger of `match_nist` and `match_omb`, meaning the best US counterpart available. |
| `notes` | Reasoning, caveats and disagreements. |
| `match_nist`, `match_omb` | Match level for each framework. These two columns were added beyond the requested schema because a single level hid real differences. |

## How to read the match levels

- **strong**: the US text asks for the same outcome or obligation as the AIA questions, so answering the AIA questions would substantially produce what the US text requires. NIST subcategories are voluntary outcomes, not legal duties. "Strong" against NIST means the AIA questions produce the documented outcome the subcategory describes. It does not mean conformity with the AI RMF.
- **partial**: same topic, but a different obligation. Typical reasons: different scope, a yes/no flag against a required evaluation, a process against a result, or a narrower or broader trigger.
- **none**: no counterpart in that document. A US cell can be blank, or it can quote text that shows the item is out of scope (for example the Section 7 exclusion of data privacy and security).

Counts across all 57 rows:

| Level | `match` (overall) | `match_nist` | `match_omb` |
|---|---|---|---|
| strong | 6 | 5 | 2 |
| partial | 35 | 35 | 32 |
| none | 16 | 17 | 23 |

Only two OMB matches are strong: purpose and expected benefit (4(b)(ii)(A)), and disclosure as open government data (4(b)(ii)(B)).

## Gap list

### US practices with no or weak AIA counterpart

| Practice | NIST | M-25-21 | AIA status |
|---|---|---|---|
| Pre-deployment testing under deployment-like conditions | MEASURE 2.3, 2.5 | 4(b)(i) | **partial**: subgroup performance (impact18, impact19I) and bias testing (fairnessDesign18) only; no general validity test |
| Independent review | MEASURE 1.3 | 4(b)(ii)(F), 3(a)(i)(F)(4) | none in the questionnaire (Directive peer review is outside it) |
| Named risk acceptance and residual risk | MANAGE 1.4, GOVERN 2.3 | 4(b)(ii)(G) | none |
| Cost analysis | — | 4(b)(ii)(E) | none |
| Reassessment schedule and significant modification | GOVERN 1.5 | 4(b)(ii)(D) | partial (change log, retraining review) |
| Ongoing monitoring that covers civil-rights harms, security and changes in context or data | MEASURE 2.4, MANAGE 4.1 | 4(b)(iii) | partial: the AIA monitors performance only (fairnessDesign24) |
| Periodic, system-specific operator training and assessment | GOVERN 2.2, MAP 3.4 | 4(b)(iv) | partial: one yes/no on automation-bias training |
| Timely *human* review and appeal | MEASURE 3.3 | 4(b)(vi) | partial: recourse is asked about but need not be human or timely |
| Waivers, high-impact determinations and their publication | — | 4(a)(ii)–(iv) | none |
| Termination of non-compliant AI; decommissioning | GOVERN 1.7, MANAGE 2.4 | 4(a)(i) | none |
| Incident response and communication | MANAGE 4.3, 2.3, GOVERN 4.3 | — | none |
| Organisational risk tolerance | MAP 1.5, GOVERN 1.3 | — | none (the AIA computes a level instead) |
| Third-party and pre-trained model monitoring | MANAGE 3.2, GOVERN 6.1 | (M-25-22, out of scope) | none |
| Diverse, interdisciplinary risk team | GOVERN 3.1, MAP 1.2 | — | none |
| TEVV documentation | MEASURE 2.1, 2.13 | — | none |
| **Opt-out to a human alternative** | — | **only for pilots**, 4(a)(i)(C) | none on either side (see below) |

### AIA items with no counterpart in at least one US document

- Chain of legislative authority in the audit trail (fairnessDesign1/1A).
- Relevance of inputs and rules to the administrative decision (fairnessDesign17/19/20).
- Public availability of bias-testing and data-quality processes (dataQualityDesign2/4/9 and implementation twins).
- GBA Plus. NIST fairness evaluation overlaps only in purpose; OMB has nothing.
- TBS concept case and GC Enterprise Architecture Review Board (riskProfile9/10).
- Accessibility: EN 301 549 conformance and disability barriers (aboutSystem8, riskProfile4).
- Trade-secret status of the algorithm (aboutAlgorithm1).
- Environmental impact (aboutSystem11, impact15): strong or partial against NIST MEASURE 2.12, none against OMB.
- Impact on staff (impact4A): no OMB counterpart.
- Notice, reasons and explanations to affected people (fairnessDesign7/10/21): none in M-25-21.
- Data privacy and security by design (privacyDesign2/3/4/7/9): M-25-21 has no by-design practice; its Section 7 leaves training- and input-data privacy, security and confidentiality out of AI-use risk, though 4(b)(ii)(C) asks for privacy impacts to be documented and 4(b)(iii) for security monitoring.

## Disagreements with the obvious mapping

1. **Opt-out.** A common assumption is that the US requires an opt-out to a human alternative and the AIA lacks one. M-25-21 has no such general practice; it was in M-24-10, which M-25-21 rescinded. The only opt-in/opt-out text is a condition for exempting *pilots*. NIST AI RMF 1.0 has no opt-out subcategory either. AIA `aboutSystem9` is a continuity fallback, not an individual choice. Neither side has it.
2. **Degree of automation.** The AIA scores full automation as riskier. M-25-21 says AI-use risk exists "regardless of whether" the AI informs, partially automates or fully automates, and that a high-impact determination is possible with or without human oversight. M-25-21 does not grade risk by degree of automation, unlike the AIA; but whether its practices apply at all depends on the AI output being a "principal basis" for the decision (Section 5; footnote 27).
3. **Recourse.** This is kept at partial although it is often called equivalent. OMB specifies a *timely human* review; the AIA question does not.
4. **Privacy.** M-25-21 does not set its own privacy practices. Its Section 7 leaves the privacy, security and confidentiality of training and input data out of its definition of AI-use risk; elsewhere it asks the impact assessment to document privacy impacts (4(b)(ii)(C)) and to "reference" PIAs, and monitoring to catch security problems (4(b)(iii)).
5. **Explanations.** The AIA's reasons and explanation questions have no M-25-21 counterpart. NIST MEASURE 2.9 is about explaining the model for governance, not giving reasons to the affected person. M-25-21's public reporting (use-case inventory, 3(b)(v); determinations and waivers, 4(a)(iv)) is transparency about the system, not notice to affected people.

## Limitations

- An interpretive mapping by the author, not an official equivalence, and not legal advice.
- The mapping covers the AIA **questionnaire** only (v1.0.1 as catalogued). It does not cover the Directive on Automated Decision-Making itself. Several "gaps" (peer review, AIA updates on change, testing) are addressed by the Directive's own requirements outside the questionnaire.
- The NIST AI RMF is under revision. The 2025 US AI Action Plan directs NIST to remove certain references (including climate change), so subcategories such as MEASURE 2.12 may change. Re-check the mapping when a revised version is published.
- The M-25-21 minimum practices apply only to high-impact use cases. A match does not mean the US practice would apply to a given system.
- The OMB text is quoted from an OCR'd scan, with the OCR corrections listed in the Method section.
- The mapping is done at section level. Individual answer choices and the AIA scoring weights are not mapped.
- The grades are the author's judgment calls; check the cited text before relying on a row.
- The mapping is accurate as of 2026-11-05 and will go stale when the AI RMF revision or a new OMB AI memo is published.
- One author made the mapping in one pass, time-boxed; an independent check of 30 rows (2026-11-05) led to the corrections in rows 5, 9, 18, 24, 25, 27 and 43. No second-coder agreement was measured. The rows the author was least sure of are listed below.

### Rows to review first

- Recourse (fairnessDesign13): partial or strong against 4(b)(vi)?
- Consultations against GOVERN 5.1: lowered to partial after review (organization-level policy vs one project).
- Reasons for Automation, purpose and benefit: strong for both. It depends on reading businessDrivers6C/6D as the "compared to existing agency processes" comparison.
- Data representativeness against MAP 2.3: lowered to partial after review.
- Scope (businessDrivers7) against MAP 3.3: strong, a close call.
- Monitoring (fairnessDesign24) against MEASURE 2.4: strong for NIST.
- Data sources (aboutDataSource13) against 4(b)(ii)(B) "describe the data collection, and preparation process": kept partial, could be argued strong.
