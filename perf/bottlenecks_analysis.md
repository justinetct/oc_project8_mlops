# Analyse simple des goulots d'étranglement

## Objectif

Identifier, avec des mesures simples, ce qui ralentit le plus l'application aujourd'hui. Le but est de repérer quelques pistes d'optimisation pour l'étape suivante, sans encore décider de la solution finale.


> **Résultats clés**
> - **Inference (local)** : médiane **0.514 ms**
> - **Service (local)** : médiane **0.737 ms**
> - **HTTP local** : médiane **121.810 ms**
> - **HTTP préprod** : médiane **372.247 ms**
> - **`duration_ms` préprod** : médiane **4.877 ms**, p95 **7.679 ms**
> - **cProfile local** : **1.742 s** pour 1000 appels, soit environ **1.75 ms / appel**
> - **Conclusion rapide** : le modèle est très rapide ; le temps utilisateur vient surtout de la couche autour du modèle.

## Méthodologie

On s'appuie sur 3 sources simples :

1. **Baseline** (`perf/results/baseline_*.json`)
   Mesures déjà faites sur les temps `inference`, `service` et `http`.
   
2. **cProfile** (`perf/results/cprofile_*.txt`)
   Profiling de `score_client()` appelé 1000 fois, sans la base, pour regarder où le temps est passé côté Python.

3. **Monitoring production** (`prediction_logs.duration_ms`)
   Cette métrique mesure le temps passé dans `score_client()` en préprod.
   Elle couvre la validation, la préparation des données et la prédiction.
   Elle ne couvre pas le transport HTTP, la queue Gradio ni l'écriture en base.
   Elle complète donc la baseline locale, mais ne remplace pas la mesure HTTP côté client.

Commandes reproductibles :

```bash
# 1. cProfile + CPU/RAM (in-process, pas de DB ni de serveur requis)
poetry run python scripts/profile_bottlenecks.py --n 1000

# 2. Agrégat monitoring production (DATABASE_URL dans .env)
set -a; source .env; set +a
psql "$DATABASE_URL" -c "SELECT COUNT(*), \
  ROUND(AVG(duration_ms)::numeric, 3) AS mean_ms, \
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) AS median_ms, \
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms, \
  MAX(duration_ms) AS max_ms \
  FROM prediction_logs WHERE environment = 'preprod';"
```

## Constats mesurés

### Baseline (médianes sur n=100)

| Portée       | Médiane (ms) | Source |
|--------------|-------------:|--------|
| inference    |        0.514 | `perf/results/baseline_20260416_101611.json` |
| service      |        0.737 | idem |
| http local   |      121.810 | idem |
| http préprod |      372.247 | `perf/results/preprod_20260416_105012.json` |

### cProfile — top fonctions par temps cumulé (cumtime)

Commande : `poetry run python scripts/profile_bottlenecks.py --n 1000`
Résultat global : **1.742 s** pour 1000 appels, soit environ **1.75 ms par appel**.
Détail complet : `perf/results/cprofile_20260416_111819.txt`.

| fonction                                         | ncalls | cumtime (s) | tottime (s) |
|--------------------------------------------------|-------:|------------:|------------:|
| `scoring_service.score_client` (racine)          |   1000 |       1.748 |       0.005 |
| `app_gradio.predict.predict`                     |   1000 |       1.682 |       0.006 |
| `sklearn.pipeline.Pipeline.predict_proba`        |   1000 |       1.246 |       0.002 |
| `sklearn.utils._set_output.wrapped` (output pandas) |   1000 |       0.625 |       0.001 |
| `sklearn.utils.validation.check_array`           |   1000 |       0.479 |       0.014 |
| `lightgbm.basic.Booster.predict` (calcul LightGBM pur) | 1000 |    0.301 |       0.001 |
| `pandas.frame.DataFrame.__init__`                |   2000 |       0.246 |       0.007 |
| `pandas.series.Series.__init__`                  |  12000 |       0.311 |       0.040 |

### CPU / RAM pendant le profiling

- Elapsed : 1.749 s
- CPU time total : 1.773 s
- CPU % : 101.4 (un process Python mono-thread se rapproche de 100 % d'un cœur en charge CPU pure — cohérent)
- Peak RSS : 213.3 MB

### Monitoring production (`prediction_logs`, environment='preprod')

| n   | mean_ms | median_ms | p95_ms | max_ms  |
|----:|--------:|----------:|-------:|--------:|
| 843 |   5.589 |     4.877 |  7.679 | 157.662 |

## Interprétation prudente

Les résultats montrent surtout 3 choses.

- **Le modèle seul n'est pas le principal problème côté utilisateur.**
  En local, `service` est inférieur à 1 ms, alors que `http` est autour de 122 ms en local et 372 ms en préprod. La plus grande partie du temps vient donc de la couche autour du modèle : HTTP, Gradio, sérialisation, environnement de déploiement et logging.

- **Dans le chemin Python local, le temps ne vient pas seulement du calcul LightGBM.**
  Le calcul pur LightGBM représente environ **17 %** du temps profilé. Une grande partie du coût vient plutôt de l'overhead `sklearn` et `pandas` autour du modèle : validation, transformation de sortie et construction des objets pandas.

- **La préprod est plus lente que le local sur la partie service.**
  La médiane `duration_ms` en préprod est d'environ **4.88 ms**, contre **0.74 ms** en local. Cela suggère surtout un effet d'environnement (conteneur, ressources partagées, charge), sans permettre d'isoler une cause précise à ce stade.

Le `max_ms` à **157.662 ms** reste isolé. Il peut venir d'un événement ponctuel et ne doit pas être sur-interprété.

### Pourquoi le GPU n'est pas pertinent ici

1. Le modèle utilisé est un LightGBM, pas un modèle qui a vraiment besoin d'un GPU pour ce type d'inférence.
2. L'application traite un dossier à la fois, pas de gros batchs.
3. Le temps principal vu par l'utilisateur ne vient pas du calcul du modèle seul.
4. L'environnement de déploiement actuel ne fournit pas de GPU.

## Hypothèses d'optimisation

Ces pistes seront testées plus tard. À ce stade, ce sont seulement des hypothèses.

1. **Réduire l'overhead `sklearn` / `pandas` autour du modèle.**
   Le profiling montre que la validation et la manipulation des objets pandas prennent une place importante dans la portée `service`.

2. **Sortir le logging PostgreSQL du chemin critique HTTP.**
   L'écriture en base ne fait pas partie de `duration_ms`, mais elle fait partie du temps de réponse vu par le client.

3. **Regarder la couche d'exposition HTTP / Gradio.**
   L'écart entre `service` et `http` suggère qu'une partie importante du temps est hors modèle.

La priorisation exacte sera faite dans la tâche suivante, après choix de l'optimisation à tester.
