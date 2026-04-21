"""Logique pure du dashboard (sans Streamlit).

Extrait de ``app.py`` pour rendre la logique testable :
- calcul des KPIs globaux affichés en haut du dashboard
- préparation des données temporelles (volume et score moyen par jour)

Aucune dépendance à Streamlit : uniquement pandas. Les fonctions sont
pures et sans effet de bord, ce qui permet de les tester simplement.
"""

from __future__ import annotations

import pandas as pd


def compute_kpis(
    df: pd.DataFrame,
    total_predictions: int,
    total_errors: int,
) -> dict:
    """Calcule les indicateurs clés affichés en haut du dashboard.

    Paramètres
    ----------
    df : DataFrame des prédictions valides (peut être vide).
    total_predictions : nombre total de prédictions en base.
    total_errors : nombre total d'erreurs en base.

    Retour : dict avec les clés suivantes (valeurs ``None`` ou ``0.0`` si
    aucune donnée) : ``acceptance_rate``, ``mean_score``, ``median_score``,
    ``latency_mean``, ``latency_median``, ``latency_max``, ``error_rate``.
    """
    if df.empty:
        accepted = 0
        acceptance_rate = 0.0
        mean_score = None
        median_score = None
    else:
        accepted = int((df["label"] == "Crédit accordé").sum())
        acceptance_rate = accepted / len(df) * 100
        mean_score = float(df["score"].mean())
        median_score = float(df["score"].median())

    if "duration_ms" in df.columns:
        latency_values = df["duration_ms"].dropna()
    else:
        latency_values = pd.Series(dtype=float)

    latency_mean = float(latency_values.mean()) if not latency_values.empty else None
    latency_median = float(latency_values.median()) if not latency_values.empty else None
    latency_max = float(latency_values.max()) if not latency_values.empty else None

    denom = total_predictions + total_errors
    error_rate = (total_errors / denom * 100) if denom > 0 else 0.0

    return {
        "acceptance_rate": acceptance_rate,
        "mean_score": mean_score,
        "median_score": median_score,
        "latency_mean": latency_mean,
        "latency_median": latency_median,
        "latency_max": latency_max,
        "error_rate": error_rate,
    }


def prepare_daily_data(df: pd.DataFrame) -> pd.DataFrame:
    """Agrège les prédictions par jour (volume + score moyen).

    Retourne un DataFrame trié par date avec les colonnes ``date``,
    ``volume`` et ``score_moyen``. Si ``df`` est vide, retourne un
    DataFrame vide avec les mêmes colonnes.
    """
    if df.empty:
        return pd.DataFrame(columns=["date", "volume", "score_moyen"])

    work = df.copy()
    work["date"] = pd.to_datetime(work["timestamp"]).dt.date
    daily = (
        work.groupby("date")
        .agg(volume=("id", "count"), score_moyen=("score", "mean"))
        .reset_index()
    )
    daily["date"] = pd.to_datetime(daily["date"])
    return daily
