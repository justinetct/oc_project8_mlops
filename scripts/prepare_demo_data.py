"""
Genere deux fichiers techniques de demonstration pour l'analyse de drift.

Fichiers produits dans data/demo/ :
  - monitoring_baseline.csv  (100 lignes, format technique)
  - monitoring_drift.csv     (100 lignes, format technique avec derive)

Usage :
    python scripts/prepare_demo_data.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_FILE = PROJECT_ROOT / "data" / "demo" / "source" / "test_enc.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "demo"

BASELINE_SIZE = 100
DRIFT_SIZE = 100
TOTAL_SAMPLE_SIZE = BASELINE_SIZE + DRIFT_SIZE
RANDOM_STATE = 42

BASELINE_FILE = OUTPUT_DIR / "monitoring_baseline.csv"
DRIFT_FILE = OUTPUT_DIR / "monitoring_drift.csv"

# Colonnes techniques (format modele)
COLS_TECHNIQUE = [
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
    "DAYS_BIRTH",
    "DAYS_EMPLOYED",
    "DAYS_ID_PUBLISH",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "AMT_CREDIT",
    "AMT_INCOME_TOTAL",
    "NAME_FAMILY_STATUS_is_MARRIED",
]

# Derive appliquee au fichier drift
DRIFT_ADJUSTMENTS = {
    "EXT_SOURCE_1": -0.12,
    "EXT_SOURCE_2": -0.10,
    "EXT_SOURCE_3": -0.11,
    "AMT_CREDIT": 0.28,
    "AMT_ANNUITY": 0.08,
    "AMT_INCOME_TOTAL": -0.15,
}


# ============================================================
# Fonctions utilitaires
# ============================================================


def apply_drift(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Applique une derive simple et lisible sur un lot technique."""
    drifted = df.copy()

    for col, adjustment in DRIFT_ADJUSTMENTS.items():
        if col in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"):
            noise = rng.normal(0, 0.02, size=len(drifted))
            drifted[col] = (drifted[col] + adjustment + noise).clip(0, 1)
        else:
            factor = 1 + adjustment
            noise = rng.normal(1, 0.03, size=len(drifted))
            drifted[col] = (drifted[col] * factor * noise).round(2)
            drifted[col] = drifted[col].clip(lower=1.0)

    mask = drifted["AMT_CREDIT"] > drifted["AMT_GOODS_PRICE"]
    drifted.loc[mask, "AMT_CREDIT"] = drifted.loc[mask, "AMT_GOODS_PRICE"]

    return drifted


# ============================================================
# Generation des fichiers
# ============================================================


def main():
    print("=" * 60)
    print("Preparation des donnees de demo — Projet 8 MLOps")
    print("=" * 60)
    print(f"Tailles cibles : baseline={BASELINE_SIZE}, drift={DRIFT_SIZE}")

    if not SOURCE_FILE.exists():
        print(f"\nERREUR : fichier source introuvable : {SOURCE_FILE}")
        sys.exit(1)
    print(f"\nFichier source : {SOURCE_FILE}")

    df_raw = pd.read_csv(SOURCE_FILE)
    print(f"Lignes chargees : {len(df_raw)}")

    missing_cols = [col for col in COLS_TECHNIQUE if col not in df_raw.columns]
    if missing_cols:
        print(f"\nERREUR : colonnes manquantes dans le CSV : {missing_cols}")
        sys.exit(1)
    print("Colonnes requises : toutes presentes")

    df = df_raw[COLS_TECHNIQUE].dropna().copy()
    df = df[df["AMT_CREDIT"] <= df["AMT_GOODS_PRICE"]].copy()
    print(f"Lignes valides (sans NaN, credit <= prix) : {len(df)}")

    if len(df) < TOTAL_SAMPLE_SIZE:
        print(
            f"\nERREUR : pas assez de lignes valides "
            f"({len(df)} < {TOTAL_SAMPLE_SIZE})"
        )
        sys.exit(1)

    for csv_file in OUTPUT_DIR.glob("*.csv"):
        if csv_file not in {BASELINE_FILE, DRIFT_FILE}:
            csv_file.unlink()
            print(f"Suppression ancien fichier : {csv_file.name}")

    sample = df.sample(n=TOTAL_SAMPLE_SIZE, random_state=RANDOM_STATE).reset_index(drop=True)
    baseline = sample.iloc[:BASELINE_SIZE].copy()
    drift_source = sample.iloc[BASELINE_SIZE:TOTAL_SAMPLE_SIZE].copy()

    rng = np.random.default_rng(RANDOM_STATE)
    drift = apply_drift(drift_source, rng)

    baseline.to_csv(BASELINE_FILE, index=False)
    drift.to_csv(DRIFT_FILE, index=False)

    print(f"\n✓ {BASELINE_FILE.name} : {len(baseline)} lignes")
    print(f"✓ {DRIFT_FILE.name} : {len(drift)} lignes")

    print("\n" + "=" * 60)
    print("Verifications")
    print("=" * 60)
    checks_ok = True

    def check(condition, message):
        nonlocal checks_ok
        status = "✓" if condition else "✗ ERREUR"
        if not condition:
            checks_ok = False
        print(f"  {status} — {message}")

    check(BASELINE_FILE.exists(), f"{BASELINE_FILE.name} existe")
    check(DRIFT_FILE.exists(), f"{DRIFT_FILE.name} existe")

    df_baseline = pd.read_csv(BASELINE_FILE)
    df_drift = pd.read_csv(DRIFT_FILE)

    check(
        len(df_baseline) == BASELINE_SIZE,
        f"baseline : {len(df_baseline)} lignes (attendu {BASELINE_SIZE})",
    )
    check(
        len(df_drift) == DRIFT_SIZE,
        f"drift : {len(df_drift)} lignes (attendu {DRIFT_SIZE})",
    )

    check(
        list(df_baseline.columns) == COLS_TECHNIQUE,
        "baseline : colonnes techniques correctes",
    )
    check(
        list(df_drift.columns) == COLS_TECHNIQUE,
        "drift : colonnes techniques correctes",
    )

    check(df_baseline.isna().sum().sum() == 0, "baseline : aucune valeur manquante")
    check(df_drift.isna().sum().sum() == 0, "drift : aucune valeur manquante")

    check(
        (df_baseline["AMT_CREDIT"] <= df_baseline["AMT_GOODS_PRICE"]).all(),
        "baseline : AMT_CREDIT <= AMT_GOODS_PRICE",
    )
    check(
        (df_drift["AMT_CREDIT"] <= df_drift["AMT_GOODS_PRICE"]).all(),
        "drift : AMT_CREDIT <= AMT_GOODS_PRICE",
    )

    print("\n" + "=" * 60)
    if checks_ok:
        print("Toutes les verifications sont passees.")
    else:
        print("ATTENTION : certaines verifications ont echoue.")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
