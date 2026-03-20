"""Utility helpers for MLflow tracking.

The module supports 3 cases:
- a tracking URI passed explicitly to a function,
- a tracking URI provided by the `MLFLOW_TRACKING_URI` environment variable,
- a hardcoded fallback tracking URI when the environment variable is missing.

This fallback is useful for local development of project 8 when the `.env` file
is not available or incomplete.

Environment variables
---------------------
MLFLOW_TRACKING_URI:
    Preferred way to configure the remote tracking server URI.
MLFLOW_REMOTE_ENABLED:
    If set to one of {"0", "false", "no", "off"}, remote tracking is disabled.
    In that case, the module uses a local file-based MLflow store.
MLFLOW_LOCAL_FALLBACK_DIR:
    Directory used for the local fallback store when remote tracking is disabled.
    Default: ./mlruns
"""
from __future__ import annotations

import io
import os
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

import mlflow
import mlflow.sklearn
import pandas as pd
from dotenv import load_dotenv
from IPython.display import Markdown, display

# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------
env_path = Path(".env")
if env_path.exists():
    load_dotenv(env_path, override=False)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
# Garde-fou : URI utilisée si `MLFLOW_TRACKING_URI` n'est pas définie.
# À adapter si l'instance MLflow par défaut change.
DEFAULT_TRACKING_URI = "http://127.0.0.1:5001"
DEFAULT_LOCAL_TRACKING_DIR = Path("mlruns")
DEFAULT_SERIALIZATION_FORMAT = "cloudpickle"
DEFAULT_ARTIFACT_PATH = "model"
FALSE_VALUES = {"0", "false", "no", "off"}


# ---------------------------------------------------------------------------
# URI resolution
# ---------------------------------------------------------------------------
def is_remote_tracking_enabled() -> bool:
    """Return whether remote tracking should be used."""
    value = os.getenv("MLFLOW_REMOTE_ENABLED", "true").strip().lower()
    return value not in FALSE_VALUES


def get_local_tracking_uri(
    local_dir: str | Path | None = None,
) -> str:
    """Return a file-based tracking URI for local/offline usage."""
    base_dir = Path(local_dir) if local_dir is not None else Path(
        os.getenv("MLFLOW_LOCAL_FALLBACK_DIR", DEFAULT_LOCAL_TRACKING_DIR)
    )
    resolved = base_dir.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved.as_uri()


def get_effective_tracking_uri(
    tracking_uri: str | None = None,
    allow_remote: bool = True,
    fallback_to_local: bool = True,
    local_dir: str | Path | None = None,
) -> str:
    """Return the tracking URI actually used by the project.

    Priority order:
    1. Explicit ``tracking_uri`` argument
    2. ``MLFLOW_TRACKING_URI`` environment variable
    3. Hardcoded ``DEFAULT_TRACKING_URI``

    Falls back to a local file-based store when remote tracking is disabled.
    """
    requested_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI") or DEFAULT_TRACKING_URI

    if requested_uri is None and fallback_to_local:
        return get_local_tracking_uri(local_dir=local_dir)

    if allow_remote and is_remote_tracking_enabled():
        return requested_uri

    if fallback_to_local:
        return get_local_tracking_uri(local_dir=local_dir)

    if requested_uri is None:
        raise ValueError(
            "No MLflow tracking URI configured. Set MLFLOW_TRACKING_URI for remote usage "
            "or enable a local fallback."
        )

    return requested_uri


def get_tracking_uri_source(tracking_uri: str | None = None) -> str:
    """Return where the effective tracking URI comes from."""
    if tracking_uri:
        return "argument"
    if os.getenv("MLFLOW_TRACKING_URI"):
        return "env"
    if DEFAULT_TRACKING_URI is not None:
        return "hardcoded"
    return "local_fallback"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
