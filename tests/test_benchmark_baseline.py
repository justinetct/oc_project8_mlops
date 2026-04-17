"""Tests du script de benchmark baseline.

Focus sur les fonctions pures utiles (stats, construction du DataFrame).
Pas de test basé sur les timings réels : instables et peu utiles.
"""

from __future__ import annotations

import pytest

from scripts.benchmark_baseline import (
    UI_INPUT,
    build_sample_dataframe,
    summarize,
)


def test_summarize_fixed_values():
    stats = summarize([1.0, 2.0, 3.0, 4.0, 5.0])
    assert stats["n"] == 5
    assert stats["mean_ms"] == 3.0
    assert stats["median_ms"] == 3.0
    assert stats["max_ms"] == 5.0
    assert stats["p95_ms"] == 5.0


def test_summarize_single_value():
    stats = summarize([42.0])
    assert stats["n"] == 1
    assert stats["mean_ms"] == 42.0
    assert stats["median_ms"] == 42.0
    assert stats["max_ms"] == 42.0
    assert stats["p95_ms"] == 42.0


def test_summarize_empty_raises():
    with pytest.raises(ValueError):
        summarize([])


def test_build_sample_dataframe_matches_model_features():
    """Le DataFrame construit a les colonnes exactes du modèle,
    et les dates UI sont bien converties en DAYS négatifs (avant la date de référence).
    """
    from app_gradio.loader import FEATURES

    df = build_sample_dataframe(UI_INPUT)
    assert list(df.columns) == FEATURES
    assert len(df) == 1
    assert df["DAYS_BIRTH"].iloc[0] < 0
    # Les 3 ratios dérivés doivent être présents et positifs pour ce profil
    assert df["RATIO_CREDIT_ANNUITY"].iloc[0] > 0
