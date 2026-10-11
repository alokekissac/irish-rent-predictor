.PHONY: install data train pipeline test lint format api dashboard mlflow docker up

install:          ## Install all dependencies (incl. dev) with uv
	uv sync
	uv run pre-commit install

data:             ## Download RTB rents (CSO API) + Property Price Register, then clean
	uv run rentcast-ingest
	uv run rentcast-transform

train:            ## Train, backtest and log to MLflow; writes models/ and reports/
	uv run rentcast-train

pipeline: data train

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

api:              ## FastAPI with Swagger docs at http://localhost:8000/docs
	uv run uvicorn rentcast.api.main:app --reload

dashboard:        ## Streamlit dashboard at http://localhost:8501
	uv run streamlit run dashboard/app.py

mlflow:           ## Browse experiment runs at http://localhost:5000
	uv run mlflow ui --backend-store-uri sqlite:///mlflow.db

docker:
	docker build -t rentcast:latest .

up:               ## API + dashboard via Docker Compose
	docker compose up --build
