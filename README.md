<p align="center">
  <img src="app_gradio/assets/logo_m3_gold.svg" alt="Prêt à Dépenser" width="300">
</p>

# Projet 8 OpenClassrooms - MLOps

Base de travail du projet 8.

## Structure actuelle

- `pyproject.toml` / `poetry.lock` : source de vérité pour l’environnement local
- `requirements.txt` : dépendances de build et de déploiement
- `app_gradio/` : futur espace pour l'application de scoring
- `dashboard_streamlit/` : futur espace pour le dashboard
- `model/` : modèle importé localement pour le projet 8
- `notebooks/` : notebooks du projet
- `scripts/` : scripts utilitaires
- `tests/` : futurs tests

## Modèle utilisé dans le projet 8

Le modèle issu du projet 6 est importé dans un format local stable afin d’éviter une dépendance directe à MLflow au moment de l’exécution de l’application.

Le dépôt contient :
- `model/imported_model/` : artefact local du modèle
- `model/model_metadata.json` : métadonnées minimales du modèle importé
- `notebooks/00_import_model_mlflow.ipynb` : notebook de préparation de l’import
- `scripts/import_model_mlflow.py` : script d’import du modèle

Le notebook et le script d’import servent uniquement à préparer l’artefact local à partir du projet 6. Ils ne sont pas nécessaires pour exécuter l’application au quotidien une fois le modèle importé.

## Chargement et prédiction

Le modèle V5 (variante `V5_plus_married`, LightGBM) est chargé localement via `cloudpickle` depuis `model/imported_model/model.pkl`. Aucune dépendance à MLflow n’est requise au runtime.

- `app_gradio/loader.py` : chargement unique du modèle (singleton module-level)
- `app_gradio/predict.py` : logique de prédiction (recalcul des ratios + scoring)
- `model/v5_ui_model_config.json` : config exportée du P6 (features, seuil, métriques)

Le seuil de décision (`0.1`) est lu depuis la config du modèle.

```bash
poetry run pytest tests/test_predict.py -v
```

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

`requirements.txt` est conservé pour les contextes de build et de déploiement (Docker, Hugging Face, CI/CD) et ne constitue pas la source principale de vérité de l’environnement local.
