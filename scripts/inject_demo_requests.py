"""Injecte les requêtes de démonstration dans la base de monitoring.

Lit les 3 CSV de démo et :
  - injecte les lignes valides (valid + drift) via score_client()
  - teste les lignes d'erreur (errors) pour vérifier qu'elles sont rejetées
  - vérifie le delta dans prediction_logs
  - vérifie que les timestamps sont bien étalés dans le temps

Les timestamps sont répartis ainsi :
  - valid : étalé sur les 10 derniers jours (J-13 à J-4)
  - drift : concentré sur les 3 derniers jours (J-3 à J-1)
Cela simule une période normale suivie d'une dérive récente.

Usage :
    poetry run python scripts/inject_demo_requests.py

Chaque exécution ajoute de nouvelles lignes (pas de déduplication).
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Ajouter la racine du projet au path pour les imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app_gradio.scoring_service import score_client  # noqa: E402
from src.database import ensure_tables  # noqa: E402

# ============================================================
# Configuration
# ============================================================

load_dotenv()

DATA_DIR = PROJECT_ROOT / "data" / "demo"

FILES = {
    "valid": DATA_DIR / "monitoring_requests_valid.csv",
    "drift": DATA_DIR / "monitoring_requests_drift.csv",
    "errors": DATA_DIR / "monitoring_requests_errors.csv",
}


# ============================================================
# Génération des timestamps
# ============================================================


def generate_timestamps(n: int, start_days_ago: int, end_days_ago: int) -> list:
    """Génère n timestamps répartis régulièrement entre deux bornes.

    Parameters
    ----------
    n : nombre de timestamps à générer
    start_days_ago : début de la période (ex: 13 = il y a 13 jours)
    end_days_ago : fin de la période (ex: 4 = il y a 4 jours)

    Returns
    -------
    Liste de datetime UTC, du plus ancien au plus récent.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=start_days_ago)
    end = now - timedelta(days=end_days_ago)

    if n == 1:
        return [start]

    step = (end - start) / (n - 1)
    return [start + step * i for i in range(n)]


# ============================================================
# Utilitaires
# ============================================================


def count_rows_in_db(database_url: str) -> int:
    """Compte le nombre de lignes dans prediction_logs."""
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM prediction_logs")
            return cur.fetchone()[0]


def call_score_client(row: pd.Series, logged_at=None):
    """Appelle score_client() avec les colonnes d'une ligne CSV format UI."""
    return score_client(
        ext_source_1=float(row["EXT_SOURCE_1"]),
        ext_source_2=float(row["EXT_SOURCE_2"]),
        ext_source_3=float(row["EXT_SOURCE_3"]),
        date_naissance=str(row["date_naissance"]),
        date_embauche=str(row["date_embauche"]),
        date_id=str(row["date_id"]),
        amt_annuity=float(row["AMT_ANNUITY"]),
        amt_goods_price=float(row["AMT_GOODS_PRICE"]),
        amt_credit=float(row["AMT_CREDIT"]),
        amt_income_total=float(row["AMT_INCOME_TOTAL"]),
        is_married=str(row["is_married"]),
        logged_at=logged_at,
    )


def inject_lot(df: pd.DataFrame, lot_name: str, expect_success: bool,
               timestamps: list | None = None) -> dict:
    """Injecte un lot de requêtes et retourne les compteurs.

    Parameters
    ----------
    df : DataFrame avec les colonnes UI
    lot_name : nom du lot pour l'affichage
    expect_success : True si on attend des succès, False si on attend des rejets
    timestamps : liste de datetime, un par ligne (optionnel)
    """
    ok = 0
    ko = 0
    details = []

    for idx, (i, row) in enumerate(df.iterrows()):
        ts = timestamps[idx] if timestamps else None

        try:
            result = call_score_client(row, logged_at=ts)
        except Exception as exc:
            ko += 1
            details.append(f"  Ligne {i}: exception inattendue — {exc}")
            continue

        if expect_success:
            if result.success:
                ok += 1
            else:
                ko += 1
                details.append(
                    f"  Ligne {i}: rejeté (inattendu) — {result.errors}"
                )
        else:
            if not result.success:
                ok += 1  # rejet attendu
            else:
                ko += 1  # accepté alors qu'on attendait un rejet
                details.append(
                    f"  Ligne {i}: accepté (inattendu) — score={result.score}"
                )

    return {"ok": ok, "ko": ko, "details": details}


def verify_timestamps(database_url: str, expected_count: int):
    """Vérifie que les dernières lignes insérées ont des timestamps étalés."""
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timestamp FROM prediction_logs "
                "ORDER BY id DESC LIMIT %s",
                (expected_count,),
            )
            rows = cur.fetchall()

    if not rows:
        print("  ✗ Aucune ligne trouvée")
        return False

    timestamps = sorted([r[0] for r in rows])
    dates = sorted(set(t.date() for t in timestamps))

    print(f"  Timestamps : du {timestamps[0]} au {timestamps[-1]}")
    print(f"  Jours distincts : {len(dates)} ({dates[0]} → {dates[-1]})")

    if len(dates) < 2:
        print("  ✗ Tous les timestamps sont le même jour")
        return False

    # Vérifier que drift est plus récent que valid
    # Les dernières lignes insérées sont le drift (les plus récentes par id)
    mid = expected_count // 2
    recent_ts = sorted([r[0] for r in rows[:mid]])   # drift (derniers insérés)
    older_ts = sorted([r[0] for r in rows[mid:]])     # valid (premiers insérés)

    if recent_ts and older_ts and min(recent_ts) > min(older_ts):
        print("  ✓ Drift plus récent que valid")
    else:
        print("  ⚠ Impossible de confirmer l'ordre drift > valid (vérifier manuellement)")

    return True


