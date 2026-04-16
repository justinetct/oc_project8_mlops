"""Test ONNX Runtime vs sklearn (faisabilité puis benchmark).

Deux phases dans un seul script :

  [Phase 1 - Faisabilité]  (toujours exécutée)
    - Convertit la pipeline sklearn en ONNX si model/model_simple.onnx absent
    - Vérifie la cohérence des scores sklearn vs ONNX sur le profil UI
    - Produit un statut : "ok" | "conversion_failed" | "score_divergence"

  [Phase 2 - Benchmark]  (exécutée uniquement si phase 1 = "ok")
    - N appels mesurés après warmup, sklearn vs ONNX Runtime
    - Ratio médiane sklearn / ONNX

Quel que soit le statut, un JSON est sauvegardé dans perf/results/onnx_<ts>.json.
Le script ne lève pas d'exception en cas d'échec métier (exit code 0) :
l'échec mesuré est un résultat légitime du test de faisabilité.

Aucune modification du code produit.

Usage :
    poetry install --with perf
    poetry run python scripts/benchmark_onnx.py
    poetry run python scripts/benchmark_onnx.py --n 200 --warmup 10
    poetry run python scripts/benchmark_onnx.py --force   # force la reconversion
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.benchmark_baseline import UI_INPUT, build_sample_dataframe, summarize  # noqa: E402

ONNX_PATH = PROJECT_ROOT / "model" / "model_simple.onnx"
RESULTS_DIR = PROJECT_ROOT / "perf" / "results"


# ---------------------------------------------------------------------------
# Phase 1 - Faisabilité
# ---------------------------------------------------------------------------

def try_convert_pipeline_to_onnx() -> tuple[bool, str]:
    """Tente la conversion. Retourne (True, "") si OK, (False, raison) sinon."""
    try:
        import lightgbm as lgb
        from onnxmltools.convert.lightgbm.operator_converters.LightGbm import (
            convert_lightgbm,
        )
        from skl2onnx import convert_sklearn, update_registered_converter
        from skl2onnx.common.data_types import FloatTensorType
        from skl2onnx.common.shape_calculator import (
            calculate_linear_classifier_output_shapes,
        )
    except ImportError as exc:
        return False, f"dépendances ONNX manquantes : {exc}"

    try:
        from app_gradio.loader import FEATURES, model
    except Exception as exc:  # noqa: BLE001
        return False, f"chargement du modèle sklearn échoué : {exc}"

    try:
        update_registered_converter(
            lgb.LGBMClassifier,
            "LightGbmLGBMClassifier",
            calculate_linear_classifier_output_shapes,
            convert_lightgbm,
            options={"nocl": [True, False], "zipmap": [True, False]},
        )
        initial_types = [("input", FloatTensorType([None, len(FEATURES)]))]
        # target_opset explicite : 15 pour le domaine principal, 3 pour
        # 'ai.onnx.ml' (requis par la version actuelle de skl2onnx/onnxruntime).
        onnx_model = convert_sklearn(
            model,
            initial_types=initial_types,
            target_opset={"": 15, "ai.onnx.ml": 3},
            options={id(model): {"zipmap": False}},
        )
        ONNX_PATH.write_bytes(onnx_model.SerializeToString())
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"conversion skl2onnx échouée : {exc}"


def phase1_feasibility(tol: float, force: bool) -> dict:
    """Phase 1 : (re)conversion si besoin + contrôle de l'équivalence des scores."""
    if force and ONNX_PATH.exists():
        ONNX_PATH.unlink()

    if not ONNX_PATH.exists():
        print("  → conversion pipeline sklearn → ONNX ...")
        ok, reason = try_convert_pipeline_to_onnx()
        if not ok:
            print(f"    ✗ {reason}")
            return {"status": "conversion_failed", "reason": reason, "equivalence": None}
        print(f"    ✓ modèle ONNX écrit : {ONNX_PATH.relative_to(PROJECT_ROOT)}")
    else:
        print(f"  → ONNX trouvé : {ONNX_PATH.relative_to(PROJECT_ROOT)}")

    try:
        import numpy as np
        import onnxruntime as ort

        from app_gradio.loader import model
    except ImportError as exc:
        return {
            "status": "conversion_failed",
            "reason": f"runtime ONNX manquant : {exc}",
            "equivalence": None,
        }

    df = build_sample_dataframe(UI_INPUT)
    sk_score = float(model.predict_proba(df)[0, 1])

    session = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    X = df.to_numpy(dtype=np.float32)
    outputs = session.run(None, {input_name: X})
    probas = outputs[1] if len(outputs) > 1 else outputs[0]
    onnx_score = float(probas[0][1])

    diff = abs(sk_score - onnx_score)
    within_tol = diff <= tol

    print(f"  sklearn score : {sk_score:.6f}")
    print(f"  onnx    score : {onnx_score:.6f}")
    print(f"  écart         : {diff:.2e}  (tolérance {tol:.0e})")
    print(f"    {'✓ scores équivalents' if within_tol else '✗ écart au-dessus de la tolérance'}")

    equivalence = {
        "sklearn_score": sk_score,
        "onnx_score": onnx_score,
        "diff": diff,
        "tolerance": tol,
        "within_tolerance": within_tol,
    }
    status = "ok" if within_tol else "score_divergence"
    return {
        "status": status,
        "equivalence": equivalence,
        "runtime": {"session": session, "df": df},
    }


