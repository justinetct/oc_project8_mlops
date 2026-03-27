# Makefile — Projet 8 OpenClassrooms (MLOps)

.PHONY: test coverage export-requirements docker-build docker-run

# -- Tests ------------------------------------------------------------------
test:
	poetry run pytest tests/ -v

coverage:
	poetry run pytest tests/ --cov=app_gradio --cov-report=term-missing

coverage-html:
	poetry run pytest tests/ --cov=app_gradio --cov-report=html

# -- Export des dépendances Gradio ------------------------------------------
export-requirements:
	poetry export --only main --without-hashes --format requirements.txt \
		| sed 's/ ;.*$$//' > requirements.gradio.txt
	@# requests est requis par gradio.cli mais non résolu par poetry export
	@grep -q "^requests==" requirements.gradio.txt || echo "requests>=2.28,<3" >> requirements.gradio.txt
	@echo "requirements.gradio.txt généré ($(shell wc -l < requirements.gradio.txt) paquets)"

# -- Docker -----------------------------------------------------------------
docker-build: export-requirements
	docker build -f Dockerfile.gradio -t scoring-gradio .

docker-run:
	docker run -p 7860:7860 scoring-gradio
