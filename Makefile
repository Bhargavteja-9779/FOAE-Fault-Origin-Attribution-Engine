.PHONY: install test data reproduce figures

install:
	pip install -r ocwd/requirements.txt

test:
	PYTHONPATH=. python -m pytest -q ocwd/tests

data:
	bash ocwd/get_data.sh

reproduce:
	bash ocwd/run_all.sh

figures:
	python -m ocwd.experiments.figures
