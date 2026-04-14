"""
Génère les fichiers de démonstration pour le monitoring du projet 8.

Fichiers produits dans data/demo/ :
  - monitoring_baseline.csv        (50 lignes, format technique)
  - monitoring_requests_valid.csv   (30 lignes, format UI)
  - monitoring_requests_drift.csv   (20 lignes, format UI avec dérive)
  - monitoring_requests_errors.csv  (10 lignes, format UI avec erreurs volontaires)

Usage :
    python scripts/prepare_demo_data.py
"""

import sys
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import numpy as np

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_FILE = PROJECT_ROOT / "data" / "demo" / "source" / "test_enc.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "demo"

REFERENCE_DATE = date(2018, 5, 17)
RANDOM_STATE = 42

# Colonnes techniques (format modèle)
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

# Colonnes UI (format application Gradio)
COLS_UI = [
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
    "date_naissance",
    "date_embauche",
    "date_id",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "AMT_CREDIT",
    "AMT_INCOME_TOTAL",
    "is_married",
]

# Dérive appliquée au fichier drift
DRIFT_ADJUSTMENTS = {
    "EXT_SOURCE_1": -0.08,
    "EXT_SOURCE_2": -0.06,
    "EXT_SOURCE_3": -0.07,
    "AMT_CREDIT": 0.15,       # +15%
    "AMT_ANNUITY": 0.12,      # +12%
    "AMT_INCOME_TOTAL": -0.10, # -10%
}


# ============================================================
# Fonctions utilitaires
# ============================================================


def days_to_date(days_value: int) -> str:
    """Convertit DAYS_X en date YYYY-MM-DD.

    Dans le dataset encodé du projet 6, les valeurs DAYS sont positives
    (le signe négatif d'origine Home Credit a été retiré au preprocessing).
    On soustrait donc les jours à la date de référence.
    """
    return (REFERENCE_DATE - timedelta(days=int(days_value))).isoformat()


