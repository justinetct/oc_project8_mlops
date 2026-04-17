"""Vérification de non-régression fonctionnelle : sklearn vs ONNX.

Score N profils contrastés avec les deux moteurs via score_client(), compare
scores et décisions, affiche un tableau lisible et un verdict simple.

Garde-fou : en mode ONNX, si la session n'est pas effectivement chargée, le
script échoue explicitement (RuntimeError + exit 2) pour éviter qu'un fallback
silencieux vers sklearn ne produise un faux verdict OK.

Usage :
    poetry run python scripts/check_non_regression.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Profils contrastés — variations volontaires autour de cas utilisateur réels
# ---------------------------------------------------------------------------
PROFILES = [
    {
        "nom": "senior stable (exemple UI 1)",
        "ui": {
            "ext_source_1": 0.62, "ext_source_2": 0.71, "ext_source_3": 0.51,
            "date_naissance": "1975-03-15", "date_embauche": "2010-01-10",
            "date_id": "2015-06-20",
            "amt_annuity": 20_000, "amt_goods_price": 250_000,
            "amt_credit": 230_000, "amt_income_total": 250_000,
            "is_married": "Oui",
        },
    },
    {
        "nom": "jeune, emploi récent (exemple UI 2)",
        "ui": {
            "ext_source_1": 0.10, "ext_source_2": 0.18, "ext_source_3": 0.12,
            "date_naissance": "1992-08-20", "date_embauche": "2017-11-01",
            "date_id": "2016-03-10",
            "amt_annuity": 40_000, "amt_goods_price": 500_000,
            "amt_credit": 480_000, "amt_income_total": 120_000,
            "is_married": "Non",
        },
    },
    {
        "nom": "profil intermédiaire (exemple UI 3)",
        "ui": {
            "ext_source_1": 0.40, "ext_source_2": 0.42, "ext_source_3": 0.30,
            "date_naissance": "1985-06-10", "date_embauche": "2015-09-01",
            "date_id": "2013-01-15",
            "amt_annuity": 30_000, "amt_goods_price": 350_000,
            "amt_credit": 330_000, "amt_income_total": 180_000,
            "is_married": "Oui",
        },
    },
    {
        "nom": "très bas risque (scores externes élevés)",
        "ui": {
            "ext_source_1": 0.90, "ext_source_2": 0.88, "ext_source_3": 0.85,
            "date_naissance": "1970-01-01", "date_embauche": "2000-01-01",
            "date_id": "2010-01-01",
            "amt_annuity": 15_000, "amt_goods_price": 200_000,
            "amt_credit": 180_000, "amt_income_total": 400_000,
            "is_married": "Oui",
        },
    },
    {
        "nom": "très haut risque (scores externes faibles)",
        "ui": {
            "ext_source_1": 0.05, "ext_source_2": 0.08, "ext_source_3": 0.03,
            "date_naissance": "1998-01-01", "date_embauche": "2018-01-01",
            "date_id": "2017-01-01",
            "amt_annuity": 50_000, "amt_goods_price": 600_000,
            "amt_credit": 600_000, "amt_income_total": 100_000,
            "is_married": "Non",
        },
    },
    {
        "nom": "petits montants",
        "ui": {
            "ext_source_1": 0.50, "ext_source_2": 0.50, "ext_source_3": 0.50,
            "date_naissance": "1980-05-05", "date_embauche": "2012-06-01",
            "date_id": "2014-01-01",
            "amt_annuity": 5_000, "amt_goods_price": 50_000,
            "amt_credit": 45_000, "amt_income_total": 60_000,
            "is_married": "Oui",
        },
    },
]

TOLERANCE = 5e-3        # tolérance de score (au-delà = régression)
NOTABLE_DIFF = 1e-4     # seuil d'écart numérique à signaler même s'il reste acceptable


def score_with(ui_input: dict, engine: str) -> tuple[float, str]:
    """Score un profil UI via score_client() en forçant sklearn ou ONNX.

    En mode ONNX, vérifie explicitement qu'une session est bien chargée.
    Si la session n'est pas disponible, lève RuntimeError pour éviter
    qu'un fallback silencieux ne produise un faux verdict OK.
    """
    import app_gradio.loader as loader

    loader._onnx_session = None
    loader.USE_ONNX = (engine == "onnx")

    # Hard check : en mode ONNX, la session doit réellement se charger
    if engine == "onnx":
        session = loader.get_onnx_session()
        if session is None:
            raise RuntimeError(
                "ONNX indisponible : session non chargée "
                "(artefact manquant ou erreur au chargement). "
                "Verdict non calculable — le fallback sklearn masquerait la comparaison."
            )

    from app_gradio.scoring_service import score_client

    with patch("app_gradio.scoring_service.log_prediction"), \
         patch("app_gradio.scoring_service.log_prediction_error"):
        result = score_client(**ui_input)

    assert result.success, f"scoring échoué pour le profil : {result.errors}"
    return result.score, result.label


def main() -> None:
    print("=" * 78)
    print("Non-régression fonctionnelle — sklearn vs ONNX sur profils contrastés")
    print("=" * 78)

    all_ok = True
    notable_profiles: list[tuple[str, float]] = []  # (nom, diff) — écarts notables acceptés
    header = f"{'#':>2}  {'profil':<42}  {'sklearn':>9}  {'onnx':>9}  {'écart':>9}  verdict"
    print("\n" + header)
    print("-" * len(header))

    try:
        for i, p in enumerate(PROFILES, 1):
            sk_score, sk_label = score_with(p["ui"], "sklearn")
            onnx_score, onnx_label = score_with(p["ui"], "onnx")
            diff = abs(sk_score - onnx_score)
            same_label = sk_label == onnx_label
            ok = (diff < TOLERANCE) and same_label
            all_ok = all_ok and ok

            if not ok:
                verdict = "✗ divergence"
            elif diff >= NOTABLE_DIFF:
                verdict = "✓ OK (écart notable)"
                notable_profiles.append((p["nom"], diff))
            else:
                verdict = "✓ OK"

            print(
                f"{i:>2}  {p['nom']:<42}  {sk_score:>9.6f}  {onnx_score:>9.6f}  "
                f"{diff:>9.2e}  {verdict}"
            )
            if not same_label:
                print(f"     → labels : sklearn='{sk_label}'  onnx='{onnx_label}'")
    except RuntimeError as exc:
        print(f"\n✗ {exc}")
        sys.exit(2)

    print("-" * len(header))
    print()
    if not all_ok:
        print("✗ Régression détectée — voir tableau ci-dessus")
        sys.exit(1)

    print(f"✓ Aucune régression de décision sur {len(PROFILES)} profils "
          f"(tolérance score {TOLERANCE:.0e}, labels identiques).")

    if notable_profiles:
        max_diff = max(d for _, d in notable_profiles)
        print()
        print("Écarts numériques notables (≥ 1e-4) mais sous la tolérance :")
        for name, diff in notable_profiles:
            print(f"  - {name} : écart {diff:.2e}")
        print()
        print("Interprétation :")
        print(f"  Sur {len(PROFILES)} profils contrastés, les décisions restent identiques.")
        print(f"  {len(notable_profiles)} profil(s) présentent un écart de score allant jusqu'à {max_diff:.2e},")
        print("  compatible avec la différence de précision float32 (ONNX) vs float64 (sklearn).")
        print("  Cet écart ne change aucune décision finale → pas de régression fonctionnelle utilisateur.")


if __name__ == "__main__":
    main()
