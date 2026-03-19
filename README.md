# Projet 8 OpenClassrooms - MLOps

Base de travail du projet 8.

## Structure actuelle

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
