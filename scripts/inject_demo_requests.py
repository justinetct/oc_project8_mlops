"""Injecte les lots techniques de demonstration dans la base de monitoring.

Lit les 2 CSV techniques de demo et :
  - score chaque ligne avec le pipeline local
  - loggue les predictions dans prediction_logs
  - verifie le delta dans la base cible
  - verifie que baseline et drift sont bien etales dans le temps

Les timestamps sont repartis ainsi :
  - baseline : ancienne periode, de J-20 a J-10
  - drift    : periode recente, de J-10 a J

Usage :
    poetry run python scripts/inject_demo_requests.py
    poetry run python scripts/inject_demo_requests.py --environment preprod
    poetry run python scripts/inject_demo_requests.py --environment prod --allow-demo-prod

Chaque execution ajoute de nouvelles lignes (pas de deduplication).
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Ajouter la racine du projet au path pour les imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Configuration
# ============================================================

DATA_DIR = PROJECT_ROOT / "data" / "demo"

FILES = {
    "baseline": DATA_DIR / "monitoring_baseline.csv",
    "drift": DATA_DIR / "monitoring_drift.csv",
}


# ============================================================
# Generation des timestamps
# ============================================================


def generate_timestamps(
    n: int,
    start_days_ago: float,
    end_days_ago: float,
    seed: int = 42,
) -> list:
    """Genere n timestamps avec une repartition journaliere naturelle et reproductible.

    - Chaque journee de la fenetre recoit un poids tire dans [0.7, 1.3] (seed fixe).
    - Les poids sont normalises puis convertis en comptes entiers de somme exacte n.
    - Les timestamps sont ensuite disperses dans la journee correspondante.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=start_days_ago)
    end = now - timedelta(days=end_days_ago)

    if n == 0:
        return []

    rng = np.random.default_rng(seed)
    n_days = max(1, round((end - start).total_seconds() / 86400))

    # Poids journaliers bornes : evite volumes plats et pics absurdes
    weights = rng.uniform(0.7, 1.3, size=n_days)
    weights /= weights.sum()

    # Comptes entiers par jour, somme exacte = n
    raw = weights * n
    counts = np.floor(raw).astype(int)
    remainder = int(n - counts.sum())
    if remainder > 0:
        order = np.argsort(-(raw - counts))
        for i in range(remainder):
            counts[order[i % n_days]] += 1

    # Dispersion intra-journee
    timestamps = []
    for day_idx, count in enumerate(counts):
        day_start = start + timedelta(days=day_idx)
        offsets = rng.uniform(0, 86400, size=int(count))
        timestamps.extend(day_start + timedelta(seconds=float(s)) for s in offsets)

    timestamps.sort()
    return timestamps


# ============================================================
# Utilitaires
# ============================================================


def parse_args() -> argparse.Namespace:
    """Lit les arguments CLI."""
    parser = argparse.ArgumentParser(
        description="Injecte les lots techniques de demonstration dans prediction_logs."
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
    """Bloque l'injection en prod sans autorisation explicite."""
    if args.environment == "prod" and not args.allow_demo_prod:
        print("ERREUR : l'injection en prod est bloquee par defaut.")
        print("Ajoutez le flag --allow-demo-prod pour autoriser explicitement cette demo.")
        sys.exit(1)


def format_database_label(database_url: str) -> str:
    """Retourne une description courte de la base cible sans mot de passe."""
    parsed = urlsplit(database_url)
    if not parsed.scheme or not parsed.hostname:
        return "DATABASE_URL definie"

    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    database_name = parsed.path.lstrip("/") or "(default)"
    return f"{parsed.scheme}://{host}{port}/{database_name}"


def load_runtime_dependencies():
    """Importe les modules qui lisent APP_ENV apres sa definition."""
    from app_gradio.loader import FEATURES, THRESHOLD, model
    from app_gradio.predict import compute_ratios
    from src.database import ensure_tables, log_prediction

    return {
        "model": model,
        "features": FEATURES,
        "threshold": THRESHOLD,
        "compute_ratios": compute_ratios,
        "ensure_tables": ensure_tables,
        "log_prediction": log_prediction,
    }


def count_rows_in_db(database_url: str, environment: str) -> int:
    """Compte le nombre de lignes dans prediction_logs pour un environnement."""
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM prediction_logs WHERE environment = %s",
                (environment,),
            )
            return cur.fetchone()[0]


