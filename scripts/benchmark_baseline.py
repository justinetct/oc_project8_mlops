"""Mesure de référence (baseline) des temps d'inférence et de réponse API.

Trois portées mesurées, toutes à partir du même profil UI fixe :

  1. inference : model.predict_proba(df) seul.
                 Le DataFrame est construit une fois en amont en réutilisant
                 les briques du pipeline (date_str_to_days, compute_ratios,
                 FEATURES). Aucune valeur technique codée en dur.

  2. service   : score_client() complet — la fonction branchée au bouton
                 Gradio. Validation + conversion dates + compute_ratios +
                 predict_proba + construction du ScoringResult. Le logging
                 PostgreSQL est stubbé via unittest.mock.patch pour isoler
                 la logique applicative des I/O DB.

  3. http      : aller-retour HTTP via gradio_client vers un serveur Gradio
                 actif. Inclut sérialisation JSON, réseau aller/retour, queue
                 Gradio, exécution serveur (= service + logging PostgreSQL
                 réel). Pas de rendu HTML navigateur. Le nom d'endpoint est
                 auto-détecté via client.view_api() si un seul endpoint
                 nommé existe ; sinon une erreur liste les endpoints et
                 demande d'utiliser --api-name.

Usage :
    # Baseline in-process (inférence + service)
    poetry run python scripts/benchmark_baseline.py

    # Baseline complète avec HTTP local
    poetry run python scripts/benchmark_baseline.py --http

    # HTTP contre la préprod Render
    poetry run python scripts/benchmark_baseline.py --http \\
        --url https://oc-p8-gradio-preprod.onrender.com --tag baseline_preprod
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "perf" / "results"

# ----------------------------------------------------------------------------
# Unique source de vérité : un profil UI (strings, montants bruts).
# Toutes les features techniques sont dérivées via les helpers du projet.
# ----------------------------------------------------------------------------
UI_INPUT: dict = {
    "ext_source_1": 0.62,
    "ext_source_2": 0.71,
    "ext_source_3": 0.51,
    "date_naissance": "1975-03-15",
    "date_embauche": "2010-01-10",
    "date_id": "2015-06-20",
    "amt_annuity": 20_000,
    "amt_goods_price": 250_000,
    "amt_credit": 230_000,
    "amt_income_total": 250_000,
    "is_married": "Oui",
}


# ----------------------------------------------------------------------------
# Construction du DataFrame de référence via les vraies briques du pipeline.
# (Ne dépend pas de score_client ni de la DB.)
# ----------------------------------------------------------------------------
def build_sample_dataframe(ui_input: dict):
    """Construit le DataFrame technique à partir du profil UI.

    Utilise les helpers publics du projet :
      - date_str_to_days (scoring_service) pour la conversion dates
      - compute_ratios   (predict)         pour les 3 ratios dérivés
      - FEATURES         (loader)          pour la sélection des colonnes
    Le seul code spécifique au benchmark est le mapping UI → clés techniques.
    """
    import pandas as pd

    from app_gradio.loader import FEATURES
    from app_gradio.predict import compute_ratios
    from app_gradio.scoring_service import date_str_to_days

    tech_input = {
        "EXT_SOURCE_1": ui_input["ext_source_1"],
        "EXT_SOURCE_2": ui_input["ext_source_2"],
        "EXT_SOURCE_3": ui_input["ext_source_3"],
        "DAYS_BIRTH": date_str_to_days(ui_input["date_naissance"]),
        "DAYS_EMPLOYED": date_str_to_days(ui_input["date_embauche"]),
        "DAYS_ID_PUBLISH": date_str_to_days(ui_input["date_id"]),
        "AMT_ANNUITY": ui_input["amt_annuity"],
        "AMT_GOODS_PRICE": ui_input["amt_goods_price"],
        "AMT_CREDIT": ui_input["amt_credit"],
        "AMT_INCOME_TOTAL": ui_input["amt_income_total"],
        "NAME_FAMILY_STATUS_is_MARRIED": 1 if ui_input["is_married"] == "Oui" else 0,
    }
    features = compute_ratios(tech_input)
    return pd.DataFrame([features])[FEATURES]


# ----------------------------------------------------------------------------
# Benchmarks par portée
# ----------------------------------------------------------------------------
def run_inference_benchmark(ui_input: dict, n: int, warmup: int) -> list[float]:
    """Mesure model.predict_proba seul (DataFrame construit une fois hors mesure)."""
    from app_gradio.loader import model

    df = build_sample_dataframe(ui_input)

    for _ in range(warmup):
        model.predict_proba(df)

    timings = []
    for _ in range(n):
        t0 = perf_counter()
        model.predict_proba(df)
        timings.append((perf_counter() - t0) * 1000.0)
    return timings


def run_service_benchmark(ui_input: dict, n: int, warmup: int) -> list[float]:
    """Mesure score_client() complet avec logging DB stubbé."""
    from app_gradio.scoring_service import score_client

    with patch("app_gradio.scoring_service.log_prediction"), \
         patch("app_gradio.scoring_service.log_prediction_error"):
        for _ in range(warmup):
            score_client(**ui_input)

        timings = []
        for _ in range(n):
            t0 = perf_counter()
            score_client(**ui_input)
            timings.append((perf_counter() - t0) * 1000.0)
    return timings


def _detect_api_name(client) -> str:
    """Auto-détecte l'unique endpoint nommé exposé par le serveur Gradio.

    Règles :
    - 0 endpoint nommé   → erreur (demande d'utiliser --api-name).
    - 1 endpoint nommé   → retourne son nom.
    - 2+ endpoints nommés → erreur, liste les endpoints, demande --api-name
      pour ne pas choisir arbitrairement.
    """
    try:
        info = client.view_api(return_format="dict", print_info=False)
    except TypeError:
        # Ancienne signature de view_api
        info = client.view_api(print_info=False)
    named = (info or {}).get("named_endpoints") or {}

    if not named:
        raise RuntimeError(
            "Aucun endpoint API nommé détecté sur le serveur Gradio. "
            "Relancez avec --api-name <nom> pour cibler un endpoint précis."
        )
    if len(named) > 1:
        listing = "\n  - ".join(sorted(named.keys()))
        raise RuntimeError(
            "Plusieurs endpoints API nommés détectés :\n"
            f"  - {listing}\n"
            "Relancez avec --api-name <nom> pour choisir explicitement."
        )
    return next(iter(named.keys()))


def run_http_benchmark(
    ui_input: dict,
    url: str,
    n: int,
    warmup: int,
    api_name: str | None = None,
) -> tuple[list[float], str]:
    """Mesure un aller-retour HTTP complet via gradio_client.

    Retourne (timings, api_name_utilisé).
    """
    try:
        from gradio_client import Client
    except ImportError as exc:
        raise RuntimeError(
            "gradio_client est requis pour --http "
            "(normalement installé avec gradio via `poetry install --with gradio`)."
        ) from exc

    client = Client(url, verbose=False)
    if api_name is None:
        api_name = _detect_api_name(client)
        print(f"    → endpoint détecté : {api_name}")

    args = (
        ui_input["ext_source_1"],
        ui_input["ext_source_2"],
        ui_input["ext_source_3"],
        ui_input["date_naissance"],
        ui_input["date_embauche"],
        ui_input["date_id"],
        ui_input["amt_annuity"],
        ui_input["amt_goods_price"],
        ui_input["amt_credit"],
        ui_input["amt_income_total"],
        ui_input["is_married"],
    )

    for _ in range(warmup):
        client.predict(*args, api_name=api_name)

    timings = []
    for _ in range(n):
        t0 = perf_counter()
        client.predict(*args, api_name=api_name)
        timings.append((perf_counter() - t0) * 1000.0)
    return timings, api_name


# ----------------------------------------------------------------------------
# Stats et sauvegarde
# ----------------------------------------------------------------------------
def summarize(timings: list[float]) -> dict:
    """Stats en ms, arrondies à 3 décimales.

    p95 défini comme la valeur à l'indice int(round(0.95*n))-1 des timings triés.
    """
    if not timings:
        raise ValueError("Liste de timings vide.")
    sorted_ts = sorted(timings)
    p95_idx = max(0, int(round(0.95 * len(sorted_ts))) - 1)
    return {
        "n": len(timings),
        "mean_ms": round(statistics.mean(timings), 3),
        "median_ms": round(statistics.median(timings), 3),
        "max_ms": round(max(timings), 3),
        "p95_ms": round(sorted_ts[p95_idx], 3),
    }


def print_summary(label: str, stats: dict) -> None:
    print(
        f"  {label:<10} n={stats['n']:<4} "
        f"mean={stats['mean_ms']:>9.3f} ms  "
        f"median={stats['median_ms']:>9.3f} ms  "
        f"max={stats['max_ms']:>9.3f} ms  "
        f"p95={stats['p95_ms']:>9.3f} ms"
    )


def build_metric_entry(timings: list[float]) -> dict:
    """Entrée JSON : stats de synthèse + timings bruts (4 décimales)."""
    return {
        "stats": summarize(timings),
        "raw_ms": [round(t, 4) for t in timings],
    }


def save_results(results: dict, results_dir: Path = RESULTS_DIR) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = results_dir / f"baseline_{ts}.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baseline de performance (inférence + API).")
    parser.add_argument("--n", type=int, default=100, help="Nombre d'appels mesurés (défaut : 100).")
    parser.add_argument("--warmup", type=int, default=5, help="Appels de chauffe (défaut : 5).")
    parser.add_argument("--http", action="store_true", help="Active la mesure HTTP.")
    parser.add_argument(
        "--url",
        default="http://localhost:7860",
        help="URL du serveur Gradio pour la mesure HTTP (défaut : localhost).",
    )
    parser.add_argument(
        "--api-name",
        default=None,
        help="Nom d'API Gradio à cibler (défaut : auto-détection si un seul endpoint nommé).",
    )
    parser.add_argument("--tag", default="baseline", help="Étiquette libre du run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 64)
    print(f"Benchmark baseline — n={args.n}, warmup={args.warmup}, tag={args.tag}")
    print("=" * 64)

    metrics: dict[str, dict] = {}
    used_api_name: str | None = None

    print("\n[1/3] Inférence pure (model.predict_proba)")
    metrics["inference"] = build_metric_entry(
        run_inference_benchmark(UI_INPUT, args.n, args.warmup)
    )
    print_summary("inference", metrics["inference"]["stats"])

    print("\n[2/3] Service applicatif (score_client, DB stubbée)")
    metrics["service"] = build_metric_entry(
        run_service_benchmark(UI_INPUT, args.n, args.warmup)
    )
    print_summary("service", metrics["service"]["stats"])

    if args.http:
        print(f"\n[3/3] HTTP API via gradio_client — {args.url}")
        http_timings, used_api_name = run_http_benchmark(
            UI_INPUT, args.url, args.n, args.warmup, args.api_name
        )
        metrics["http"] = build_metric_entry(http_timings)
        print_summary("http", metrics["http"]["stats"])
    else:
        print("\n[3/3] HTTP : sauté (--http non passé)")

    results = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "tag": args.tag,
        "protocol": {
            "n": args.n,
            "warmup": args.warmup,
            "http_url": args.url if args.http else None,
            "api_name": used_api_name,
            "sample_profile": "profil_ui_senior_stable",
            "ui_input": UI_INPUT,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "metrics": metrics,
    }

    path = save_results(results)
    print(f"\n→ Résultats sauvegardés : {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
