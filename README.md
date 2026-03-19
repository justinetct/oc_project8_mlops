# Projet 8 OpenClassrooms - MLOps

Base de travail du projet 8.

## Structure actuelle

- `pyproject.toml` / `poetry.lock` : source de vérité pour l’environnement local
- `requirements.txt` : dépendances de build et de déploiement
- `app_gradio/` : futur espace pour l'application de scoring
- `dashboard_streamlit/` : futur espace pour le dashboard
- `model/` : fichiers liés au modèle importé via MLflow
- `notebooks/` : notebooks du projet
- `scripts/` : scripts utilitaires
- `tests/` : futurs tests

## Import du modèle via MLflow

Le dépôt prépare l'import du modèle via MLflow avec :
- `model/imported_model/` pour recevoir l'artefact importé
- `model/model_metadata.json` pour les métadonnées du modèle
- `notebooks/00_import_model_mlflow.ipynb` pour documenter l'import
- `scripts/import_model_mlflow.py` pour automatiser l'import ensuite

Le contenu de ces fichiers est volontairement minimal a ce stade.

## Environnement local avec Poetry

Poetry gère l’environnement de développement local et les dépendances source du projet.

Commandes utiles :

```bash
poetry env use python3.12
poetry install
poetry run python scripts/import_model_mlflow.py
poetry run jupyter notebook
```

Ajout de dépendances :

```bash
poetry add <package>
poetry add --group dev <package>
```

`requirements.txt` est conservé pour les contextes de build et de déploiement
(Docker, Hugging Face, CI/CD) et ne constitue pas la source principale de vérité
de l’environnement local.