def setup_mlflow(
    experiment_name: str,
    tracking_uri: str | None = None,
    *,
    allow_remote: bool = True,
    fallback_to_local: bool = True,
    local_dir: str | Path | None = None,
) -> str:
    """Configure MLflow tracking URI and experiment.

    Returns the effective tracking URI.
    """
    effective_tracking_uri = get_effective_tracking_uri(
        tracking_uri=tracking_uri,
        allow_remote=allow_remote,
        fallback_to_local=fallback_to_local,
        local_dir=local_dir,
    )
    mlflow.set_tracking_uri(effective_tracking_uri)
    mlflow.set_experiment(experiment_name)
    effective_uri = mlflow.get_tracking_uri()
    tracking_source = get_tracking_uri_source(tracking_uri=tracking_uri)
    print(f"MLflow tracking URI source: {tracking_source}")
    return effective_uri


def setup_mlflow_safe_for_evaluation(
    experiment_name: str,
    local_dir: str | Path = "mlruns_evaluation",
) -> str:
    """Configure MLflow in a safe local-only mode for evaluation."""
    return setup_mlflow(
        experiment_name=experiment_name,
        allow_remote=False,
        fallback_to_local=True,
        local_dir=local_dir,
    )


# ---------------------------------------------------------------------------
# Masking helpers (hide personal IPs in shared notebooks)
# ---------------------------------------------------------------------------
def get_tracking_mode_label(tracking_uri: str | None = None) -> str:
    """Return a human-readable label for the active tracking mode."""
    effective_uri = get_effective_tracking_uri(tracking_uri=tracking_uri)
    if effective_uri.startswith("file://"):
        return "local"
    return "remote"


def get_masked_tracking_uri(tracking_uri: str | None = None) -> str:
    """Return a sanitized label for the active tracking URI."""
    effective_uri = get_effective_tracking_uri(tracking_uri=tracking_uri)
    if effective_uri.startswith("file://"):
        return "file://<local-mlruns>"
    if get_tracking_uri_source(tracking_uri=tracking_uri) == "hardcoded":
        return "<DEFAULT_TRACKING_URI>"
    return "<MLFLOW_TRACKING_URI>"


def mask_tracking_uri_in_text(text: str, tracking_uri: str | None = None) -> str:
    """Replace the active tracking URI with a safe placeholder in text."""
    effective_uri = get_effective_tracking_uri(tracking_uri=tracking_uri)
    masked_uri = get_masked_tracking_uri(tracking_uri=tracking_uri)
    return text.replace(effective_uri, masked_uri)


@contextmanager
def mask_mlflow_output(tracking_uri: str | None = None) -> Iterator[None]:
    """Capture stdout/stderr and mask the active tracking URI before printing."""
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        yield

    stdout_text = stdout_buffer.getvalue()
    stderr_text = stderr_buffer.getvalue()

    if stdout_text:
        print(mask_tracking_uri_in_text(stdout_text, tracking_uri=tracking_uri), end="")
    if stderr_text:
        print(mask_tracking_uri_in_text(stderr_text, tracking_uri=tracking_uri), end="")


# ---------------------------------------------------------------------------
# Run management
# ---------------------------------------------------------------------------
@contextmanager
def start_mlflow_run(
    run_name: str | None = None,
    tags: Mapping[str, Any] | None = None,
    tracking_uri: str | None = None,
) -> Iterator[Any]:
    """Start an MLflow run while masking the tracking URI in printed outputs."""
    with mask_mlflow_output(tracking_uri=tracking_uri):
        with start_run(run_name=run_name, tags=tags) as run:
            yield run


def start_run(
    run_name: str | None = None,
    tags: Mapping[str, Any] | None = None,
):
    """Thin wrapper around mlflow.start_run with optional tags."""
    run = mlflow.start_run(run_name=run_name)
    if tags:
        mlflow.set_tags(dict(tags))
    return run


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
def log_params(params: Mapping[str, Any]) -> None:
    """Log params after converting values to MLflow-friendly scalars."""
    clean_params = {k: _to_param_value(v) for k, v in params.items()}
    mlflow.log_params(clean_params)


def log_metrics(metrics: Mapping[str, float]) -> None:
    """Log metrics as floats."""
    clean_metrics = {k: float(v) for k, v in metrics.items()}
    mlflow.log_metrics(clean_metrics)


def log_artifacts(paths: Iterable[str | Path], artifact_path: str | None = None) -> None:
    """Log multiple local files as MLflow artifacts."""
    for path in paths:
        mlflow.log_artifact(str(path), artifact_path=artifact_path)


