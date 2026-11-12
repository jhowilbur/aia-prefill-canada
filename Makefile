# Requires Python >= 3.10, numpy (eval/ only), git, curl, pdftotext (poppler) for `data`,
# and Node.js for the optional store.ts cross-check test (runs after `make vendor`).
PY = python3 -I
AIA_TOOL_COMMIT = b62573389db4946b4d70b7fa62c4ca8d9990dba3

.PHONY: verify test vendor data reproduce clean-data

verify:            ## offline: recompute 32 published scores from data/aia_answers.jsonl (expect 31/32)
	$(PY) scripts/verify_scores.py

test:              ## unit tests (19 data/vendor-dependent pipeline tests skip until `make vendor data`)
	$(PY) -m unittest discover -s pipeline/tests
	$(PY) -m unittest discover -s eval/tests

vendor:            ## the official AIA tool at the pinned commit (scoring code + current survey)
	test -d vendor/aia-eia-js || (git init -q vendor/aia-eia-js && cd vendor/aia-eia-js && \
	  git remote add origin https://github.com/canada-ca/aia-eia-js.git && \
	  git fetch -q --depth 1 origin $(AIA_TOOL_COMMIT) && git checkout -q FETCH_HEAD)

data: vendor       ## re-download the pinned corpus from open.canada.ca (about 27 MB) and parse it
	$(PY) scripts/fetch_pinned.py
	$(PY) pipeline/parse_aia.py
	$(PY) pipeline/redact_pii.py

reproduce: vendor data   ## main pipeline: G0 score check, leakage-free inputs, leak probe, corpus and set counts
	$(PY) pipeline/g0_check.py
	$(PY) pipeline/build_inputs.py
	$(PY) pipeline/leak_probe.py
	$(PY) pipeline/aia_stats.py
	$(PY) eval/scripts/set_counts.py
	$(PY) -m unittest discover -s pipeline/tests

clean-data:        ## remove everything re-downloaded or rebuilt
	rm -rf data/raw data/interim
