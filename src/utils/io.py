from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import PATHS, mask_path


def timestamp_utc() -> str:
    """Return a compact UTC timestamp safe for file names."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def ensure_parent_dir(path: str | Path) -> Path:
    """Create the parent directory of a file path if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def to_jsonable(value: Any) -> Any:
    """Convert common non-JSON-native objects into serializable values."""
    if isinstance(value, Path):
        return mask_path(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    return value


def save_json(data: dict[str, Any], path: str | Path, indent: int = 2) -> Path:
    """Save a dictionary to JSON with UTF-8 encoding."""
    output_path = ensure_parent_dir(path)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(to_jsonable(data), f, ensure_ascii=False, indent=indent)
    return output_path


def append_csv_row(row: dict[str, Any], path: str | Path) -> Path:
    """Append one row to a CSV file, creating the header if needed."""
    output_path = ensure_parent_dir(path)
    fieldnames = list(row.keys())
    file_exists = output_path.exists()

    with output_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: to_jsonable(v) for k, v in row.items()})
    return output_path


def save_text(text: str, path: str | Path) -> Path:
    """Save plain text to a UTF-8 file."""
    output_path = ensure_parent_dir(path)
    output_path.write_text(text, encoding="utf-8")
    return output_path


def save_matplotlib_figure(fig, path: str | Path, dpi: int = 150, bbox_inches: str = "tight") -> Path:
    """Save a matplotlib figure to disk."""
    output_path = ensure_parent_dir(path)
    fig.savefig(output_path, dpi=dpi, bbox_inches=bbox_inches)
    return output_path


def build_run_paths(run_name: str) -> dict[str, Path]:
    """Return standard output paths for a lightweight experiment run."""
    run_dir = PATHS.runs / run_name
    return {
        "run_dir": run_dir,
        "json": run_dir / "run_info.json",
        "csv": PATHS.logs / "runs_summary.csv",
        "notes": run_dir / "notes.txt",
        "figure": PATHS.figures / f"{run_name}_dry_run.png",
    }
