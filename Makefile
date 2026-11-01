S3 = s3://us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge
PY = .venv/bin/python

.PHONY: env data reproduce check
env:            ## create venv with pinned versions
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
data:           ## local copy of reference/ (6.3 GB) + tract polygons; resumable
	for r in eastern-ok maricopa-az northern-ca south-central-tx; do \
	  aws s3 sync --no-sign-request $(S3)/reference/$$r/ data/reference/$$r/ ; \
	  aws s3 sync --no-sign-request $(S3)/strata/$$r/ data/strata/$$r/ --exclude "*" --include "*census-tracts*" ; done
reproduce:      ## build -> validate -> submission.csv (about 10 min from a local copy)
	BB_DATA=data PYTHONPATH=. $(PY) reproduce.py submission.csv
check:          ## byte-compare with the file that scored 0 on the leaderboard
	cmp submission.csv submissions/00_baseline_6dp.csv && echo "IDENTICAL to scored submission"
