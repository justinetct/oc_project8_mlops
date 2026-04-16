# Optimisation testée : logging PostgreSQL asynchrone

## Résultats clés

### 1. Résultats mesurés directement

| Volet | Configuration comparée | Mesure utile | Résultat | 
|-------|-------------------------|-------------|---------|
| Moteur | sklearn vs ONNX | médiane inférence | 0.619 ms → 0.012 ms | 
| Applicatif | PostgreSQL sync vs async | médiane HTTP locale | 1038.756 ms → 120.843 ms | 
| Applicatif | PostgreSQL sync vs async | intégrité des logs | 100/100 → 100/100 |

### 2. Lecture simple des optimisations

| Optimisation | Ce qu'elle améliore | Gain principal | Conclusion |
|-------------|---------------------|---------------|------------|
| ONNX Runtime | moteur d'inférence | ~0.6 ms gagnée par appel | optimisation moteur validée |
| PostgreSQL async | temps de réponse HTTP | ~918 ms gagnées sur la médiane locale | optimisation applicative retenue |

### 3. Lecture combinée

| Cas | Lecture |
|-----|---------|
| ONNX seul | utile pour accélérer le moteur, mais impact limité seul sur le temps utilisateur |
| PostgreSQL async seul | très fort impact sur le temps HTTP mesuré |
| ONNX + PostgreSQL async | combinaison cohérente : moteur plus rapide + application plus rapide |

### 4. Préprod

| Configuration                       | HTTP préprod (médiane) | Statut                       |
|-------------------------------------|-----------------------:|------------------------------|
| baseline                            |              372.247 ms | mesuré                       |
| baseline + ONNX                     | n/a                    | non déployé                  |
| baseline + PostgreSQL async         |              380.158 ms | mesuré (ASYNC=1 sur Gradio) |
| baseline + ONNX + PostgreSQL async  | n/a                    | non déployé                  |

