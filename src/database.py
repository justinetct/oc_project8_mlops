"""Accès base PostgreSQL — écriture et lecture du monitoring.

Écriture prédictions :
    from src.database import log_prediction
    log_prediction(score=0.12, label="Crédit accordé", threshold=0.25, features={...})

Écriture erreurs :
    from src.database import log_prediction_error
    log_prediction_error(error_type="validation_error", error_message="...")

Lecture (Streamlit) :
    from src.database import read_prediction_logs
    df = read_prediction_logs(limit=1000)

Création automatique des tables au démarrage :
    from src.database import ensure_tables
    ensure_tables()

Les fonctions sont non-bloquantes : toute erreur est loggée en warning.
Sans effet si DATABASE_URL n'est pas défini (développement local sans DB).

Cloisonnement par environnement : toutes les écritures tagguent les lignes
avec APP_ENV (default "preprod"), et les lectures ne retournent que les
lignes du même environnement.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

from src.config import APP_ENV

logger = logging.getLogger(__name__)

_INSERT_SQL = """
INSERT INTO prediction_logs (
    environment,
    duration_ms,
    score, label, threshold,
    ext_source_1, ext_source_2, ext_source_3,
    days_birth, days_employed, days_id_publish,
    amt_annuity, amt_goods_price, amt_credit, amt_income_total,
    name_family_status_married,
    ratio_credit_annuity, ratio_goods_credit, ratio_annuity_income
) VALUES (
    %(environment)s,
    %(duration_ms)s,
    %(score)s, %(label)s, %(threshold)s,
    %(EXT_SOURCE_1)s, %(EXT_SOURCE_2)s, %(EXT_SOURCE_3)s,
    %(DAYS_BIRTH)s, %(DAYS_EMPLOYED)s, %(DAYS_ID_PUBLISH)s,
    %(AMT_ANNUITY)s, %(AMT_GOODS_PRICE)s, %(AMT_CREDIT)s, %(AMT_INCOME_TOTAL)s,
    %(NAME_FAMILY_STATUS_is_MARRIED)s,
    %(RATIO_CREDIT_ANNUITY)s, %(RATIO_GOODS_CREDIT)s, %(RATIO_ANNUITY_INCOME)s
)
"""

_INSERT_SQL_WITH_TIMESTAMP = """
INSERT INTO prediction_logs (
    timestamp,
    environment,
    duration_ms,
    score, label, threshold,
    ext_source_1, ext_source_2, ext_source_3,
    days_birth, days_employed, days_id_publish,
    amt_annuity, amt_goods_price, amt_credit, amt_income_total,
    name_family_status_married,
    ratio_credit_annuity, ratio_goods_credit, ratio_annuity_income
) VALUES (
    %(logged_at)s,
    %(environment)s,
    %(duration_ms)s,
    %(score)s, %(label)s, %(threshold)s,
    %(EXT_SOURCE_1)s, %(EXT_SOURCE_2)s, %(EXT_SOURCE_3)s,
    %(DAYS_BIRTH)s, %(DAYS_EMPLOYED)s, %(DAYS_ID_PUBLISH)s,
    %(AMT_ANNUITY)s, %(AMT_GOODS_PRICE)s, %(AMT_CREDIT)s, %(AMT_INCOME_TOTAL)s,
    %(NAME_FAMILY_STATUS_is_MARRIED)s,
    %(RATIO_CREDIT_ANNUITY)s, %(RATIO_GOODS_CREDIT)s, %(RATIO_ANNUITY_INCOME)s
)
"""


# ---------------------------------------------------------------------------
# Création automatique — appelée au démarrage des services
# ---------------------------------------------------------------------------

_CREATE_PREDICTION_LOGS = """
CREATE TABLE IF NOT EXISTS prediction_logs (
    id                          SERIAL           PRIMARY KEY,
    timestamp                   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    environment                 TEXT             NOT NULL DEFAULT 'preprod',
    duration_ms                 DOUBLE PRECISION,
    score                       DOUBLE PRECISION NOT NULL,
    label                       TEXT             NOT NULL,
    threshold                   DOUBLE PRECISION NOT NULL,
    ext_source_1                DOUBLE PRECISION NOT NULL,
    ext_source_2                DOUBLE PRECISION NOT NULL,
    ext_source_3                DOUBLE PRECISION NOT NULL,
    days_birth                  INTEGER          NOT NULL,
    days_employed               INTEGER          NOT NULL,
    days_id_publish             INTEGER          NOT NULL,
    amt_annuity                 DOUBLE PRECISION NOT NULL,
    amt_goods_price             DOUBLE PRECISION NOT NULL,
    amt_credit                  DOUBLE PRECISION NOT NULL,
    amt_income_total            DOUBLE PRECISION NOT NULL,
    name_family_status_married  BOOLEAN          NOT NULL,
    ratio_credit_annuity        DOUBLE PRECISION NOT NULL,
    ratio_goods_credit          DOUBLE PRECISION NOT NULL,
    ratio_annuity_income        DOUBLE PRECISION NOT NULL
);
"""

_ADD_ENVIRONMENT_COLUMN = """
ALTER TABLE prediction_logs
ADD COLUMN IF NOT EXISTS environment TEXT NOT NULL DEFAULT 'preprod';
"""

_ADD_DURATION_MS_COLUMN = """
ALTER TABLE prediction_logs
ADD COLUMN IF NOT EXISTS duration_ms DOUBLE PRECISION;
"""

_CREATE_PREDICTION_ERRORS = """
CREATE TABLE IF NOT EXISTS prediction_errors (
    id              SERIAL           PRIMARY KEY,
    timestamp       TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    environment     TEXT             NOT NULL DEFAULT 'preprod',
    error_type      TEXT             NOT NULL,
    error_message   TEXT             NOT NULL
);
"""


def ensure_tables() -> None:
    """Crée les tables de monitoring si elles n'existent pas.

    Idempotent. Non-bloquant : toute erreur est loggée en warning pour ne pas
    empêcher le service de démarrer. Sans effet si DATABASE_URL n'est pas défini.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return

    try:
        import psycopg2

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_CREATE_PREDICTION_LOGS)
                cur.execute(_ADD_ENVIRONMENT_COLUMN)
                cur.execute(_ADD_DURATION_MS_COLUMN)
                cur.execute(_CREATE_PREDICTION_ERRORS)
        logger.info("ensure_tables: tables de monitoring prêtes (env=%s)", APP_ENV)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_tables failed (non-blocking): %s", repr(exc))


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------

