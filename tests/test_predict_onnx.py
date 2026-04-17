"""Tests de l'intégration ONNX dans le chemin de prédiction.

Le module `app_gradio.loader` met la session ONNX en cache au premier appel,
ce qui rend difficile de comparer deux modes dans le même process. On utilise
donc un sous-process pour comparer sklearn vs ONNX sur un même profil.
Pour le test de fallback (session=None), on mocke `get_onnx_session` dans
le process courant.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ONNX_PATH = PROJECT_ROOT / "model" / "model_simple.onnx"

SAMPLE_INPUT = {
    "EXT_SOURCE_1": 0.62,
    "EXT_SOURCE_2": 0.71,
    "EXT_SOURCE_3": 0.51,
    "DAYS_BIRTH": -15770,
    "DAYS_EMPLOYED": -3049,
    "DAYS_ID_PUBLISH": -1062,
    "AMT_ANNUITY": 20_000,
    "AMT_GOODS_PRICE": 250_000,
    "AMT_CREDIT": 230_000,
    "AMT_INCOME_TOTAL": 250_000,
    "NAME_FAMILY_STATUS_is_MARRIED": 1,
}


def _run_predict_subprocess(env_vars: dict) -> float:
    """Lance predict(SAMPLE_INPUT) dans un sous-process avec env_vars définis."""
    code = (
        "import json, sys\n"
        "sys.path.insert(0, '.')\n"
        "from app_gradio.predict import predict\n"
        f"print(json.dumps(predict({SAMPLE_INPUT!r})))\n"
    )
    env = {**os.environ, **env_vars}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    # Dernière ligne = JSON ; les lignes au-dessus sont les print [loader] etc.
    last_line = result.stdout.strip().splitlines()[-1]
    return float(json.loads(last_line)["score"])


def test_predict_works_without_use_onnx():
    """USE_ONNX absent → sklearn, predict() fonctionne normalement."""
    score = _run_predict_subprocess({"USE_ONNX": "0"})
    assert 0.0 <= score <= 1.0


@pytest.mark.skipif(not ONNX_PATH.exists(), reason="artefact ONNX absent")
def test_predict_scores_match_between_sklearn_and_onnx():
    """USE_ONNX=1 + artefact présent → score cohérent avec sklearn (tolérance 1e-4)."""
    sk_score = _run_predict_subprocess({"USE_ONNX": "0"})
    onnx_score = _run_predict_subprocess({"USE_ONNX": "1"})
    assert abs(sk_score - onnx_score) < 1e-4


def test_predict_falls_back_to_sklearn_when_session_is_none(monkeypatch):
    """Si get_onnx_session() retourne None, predict() doit utiliser sklearn sans planter."""
    from app_gradio import predict as predict_mod

    monkeypatch.setattr(predict_mod, "get_onnx_session", lambda: None)

    result = predict_mod.predict(SAMPLE_INPUT)
    assert 0.0 <= result["score"] <= 1.0
    assert result["label"] in ("Crédit accordé", "Crédit refusé")


# ---------------------------------------------------------------------------
# Tests in-process de get_onnx_session() — couvrent les branches que les tests
# en sous-process ne voient pas du point de vue du collecteur de coverage.
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_loader(monkeypatch):
    """Reset le singleton _onnx_session avant chaque test (évite la pollution de cache)."""
    from app_gradio import loader
    monkeypatch.setattr(loader, "_onnx_session", None)
    return loader


def test_loader_returns_none_when_use_onnx_disabled(fresh_loader, monkeypatch):
    """USE_ONNX=False → get_onnx_session retourne None."""
    monkeypatch.setattr(fresh_loader, "USE_ONNX", False)
    assert fresh_loader.get_onnx_session() is None


def test_loader_returns_none_when_artifact_missing(fresh_loader, monkeypatch, tmp_path):
    """USE_ONNX=True mais artefact absent → None (fallback sklearn)."""
    monkeypatch.setattr(fresh_loader, "USE_ONNX", True)
    monkeypatch.setattr(fresh_loader, "ONNX_PATH", tmp_path / "missing.onnx")
    assert fresh_loader.get_onnx_session() is None


def test_loader_returns_none_when_load_fails(fresh_loader, monkeypatch, tmp_path):
    """Fichier corrompu → InferenceSession lève → None (fallback sklearn)."""
    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"this is not a valid onnx file")
    monkeypatch.setattr(fresh_loader, "USE_ONNX", True)
    monkeypatch.setattr(fresh_loader, "ONNX_PATH", bad)
    assert fresh_loader.get_onnx_session() is None


@pytest.mark.skipif(not ONNX_PATH.exists(), reason="artefact ONNX absent")
def test_loader_returns_session_and_caches(fresh_loader, monkeypatch):
    """USE_ONNX=True + artefact présent → session chargée puis mise en cache."""
    monkeypatch.setattr(fresh_loader, "USE_ONNX", True)

    session = fresh_loader.get_onnx_session()
    assert session is not None

    # Deuxième appel : hit du cache (même objet)
    assert fresh_loader.get_onnx_session() is session


@pytest.mark.skipif(not ONNX_PATH.exists(), reason="artefact ONNX absent")
def test_predict_uses_onnx_in_process(fresh_loader, monkeypatch):
    """predict() passe réellement par ONNX : on casse sklearn et on vérifie qu'il n'est pas appelé.

    Preuve que le chemin ONNX est bien emprunté : si le fallback sklearn avait lieu,
    model.predict_proba serait appelé et le test échouerait explicitement.
    Le score ONNX doit aussi rester cohérent avec la référence sklearn (tolérance 1e-4).
    """
    # Référence sklearn avant le patching (USE_ONNX encore False ici)
    from app_gradio.predict import predict
    sklearn_reference = predict(SAMPLE_INPUT)["score"]

    # Active ONNX + invalide sklearn : tout appel à model.predict_proba fera échouer le test
    monkeypatch.setattr(fresh_loader, "USE_ONNX", True)

    def _sklearn_should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "model.predict_proba ne doit pas être appelé quand ONNX prend la main"
        )
    monkeypatch.setattr(fresh_loader.model, "predict_proba", _sklearn_should_not_be_called)

    result = predict(SAMPLE_INPUT)

    # Si on arrive ici, c'est que predict() est passé par ONNX (sinon l'AssertionError aurait levé)
    assert 0.0 <= result["score"] <= 1.0
    assert result["label"] in ("Crédit accordé", "Crédit refusé")
    assert abs(result["score"] - sklearn_reference) < 1e-4