def convert_to_ui_format(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit un DataFrame technique en format UI Gradio."""
    ui = pd.DataFrame()
    ui["EXT_SOURCE_1"] = df["EXT_SOURCE_1"].round(6)
    ui["EXT_SOURCE_2"] = df["EXT_SOURCE_2"].round(6)
    ui["EXT_SOURCE_3"] = df["EXT_SOURCE_3"].round(6)
    ui["date_naissance"] = df["DAYS_BIRTH"].apply(days_to_date)
    ui["date_embauche"] = df["DAYS_EMPLOYED"].apply(days_to_date)
    ui["date_id"] = df["DAYS_ID_PUBLISH"].apply(days_to_date)
    ui["AMT_ANNUITY"] = df["AMT_ANNUITY"].round(2)
    ui["AMT_GOODS_PRICE"] = df["AMT_GOODS_PRICE"].round(2)
    ui["AMT_CREDIT"] = df["AMT_CREDIT"].round(2)
    ui["AMT_INCOME_TOTAL"] = df["AMT_INCOME_TOTAL"].round(2)
    ui["is_married"] = df["NAME_FAMILY_STATUS_is_MARRIED"].map(
        {1: "Oui", 0: "Non", 1.0: "Oui", 0.0: "Non"}
    )
    return ui


def apply_drift(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Applique une dérive réaliste aux données techniques."""
    drifted = df.copy()

    for col, adjustment in DRIFT_ADJUSTMENTS.items():
        if col in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"):
            # Décalage additif + petit bruit
            noise = rng.normal(0, 0.02, size=len(drifted))
            drifted[col] = (drifted[col] + adjustment + noise).clip(0, 1)
        else:
            # Décalage multiplicatif + petit bruit
            factor = 1 + adjustment
            noise = rng.normal(1, 0.03, size=len(drifted))
            drifted[col] = (drifted[col] * factor * noise).round(2)
            # Garantir des valeurs positives
            drifted[col] = drifted[col].clip(lower=1.0)

    # Garantir que AMT_CREDIT <= AMT_GOODS_PRICE (contrainte de validation)
    mask = drifted["AMT_CREDIT"] > drifted["AMT_GOODS_PRICE"]
    drifted.loc[mask, "AMT_CREDIT"] = drifted.loc[mask, "AMT_GOODS_PRICE"]

    return drifted


def generate_errors() -> pd.DataFrame:
    """Crée 10 lignes avec des erreurs volontaires variées."""
    errors = [
        {  # 1 - montant annuité négatif
            "EXT_SOURCE_1": 0.5, "EXT_SOURCE_2": 0.6, "EXT_SOURCE_3": 0.4,
            "date_naissance": "1985-03-12", "date_embauche": "2010-06-01",
            "date_id": "2015-01-15",
            "AMT_ANNUITY": -5000.0, "AMT_GOODS_PRICE": 200000.0,
            "AMT_CREDIT": 180000.0, "AMT_INCOME_TOTAL": 45000.0,
            "is_married": "Oui",
        },
        {  # 2 - montant crédit nul
            "EXT_SOURCE_1": 0.3, "EXT_SOURCE_2": 0.5, "EXT_SOURCE_3": 0.7,
            "date_naissance": "1990-07-20", "date_embauche": "2015-09-01",
            "date_id": "2016-03-10",
            "AMT_ANNUITY": 12000.0, "AMT_GOODS_PRICE": 150000.0,
            "AMT_CREDIT": 0.0, "AMT_INCOME_TOTAL": 60000.0,
            "is_married": "Non",
        },
        {  # 3 - revenu négatif
            "EXT_SOURCE_1": 0.6, "EXT_SOURCE_2": 0.4, "EXT_SOURCE_3": 0.5,
            "date_naissance": "1978-11-05", "date_embauche": "2005-04-15",
            "date_id": "2012-08-20",
            "AMT_ANNUITY": 18000.0, "AMT_GOODS_PRICE": 300000.0,
            "AMT_CREDIT": 270000.0, "AMT_INCOME_TOTAL": -10000.0,
            "is_married": "Oui",
        },
        {  # 4 - date d'embauche dans le futur
            "EXT_SOURCE_1": 0.4, "EXT_SOURCE_2": 0.5, "EXT_SOURCE_3": 0.6,
            "date_naissance": "1995-01-30", "date_embauche": "2030-01-01",
            "date_id": "2017-06-10",
            "AMT_ANNUITY": 10000.0, "AMT_GOODS_PRICE": 120000.0,
            "AMT_CREDIT": 100000.0, "AMT_INCOME_TOTAL": 35000.0,
            "is_married": "Non",
        },
        {  # 5 - date de naissance au mauvais format
            "EXT_SOURCE_1": 0.7, "EXT_SOURCE_2": 0.3, "EXT_SOURCE_3": 0.5,
            "date_naissance": "12/03/1988", "date_embauche": "2012-05-01",
            "date_id": "2014-09-22",
            "AMT_ANNUITY": 15000.0, "AMT_GOODS_PRICE": 250000.0,
            "AMT_CREDIT": 220000.0, "AMT_INCOME_TOTAL": 55000.0,
            "is_married": "Oui",
        },
        {  # 6 - crédit supérieur au prix du bien
            "EXT_SOURCE_1": 0.5, "EXT_SOURCE_2": 0.5, "EXT_SOURCE_3": 0.5,
            "date_naissance": "1982-06-15", "date_embauche": "2008-03-01",
            "date_id": "2013-11-05",
            "AMT_ANNUITY": 20000.0, "AMT_GOODS_PRICE": 100000.0,
            "AMT_CREDIT": 250000.0, "AMT_INCOME_TOTAL": 70000.0,
            "is_married": "Non",
        },
        {  # 7 - prix du bien négatif
            "EXT_SOURCE_1": 0.2, "EXT_SOURCE_2": 0.8, "EXT_SOURCE_3": 0.3,
            "date_naissance": "1975-09-28", "date_embauche": "2000-01-15",
            "date_id": "2010-04-18",
            "AMT_ANNUITY": 25000.0, "AMT_GOODS_PRICE": -50000.0,
            "AMT_CREDIT": 180000.0, "AMT_INCOME_TOTAL": 80000.0,
            "is_married": "Oui",
        },
        {  # 8 - annuité nulle
            "EXT_SOURCE_1": 0.5, "EXT_SOURCE_2": 0.5, "EXT_SOURCE_3": 0.5,
            "date_naissance": "1992-04-10", "date_embauche": "2014-01-01",
            "date_id": "2017-12-01",
            "AMT_ANNUITY": 0.0, "AMT_GOODS_PRICE": 90000.0,
            "AMT_CREDIT": 85000.0, "AMT_INCOME_TOTAL": 30000.0,
            "is_married": "Non",
        },
        {  # 9 - date d'identité au mauvais format
            "EXT_SOURCE_1": 0.6, "EXT_SOURCE_2": 0.6, "EXT_SOURCE_3": 0.6,
            "date_naissance": "1988-08-22", "date_embauche": "2014-10-01",
            "date_id": "pas-une-date",
            "AMT_ANNUITY": 14000.0, "AMT_GOODS_PRICE": 200000.0,
            "AMT_CREDIT": 190000.0, "AMT_INCOME_TOTAL": 50000.0,
            "is_married": "Oui",
        },
        {  # 10 - revenu nul
            "EXT_SOURCE_1": 0.4, "EXT_SOURCE_2": 0.4, "EXT_SOURCE_3": 0.4,
            "date_naissance": "1980-12-01", "date_embauche": "2006-07-15",
            "date_id": "2011-03-25",
            "AMT_ANNUITY": 16000.0, "AMT_GOODS_PRICE": 220000.0,
            "AMT_CREDIT": 200000.0, "AMT_INCOME_TOTAL": 0.0,
            "is_married": "Non",
        },
    ]
    return pd.DataFrame(errors)[COLS_UI]


# ============================================================
# Génération des fichiers
# ============================================================


def main():
    print("=" * 60)
    print("Préparation des données de démo — Projet 8 MLOps")
    print("=" * 60)

    # --- Vérification du fichier source ---
    if not SOURCE_FILE.exists():
        print(f"\nERREUR : fichier source introuvable : {SOURCE_FILE}")
        sys.exit(1)
    print(f"\nFichier source : {SOURCE_FILE}")

    # --- Chargement ---
    df_raw = pd.read_csv(SOURCE_FILE)
    print(f"Lignes chargées : {len(df_raw)}")

    # Vérification des colonnes
    missing_cols = [c for c in COLS_TECHNIQUE if c not in df_raw.columns]
    if missing_cols:
        print(f"\nERREUR : colonnes manquantes dans le CSV : {missing_cols}")
        sys.exit(1)
    print(f"Colonnes requises : toutes présentes")

    # --- Sélection et nettoyage ---
    df = df_raw[COLS_TECHNIQUE].dropna().copy()
    # Garder seulement les lignes où crédit <= prix du bien (contrainte de validation)
    df = df[df["AMT_CREDIT"] <= df["AMT_GOODS_PRICE"]].copy()
    print(f"Lignes valides (sans NaN, crédit ≤ prix) : {len(df)}")

    if len(df) < 100:
        print(f"\nERREUR : pas assez de lignes valides ({len(df)} < 100)")
        sys.exit(1)

    # --- Échantillonnage ---
    rng = np.random.default_rng(RANDOM_STATE)
    sample = df.sample(n=100, random_state=RANDOM_STATE).reset_index(drop=True)

    baseline = sample.iloc[:50]
    valid_tech = sample.iloc[50:80]
    drift_tech = sample.iloc[80:100]

    # --- 1. Baseline (format technique) ---
    baseline_path = OUTPUT_DIR / "monitoring_baseline.csv"
    baseline.to_csv(baseline_path, index=False)
    print(f"\n✓ {baseline_path.name} : {len(baseline)} lignes")

    # --- 2. Requêtes valides (format UI) ---
    valid_ui = convert_to_ui_format(valid_tech)
    valid_path = OUTPUT_DIR / "monitoring_requests_valid.csv"
    valid_ui.to_csv(valid_path, index=False)
    print(f"✓ {valid_path.name} : {len(valid_ui)} lignes")

    # --- 3. Requêtes avec dérive (format UI) ---
    drifted_tech = apply_drift(drift_tech, rng)
    drift_ui = convert_to_ui_format(drifted_tech)
    drift_path = OUTPUT_DIR / "monitoring_requests_drift.csv"
    drift_ui.to_csv(drift_path, index=False)
    print(f"✓ {drift_path.name} : {len(drift_ui)} lignes")

    # --- 4. Requêtes avec erreurs (format UI) ---
    errors_ui = generate_errors()
    errors_path = OUTPUT_DIR / "monitoring_requests_errors.csv"
    errors_ui.to_csv(errors_path, index=False)
    print(f"✓ {errors_path.name} : {len(errors_ui)} lignes")

    # --- Vérifications ---
    print("\n" + "=" * 60)
    print("Vérifications")
    print("=" * 60)
    checks_ok = True

    def check(condition, message):
        nonlocal checks_ok
        status = "✓" if condition else "✗ ERREUR"
        if not condition:
            checks_ok = False
        print(f"  {status} — {message}")

    # Fichiers existent
    for path in [baseline_path, valid_path, drift_path, errors_path]:
        check(path.exists(), f"{path.name} existe")

    # Nombre de lignes
    df_b = pd.read_csv(baseline_path)
    df_v = pd.read_csv(valid_path)
    df_d = pd.read_csv(drift_path)
    df_e = pd.read_csv(errors_path)

    check(len(df_b) == 50, f"baseline : {len(df_b)} lignes (attendu 50)")
    check(len(df_v) == 30, f"valid : {len(df_v)} lignes (attendu 30)")
    check(len(df_d) == 20, f"drift : {len(df_d)} lignes (attendu 20)")
    check(len(df_e) == 10, f"errors : {len(df_e)} lignes (attendu 10)")

    # Colonnes correctes
    check(
        list(df_b.columns) == COLS_TECHNIQUE,
        "baseline : colonnes techniques correctes"
    )
    check(list(df_v.columns) == COLS_UI, "valid : colonnes UI correctes")
    check(list(df_d.columns) == COLS_UI, "drift : colonnes UI correctes")
    check(list(df_e.columns) == COLS_UI, "errors : colonnes UI correctes")

    # Pas de NaN dans baseline / valid / drift
    check(df_b.isna().sum().sum() == 0, "baseline : aucune valeur manquante")
    check(df_v.isna().sum().sum() == 0, "valid : aucune valeur manquante")
    check(df_d.isna().sum().sum() == 0, "drift : aucune valeur manquante")

    # Dates au format YYYY-MM-DD dans valid et drift
    date_cols = ["date_naissance", "date_embauche", "date_id"]
    for col in date_cols:
        valid_dates = df_v[col].str.match(r"^\d{4}-\d{2}-\d{2}$").all()
        check(valid_dates, f"valid.{col} : format YYYY-MM-DD")
        drift_dates = df_d[col].str.match(r"^\d{4}-\d{2}-\d{2}$").all()
        check(drift_dates, f"drift.{col} : format YYYY-MM-DD")

    # is_married contient seulement Oui/Non
    check(
        set(df_v["is_married"].unique()) <= {"Oui", "Non"},
        "valid.is_married : seulement Oui/Non"
    )
    check(
        set(df_d["is_married"].unique()) <= {"Oui", "Non"},
        "drift.is_married : seulement Oui/Non"
    )

    # Pas de montants négatifs ou nuls dans valid et drift
    amount_cols = ["AMT_ANNUITY", "AMT_GOODS_PRICE", "AMT_CREDIT", "AMT_INCOME_TOTAL"]
    for col in amount_cols:
        check((df_v[col] > 0).all(), f"valid.{col} > 0")
        check((df_d[col] > 0).all(), f"drift.{col} > 0")

    # Résultat final
    print("\n" + "=" * 60)
    if checks_ok:
        print("Toutes les vérifications sont passées.")
    else:
        print("ATTENTION : certaines vérifications ont échoué.")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