def log_prediction(
    score: float,
    label: str,
    threshold: float,
    features: dict[str, Any],
    duration_ms: float | None = None,
    logged_at: Any | None = None,
) -> None:
    """Insère une ligne de log dans prediction_logs.

    Non-bloquant : toute erreur est loggée en warning.
    Sans effet si DATABASE_URL n'est pas défini.
    La ligne est taguée avec APP_ENV (default "preprod").

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
    duration_ms : float, optional
        Durée mesurée du flux de scoring, en millisecondes.
    logged_at : datetime, optional
        Timestamp explicite pour l'insertion. Si None, utilise DEFAULT NOW().
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return

    try:
        import psycopg2

        params: dict[str, Any] = {
            "environment": APP_ENV,
            "duration_ms": duration_ms,
            "score": score,
            "label": label,
            "threshold": threshold,
            **features,
            # psycopg2 n'adapte pas int→boolean ; conversion explicite requise
            "NAME_FAMILY_STATUS_is_MARRIED": bool(features["NAME_FAMILY_STATUS_is_MARRIED"]),
        }

        if logged_at is not None:
            sql = _INSERT_SQL_WITH_TIMESTAMP
            params["logged_at"] = logged_at
        else:
            sql = _INSERT_SQL

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_prediction failed (non-blocking): %s", repr(exc))


_INSERT_ERROR_SQL = """
INSERT INTO prediction_errors (
    environment,
    error_type,
    error_message
) VALUES (
    %(environment)s,
    %(error_type)s,
    %(error_message)s
)
"""

_INSERT_ERROR_SQL_WITH_TIMESTAMP = """
INSERT INTO prediction_errors (
    timestamp,
    environment,
    error_type,
    error_message
) VALUES (
    %(logged_at)s,
    %(environment)s,
    %(error_type)s,
    %(error_message)s
)
"""


def log_prediction_error(
    error_type: str,
    error_message: str,
    logged_at: Any | None = None,
) -> None:
    """Insère une erreur métier ou technique dans prediction_errors."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return

    try:
        import psycopg2

        params: dict[str, Any] = {
            "environment": APP_ENV,
            "error_type": error_type,
            "error_message": error_message,
        }

        if logged_at is not None:
            sql = _INSERT_ERROR_SQL_WITH_TIMESTAMP
            params["logged_at"] = logged_at
        else:
            sql = _INSERT_ERROR_SQL

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_prediction_error failed (non-blocking): %s", repr(exc))


# ---------------------------------------------------------------------------
# Lecture — utilisée par le dashboard Streamlit
# ---------------------------------------------------------------------------

_SELECT_SQL = """
SELECT *
FROM prediction_logs
WHERE environment = %(environment)s
ORDER BY timestamp DESC
LIMIT %(limit)s
"""

_SELECT_ERRORS_SQL = """
SELECT *
FROM prediction_errors
WHERE environment = %(environment)s
ORDER BY timestamp DESC
LIMIT %(limit)s
"""

_COUNT_PREDICTIONS_SQL = """
SELECT COUNT(*)
FROM prediction_logs
WHERE environment = %(environment)s
"""

_COUNT_ERRORS_SQL = """
SELECT COUNT(*)
FROM prediction_errors
WHERE environment = %(environment)s
"""


def read_prediction_logs(limit: int = 1000) -> pd.DataFrame:
    """Lit les dernières prédictions depuis PostgreSQL.

    Filtre uniquement les lignes de l'environnement courant (APP_ENV).
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
            with conn.cursor() as cur:
                cur.execute(_SELECT_SQL, {"environment": APP_ENV, "limit": limit})
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=columns)
    except Exception as exc:  # noqa: BLE001
        logger.warning("read_prediction_logs failed: %s", repr(exc))
        return empty


def read_prediction_errors(limit: int = 1000) -> pd.DataFrame:
    """Lit les dernières erreurs depuis PostgreSQL pour l'environnement courant."""
    empty = pd.DataFrame()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return empty

    try:
        import psycopg2

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_SELECT_ERRORS_SQL, {"environment": APP_ENV, "limit": limit})
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=columns)
    except Exception as exc:  # noqa: BLE001
        logger.warning("read_prediction_errors failed: %s", repr(exc))
        return empty


def count_prediction_logs() -> int:
    """Compte toutes les prédictions de l'environnement courant."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return 0

    try:
        import psycopg2

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_COUNT_PREDICTIONS_SQL, {"environment": APP_ENV})
                return int(cur.fetchone()[0])
    except Exception as exc:  # noqa: BLE001
        logger.warning("count_prediction_logs failed: %s", repr(exc))
        return 0


def count_prediction_errors() -> int:
    """Compte toutes les erreurs de l'environnement courant."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return 0

    try:
        import psycopg2

        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_COUNT_ERRORS_SQL, {"environment": APP_ENV})
                return int(cur.fetchone()[0])
    except Exception as exc:  # noqa: BLE001
        logger.warning("count_prediction_errors failed: %s", repr(exc))
        return 0
