"""Accès base PostgreSQL — écriture et lecture des prédictions.

Écriture (Gradio) :
    from src.database import log_prediction
    log_prediction(score=0.12, label="Crédit accordé", threshold=0.25, features={...})

Lecture (Streamlit) :
    from src.database import read_prediction_logs
    df = read_prediction_logs(limit=1000)

Les fonctions sont non-bloquantes : toute erreur est loggée en warning.
Sans effet si DATABASE_URL n'est pas défini (développement local sans DB).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_INSERT_SQL = """
INSERT INTO prediction_logs (
    score, label, threshold,
    ext_source_1, ext_source_2, ext_source_3,
    days_birth, days_employed, days_id_publish,
    amt_annuity, amt_goods_price, amt_credit, amt_income_total,
    name_family_status_married,
    ratio_credit_annuity, ratio_goods_credit, ratio_annuity_income
) VALUES (
    %(score)s, %(label)s, %(threshold)s,
    %(EXT_SOURCE_1)s, %(EXT_SOURCE_2)s, %(EXT_SOURCE_3)s,
    %(DAYS_BIRTH)s, %(DAYS_EMPLOYED)s, %(DAYS_ID_PUBLISH)s,
    %(AMT_ANNUITY)s, %(AMT_GOODS_PRICE)s, %(AMT_CREDIT)s, %(AMT_INCOME_TOTAL)s,
    %(NAME_FAMILY_STATUS_is_MARRIED)s,
    %(RATIO_CREDIT_ANNUITY)s, %(RATIO_GOODS_CREDIT)s, %(RATIO_ANNUITY_INCOME)s
)
"""


def log_prediction(
    score: float,
    label: str,
    threshold: float,
    features: dict[str, Any],
) -> None:
    """Insère une ligne de log dans prediction_logs.

    Non-bloquant : toute erreur est loggée en warning.
    Sans effet si DATABASE_URL n'est pas défini.

    Parameters
    ----------
    score : float
        Probabilité de défaut retournée par le modèle.
    label : str
        "Crédit accordé" ou "Crédit refusé".
    threshold : float
        Seuil de décision utilisé.
    features : dict
        Les 14 features (11 saisies + 3 ratios calculés).
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return

    try:
        import psycopg2

        params: dict[str, Any] = {
            "score": score,
            "label": label,
            "threshold": threshold,
            **features,
            # psycopg2 n'adapte pas int→boolean ; conversion explicite requise
            "NAME_FAMILY_STATUS_is_MARRIED": bool(features["NAME_FAMILY_STATUS_is_MARRIED"]),
        }
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_INSERT_SQL, params)
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_prediction failed (non-blocking): %s", repr(exc))


# ---------------------------------------------------------------------------
# Lecture — utilisée par le dashboard Streamlit
# ---------------------------------------------------------------------------

_SELECT_SQL = """
SELECT *
FROM prediction_logs
ORDER BY timestamp DESC
LIMIT %(limit)s
"""


def read_prediction_logs(limit: int = 1000) -> pd.DataFrame:
    """Lit les dernières prédictions depuis PostgreSQL.

    Retourne un DataFrame vide (avec les bonnes colonnes) si la base
    est inaccessible ou si DATABASE_URL n'est pas défini.
    """
    empty = pd.DataFrame()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return empty

    try:
        import psycopg2

        with psycopg2.connect(database_url) as conn:
            df = pd.read_sql_query(
                _SELECT_SQL,
                conn,
                params={"limit": limit},
            )
        return df
    except Exception as exc:  # noqa: BLE001
        logger.warning("read_prediction_logs failed: %s", repr(exc))
        return empty