def read_recent_logs(database_url: str, environment: str, limit: int) -> pd.DataFrame:
    """Lit les dernieres lignes d'un environnement cible."""
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, timestamp, environment, score, label, threshold
                FROM prediction_logs
                WHERE environment = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (environment, limit),
            )
            rows = cur.fetchall()

    return pd.DataFrame(
        rows,
        columns=["id", "timestamp", "environment", "score", "label", "threshold"],
    )


def score_technical_row(
    row: pd.Series,
    model,
    features: list[str],
    threshold: float,
    compute_ratios_fn,
) -> tuple[float, str, float, dict, float]:
    """Score une ligne technique et retourne score, label, seuil, features."""
    start_time = perf_counter()
    data = compute_ratios_fn(row.to_dict())
    df = pd.DataFrame([data])[features]

    proba = float(model.predict_proba(df)[0, 1])
    label = "Crédit accordé" if proba < threshold else "Crédit refusé"
    duration_ms = round((perf_counter() - start_time) * 1000, 3)

    return round(proba, 6), label, threshold, data, duration_ms


def inject_lot(
    df: pd.DataFrame,
    lot_name: str,
    timestamps: list,
    runtime: dict,
) -> dict:
    """Injecte un lot technique et retourne les compteurs."""
    inserted = 0
    failures = 0
    details = []

    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            score, label, threshold, features, duration_ms = score_technical_row(
                row=row,
                model=runtime["model"],
                features=runtime["features"],
                threshold=runtime["threshold"],
                compute_ratios_fn=runtime["compute_ratios"],
            )
            runtime["log_prediction"](
                score=score,
                label=label,
                threshold=threshold,
                features=features,
                duration_ms=duration_ms,
                logged_at=timestamps[idx],
            )
            inserted += 1
        except Exception as exc:
            failures += 1
            details.append(f"  Ligne {idx}: echec inattendu — {exc}")

    return {"inserted": inserted, "failures": failures, "details": details, "lot": lot_name}


def verify_recent_inserts(
    database_url: str,
    environment: str,
    baseline_count: int,
    drift_count: int,
) -> bool:
    """Verifie les timestamps et l'ordre temporel baseline puis drift."""
    total_count = baseline_count + drift_count
    recent_logs = read_recent_logs(database_url, environment, total_count)

    if len(recent_logs) != total_count:
        print(f"  ✗ Nombre de lignes relues insuffisant : {len(recent_logs)} / {total_count}")
        return False

    if not (recent_logs["environment"] == environment).all():
        print("  ✗ Certaines lignes relues n'ont pas le bon environment")
        return False

    recent_logs = recent_logs.sort_values("id").reset_index(drop=True)
    baseline_logs = recent_logs.iloc[:baseline_count].copy()
    drift_logs = recent_logs.iloc[baseline_count:].copy()

    baseline_dates = sorted(set(ts.date() for ts in baseline_logs["timestamp"]))
    drift_dates = sorted(set(ts.date() for ts in drift_logs["timestamp"]))

    print(
        f"  Baseline : {baseline_logs['timestamp'].min()} → {baseline_logs['timestamp'].max()}"
    )
    print(
        f"  Drift    : {drift_logs['timestamp'].min()} → {drift_logs['timestamp'].max()}"
    )
    print(
        f"  Jours baseline : {len(baseline_dates)} "
        f"({baseline_dates[0]} → {baseline_dates[-1]})"
    )
    print(
        f"  Jours drift    : {len(drift_dates)} "
        f"({drift_dates[0]} → {drift_dates[-1]})"
    )

    checks_ok = True

    if len(baseline_dates) < 2 or len(drift_dates) < 2:
        print("  ✗ Les timestamps ne sont pas assez etales")
        checks_ok = False
    else:
        print("  ✓ Timestamps etales sur plusieurs jours")

    if baseline_logs["timestamp"].max() < drift_logs["timestamp"].min():
        print("  ✓ Le lot drift est plus recent que la baseline")
    else:
        print("  ✗ Le lot drift n'apparait pas plus recent que la baseline")
        checks_ok = False

    return checks_ok


# ============================================================
# Script principal
# ============================================================


