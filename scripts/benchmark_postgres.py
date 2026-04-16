"""Benchmark HTTP + vérification fiable de l'intégrité des logs PostgreSQL.

Mesure la latence HTTP via gradio_client (même profil UI que la baseline)
et vérifie qu'aucune ligne de prediction_logs n'est perdue en mode async.

Isolation des logs du benchmark :
  1. Le serveur Gradio est lancé avec un APP_ENV dédié (ex : bench_sync).
     Toutes les écritures héritent de ce tag (mécanisme déjà en place dans
     src/database.py, qui taggue chaque ligne avec APP_ENV).
  2. Le script fait d'abord les warmups, puis capture un timestamp côté DB (SELECT NOW()) juste avant les appels mesurés,
  3. À la fin, filtre : environment = <bench_*> ET timestamp >= t0. Les warmups sont ainsi exclus du comptage.

Le mode sync vs async est contrôlé côté serveur par ASYNC_DB_LOGGING (0 / 1).
Ce script ne le contrôle pas ; il mesure ce que fait le serveur actif.

Usage :
    # Mode sync, environnement dédié
    APP_ENV=bench_sync poetry run python -m app_gradio.app                     # terminal A
    poetry run python scripts/benchmark_postgres.py --tag sync \\
            --environment bench_sync                                           # terminal B

    # Mode async, environnement dédié
    APP_ENV=bench_async ASYNC_DB_LOGGING=1 poetry run python -m app_gradio.app
    poetry run python scripts/benchmark_postgres.py --tag async \\
            --environment bench_async
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from time import perf_counter

import psycopg2
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.benchmark_baseline import UI_INPUT, summarize  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "perf" / "results"


def fetch_db_now(database_url: str):
    """Timestamp côté serveur DB, à utiliser comme borne inférieure du filtre."""
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT NOW()")
            return cur.fetchone()[0]


def count_rows_in_window(database_url: str, environment: str, since_ts) -> int:
    """Lignes insérées dans prediction_logs pour cet environnement depuis since_ts."""
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM prediction_logs "
                "WHERE environment = %s AND timestamp >= %s",
                (environment, since_ts),
            )
            return int(cur.fetchone()[0])


def warmup_http(url: str, warmup: int, api_name: str) -> None:
    from gradio_client import Client

    client = Client(url, verbose=False)
    args = (
        UI_INPUT["ext_source_1"], UI_INPUT["ext_source_2"], UI_INPUT["ext_source_3"],
        UI_INPUT["date_naissance"], UI_INPUT["date_embauche"], UI_INPUT["date_id"],
        UI_INPUT["amt_annuity"], UI_INPUT["amt_goods_price"], UI_INPUT["amt_credit"],
        UI_INPUT["amt_income_total"], UI_INPUT["is_married"],
    )
    for _ in range(warmup):
        client.predict(*args, api_name=api_name)



def bench_http(url: str, n: int, api_name: str) -> list[float]:
    from gradio_client import Client

    client = Client(url, verbose=False)
    args = (
        UI_INPUT["ext_source_1"], UI_INPUT["ext_source_2"], UI_INPUT["ext_source_3"],
        UI_INPUT["date_naissance"], UI_INPUT["date_embauche"], UI_INPUT["date_id"],
        UI_INPUT["amt_annuity"], UI_INPUT["amt_goods_price"], UI_INPUT["amt_credit"],
        UI_INPUT["amt_income_total"], UI_INPUT["is_married"],
    )
    timings = []
    for _ in range(n):
        t0 = perf_counter()
        client.predict(*args, api_name=api_name)
        timings.append((perf_counter() - t0) * 1000.0)
    return timings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark HTTP + vérif intégrité logs PostgreSQL."
    )
    parser.add_argument("--tag", required=True, help="Étiquette du run (ex : sync, async).")
    parser.add_argument(
        "--environment",
        required=True,
        help="APP_ENV avec lequel le serveur Gradio a été lancé (ex : bench_sync).",
    )
    parser.add_argument("--url", default="http://localhost:7860")
    parser.add_argument("--api-name", default="/gradio_predict")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument(
        "--max-wait-s",
        type=float,
        default=30.0,
        help="Temps max (s) à attendre le drain des écritures async.",
    )
    parser.add_argument(
        "--poll-interval-s",
        type=float,
        default=1.0,
        help="Intervalle (s) entre deux recomptages pendant le polling du drain.",
    )
    return parser.parse_args()


def poll_until_drained(
    database_url: str,
    environment: str,
    since_ts,
    expected: int,
    max_wait_s: float,
    poll_interval_s: float,
) -> tuple[int, float, bool]:
    """Recompte jusqu'à ce que inserted >= expected, ou timeout.

    Retourne (inserted, waited_s, drain_complete).
    Affiche la progression à chaque itération.
    """
    waited = 0.0
    inserted = count_rows_in_window(database_url, environment, since_ts)
    print(f"  t+{waited:>5.1f}s : inserted={inserted:>4d} / {expected}")
    while inserted < expected and waited < max_wait_s:
        time.sleep(poll_interval_s)
        waited += poll_interval_s
        inserted = count_rows_in_window(database_url, environment, since_ts)
        print(f"  t+{waited:>5.1f}s : inserted={inserted:>4d} / {expected}")
    drain_complete = inserted >= expected
    return inserted, waited, drain_complete


def main() -> None:
    args = parse_args()
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERREUR : DATABASE_URL non défini dans .env", file=sys.stderr)
        sys.exit(1)

    print("=" * 64)
    print(f"Benchmark PostgreSQL — tag={args.tag}, environment={args.environment}")
    print("=" * 64)

    print(f"\n[1/5] Warmup HTTP — warmup={args.warmup}")
    warmup_http(args.url, args.warmup, args.api_name)
    print("  ✓ warmup terminé (non compté dans l'intégrité des logs)")

    print("\n[2/5] Capture du timestamp DB de référence")
    t0 = fetch_db_now(database_url)
    print(f"  t0 (NOW() côté DB) = {t0}")

    print(f"\n[3/5] Benchmark HTTP mesuré — n={args.n}")
    timings = bench_http(args.url, args.n, args.api_name)
    stats = summarize(timings)

    expected = args.n
    print(
        f"\n[4/5] Polling du drain (max {args.max_wait_s}s, "
        f"intervalle {args.poll_interval_s}s)"
    )
    inserted, waited_s, drain_complete = poll_until_drained(
        database_url=database_url,
        environment=args.environment,
        since_ts=t0,
        expected=expected,
        max_wait_s=args.max_wait_s,
        poll_interval_s=args.poll_interval_s,
    )

    print("\n[5/5] Verdict")
    lost = expected - inserted
    print(f"  inserted ({args.environment}, ts >= t0) = {inserted}")
    print(f"  attendu                                 = {expected}")
    print(f"  waited_s                                = {waited_s:.1f}")
    if drain_complete and lost == 0:
        print("  ✓ drain complet, aucune perte")
    elif lost > 0:
        print(f"  ✗ {lost} ligne(s) manquante(s) après {waited_s:.1f}s")
        print(f"    (timeout {args.max_wait_s}s atteint — soit perte réelle, "
              f"soit drain plus lent que la fenêtre)")
    else:
        print(f"  ⚠ {-lost} ligne(s) inattendue(s) — run parallèle sur même environnement ?")

    results = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "tag": args.tag,
        "environment": args.environment,
        "protocol": {
            "n": args.n, "warmup": args.warmup,
            "max_wait_s": args.max_wait_s,
            "poll_interval_s": args.poll_interval_s,
            "url": args.url, "api_name": args.api_name,
            "db_timestamp_before": t0.isoformat(),
            "sample_profile": "profil_ui_senior_stable",
            "ui_input": UI_INPUT,
        },
        "env": {"python": sys.version.split()[0], "platform": platform.platform()},
        "log_integrity": {
            "inserted": inserted,
            "expected": expected,
            "lost": lost,
            "waited_s": round(waited_s, 2),
            "drain_complete": drain_complete,
            "ok": drain_complete and lost == 0,
        },
        "metrics": {
            "http": {"stats": stats, "raw_ms": [round(t, 4) for t in timings]},
        },
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"postgres_{args.tag}_{ts}.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n→ Résultats sauvegardés : {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
