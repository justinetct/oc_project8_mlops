"""Importer un modèle MLflow dans le projet 8.

Le script télécharge un artefact MLflow déjà sélectionné dans
`model/imported_model/`, génère un fichier `model/model_metadata.json`
puis vérifie que le modèle peut être rechargé localement.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow
from dotenv import load_dotenv

from src.config import PATHS, mask_path

MODEL_DIR = PATHS.imported_model
MODEL_METADATA_PATH = PATHS.model_metadata

# Garde-fou : si MLFLOW_TRACKING_URI n'est pas défini dans l'environnement,
# on n'essaie pas de contacter MLflow et on bascule sur des métadonnées codées en dur.
HARD_CODED_MODEL_URI = "mlflow-artifacts:/9/56b9ca33984942c39ce1e723f20ec835/artifacts/model"

HARD_CODED_MODEL_METADATA = {
    "source": {
        "tracking_uri": None,
        "tracking_uri_source": "hardcoded_metadata",
        "model_uri": HARD_CODED_MODEL_URI,
    }
}


def timestamp_utc() -> str:
    """Return an ISO UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def resolve_tracking_uri() -> tuple[str | None, str]:
    """Return the MLflow tracking URI and its source."""
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        return tracking_uri, "env"
    return None, "missing"


def copy_model_dir(source_dir: Path, target_dir: Path) -> None:
    """Replace the target model directory with a clean copy of the source."""
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)


def build_metadata(
    local_model_path: Path,
    tracking_uri: str | None,
    tracking_uri_source: str,
    model_uri: str | None = None,
) -> dict[str, Any]:
    """Build a minimal stable metadata dictionary."""
    return {
        "imported_at_utc": timestamp_utc(),
        "source": {
            "tracking_uri": None,
            "tracking_uri_source": tracking_uri_source,
        },
        "fallback": {
            "source": {
                "tracking_uri": None,
                "tracking_uri_source": "hardcoded_metadata",
                "model_uri": model_uri,
            }
        },
        "local": {
            "model_dir": mask_path(local_model_path),
            "metadata_path": mask_path(MODEL_METADATA_PATH),
        },
    }


def save_metadata(metadata: dict[str, Any], path: Path) -> None:
    """Save metadata as UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def verify_local_reload(local_model_path: Path):
    """Reload the imported model from the local project folder."""
    return mlflow.pyfunc.load_model(model_uri=str(local_model_path.resolve()))


def export_simple_model(local_model_path: Path) -> Path:
    """Re-sauvegarde le modèle en joblib pour un chargement sans MLflow.

    Charge l'artefact MLflow, extrait le modèle sklearn sous-jacent,
    et le sauvegarde en format joblib simple.
    """
    import joblib

    pyfunc_model = mlflow.pyfunc.load_model(model_uri=str(local_model_path.resolve()))
    raw_model = pyfunc_model.get_raw_model()

    output_path = local_model_path.parent / "model_simple.joblib"
    joblib.dump(raw_model, output_path)
    return output_path


def import_model() -> dict[str, Any]:
    """Import the MLflow model into the local project tree."""
    load_dotenv(override=False)

    tracking_uri, tracking_uri_source = resolve_tracking_uri()

    if tracking_uri is None:
        metadata = build_metadata(
            tracking_uri=None,
            tracking_uri_source=tracking_uri_source,
            local_model_path=MODEL_DIR,
            model_uri=HARD_CODED_MODEL_URI,
        )
        save_metadata(metadata, MODEL_METADATA_PATH)

        print("MLFLOW_TRACKING_URI absent : import MLflow ignoré.")
        print("Métadonnées de fallback écrites dans :", mask_path(MODEL_METADATA_PATH))
        return metadata

    mlflow.set_tracking_uri(tracking_uri)

    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        downloaded_path_str = mlflow.artifacts.download_artifacts(
            artifact_uri=HARD_CODED_MODEL_URI,
            dst_path=tmp_dir,
        )
        downloaded_path = Path(downloaded_path_str)
        copy_model_dir(downloaded_path, MODEL_DIR)

    metadata = build_metadata(
        tracking_uri=None,
        tracking_uri_source=tracking_uri_source,
        local_model_path=MODEL_DIR,
        model_uri=HARD_CODED_MODEL_URI,
    )
    save_metadata(metadata, MODEL_METADATA_PATH)

    _ = verify_local_reload(MODEL_DIR)

    simple_path = export_simple_model(MODEL_DIR)
    print(f"Modèle simplifié exporté dans : {mask_path(simple_path)}")

    print("Connexion MLflow configurée : OK")
    print(f"Source de configuration MLflow : {tracking_uri_source}")
    print(f"Modèle importé dans : {mask_path(MODEL_DIR)}")
    print(f"Métadonnées écrites dans : {mask_path(MODEL_METADATA_PATH)}")
    print("Vérification de rechargement local : OK")

    return metadata


def main() -> None:
    import_model()


if __name__ == "__main__":
    main()