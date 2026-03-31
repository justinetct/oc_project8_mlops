"""Crée les tables PostgreSQL nécessaires à l'application.

Usage :
    DATABASE_URL=postgresql://... python scripts/create_tables.py

Idempotent : utilise CREATE TABLE IF NOT EXISTS.
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Erreur : DATABASE_URL non défini.", file=sys.stderr)
    sys.exit(1)

CREATE_PREDICTION_LOGS = """
CREATE TABLE IF NOT EXISTS prediction_logs (
    id                          SERIAL           PRIMARY KEY,
    timestamp                   TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
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

try:
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_PREDICTION_LOGS)
    print("OK : table prediction_logs prête.")
except Exception as exc:
    print(f"Erreur : {exc}", file=sys.stderr)
    sys.exit(1)