# ---------------------------------------------------------------------------
# Phase 2 - Benchmark
# ---------------------------------------------------------------------------

def bench_sklearn(df, n: int, warmup: int) -> list[float]:
    from app_gradio.loader import model
    for _ in range(warmup):
        model.predict_proba(df)
    timings = []
    for _ in range(n):
        t0 = perf_counter()
        model.predict_proba(df)
        timings.append((perf_counter() - t0) * 1000.0)
    return timings


def bench_onnx(session, df, n: int, warmup: int) -> list[float]:
    import numpy as np
    input_name = session.get_inputs()[0].name
    X = df.to_numpy(dtype=np.float32)
    for _ in range(warmup):
        session.run(None, {input_name: X})
    timings = []
    for _ in range(n):
        t0 = perf_counter()
        session.run(None, {input_name: X})
        timings.append((perf_counter() - t0) * 1000.0)
    return timings


def metric_entry(timings: list[float]) -> dict:
    return {
        "stats": summarize(timings),
        "raw_ms": [round(t, 4) for t in timings],
    }


# ---------------------------------------------------------------------------
# Sauvegarde
# ---------------------------------------------------------------------------

def save_results(payload: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"onnx_{ts}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test ONNX Runtime vs sklearn (2 phases).")
    parser.add_argument("--n", type=int, default=100, help="Nombre d'appels mesurés (phase 2).")
    parser.add_argument("--warmup", type=int, default=5, help="Appels de chauffe.")
    parser.add_argument("--tol", type=float, default=1e-4, help="Tolérance sur l'écart de score.")
    parser.add_argument("--force", action="store_true", help="Force la reconversion de l'ONNX.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 64)
    print("Benchmark ONNX (phase 1 : faisabilité, phase 2 : benchmark)")
    print("=" * 64)

    base_payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "protocol": {
            "n": args.n,
            "warmup": args.warmup,
            "tolerance": args.tol,
            "sample_profile": "profil_ui_senior_stable",
            "ui_input": UI_INPUT,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }

    print("\n[Phase 1/2] Faisabilité")
    p1 = phase1_feasibility(args.tol, args.force)

    payload = {
        **base_payload,
        "status": p1["status"],
        "equivalence": p1.get("equivalence"),
    }
    if "reason" in p1:
        payload["reason"] = p1["reason"]

    if p1["status"] != "ok":
        path = save_results(payload)
        print(f"\n→ Phase 2 non exécutée (statut : {p1['status']}).")
        print(f"  Résultat sauvegardé : {path.relative_to(PROJECT_ROOT)}")
        return

    session = p1["runtime"]["session"]
    df = p1["runtime"]["df"]

    print(f"\n[Phase 2/2] Benchmark inférence — n={args.n}")
    sk_timings = bench_sklearn(df, args.n, args.warmup)
    onnx_timings = bench_onnx(session, df, args.n, args.warmup)
    sk_stats = summarize(sk_timings)
    onnx_stats = summarize(onnx_timings)

    print(
        f"  sklearn : mean={sk_stats['mean_ms']:>7.3f}  "
        f"median={sk_stats['median_ms']:>7.3f}  p95={sk_stats['p95_ms']:>7.3f} ms"
    )
    print(
        f"  onnx    : mean={onnx_stats['mean_ms']:>7.3f}  "
        f"median={onnx_stats['median_ms']:>7.3f}  p95={onnx_stats['p95_ms']:>7.3f} ms"
    )

    ratio = (
        sk_stats["median_ms"] / onnx_stats["median_ms"]
        if onnx_stats["median_ms"] > 0
        else float("inf")
    )
    print(f"\n  ratio médiane sklearn / ONNX : ×{ratio:.2f}")

    payload["metrics"] = {
        "sklearn": metric_entry(sk_timings),
        "onnx": metric_entry(onnx_timings),
    }
    payload["ratio_median_sklearn_over_onnx"] = round(ratio, 3)

    path = save_results(payload)
    print(f"\n→ Résultats sauvegardés : {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