def main():
    args = parse_args()
    validate_args(args)

    load_dotenv()
    os.environ["APP_ENV"] = args.environment
    runtime = load_runtime_dependencies()

    print("=" * 60)
    print("Injection des lots techniques de demonstration")
    print("=" * 60)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("\nERREUR : DATABASE_URL non defini dans .env")
        sys.exit(1)

    print(f"\nEnvironnement cible : {args.environment}")
    print(f"Base utilisee : {format_database_label(database_url)}")
    if args.environment == "prod":
        print("Mode demo prod explicitement autorise")
    else:
        print("Mode demo prod : non (environnement preprod)")

    runtime["ensure_tables"]()

    print("\nFichiers CSV :")
    for name, path in FILES.items():
        if not path.exists():
            print(f"  ERREUR : {path.name} introuvable")
            sys.exit(1)

    df_baseline = pd.read_csv(FILES["baseline"])
    df_drift = pd.read_csv(FILES["drift"])

    print(f"  baseline : {len(df_baseline)} lignes")
    print(f"  drift    : {len(df_drift)} lignes")

    ts_baseline = generate_timestamps(
        len(df_baseline),
        start_days_ago=20,
        end_days_ago=10.001,
        seed=42,
    )
    ts_drift = generate_timestamps(
        len(df_drift),
        start_days_ago=10,
        end_days_ago=0,
        seed=43,
    )

    print("\nTimestamps generes :")
    print(
        f"  baseline : {ts_baseline[0].strftime('%Y-%m-%d %H:%M')} → "
        f"{ts_baseline[-1].strftime('%Y-%m-%d %H:%M')}"
    )
    print(
        f"  drift    : {ts_drift[0].strftime('%Y-%m-%d %H:%M')} → "
        f"{ts_drift[-1].strftime('%Y-%m-%d %H:%M')}"
    )

    count_before = count_rows_in_db(database_url, args.environment)
    print(f"\nBase avant injection ({args.environment}) : {count_before} lignes")

    print(f"\n--- Injection BASELINE ({len(df_baseline)} lignes) ---")
    r_baseline = inject_lot(
        df=df_baseline,
        lot_name="baseline",
        timestamps=ts_baseline,
        runtime=runtime,
    )
    print(f"  Insertion reussie : {r_baseline['inserted']}")
    print(f"  Echecs inattendus : {r_baseline['failures']}")
    for detail in r_baseline["details"]:
        print(detail)

    print(f"\n--- Injection DRIFT ({len(df_drift)} lignes) ---")
    r_drift = inject_lot(
        df=df_drift,
        lot_name="drift",
        timestamps=ts_drift,
        runtime=runtime,
    )
    print(f"  Insertion reussie : {r_drift['inserted']}")
    print(f"  Echecs inattendus : {r_drift['failures']}")
    for detail in r_drift["details"]:
        print(detail)

    count_after = count_rows_in_db(database_url, args.environment)
    delta = count_after - count_before
    expected_delta = r_baseline["inserted"] + r_drift["inserted"]

    print(f"\n{'=' * 60}")
    print("Verification base de donnees")
    print(f"{'=' * 60}")
    print(f"  Environnement verifie : {args.environment}")
    print(f"  Avant  : {count_before} lignes")
    print(f"  Apres  : {count_after} lignes")
    print(f"  Delta  : {delta}")
    print(
        f"  Attendu: {expected_delta} "
        f"(baseline={r_baseline['inserted']} + drift={r_drift['inserted']})"
    )

    print(f"\n{'=' * 60}")
    print("Verification des timestamps")
    print(f"{'=' * 60}")
    timestamps_ok = verify_recent_inserts(
        database_url=database_url,
        environment=args.environment,
        baseline_count=r_baseline["inserted"],
        drift_count=r_drift["inserted"],
    )

    print(f"\n{'=' * 60}")
    print("Bilan")
    print(f"{'=' * 60}")

    all_ok = True

    if r_baseline["failures"] > 0:
        print("  ✗ Des lignes baseline n'ont pas ete injectees")
        all_ok = False
    else:
        print(f"  ✓ baseline : {r_baseline['inserted']}/{len(df_baseline)} injectees")

    if r_drift["failures"] > 0:
        print("  ✗ Des lignes drift n'ont pas ete injectees")
        all_ok = False
    else:
        print(f"  ✓ drift : {r_drift['inserted']}/{len(df_drift)} injectees")

    if delta != expected_delta:
        print(f"  ✗ Delta base incorrect : {delta} ≠ {expected_delta}")
        all_ok = False
    else:
        print(f"  ✓ Delta base correct : +{delta} lignes")

    if not timestamps_ok:
        print("  ✗ Verification temporelle non validee")
        all_ok = False
    else:
        print("  ✓ Chronologie baseline puis drift validee")

    print()
    if all_ok:
        print("Toutes les verifications sont passees.")
    else:
        print("ATTENTION : certaines verifications ont echoue.")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
