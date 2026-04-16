<p align="center">
  <img src="app_gradio/assets/logo_m3_gold.svg" alt="Prêt à Dépenser" width="300">
</p>

# Prêt à Dépenser — Scoring Crédit

Projet 8 OpenClassrooms — Parcours Data Scientist.

Application de scoring crédit permettant d’estimer le risque d’un dossier et d’afficher une décision d’accord ou de refus.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Environnement](#environnement)
- [Lancer les applications](#lancer-les-applications)
- [Lancer les tests](#lancer-les-tests)
- [Structure du projet](#structure-du-projet)
- [Modèle](#modèle)
- [Déploiements](#déploiements)
- [Schéma simple des services](#schéma-simple-des-services)
- [Règles de validation](#règles-de-validation)
- [Docker](#docker)
- [Gestion des dépendances](#gestion-des-dépendances)
- [Base de données](#base-de-données)
- [Performance](#performance)
- [Monitoring et drift](#monitoring-et-drift)

## Accès rapides

- **API de scoring Gradio (préprod)** : [oc-p8-gradio-preprod.onrender.com](https://oc-p8-gradio-preprod.onrender.com)
- **Dashboard Streamlit (préprod)** : [oc-p8-streamlit-preprod.onrender.com](https://oc-p8-streamlit-preprod.onrender.com)

## Fonctionnalités

- Interface Gradio avec saisie du profil client (dates, montants, scores externes)
- Validation des entrées avec messages d'erreur explicites
- Prédiction locale via un modèle LightGBM (pas de dépendance MLflow au runtime)
- Carte de résultat avec jauge de risque et décision lisible
- 3 exemples de profils pré-enregistrés pour la démo
- Logging PostgreSQL des prédictions avec latence mesurée (`duration_ms`)
- Logging des erreurs de validation / erreurs techniques dans `prediction_errors`
- Dashboard Streamlit avec score, volume, latence et taux d'erreur


## Environnement

```bash
poetry env use python3.12
poetry install
```

Python 3.12 requis. Poetry gère l'environnement de développement local.

## Lancer les applications

```bash
# Application de scoring
poetry run python -m app_gradio.app

# Dashboard de monitoring
poetry run streamlit run dashboard_streamlit/app.py
```

- Scoring Gradio : `http://localhost:7860`
- Monitoring Streamlit : `http://localhost:8501`

## Lancer les tests

```bash
# Tous les tests
poetry run pytest tests/ -v

# Avec couverture (terminal)
poetry run pytest tests/ --cov=app_gradio --cov-report=term-missing

# Rapport de couverture HTML
poetry run pytest tests/ --cov=app_gradio --cov-report=html
```

64 tests couvrant :
- **Prédiction** : chargement du modèle, format de sortie, score, label — 7 tests (`test_predict.py`)
- **Validation** : montants, dates, cohérence métier, types incorrects, edge cases — 30 tests (`test_validation.py`)
- **Intégration** : chaîne complète UI → validation → prédiction, helpers, construction de l'app — 17 tests (`test_integration.py`)
- **Service de scoring** : validation, appel au modèle, logging — 3 tests (`test_scoring_service.py`)
- **Baseline performance** : stats et construction du DataFrame du benchmark — 4 tests (`test_benchmark_baseline.py`)
- **Inférence ONNX** : fallback sklearn, cohérence des scores sklearn vs ONNX — 3 tests (`test_predict_onnx.py`)

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
│   └── app.py               # Dashboard Streamlit de monitoring (lecture PostgreSQL)
├── model/
│   ├── model_simple.joblib          # Modèle LightGBM local
│   ├── model_simple.onnx            # Modèle converti en ONNX (inférence optionnelle via USE_ONNX=1)
│   └── v5_ui_model_config.json      # Config (features, seuil, métriques)
├── notebooks/
│   ├── 00_import_model_mlflow.ipynb      # Import du modèle depuis P6
│   ├── 01_monitoring_drift.ipynb         # Monitoring et démonstration de drift
│   └── 02_performance_optimization.ipynb # Synthèse de l'étape 4 performances
├── perf/
│   ├── README.md                    # protocole baseline
│   ├── bottlenecks_analysis.md      # analyse des goulots
│   ├── optimization_onnx.md         # optimisation moteur
│   ├── optimization_postgres.md     # optimisation applicative
│   └── results/                     # résultats JSON et profiling
├── scripts/
│   ├── import_model_mlflow.py        # Script d'import MLflow
│   ├── prepare_demo_data.py          # Génération baseline/drift de démonstration
│   ├── inject_demo_requests.py       # Injection technique baseline + drift en base
│   ├── inject_demo_errors.py         # Injection de cas d'erreur de démonstration
│   ├── benchmark_baseline.py         # Benchmark inférence + service + HTTP
│   ├── profile_bottlenecks.py        # cProfile + snapshot CPU/RAM
│   ├── benchmark_onnx.py             # Faisabilité et benchmark sklearn vs ONNX
│   ├── benchmark_postgres.py         # Benchmark HTTP sync vs async + intégrité logs
│   └── check_logs.py                 # Inspection rapide des dernières lignes en base
├── src/
│   ├── config.py            # Configuration centralisée (chemins, constantes)
│   └── database.py          # Accès PostgreSQL (logs sync/async, erreurs, création de tables)
├── tests/
│   ├── test_predict.py              # 7 tests — prédiction
│   ├── test_validation.py           # 30 tests — validation des entrées
│   ├── test_integration.py          # 17 tests — intégration et helpers
│   ├── test_scoring_service.py      # 3 tests — service de scoring
│   ├── test_benchmark_baseline.py   # 4 tests — stats benchmark et DataFrame
│   └── test_predict_onnx.py         # 3 tests — intégration ONNX et fallback
├── Dockerfile.gradio         # Image Docker — scoring Gradio (convertit le modèle en ONNX au build)
├── Dockerfile.streamlit      # Image Docker — dashboard Streamlit
├── docker-compose.yml        # Lancement local des deux services
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

## Déploiements

Les deux services sont déployés en préproduction sur Render.
- **API de scoring Gradio (préprod)** : [oc-p8-gradio-preprod.onrender.com](https://oc-p8-gradio-preprod.onrender.com)
- **Dashboard Streamlit (préprod)** : [oc-p8-streamlit-preprod.onrender.com](https://oc-p8-streamlit-preprod.onrender.com)


## Schéma simple des services

```text
Utilisateur
   ├──> Gradio (scoring) ───> PostgreSQL (prediction_logs)
   └──> Streamlit (monitoring) ──┘

GitHub Actions ───> Render (déploiement après CI)
Docker Compose ───> secours local pour Gradio + Streamlit
```

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
# Les deux services ensemble (Docker Compose)
make compose-up               # → Gradio http://localhost:7860
                               #   Streamlit http://localhost:8501
make compose-down              # Arrêter les services

# Ou séparément
make docker-build-gradio
make docker-run-gradio        # → http://localhost:7860

make docker-build-streamlit
make docker-run-streamlit     # → http://localhost:8501
```

> **Note :** en local, `docker-compose.yml` permet de lancer ensemble l’API Gradio et le dashboard Streamlit avec une configuration cohérente du projet.

## Gestion des dépendances

Poetry est la source de vérité. Les dépendances sont organisées en groupes :

| Groupe | Contenu | Usage |
|---|---|---|
| `main` | numpy, pandas, scikit-learn, lightgbm, joblib, python-dotenv | Socle commun (modèle + prédiction) |
| `gradio` | gradio | Application de scoring |
| `streamlit` | streamlit | Dashboard de monitoring |
| `db` | psycopg2-binary | Logging PostgreSQL |
| `mlflow` | mlflow | Import du modèle depuis P6 |
| `extras` | pyarrow, scipy, graphviz | Notebooks / exploration |
| `dev` | pytest, black, ruff… | Développement |

Chaque service a son propre fichier de dépendances exporté depuis Poetry :

```bash
make export-requirements-gradio      # → requirements.gradio.txt
make export-requirements-streamlit   # → requirements.streamlit.txt
```

> **Note :** `requests` est requis par `gradio.cli` mais n'est pas résolu par `poetry export`. La commande `make export-requirements-gradio` l'ajoute automatiquement si absent.

En résumé :
- **Poetry** est utilisé pour le développement local et comme source de vérité.
- **requirements.gradio.txt** et **requirements.streamlit.txt** sont utilisés pour les builds Docker et les déploiements Render.

## Base de données

Les prédictions sont loggées dans une table PostgreSQL `prediction_logs`.

- **Gradio** écrit une ligne dans `prediction_logs` après chaque prédiction valide, avec score, décision et latence.
- **Les erreurs** de validation ou techniques sont stockées dans `prediction_errors`.
- **Streamlit** lit `prediction_logs` et `prediction_errors` pour afficher les indicateurs de monitoring.

Créer la table (une seule fois, idempotent) :

```bash
poetry install --with db
poetry run python scripts/create_tables.py
```

Requiert `DATABASE_URL` dans le `.env` (voir `.env.example`).

Script utile pour vérifier rapidement les dernières lignes :

```bash
poetry run python scripts/check_logs.py
```

### Logging asynchrone (optionnel)

Variable d'environnement optionnelle : `ASYNC_DB_LOGGING=1` sur le service Gradio.
Si activée, les écritures dans `prediction_logs` passent dans un thread d'arrière-plan au lieu de bloquer la réponse HTTP. Utile pour réduire la latence utilisateur quand la base PostgreSQL est distante. Sans la variable, comportement synchrone (défaut, inchangé).

Documentation complète : [perf/optimization_postgres.md](perf/optimization_postgres.md).

### Inférence ONNX (optionnel)

Variable d'environnement optionnelle : `USE_ONNX=1` sur le service Gradio.
Si activée et si l'artefact `model/model_simple.onnx` est disponible, le scoring utilise ONNX Runtime. Sinon fallback sklearn (comportement par défaut).
L'artefact est versionné dans le repo, de la même manière que `model_simple.joblib` : pas de génération au build, déploiement simple.

Documentation complète : [perf/optimization_onnx.md](perf/optimization_onnx.md).

### Générer et injecter les données de démonstration

```bash
# Générer les deux jeux techniques de référence
poetry run python scripts/prepare_demo_data.py

# Injecter les prédictions de démonstration en prod
poetry run python scripts/inject_demo_requests.py --environment prod --allow-demo-prod

# Injecter quelques erreurs de démonstration en prod
poetry run python scripts/inject_demo_errors.py --environment prod --allow-demo-prod

# Lancer le dashboard sur l'environnement prod
APP_ENV=prod poetry run streamlit run dashboard_streamlit/app.py
```

## Performance

Mesures de performance et optimisations documentées pour l'application de scoring.

```bash
# Baseline in-process (inférence + service)
poetry run python scripts/benchmark_baseline.py

# Baseline complète avec HTTP (nécessite un serveur Gradio actif)
poetry run python scripts/benchmark_baseline.py --http
```

Deux optimisations ont été étudiées : ONNX Runtime pour le moteur d’inférence et le logging PostgreSQL asynchrone pour le temps de réponse applicatif.

Le notebook de synthèse correspondant est [`notebooks/02_performance_optimization.ipynb`](notebooks/02_performance_optimization.ipynb).

Synthèse :
- **ONNX Runtime** améliore fortement le moteur (scores équivalents, inférence ×50 environ), mais le gain absolu reste de l’ordre de la milliseconde.
- **PostgreSQL async** apporte un gain très net sur le temps HTTP **en local** (~918 ms gagnées en médiane).
- Sur la **préprod Render**, ce gain n’est pas observé clairement : la variabilité de l’environnement partagé masque l’effet. L’optimisation reste intéressante, mais son impact dépend du contexte d’hébergement.

Documentation disponible :
- Résultats JSON dans [perf/results/](perf/results/)
- Protocole de baseline : [perf/README.md](perf/README.md)
- Analyse des goulots : [perf/bottlenecks_analysis.md](perf/bottlenecks_analysis.md)
- Optimisation ONNX Runtime : [perf/optimization_onnx.md](perf/optimization_onnx.md)
- Optimisation PostgreSQL async : [perf/optimization_postgres.md](perf/optimization_postgres.md)

## Monitoring et drift

Ici, on a **volontairement simulé** des scores externes plus faibles, des revenus plus bas, des crédits plus élevés et une annuité légèrement plus élevée.

Jeux utilisés :
- **baseline** : échantillon extrait du split de test du modèle source ;
- **drift** : lot artificiellement drifté à partir de la baseline.

Lancer la préparation des jeux et l’injection de démonstration :

```bash
# Génère monitoring_baseline.csv et monitoring_drift.csv 
poetry run python scripts/prepare_demo_data.py
# Injecte les requêtes de démonstration en base
poetry run python scripts/inject_demo_requests.py --environment prod --allow-demo-prod
```

Le notebook [`notebooks/01_monitoring_drift.ipynb`](notebooks/01_monitoring_drift.ipynb) documente deux usages :
-  un aperçu des logs de prédiction ;
- une démonstration contrôlée de drift avec Evidently.

> Evidently détecte bien une dérive sur les variables ciblées. En revanche, d’autres variables ne franchissent pas le seuil statistique, ce qui montre aussi que l’outil ne remonte pas artificiellement tout comme “en drift”.