# ============================================================
# Script principal
# ============================================================


def main():
    print("=" * 60)
    print("Injection des requêtes de démonstration")
    print("=" * 60)

    # --- Vérification DATABASE_URL ---
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("\nERREUR : DATABASE_URL non défini dans .env")
        sys.exit(1)
    print(f"\nBase de données : connectée")

    # S'assure que la table existe et que la colonne environment est présente
    ensure_tables()

    # --- Vérification des fichiers ---
    print("\nFichiers CSV :")
    for name, path in FILES.items():
        if not path.exists():
            print(f"  ERREUR : {path.name} introuvable")
            sys.exit(1)

    # --- Lecture des CSV ---
    df_valid = pd.read_csv(FILES["valid"])
    df_drift = pd.read_csv(FILES["drift"])
    df_errors = pd.read_csv(FILES["errors"])

    print(f"  valid  : {len(df_valid)} lignes")
    print(f"  drift  : {len(df_drift)} lignes")
    print(f"  errors : {len(df_errors)} lignes")

    # --- Génération des timestamps ---
    # valid : réparti sur J-13 à J-4 (10 jours de période "normale")
    # drift : concentré sur J-3 à J-1 (3 jours récents)
    ts_valid = generate_timestamps(len(df_valid), start_days_ago=13, end_days_ago=4)
    ts_drift = generate_timestamps(len(df_drift), start_days_ago=3, end_days_ago=1)

    print(f"\nTimestamps générés :")
    print(f"  valid : {ts_valid[0].strftime('%Y-%m-%d %H:%M')} → "
          f"{ts_valid[-1].strftime('%Y-%m-%d %H:%M')}")
    print(f"  drift : {ts_drift[0].strftime('%Y-%m-%d %H:%M')} → "
          f"{ts_drift[-1].strftime('%Y-%m-%d %H:%M')}")

    # --- Comptage avant injection ---
    count_before = count_rows_in_db(database_url)
    print(f"\nBase avant injection : {count_before} lignes")

    # --- Injection valid ---
    print(f"\n--- Injection VALID ({len(df_valid)} lignes) ---")
    r_valid = inject_lot(df_valid, "valid", expect_success=True, timestamps=ts_valid)
    print(f"  Succès : {r_valid['ok']}")
    print(f"  Échecs inattendus : {r_valid['ko']}")
    for d in r_valid["details"]:
        print(d)

    # --- Injection drift ---
    print(f"\n--- Injection DRIFT ({len(df_drift)} lignes) ---")
    r_drift = inject_lot(df_drift, "drift", expect_success=True, timestamps=ts_drift)
    print(f"  Succès : {r_drift['ok']}")
    print(f"  Échecs inattendus : {r_drift['ko']}")
    for d in r_drift["details"]:
        print(d)

    # --- Test errors (pas de timestamp nécessaire, rien ne s'écrit en base) ---
    print(f"\n--- Test ERRORS ({len(df_errors)} lignes) ---")
    r_errors = inject_lot(df_errors, "errors", expect_success=False)
    print(f"  Rejets attendus : {r_errors['ok']}")
    print(f"  Acceptations inattendues : {r_errors['ko']}")
    for d in r_errors["details"]:
        print(d)

    # --- Comptage après injection ---
    count_after = count_rows_in_db(database_url)
    delta = count_after - count_before
    expected_delta = r_valid["ok"] + r_drift["ok"]

    print(f"\n{'=' * 60}")
    print("Vérification base de données")
    print(f"{'=' * 60}")
    print(f"  Avant  : {count_before} lignes")
    print(f"  Après  : {count_after} lignes")
    print(f"  Delta  : {delta}")
    print(f"  Attendu: {expected_delta} (valid={r_valid['ok']} + drift={r_drift['ok']})")

    # --- Vérification des timestamps ---
    print(f"\n{'=' * 60}")
    print("Vérification des timestamps")
    print(f"{'=' * 60}")
    ts_ok = verify_timestamps(database_url, expected_delta)

    # --- Bilan final ---
    print(f"\n{'=' * 60}")
    print("Bilan")
    print(f"{'=' * 60}")

    all_ok = True

    if r_valid["ko"] > 0:
        print("  ✗ Des lignes valid ont été rejetées")
        all_ok = False
    else:
        print(f"  ✓ valid : {r_valid['ok']}/{len(df_valid)} acceptées")

    if r_drift["ko"] > 0:
        print("  ✗ Des lignes drift ont été rejetées")
        all_ok = False
    else:
        print(f"  ✓ drift : {r_drift['ok']}/{len(df_drift)} acceptées")

    if r_errors["ko"] > 0:
        print("  ✗ Des lignes errors ont été acceptées (ne devrait pas arriver)")
        all_ok = False
    else:
        print(f"  ✓ errors : {r_errors['ok']}/{len(df_errors)} rejetées")

    if delta != expected_delta:
        print(f"  ✗ Delta base incorrect : {delta} ≠ {expected_delta}")
        all_ok = False
    else:
        print(f"  ✓ Delta base correct : +{delta} lignes")

    if not ts_ok:
        print("  ✗ Timestamps non étalés")
        all_ok = False
    else:
        print("  ✓ Timestamps étalés dans le temps")

    print()
    if all_ok:
        print("Toutes les vérifications sont passées.")
    else:
        print("ATTENTION : certaines vérifications ont échoué.")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
