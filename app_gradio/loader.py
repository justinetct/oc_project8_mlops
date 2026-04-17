"""Chargement unique du modèle LightGBM depuis l'artefact local.

Le modèle est chargé une seule fois au premier import du module.
Les appels suivants réutilisent la même instance (singleton module-level).
Aucune dépendance à MLflow : on charge le joblib extrait à l'import.
"""

from __future__ import annotations

import json
import os
import joblib
from pathlib import Path

from src.config import PATHS

# -- Chemins vers les artefacts locaux --
MODEL_JOBLIB_PATH: Path = PATHS.model / "model_simple.joblib"
MODEL_CONFIG_PATH: Path = PATHS.model / "v5_ui_model_config.json"


def _load_model():
    """Charge le modèle depuis le fichier joblib local."""
    if not MODEL_JOBLIB_PATH.exists():
        raise FileNotFoundError(
            f"Modèle introuvable : {MODEL_JOBLIB_PATH}. "
            "Lance d'abord le script d'import MLflow."
        )
    pipeline = joblib.load(MODEL_JOBLIB_PATH)
    pipeline.set_output(transform="pandas")
    return pipeline


def _load_config() -> dict:
    """Charge la config du modèle (features, seuil, métriques)."""
    if not MODEL_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config modèle introuvable : {MODEL_CONFIG_PATH}."
        )
    return json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))


# -- Chargement unique au premier import --
model = _load_model()
config = _load_config()

FEATURES: list[str] = config["features"]
THRESHOLD: float = config["metrics"]["best_threshold_holdout"]


# ---------------------------------------------------------------------------
# Chargement ONNX optionnel (activé par USE_ONNX=1)
# ---------------------------------------------------------------------------

USE_ONNX: bool = os.environ.get("USE_ONNX", "0") == "1"
ONNX_PATH: Path = PATHS.model / "model_simple.onnx"

_onnx_session = None  # singleton module-level


def get_onnx_session():
    """Retourne la session ONNX si dispo, sinon None (fallback sklearn).

    Mis en cache : chargé une seule fois au premier appel. Un message
    simple est affiché pour indiquer le chemin retenu.
    """
    global _onnx_session
    if _onnx_session is not None:
        return _onnx_session
    if not USE_ONNX:
        print("[loader] USE_ONNX désactivé → inférence sklearn")
        return None
    if not ONNX_PATH.exists():
        print(f"[loader] artefact ONNX introuvable ({ONNX_PATH.name}) → fallback sklearn")
        return None
    try:
        import onnxruntime as ort
        _onnx_session = ort.InferenceSession(
            str(ONNX_PATH), providers=["CPUExecutionProvider"]
        )
        print(f"[loader] ONNX activé ({ONNX_PATH.name})")
        return _onnx_session
    except Exception as exc:  # noqa: BLE001
        print(f"[loader] chargement ONNX échoué ({exc!r}) → fallback sklearn")
        return None