def log_sklearn_model(
    model: Any,
    artifact_path: str = DEFAULT_ARTIFACT_PATH,
    pip_requirements: list[str] | None = None,
    input_example: Any | None = None,
) -> None:
    """Log a scikit-learn model with stable default options."""
    if pip_requirements is None:
        pip_requirements = get_default_pip_requirements()

    mlflow.sklearn.log_model(
        sk_model=model,
        artifact_path=artifact_path,
        serialization_format=DEFAULT_SERIALIZATION_FORMAT,
        pip_requirements=pip_requirements,
        input_example=input_example,
    )


def get_default_pip_requirements(
    extra_requirements: Iterable[str] | None = None,
) -> list[str]:
    """Return a minimal default requirements list for sklearn models."""
    reqs = [
        "mlflow",
        "scikit-learn",
        "cloudpickle",
        "pandas",
        "numpy",
    ]
    if extra_requirements:
        reqs.extend(extra_requirements)
    return reqs


# ---------------------------------------------------------------------------
# Search & query
# ---------------------------------------------------------------------------
def search_runs_df(
    experiment_names: list[str],
    order_by: list[str] | None = None,
    filter_string: str | None = None,
) -> pd.DataFrame:
    """Read runs into a DataFrame."""
    kwargs: dict[str, Any] = {"experiment_names": experiment_names}
    if order_by is not None:
        kwargs["order_by"] = order_by
    if filter_string is not None:
        kwargs["filter_string"] = filter_string
    return mlflow.search_runs(**kwargs)


def get_best_run(
    experiment_names: list[str],
    metric_name: str,
    ascending: bool = True,
) -> pd.Series:
    """Return the best run according to a metric."""
    order = "ASC" if ascending else "DESC"
    runs = mlflow.search_runs(
        experiment_names=experiment_names,
        order_by=[f"metrics.{metric_name} {order}"],
    )
    if runs.empty:
        raise ValueError("No runs found for the requested experiments.")
    return runs.iloc[0]


def load_sklearn_model_from_run(run_id: str, artifact_path: str = DEFAULT_ARTIFACT_PATH):
    """Load a logged sklearn model from a run."""
    model_uri = f"runs:/{run_id}/{artifact_path}"
    return mlflow.sklearn.load_model(model_uri)


def build_run_model_uri(run_id: str, artifact_path: str = DEFAULT_ARTIFACT_PATH) -> str:
    """Build a runs:/ URI for a logged model."""
    return f"runs:/{run_id}/{artifact_path}"


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def display_masked_mlflow_links(run, run_name="", experiment_id: str | None = None) -> None:
    """Display masked URLs to MLflow UI for a run."""
    tracking_uri = mlflow.get_tracking_uri().rstrip("/")
    experiment_id = experiment_id or run.info.experiment_id
    run_id = run.info.run_id

    run_url = f"{tracking_uri}/#/experiments/{experiment_id}/runs/{run_id}"
    exp_url = f"{tracking_uri}/#/experiments/{experiment_id}"

    display(Markdown(
        f"- [Open run {run_name}](<{run_url}>)\n"
        f"- [Open experiment](<{exp_url}>)"
    ))


def display_masked_mlflow_runs_links(runs, experiment_id: str | None = None) -> None:
    """Display masked URLs to MLflow UI for multiple runs."""
    if not runs:
        display(Markdown("_No runs to display._"))
        return

    tracking_uri = mlflow.get_tracking_uri().rstrip("/")
    experiment_id = experiment_id or runs[0]["run"].info.experiment_id
    exp_url = f"{tracking_uri}/#/experiments/{experiment_id}"

    lines = [f"- [Open experiment](<{exp_url}>)"]

    for run_item in runs:
        run_id = run_item["run"].info.run_id
        run_url = f"{tracking_uri}/#/experiments/{experiment_id}/runs/{run_id}"
        lines.append(f"  - [Open run {run_item['name']}](<{run_url}>)")

    display(Markdown("\n".join(lines)))


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------
def _to_param_value(value: Any) -> Any:
    """Convert values to something safe for mlflow.log_params."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
