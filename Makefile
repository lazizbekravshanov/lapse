.PHONY: setup setup-nasa test demo data serve

setup:        ## install the pipeline (no NASA login needed)
	pip install -e "pipeline[dev]"

setup-nasa:   ## also install the NASA download tools
	pip install -e "pipeline[dev,nasa]"

test:         ## run the statistics tests
	cd pipeline && python -m pytest -q

demo:         ## synthetic data -> trends -> web/data (refuses if real data is present)
	python -m lapse demo

data:         ## real data -> trends -> web/data (needs Earthdata login)
	python -m lapse fetch airs
	python -m lapse fetch merra2
	python -m lapse export
	python -m lapse validate

serve:        ## open http://localhost:8000
	python -m http.server 8000 --directory web