Sur cette préprod Render, l'écart entre baseline et version async est
faible et ne montre **pas de gain net** (372 → 380 ms), là où le gain local
est très marqué (1038 → 121 ms). La latence HTTP préprod dépend de
plusieurs facteurs hors du chemin applicatif (CPU partagé Render, réseau,
cold start, variance d'infra) qui pèsent davantage que l'optimisation
testée. Le résultat local reste valide ; il n'est simplement pas
**reproduit** dans cet environnement d'hébergement.


## Motivation

Les mesures baseline et l'analyse des goulots ont montré que le temps `http`
est très supérieur au temps `service`. Une partie de cet écart vient de
l'écriture PostgreSQL synchrone : elle est hors de `duration_ms`, mais dans
le chemin critique HTTP. Avec une base distante (Render PostgreSQL), cette
écriture ajoute une latence réseau significative à chaque requête.

Hypothèse : déplacer cette écriture dans un thread d'arrière-plan réduit la
latence HTTP perçue, sans changer le comportement fonctionnel côté base.

## Protocole

- `src/database.py` dispatche vers un `ThreadPoolExecutor` si la variable
  d'environnement `ASYNC_DB_LOGGING=1`. Comportement par défaut inchangé.
- `atexit` registre un `shutdown(wait=True)` pour garantir le drain des
  écritures à la fermeture du process.
- Isolation des logs du benchmark :
  - serveur lancé avec un `APP_ENV` dédié (`bench_sync` / `bench_async`) —
    le code existant taggue déjà chaque ligne avec `APP_ENV`,
  - capture d'un `timestamp` via `SELECT NOW()` côté DB avant les appels
    mesurés,
  - comptage final : `environment = <bench_*>` **et** `timestamp >= t0`.
- Intégrité vérifiée via polling : `--max-wait-s 30 --poll-interval-s 1`
  (permet de distinguer une vraie perte d'un drain qui prend du temps).
- Deux runs via `scripts/benchmark_postgres.py`, même profil UI que la
  baseline.

Reproductible :

```bash
# Sync (DB dans le chemin critique)
APP_ENV=bench_sync poetry run python -m app_gradio.app
poetry run python scripts/benchmark_postgres.py --tag sync --environment bench_sync

# Async (DB hors chemin critique)
APP_ENV=bench_async_20260416_1255 ASYNC_DB_LOGGING=1 poetry run python -m app_gradio.app
poetry run python scripts/benchmark_postgres.py --tag async \
    --environment bench_async_20260416_1255 --max-wait-s 30
```

## Résultats

### Local

Runs utilisés comme référence :
- `perf/results/postgres_sync_20260416_124914.json` (tag `sync`)
- `perf/results/postgres_async_20260416_125817.json` (tag `async`)

| mode  | http médiane (ms) | p95 (ms) | max (ms) | inserted / attendu | drain | perte ? |
|-------|------------------:|---------:|---------:|-------------------:|------:|:-------:|
| sync  |          1038.756 | 1504.851 | 1621.464 | 100 / 100          |    0s | non     |
| async |           120.843 |  127.760 |  130.209 | 100 / 100          |  ~19s | non     |

- Gain absolu médiane : **~918 ms** (1038.756 − 120.843).
- Ratio médiane sync / async : **×8.6**.
- Intégrité confirmée des deux côtés : 100 lignes insérées pour 100 requêtes.
  En mode async, le drain complet est atteint après environ **19 secondes**
  de polling — pas de perte, simplement un écart temporel entre la réponse
  HTTP et l'insertion effective en base.

### Préprod Render

Runs utilisés comme référence :
- `perf/results/preprod_20260416_105012.json` (baseline préprod, sync)
- `perf/results/preprod_20260416_144314.json` (préprod, `ASYNC_DB_LOGGING=1` sur le service Gradio)

| mode             | http médiane (ms) | p95 (ms) | max (ms) |
|------------------|------------------:|---------:|---------:|
| préprod baseline |           372.247 |  539.550 |  711.288 |
| préprod async    |           380.158 |  403.750 |  656.670 |

L'effet très net observé en local **n'est pas reproduit** sur cette préprod
Render. L'écart des médianes (372 → 380 ms) est dans le bruit d'un
environnement partagé. Les raisons probables — sans qu'on puisse les isoler
précisément dans le cadre de ce projet :

- CPU partagé et variance d'infrastructure Render
- latence réseau entre client, service Gradio et base PostgreSQL, non
  reproductible sur un test local
- effets de cold start ou de file d'attente côté Render

L'intégrité des logs n'a volontairement pas été re-testée en préprod : le
code est identique à celui validé localement, et ajouter un `APP_ENV`
dédié juste pour cela aurait pollué la base.

## Lecture

- `duration_ms` stocké en base n'est **pas** affecté par cette optimisation :
  il est mesuré avant l'appel à `log_prediction`.
- La métrique qui bouge est `http` côté client — c'est bien le temps perçu
  par l'utilisateur qui est optimisé.
- L'écart est massif parce que la base PostgreSQL utilisée est **distante**
  (Render) : chaque INSERT coûte plusieurs centaines de millisecondes de
  latence réseau. Sortir cette écriture du chemin critique supprime cette
  attente côté utilisateur.
- L'isolation par `environment + timestamp` garantit que le comptage
  n'inclut que les lignes du run, même si d'autres trafics arrivent sur la
  base.
- Contrepartie à assumer : les logs arrivent en base avec **quelques
  secondes de décalage** (ici environ 19 s pour 100 requêtes). Acceptable
  pour un usage monitoring / analyse, à signaler pour un usage qui dépend
  du temps réel.

## Décision

**PostgreSQL asynchrone est retenu comme optimisation applicative, avec
une nuance sur l'environnement de déploiement.**

Ce qui est validé :

- Gain mesuré très significatif sur le temps HTTP **en local** : environ
  **×8.6 sur la médiane**, soit **~918 ms gagnées** par requête.
- Intégrité des logs vérifiée localement (run `bench_async_20260416_1255`,
  100/100 lignes insérées, drain complet en ~19 s).
- Implémentation minimale : un `ThreadPoolExecutor` et un toggle
  `ASYNC_DB_LOGGING`, sans nouvelle dépendance.

Ce qu'il faut nuancer :

- Sur cette **préprod Render**, le gain n'est pas observé clairement
  (372 → 380 ms). L'effet théorique reste valable, mais il est masqué par
  la variabilité de l'environnement.
- L'optimisation reste donc intéressante, mais son **impact réel dépend
  du contexte d'hébergement** (CPU maîtrisé vs infra partagée, base locale
  vs base distante, charge concurrente).

Pour la défense orale : c'est l'optimisation la plus visible côté
utilisateur **en local** ; sur Render, il faut la présenter comme validée
mais non confirmée sur cette préprod.
