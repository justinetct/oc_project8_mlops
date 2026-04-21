"""Tests de la logique pure du dashboard Streamlit.

On ne teste pas l'UI Streamlit (composants visuels), mais uniquement les
fonctions pures extraites dans ``dashboard_streamlit/logic.py`` :
- ``compute_kpis`` : calcul des KPIs globaux (taux d'acceptation,
  scores, latence, taux d'erreur)
- ``prepare_daily_data`` : agrégation des prédictions par jour

Chaque test documente son entrée, sa sortie attendue et son utilité.
"""

import pandas as pd

from dashboard_streamlit.logic import compute_kpis, prepare_daily_data


# -------------------------------------------------------------------
# compute_kpis : DataFrame vide (cas "base vide au démarrage")
# -------------------------------------------------------------------
def test_compute_kpis_empty_df():
    """Entrée : DataFrame vide, 0 prédiction, 0 erreur.
    Sortie attendue : scores à None, taux à 0.0.
    Utilité : protège l'affichage quand aucune prédiction n'a encore
    été faite (cas initial au premier lancement du dashboard).
    """
    result = compute_kpis(pd.DataFrame(), total_predictions=0, total_errors=0)

    assert result["acceptance_rate"] == 0.0
    assert result["mean_score"] is None
    assert result["median_score"] is None
    assert result["latency_mean"] is None
    assert result["latency_median"] is None
    assert result["latency_max"] is None
    assert result["error_rate"] == 0.0

    # Sur un DataFrame vide, l'agrégation temporelle doit aussi renvoyer
    # un DataFrame vide avec les bonnes colonnes (les graphiques n'affichent
    # alors rien au lieu de planter).
    daily = prepare_daily_data(pd.DataFrame())
    assert daily.empty
    assert list(daily.columns) == ["date", "volume", "score_moyen"]


# -------------------------------------------------------------------
# compute_kpis : petit jeu de données connu
# -------------------------------------------------------------------
def test_compute_kpis_simple_data():
    """Entrée : 3 prédictions (2 accordées, 1 refusée) avec scores connus.
    Sortie attendue : acceptance_rate = 66.7 %, score moyen = 0.3,
    score médian = 0.2.
    Utilité : valide la formule du KPI le plus visible du dashboard
    (taux d'acceptation) et les stats de score associées.
    """
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "label": ["Crédit accordé", "Crédit refusé", "Crédit accordé"],
            "score": [0.1, 0.6, 0.2],
            "duration_ms": [10.0, 20.0, 30.0],
        }
    )

    result = compute_kpis(df, total_predictions=3, total_errors=0)

    assert round(result["acceptance_rate"], 1) == 66.7
    assert round(result["mean_score"], 4) == 0.3
    assert result["median_score"] == 0.2
    assert result["latency_mean"] == 20.0
    assert result["latency_median"] == 20.0
    assert result["latency_max"] == 30.0
    assert result["error_rate"] == 0.0


# -------------------------------------------------------------------
# compute_kpis : taux d'erreur
# -------------------------------------------------------------------
def test_compute_kpis_error_rate():
    """Entrée : 10 prédictions valides + 2 erreurs.
    Sortie attendue : error_rate = 2 / (10 + 2) * 100 ≈ 16.7 %.
    Utilité : valide le dénominateur (prédictions + erreurs), facile
    à se tromper. Sépare bien "erreur sur tentatives" et "erreur sur
    prédictions seules".
    """
    df = pd.DataFrame(
        {
            "id": list(range(10)),
            "label": ["Crédit accordé"] * 10,
            "score": [0.1] * 10,
            "duration_ms": [15.0] * 10,
        }
    )

    result = compute_kpis(df, total_predictions=10, total_errors=2)

    assert round(result["error_rate"], 1) == 16.7


# -------------------------------------------------------------------
# prepare_daily_data : agrégation par jour
# -------------------------------------------------------------------
def test_prepare_daily_data_groups_by_day():
    """Entrée : 4 prédictions réparties sur 2 jours (2 par jour).
    Sortie attendue : 2 lignes, volume=2 par jour, score moyen correct.
    Utilité : valide l'agrégation temporelle qui alimente les
    graphiques "Volume par jour" et "Score moyen par jour".
    """
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "timestamp": [
                "2026-04-01 09:00:00",
                "2026-04-01 15:00:00",
                "2026-04-02 10:00:00",
                "2026-04-02 11:00:00",
            ],
            "score": [0.1, 0.3, 0.5, 0.7],
        }
    )

    daily = prepare_daily_data(df)

    assert list(daily.columns) == ["date", "volume", "score_moyen"]
    assert len(daily) == 2
    assert daily["volume"].tolist() == [2, 2]
    assert daily["score_moyen"].tolist() == [0.2, 0.6]
