from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


PROJECT_NAME = "OC-P8-MLOps"
SEED = 42

# Date de lancement du challenge Kaggle Home Credit Default Risk.
# Sert de référence pour convertir les dates saisies en DAYS_*.
HOME_CREDIT_REFERENCE_DATE = date(2018, 5, 17)

MODEL_ARTIFACT_DIRNAME = "imported_model"
MODEL_METADATA_FILENAME = "model_metadata.json"


@dataclass(frozen=True)
class Paths:
    root: Path
    notebooks: Path
    scripts: Path
    src: Path
    tests: Path
    model: Path
    imported_model: Path
    model_metadata: Path
    app_gradio: Path
    dashboard_streamlit: Path
    logs: Path
    tmp: Path


def get_paths() -> Paths:
    here = Path(__file__).resolve()
    root = here.parents[1]

    model_dir = root / "model"

    return Paths(
        root=root,
        notebooks=root / "notebooks",
        scripts=root / "scripts",
        src=root / "src",
        tests=root / "tests",
        model=model_dir,
        imported_model=model_dir / MODEL_ARTIFACT_DIRNAME,
        model_metadata=model_dir / MODEL_METADATA_FILENAME,
        app_gradio=root / "app_gradio",
        dashboard_streamlit=root / "dashboard_streamlit",
        logs=root / "logs",
        tmp=root / "tmp",
    )


PATHS = get_paths()

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")

SAFE_ROOT_LABEL = "<PROJECT_ROOT>"


def mask_path(value: str | Path) -> str:
    """Mask absolute project path for notebook/log display."""
    p = Path(value)
    try:
        resolved = str(p.resolve())
    except Exception:
        resolved = str(p)

    root_str = str(PATHS.root.resolve())
    return resolved.replace(root_str, SAFE_ROOT_LABEL)