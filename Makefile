.PHONY: install run seed test lint fmt docker-up docker-down

install:
	pip install -r requirements-dev.txt

run:
	uvicorn app.main:app --reload

seed:
	python -m scripts.seed

test:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check .

fmt:
	ruff check . --fix

docker-up:
	docker compose up --build

docker-down:
	docker compose down
