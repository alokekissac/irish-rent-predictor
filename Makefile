.PHONY: install data train export pipeline test lint format api dashboard web web-dev mlflow docker up

install:          ## Install all dependencies (incl. dev) with uv
	uv sync
	uv run pre-commit install

data:             ## Download RTB rents (CSO API) + Property Price Register, then clean
	uv run rentcast-ingest
	uv run rentcast-transform

train:            ## Train, backtest and log to MLflow; writes models/ and reports/
	uv run rentcast-train

export:           ## Export forecasts/SHAP/what-if/backtest JSON for the static web app
	uv run rentcast-export-web

pipeline: data train export

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

web:              ## Build the static web app (web/dist), as deployed on Vercel
	cd web && npm ci && npm run build

web-dev:          ## Web app dev server at http://localhost:5173
	cd web && npm run dev

mlflow:           ## Browse experiment runs at http://localhost:5000
	uv run mlflow ui --backend-store-uri sqlite:///mlflow.db

docker:
	docker build -t rentcast:latest .

up:               ## API + dashboard via Docker Compose
	docker compose up --build
