.PHONY: install run test clean

install:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	.venv/bin/pytest

clean:
	rm -f niet_qpg.db
	rm -rf .pytest_cache htmlcov
