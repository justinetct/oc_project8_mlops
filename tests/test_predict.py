"""Vérification simple du chargement et de la prédiction."""

from app_gradio.loader import model, FEATURES, THRESHOLD
from app_gradio.predict import predict, compute_ratios


# -- Exemple d'entrée valide (valeurs réalistes) --
SAMPLE_INPUT = {
    "EXT_SOURCE_1": 0.5,
    "EXT_SOURCE_2": 0.6,
    "EXT_SOURCE_3": 0.4,
    "DAYS_BIRTH": -12000,       # ~33 ans
    "DAYS_EMPLOYED": -2000,     # ~5.5 ans d'emploi
    "DAYS_ID_PUBLISH": -3000,
    "AMT_ANNUITY": 25000.0,
    "AMT_GOODS_PRICE": 300000.0,
    "AMT_CREDIT": 350000.0,
    "AMT_INCOME_TOTAL": 200000.0,
    "NAME_FAMILY_STATUS_is_MARRIED": 1,
}


def test_model_loaded_once():
    """Le modèle est le même objet à chaque import (singleton)."""
    from app_gradio.loader import model as model2
    assert model is model2


def test_features_count():
    assert len(FEATURES) == 14


def test_threshold_is_valid():
    assert 0.0 < THRESHOLD < 1.0


def test_compute_ratios():
    data = compute_ratios(dict(SAMPLE_INPUT))
    assert "RATIO_CREDIT_ANNUITY" in data
    assert "RATIO_GOODS_CREDIT" in data
    assert "RATIO_ANNUITY_INCOME" in data
    assert data["RATIO_CREDIT_ANNUITY"] == 350000.0 / 25000.0
    assert data["RATIO_GOODS_CREDIT"] == 300000.0 / 350000.0
    assert data["RATIO_ANNUITY_INCOME"] == 25000.0 / 200000.0


def test_predict_returns_expected_keys():
    result = predict(SAMPLE_INPUT)
    assert "score" in result
    assert "label" in result
    assert "threshold" in result
    assert "message" in result


def test_predict_score_range():
    result = predict(SAMPLE_INPUT)
    assert 0.0 <= result["score"] <= 1.0


def test_predict_label_is_valid():
    result = predict(SAMPLE_INPUT)
    assert result["label"] in ("Crédit accordé", "Crédit refusé")
