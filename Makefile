install:
	poetry install
test: install
	poetry run python -m unittest tests/unit/test_* 
run: test
	poetry run ./examples/compare.py
