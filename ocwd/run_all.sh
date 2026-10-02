#!/usr/bin/env bash
# Reproduce every number, table and figure of the paper (CPU only, ~4-5 h on 4 cores).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
python -m pytest -q ocwd/tests
python -m ocwd.experiments.build
python -m ocwd.experiments.evaluate
python -m ocwd.experiments.summarize
python -m ocwd.experiments.accumulate
python -m ocwd.experiments.prognosis
python -m ocwd.experiments.time_to_detect
python -m ocwd.experiments.observability
python -m ocwd.experiments.robustness fullbus ved
python -m ocwd.experiments.extras oppoint crossmodel window hparam transformer significance
python -m ocwd.experiments.figures
( cd paper && pdflatex -interaction=nonstopmode main && bibtex main && pdflatex -interaction=nonstopmode main && pdflatex -interaction=nonstopmode main )
echo "Done: results in ocwd/results, figures in ocwd/figures, paper in paper/main.pdf"
