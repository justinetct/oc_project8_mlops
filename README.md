<p align="center">
  <img src="app_gradio/assets/logo_m3_gold.svg" alt="Prêt à Dépenser" width="300">
</p>

# Prêt à Dépenser — Scoring Crédit

Projet 8 OpenClassrooms — Parcours Data Scientist.

Application de scoring crédit permettant d’estimer le risque d’un dossier et d’afficher une décision d’accord ou de refus.

## Fonctionnalités

- Interface Gradio avec saisie du profil client (dates, montants, scores externes)
- Validation des entrées avec messages d'erreur explicites
- Prédiction locale via un modèle LightGBM (pas de dépendance MLflow au runtime)
- Carte de résultat avec jauge de risque et décision lisible
- 3 exemples de profils pré-enregistrés pour la démo

## Lancer l'application

```bash
poetry install
poetry run python -m app_gradio.app
```

L'application s'ouvre sur `http://localhost:7860`.

## Lancer les tests

```bash
# Tous les tests
poetry run pytest tests/ -v

# Avec couverture (terminal)
poetry run pytest tests/ --cov=app_gradio --cov-report=term-missing

# Rapport de couverture HTML
poetry run pytest tests/ --cov=app_gradio --cov-report=html
```

54 tests couvrant :
- **Prédiction** : chargement du modèle, format de sortie, score, label — 7 tests (`test_predict.py`)
- **Validation** : montants, dates, cohérence métier, types incorrects, edge cases — 30 tests (`test_validation.py`)
- **Intégration** : chaîne complète UI → validation → prédiction, helpers, construction de l'app — 17 tests (`test_integration.py`)

## Structure du projet

```
├── app_gradio/
│   ├── app.py              # Application Gradio (interface + logique UI)
│   ├── predict.py           # Fonction de prédiction (ratios + scoring)
│   ├── validation.py        # Validation des entrées utilisateur
│   ├── loader.py            # Chargement unique du modèle (singleton)
│   ├── themes.py            # Thème Navy Gold + CSS
│   └── assets/              # Logo SVG, favicon
├── dashboard_streamlit/
│   └── app.py               # Dashboard Streamlit de monitoring (placeholder)
├── model/
│   ├── model_simple.joblib          # Modèle LightGBM local
│   └── v5_ui_model_config.json      # Config (features, seuil, métriques)
├── notebooks/
│   └── 00_import_model_mlflow.ipynb  # Import du modèle depuis P6
├── scripts/
│   └── import_model_mlflow.py        # Script d'import MLflow
├── src/
│   └── config.py            # Configuration centralisée (chemins, constantes)
├── tests/
│   ├── test_predict.py      # 7 tests — prédiction
│   ├── test_validation.py   # 30 tests — validation des entrées
│   └── test_integration.py  # 17 tests — intégration et helpers
├── Dockerfile.gradio         # Image Docker — scoring Gradio
├── Dockerfile.streamlit      # Image Docker — dashboard Streamlit
├── Makefile                  # Commandes build / test / export
└── pyproject.toml            # Dépendances Poetry
```

## Modèle

| Propriété           | Valeur |
|---------------------|---|
| Type                | Modèle LightGBM allégé |
| Origine             | Version simplifiée du modèle développé au projet 6 |
| Features            | 14 (11 saisies + 3 ratios calculés) |
| Seuil de décision   | 0.1 |
| Performance holdout | AUC = 0.761 |

Le modèle allégé est chargé une seule fois au démarrage depuis model/model_simple.joblib. L’application fonctionne localement, sans dépendance à MLflow au runtime.
## Règles de validation

| Règle | Détail |
|---|---|
| Montants | Strictement positifs |
| Crédit vs prix du bien | Crédit ≤ prix du bien |
| Dates | Format AAAA-MM-JJ, entre 1900 et la date de référence |
| Âge minimum | 18 ans à la date de référence (2018-05-17) |
| Cohérence dates | Emploi et document d'identité postérieurs à la naissance |

## Docker

Deux services conteneurisés séparément :

| Service | Image | Port | Commande |
|---|---|---|---|
| Scoring Gradio | `scoring-gradio` | 7860 | `make docker-build-gradio` |
| Monitoring Streamlit | `monitoring-streamlit` | 8501 | `make docker-build-streamlit` |

```bash
# Scoring Gradio
make docker-build-gradio
make docker-run-gradio        # → http://localhost:7860

# Dashboard Streamlit
make docker-build-streamlit
make docker-run-streamlit     # → http://localhost:8501
```

## Gestion des dépendances

Poetry est la source de vérité. Les dépendances sont organisées en groupes :

| Groupe | Contenu | Usage |
|---|---|---|
| `main` | numpy, pandas, scikit-learn, lightgbm, joblib, python-dotenv | Socle commun (modèle + prédiction) |
| `gradio` | gradio | Application de scoring |
| `streamlit` | streamlit | Dashboard de monitoring |
| `mlflow` | mlflow | Import du modèle depuis P6 |
| `extras` | pyarrow, scipy, graphviz | Notebooks / exploration |
| `dev` | pytest, black, ruff… | Développement |

Chaque service a son propre fichier de dépendances exporté depuis Poetry :

```bash
make export-requirements-gradio      # → requirements.gradio.txt
make export-requirements-streamlit   # → requirements.streamlit.txt
```

> **Note :** `requests` est requis par `gradio.cli` mais n'est pas résolu par `poetry export`. La commande `make export-requirements-gradio` l'ajoute automatiquement si absent.

## Environnement

```bash
poetry env use python3.12
poetry install
```

Python 3.12 requis. Poetry gère l'environnement de développement local.
