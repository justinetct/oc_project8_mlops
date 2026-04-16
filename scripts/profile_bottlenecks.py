"""Profiling cProfile + snapshot CPU/RAM de score_client().

Objectif : collecter des mesures pour identifier les goulots dans le chemin
applicatif in-process, en complément de la baseline (tâche 30).

Sorties :
  - perf/results/cprofile_<ts>.prof   : dump binaire cProfile (non versionné)
  - perf/results/cprofile_<ts>.txt    : top fonctions lisibles (cumtime + tottime)
  - stdout                            : top 15 cumulatif + CPU / RAM

Usage :
    poetry run python scripts/profile_bottlenecks.py
    poetry run python scripts/profile_bottlenecks.py --n 2000 --top 40
"""

from __future__ import annotations

import argparse
import cProfile
import platform
import pstats
import resource
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.benchmark_baseline import UI_INPUT  # noqa: E402  (profil unique = celui de la baseline)

RESULTS_DIR = PROJECT_ROOT / "perf" / "results"


def _rss_to_mb(maxrss: int) -> float:
    """ru_maxrss est en octets sur macOS, en kilo-octets sur Linux."""
    if platform.system() == "Darwin":
        return maxrss / (1024 * 1024)
    return maxrss / 1024


def run_profiled_workload(n: int, warmup: int = 5) -> tuple[cProfile.Profile, dict]:
    """Profile score_client() N fois et capture CPU / RAM autour de l'exécution.

    L'écriture en base (log_prediction / log_prediction_error) est désactivée
    pendant la mesure, comme en baseline, pour isoler la logique applicative.
    """
    from app_gradio.scoring_service import score_client

    with patch("app_gradio.scoring_service.log_prediction"), \
         patch("app_gradio.scoring_service.log_prediction_error"):
        for _ in range(warmup):
            score_client(**UI_INPUT)

        r0 = resource.getrusage(resource.RUSAGE_SELF)
        t0 = time.monotonic()

        profiler = cProfile.Profile()
        profiler.enable()
        for _ in range(n):
            score_client(**UI_INPUT)
        profiler.disable()

        elapsed = time.monotonic() - t0
        r1 = resource.getrusage(resource.RUSAGE_SELF)

    cpu_time = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
    cpu_percent = (cpu_time / elapsed * 100.0) if elapsed > 0 else 0.0

    metrics = {
        "n_calls": n,
        "elapsed_s": round(elapsed, 3),
        "cpu_time_s": round(cpu_time, 3),
        "cpu_percent": round(cpu_percent, 1),
        "peak_rss_mb": round(_rss_to_mb(r1.ru_maxrss), 1),
    }
    return profiler, metrics


def save_profile(profiler: cProfile.Profile, top_n: int) -> dict[str, Path]:
    """Dump .prof binaire + .txt lisible (cumtime et tottime)."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prof_path = RESULTS_DIR / f"cprofile_{ts}.prof"
    txt_path = RESULTS_DIR / f"cprofile_{ts}.txt"

    profiler.dump_stats(prof_path)

    with txt_path.open("w", encoding="utf-8") as f:
        f.write(f"# Top {top_n} fonctions par temps cumulé (cumtime)\n\n")
        stats = pstats.Stats(profiler, stream=f).strip_dirs().sort_stats("cumulative")
        stats.print_stats(top_n)

        f.write(f"\n\n# Top {top_n} fonctions par temps propre (tottime)\n\n")
        stats = pstats.Stats(profiler, stream=f).strip_dirs().sort_stats("tottime")
        stats.print_stats(top_n)

    return {"prof": prof_path, "txt": txt_path}


def print_top(profiler: cProfile.Profile, k: int = 15) -> None:
    print(f"\n[Top {k} par temps cumulé]")
    pstats.Stats(profiler).strip_dirs().sort_stats("cumulative").print_stats(k)


def main() -> None:
    parser = argparse.ArgumentParser(description="cProfile + snapshot CPU/RAM de score_client.")
    parser.add_argument("--n", type=int, default=1000, help="Nombre d'appels profilés (défaut : 1000).")
    parser.add_argument("--top", type=int, default=30, help="Top N sauvegardé dans le .txt (défaut : 30).")
    args = parser.parse_args()

    print("=" * 64)
    print(f"Profile bottlenecks — n={args.n}")
    print("=" * 64)

    profiler, metrics = run_profiled_workload(args.n)

    print("\n[Ressources]")
    for k, v in metrics.items():
        print(f"  {k:<14} = {v}")

    paths = save_profile(profiler, top_n=args.top)
    print("\n[Profil sauvegardé]")
    print(f"  binaire : {paths['prof'].relative_to(PROJECT_ROOT)}  (non versionné)")
    print(f"  texte   : {paths['txt'].relative_to(PROJECT_ROOT)}")

    print_top(profiler, k=15)


if __name__ == "__main__":
    main()
