"""Injecte quelques erreurs de demonstration via le vrai flux de scoring.

Le script envoie plusieurs saisies invalides a `score_client()` pour
alimenter la table `prediction_errors` sans insertion SQL manuelle.

Usage :
    poetry run python scripts/inject_demo_errors.py
    poetry run python scripts/inject_demo_errors.py --environment preprod
    poetry run python scripts/inject_demo_errors.py --environment prod --allow-demo-prod
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import psycopg2
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEMO_ERRORS = [
    {
        "ext_source_1": 0.52,
        "ext_source_2": 0.41,
        "ext_source_3": 0.38,
        "date_naissance": "1988-06-10",
        "date_embauche": "2015-04-01",
        "date_id": "2019-03-10",
        "amt_annuity": 18000.0,
        "amt_goods_price": -1.0,
        "amt_credit": 150000.0,
        "amt_income_total": 210000.0,
        "is_married": "Oui",
    },
    {
        "ext_source_1": 0.21,
        "ext_source_2": 0.34,
        "ext_source_3": 0.18,
        "date_naissance": "pas-une-date",
        "date_embauche": "2018-01-01",
        "date_id": "2020-01-01",
        "amt_annuity": 12000.0,
        "amt_goods_price": 100000.0,
        "amt_credit": 90000.0,
        "amt_income_total": 150000.0,
        "is_married": "Non",
    },
    {
        "ext_source_1": 0.72,
        "ext_source_2": 0.65,
        "ext_source_3": 0.51,
        "date_naissance": "1995-08-15",
        "date_embauche": "1990-01-01",
        "date_id": "2018-03-01",
        "amt_annuity": 14000.0,
        "amt_goods_price": 160000.0,
        "amt_credit": 170000.0,
        "amt_income_total": 220000.0,
        "is_married": "Oui",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Injecte des erreurs de demonstration dans prediction_errors."
    )
    parser.add_argument(
        "--environment",
        choices=["preprod", "prod"],
        default="preprod",
        help="Environnement cible pour l'injection (defaut : preprod).",
    )
    parser.add_argument(
        "--allow-demo-prod",
        action="store_true",
        help="Autorise explicitement l'injection de donnees de demonstration en prod.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.environment == "prod" and not args.allow_demo_prod:
        print("ERREUR : l'injection en prod est bloquee par defaut.")
        print("Ajoutez le flag --allow-demo-prod pour autoriser explicitement cette demo.")
        sys.exit(1)


def format_database_label(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if not parsed.scheme or not parsed.hostname:
        return "DATABASE_URL definie"

    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    database_name = parsed.path.lstrip("/") or "(default)"
    return f"{parsed.scheme}://{host}{port}/{database_name}"


def load_runtime_dependencies():
    from app_gradio.scoring_service import score_client
    from src.database import ensure_tables

    return score_client, ensure_tables


def generate_timestamps(n: int, start_days_ago: float, end_days_ago: float) -> list:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=start_days_ago)
    end = now - timedelta(days=end_days_ago)

    if n == 1:
        return [start]

    step = (end - start) / (n - 1)
    return [start + step * i for i in range(n)]


def count_errors_in_db(database_url: str, environment: str) -> int:
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM prediction_errors WHERE environment = %s",
                (environment,),
            )
            return int(cur.fetchone()[0])


def read_recent_errors(database_url: str, environment: str, limit: int) -> pd.DataFrame:
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, timestamp, environment, error_type, error_message
                FROM prediction_errors
                WHERE environment = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (environment, limit),
            )
            rows = cur.fetchall()

    return pd.DataFrame(
        rows,
        columns=["id", "timestamp", "environment", "error_type", "error_message"],
    )


def main():
    args = parse_args()
    validate_args(args)

    load_dotenv()
    os.environ["APP_ENV"] = args.environment
    score_client, ensure_tables = load_runtime_dependencies()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERREUR : DATABASE_URL non defini dans .env")
        sys.exit(1)

    print("=" * 60)
    print("Injection des erreurs de demonstration")
    print("=" * 60)
    print(f"\nEnvironnement cible : {args.environment}")
    print(f"Base utilisee : {format_database_label(database_url)}")
    if args.environment == "prod":
        print("Mode demo prod explicitement autorise")
    else:
        print("Mode demo prod : non (environnement preprod)")

    ensure_tables()

    timestamps = generate_timestamps(len(DEMO_ERRORS), start_days_ago=2, end_days_ago=0)
    count_before = count_errors_in_db(database_url, args.environment)

    print(f"\nCas invalides injectes : {len(DEMO_ERRORS)}")
    print(f"Base avant injection ({args.environment}) : {count_before} erreurs")

    rejected = 0
    unexpected_success = 0

    for payload, logged_at in zip(DEMO_ERRORS, timestamps):
        result = score_client(**payload, logged_at=logged_at)
        if result.success:
            unexpected_success += 1
        else:
            rejected += 1

    count_after = count_errors_in_db(database_url, args.environment)
    delta = count_after - count_before
    recent_errors = read_recent_errors(database_url, args.environment, len(DEMO_ERRORS))

    print(f"\nRejets attendus : {rejected}")
    print(f"Acceptations inattendues : {unexpected_success}")
    print(f"Base apres injection ({args.environment}) : {count_after} erreurs")
    print(f"Delta observe : {delta}")

    checks_ok = True

    if rejected != len(DEMO_ERRORS) or unexpected_success != 0:
        print("  ✗ Les cas invalides n'ont pas tous ete rejetes")
        checks_ok = False
    else:
        print(f"  ✓ {rejected}/{len(DEMO_ERRORS)} cas invalides rejetes")

    if delta != len(DEMO_ERRORS):
        print(f"  ✗ Delta incorrect : {delta} ≠ {len(DEMO_ERRORS)}")
        checks_ok = False
    else:
        print(f"  ✓ Delta correct : +{delta} erreurs")

    if len(recent_errors) != len(DEMO_ERRORS):
        print("  ✗ Relecture incomplete des erreurs recentes")
        checks_ok = False
    elif not (recent_errors["environment"] == args.environment).all():
        print("  ✗ Certaines erreurs n'ont pas le bon environment")
        checks_ok = False
    elif not (recent_errors["error_type"] == "validation_error").all():
        print("  ✗ Le type d'erreur attendu n'est pas uniforme")
        checks_ok = False
    else:
        print("  ✓ Erreurs relues avec le bon environment et le bon type")

    if checks_ok:
        print("\nToutes les verifications sont passees.")
    else:
        print("\nATTENTION : certaines verifications ont echoue.")
        sys.exit(1)


if __name__ == "__main__":
    main()
