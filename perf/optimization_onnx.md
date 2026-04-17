# Optimisation testée : ONNX Runtime

## Résultats clés

| Élément | Résultat |
|--------|---------:|
| Statut conversion | ok |
| Écart de score sklearn vs ONNX | 9.37e-09 |
| Médiane sklearn | 0.619 ms |
| Médiane ONNX | 0.012 ms |
| Ratio médiane sklearn / ONNX | ×51.58 |
| Gain absolu par appel | ~0.6 ms |

### Lecture rapide

- **ONNX** améliore fortement le **moteur d'inférence**.
- Les scores restent **équivalents** à ceux de la version sklearn.
- Le gain est réel sur le moteur, mais reste **faible en valeur absolue** à l'échelle du temps de réponse complet.
- Cette optimisation est donc **retenue comme optimisation moteur**, en complément de l'optimisation applicative documentée dans `perf/optimization_postgres.md`.

## Motivation

Tester si ONNX Runtime permet d'accélérer le moteur d'inférence du modèle de scoring.

L'analyse des goulots a montré que le moteur n'était pas le seul facteur du temps de réponse complet, mais je voulais quand même mesurer cette piste explicitement, car elle est citée dans l'énoncé.

Le test reste **isolé** : aucune modification du code produit, aucun changement dans `app_gradio/`, `src/`, `loader.py` ou `predict.py`.

## Protocole

Le script `scripts/benchmark_onnx.py` exécute deux phases.

**Phase 1 — Faisabilité**
- conversion de la pipeline sklearn en ONNX ;
- vérification de la cohérence des scores sur le profil UI de référence ;
- statut produit : `ok`, `conversion_failed` ou `score_divergence`.

**Phase 2 — Benchmark**
- 100 appels mesurés après 5 warmup ;
- comparaison `sklearn.Pipeline.predict_proba` vs `onnxruntime.InferenceSession.run` ;
- même DataFrame d'entrée dans les deux cas.

Dans tous les cas, un JSON est sauvegardé dans `perf/results/onnx_<ts>.json`.

Reproductible :

```bash
poetry install --with perf
poetry run python scripts/benchmark_onnx.py
```

## Résultats

Source : `perf/results/onnx_20260416_120544.json`.

| portée  | médiane (ms) | p95 (ms) | max (ms) |
|---------|-------------:|---------:|---------:|
| sklearn |        0.619 |    1.780 |    2.363 |
| onnx    |        0.012 |    0.017 |    0.019 |

- Écart de score sklearn vs ONNX : **9.37e-09**.
- Tolérance fixée : **1e-4**.
- Ratio médiane sklearn / ONNX : **×51.58**.

## Lecture

Le gain ONNX est net sur le **moteur d'inférence**.

En revanche, il faut garder en tête que :
- le gain absolu reste d'environ **0.6 ms** par appel ;
- le temps de réponse utilisateur dépend aussi de la couche HTTP et du logging ;
- une mesure préprod Render reste une mesure **end-to-end**, pas une mesure pure du moteur.

Donc ONNX améliore bien le moteur, mais ne suffit pas à lui seul à transformer fortement le temps de réponse complet.

## Décision

**ONNX Runtime est retenu comme optimisation du moteur d'inférence.**

Ce qui est validé :
- la conversion fonctionne ;
- les scores restent cohérents avec la version sklearn ;
- l'inférence est beaucoup plus rapide sur ce périmètre isolé.

Ce qu'il faut nuancer :
- le gain mesuré porte sur le moteur seul ;
- le gain utilisateur complet reste limité si on n'optimise pas aussi la couche applicative.

Conclusion pratique :
- **ONNX = optimisation moteur validée** ;
- **PostgreSQL async = optimisation applicative complémentaire**.

## Lecture combinée

Les deux optimisations n'agissent pas au même niveau :
- **ONNX** accélère le moteur d'inférence ;
- **PostgreSQL async** réduit fortement le temps HTTP complet **en local**,
  sans effet clair sur la préprod Render dans nos mesures.

Elles restent **complémentaires** dans le récit : moteur d'un côté, chemin
applicatif de l'autre.

Pour la lecture finale et le tableau récapitulatif global, voir `perf/optimization_postgres.md`.
