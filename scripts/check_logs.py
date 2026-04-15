"""Affiche les dernières lignes de prediction_logs.

Usage :
    poetry run python scripts/check_logs.py        # 10 dernières lignes
    poetry run python scripts/check_logs.py 25     # 25 dernières lignes
"""

import sys

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Erreur : DATABASE_URL non défini.", file=sys.stderr)
    sys.exit(1)

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10

try:
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, timestamp, score, label, threshold
                FROM prediction_logs
                ORDER BY id DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
except Exception as exc:
    print(f"Erreur : {exc}", file=sys.stderr)
    sys.exit(1)

if not rows:
    print("Aucune ligne dans prediction_logs.")
    sys.exit(0)

header = f"{'id':>4}  {'timestamp':<30}  {'score':>8}  {'label':<16}  {'threshold':>9}"
sep = "-" * len(header)
print(header)
print(sep)
for row_id, ts, score, label, threshold in rows:
    print(f"{row_id:>4}  {str(ts):<30}  {score:>8.6f}  {label:<16}  {threshold:>9.4f}")
print(sep)
print(f"{len(rows)} ligne(s)")
