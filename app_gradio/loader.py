"""Chargement unique du modèle LightGBM depuis l'artefact local.

Le modèle est chargé une seule fois au premier import du module.
Les appels suivants réutilisent la même instance (singleton module-level).
Aucune dépendance à MLflow : on charge le joblib extrait à l'import.
"""

from __future__ import annotations

import json
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
