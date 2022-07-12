install:
	poetry install
lint:
	poetry run pylint -d duplicate-code taimatsu/**/*.py
test: install
	poetry run python -m unittest tests/unit/test_* 
run: test
	poetry run ./examples/compare.py
