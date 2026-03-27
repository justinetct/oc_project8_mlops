# Makefile — Projet 8 OpenClassrooms (MLOps)

.PHONY: test coverage coverage-html \
        export-requirements-gradio export-requirements-streamlit \
        docker-build-gradio docker-run-gradio \
        docker-build-streamlit docker-run-streamlit \
        compose-up compose-down compose-build

# -- Tests ------------------------------------------------------------------
test:
	poetry run pytest tests/ -v

coverage:
	poetry run pytest tests/ --cov=app_gradio --cov-report=term-missing

coverage-html:
	poetry run pytest tests/ --cov=app_gradio --cov-report=html

# -- Export des dépendances -------------------------------------------------
export-requirements-gradio:
	poetry export --only main,gradio --without-hashes --format requirements.txt \
		| sed 's/ ;.*$$//' > requirements.gradio.txt
	@# requests est requis par gradio.cli mais non résolu par poetry export
	@grep -q "^requests==" requirements.gradio.txt || echo "requests>=2.28,<3" >> requirements.gradio.txt
	@echo "requirements.gradio.txt généré ($(shell wc -l < requirements.gradio.txt) paquets)"

export-requirements-streamlit:
	poetry export --only main,streamlit --without-hashes --format requirements.txt \
		| sed 's/ ;.*$$//' > requirements.streamlit.txt
	@echo "requirements.streamlit.txt généré ($(shell wc -l < requirements.streamlit.txt) paquets)"

# -- Docker Gradio ----------------------------------------------------------
docker-build-gradio: export-requirements-gradio
	docker build -f Dockerfile.gradio -t scoring-gradio .

docker-run-gradio:
	docker run -p 7860:7860 scoring-gradio

# -- Docker Streamlit -------------------------------------------------------
docker-build-streamlit: export-requirements-streamlit
	docker build -f Dockerfile.streamlit -t monitoring-streamlit .

docker-run-streamlit:
	docker run -p 8501:8501 monitoring-streamlit

# -- Docker Compose (les deux services) ------------------------------------
compose-build: export-requirements-gradio export-requirements-streamlit
	docker compose build

compose-up: export-requirements-gradio export-requirements-streamlit
	docker compose up --build

compose-down:
	docker compose down
