# Performance — protocole de mesure baseline

## Objectif
Établir une référence chiffrée des temps d'inférence et de réponse API avant
toute optimisation (étape 4 du projet).

## Portées mesurées

| Portée     | Ce qui est inclus dans la mesure | Ce qui est exclu |
|------------|----------------------------------|-------------------|
| inference  | Uniquement `model.predict_proba(df)`. Le DataFrame est préparé une fois hors mesure via les briques du pipeline (`date_str_to_days`, `compute_ratios`, `FEATURES`). | Préparation des features, validation, DB, réseau |
| service    | Appel complet de `score_client()` : validation des entrées, conversion des dates (`date_str_to_days`), construction du dict technique, `compute_ratios`, build DataFrame, `predict_proba`, construction du `ScoringResult`. | Logging PostgreSQL (stubbé via `unittest.mock.patch`), réseau |
| http       | Aller-retour complet via `gradio_client` : sérialisation JSON côté client, transport réseau aller, file d'attente Gradio (queue), exécution serveur (= `service` + logging PostgreSQL réel), sérialisation de la réponse, transport réseau retour, désérialisation côté client. | Rendu navigateur (non exécuté par `gradio_client`) |

Lecture des écarts :
- `service` − `inference` = coût validation + conversion dates + construction DataFrame
- `http` − `service` = coût réseau + queue Gradio + (de)sérialisation + logging PostgreSQL réel

## Protocole
- **Profil d'entrée fixe** : profil UI unique, déterministe. Les features techniques sont dérivées par le vrai pipeline (via les helpers du projet), pas codées en dur.
- **Warmup** : 5 appels non mesurés (absorbe le coût du premier appel : initialisations LightGBM, handshake TCP/Gradio).
- **Mesure** : 100 appels chronométrés avec `time.perf_counter`.
- **Stats** : moyenne, médiane, max, p95 (en millisecondes).
- **Résultats** : un fichier JSON horodaté par run dans `perf/results/`, contenant protocole + environnement + stats + timings bruts.

## Lancer la baseline

```bash
# Baseline in-process (inférence + service). Pas besoin de DB ni de serveur.
poetry run python scripts/benchmark_baseline.py

# Baseline complète avec HTTP local
# Terminal A :
poetry run python -m app_gradio.app
# Terminal B :
poetry run python scripts/benchmark_baseline.py --http

# HTTP contre la préprod Render
poetry run python scripts/benchmark_baseline.py --http \
    --url https://oc-p8-gradio-preprod.onrender.com --tag baseline_preprod
```

Le nom d'endpoint HTTP est auto-détecté si un seul endpoint nommé est exposé.
Si plusieurs sont détectés, le script liste les noms et demande de choisir via
`--api-name`.

## Comparer avant / après optimisation

Chaque run produit un JSON horodaté avec les timings bruts. Pour comparer :

```bash
ls perf/results/
# Les stats sont dans metrics.<portée>.stats,
# les timings bruts dans metrics.<portée>.raw_ms.
```

Un histogramme ou une comparaison de médianes peut se faire à la main depuis
les `raw_ms` si besoin.
