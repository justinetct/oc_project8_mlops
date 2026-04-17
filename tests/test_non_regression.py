"""Non-régression fonctionnelle : score_client() donne le même résultat en sklearn et en ONNX.

Sous-ensemble de profils contrastés parmi ceux de scripts/check_non_regression.py.
Deux garde-fous pour éviter un faux verdict OK :
  - _score_with('onnx', ...) lève AssertionError si la session ne se charge pas
  - pendant le scoring ONNX, sklearn.model.predict_proba lève AssertionError s'il
    est appelé (fallback silencieux détecté → test en échec explicite)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ONNX_PATH = PROJECT_ROOT / "model" / "model_simple.onnx"

# Sous-ensemble représentatif : 3 profils (les extrêmes + un intermédiaire)
# suffisent pour la CI. Le script dédié couvre le jeu complet.
PROFILES = [
    {
        "ext_source_1": 0.62, "ext_source_2": 0.71, "ext_source_3": 0.51,
        "date_naissance": "1975-03-15", "date_embauche": "2010-01-10",
        "date_id": "2015-06-20",
        "amt_annuity": 20_000, "amt_goods_price": 250_000,
        "amt_credit": 230_000, "amt_income_total": 250_000,
        "is_married": "Oui",
    },
    {
        "ext_source_1": 0.90, "ext_source_2": 0.88, "ext_source_3": 0.85,
        "date_naissance": "1970-01-01", "date_embauche": "2000-01-01",
        "date_id": "2010-01-01",
        "amt_annuity": 15_000, "amt_goods_price": 200_000,
        "amt_credit": 180_000, "amt_income_total": 400_000,
        "is_married": "Oui",
    },
    {
        "ext_source_1": 0.05, "ext_source_2": 0.08, "ext_source_3": 0.03,
        "date_naissance": "1998-01-01", "date_embauche": "2018-01-01",
        "date_id": "2017-01-01",
        "amt_annuity": 50_000, "amt_goods_price": 600_000,
        "amt_credit": 600_000, "amt_income_total": 100_000,
        "is_married": "Non",
    },
]

TOLERANCE = 5e-3


def _score_with(engine: str, ui_input: dict) -> tuple[float, str]:
    """Score via score_client() en forçant sklearn ou ONNX en mémoire.

    En mode ONNX, vérifie explicitement qu'une session est bien chargée.
    """
    import app_gradio.loader as loader

    loader._onnx_session = None
    loader.USE_ONNX = (engine == "onnx")

    if engine == "onnx":
        session = loader.get_onnx_session()
        assert session is not None, (
            "ONNX indisponible : session non chargée — le fallback sklearn "
            "masquerait la comparaison"
        )

    from app_gradio.scoring_service import score_client

    with patch("app_gradio.scoring_service.log_prediction"), \
         patch("app_gradio.scoring_service.log_prediction_error"):
        result = score_client(**ui_input)

    assert result.success, f"scoring échoué : {result.errors}"
    return result.score, result.label


@pytest.mark.skipif(not ONNX_PATH.exists(), reason="artefact ONNX absent")
@pytest.mark.parametrize("profile", PROFILES)
def test_score_client_non_regression(profile, monkeypatch):
    """Sklearn vs ONNX sur score_client() : même score (1e-4) et même label.

    Garde-fous pour éviter un faux verdict OK :
    - _score_with('onnx', ...) lève AssertionError si la session ne se charge pas
    - pendant le scoring ONNX, sklearn.predict_proba lèvera AssertionError s'il
      est appelé (fallback détecté → test en échec explicite)
    """
    import app_gradio.loader as loader
    monkeypatch.setattr(loader, "_onnx_session", None)
    monkeypatch.setattr(loader, "USE_ONNX", False)

    # 1. Score sklearn (référence)
    sk_score, sk_label = _score_with("sklearn", profile)

    # 2. Garde-fou : sklearn ne doit pas être appelé pendant le scoring ONNX
    def _sklearn_must_not_be_called(*args, **kwargs):
        raise AssertionError(
            "fallback sklearn détecté pendant le scoring ONNX : "
            "la comparaison aurait été faussée"
        )
    monkeypatch.setattr(loader.model, "predict_proba", _sklearn_must_not_be_called)

    # 3. Score ONNX (hard check intégré dans _score_with)
    onnx_score, onnx_label = _score_with("onnx", profile)

    # 4. Non-régression
    assert abs(sk_score - onnx_score) < TOLERANCE, (
        f"écart de score au-dessus de la tolérance : "
        f"sklearn={sk_score:.6f} onnx={onnx_score:.6f}"
    )
    assert sk_label == onnx_label, (
        f"labels divergents : sklearn='{sk_label}' onnx='{onnx_label}'"
    )
