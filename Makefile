.PHONY: bundle
bundle:
	python scripts/build_bundle.py

.PHONY: test
test: bundle
	pytest -q

.PHONY: lint
lint:
	ruff check .
	mypy src tests scripts

.PHONY: build
build: bundle
	poetry build
