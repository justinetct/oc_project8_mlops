"""Service métier de scoring crédit.

Ce module centralise la logique métier réutilisable :
validation, conversion UI -> features techniques, prédiction et logging.

Il est appelé par app.py (interface Gradio) et pourra être réutilisé
par un script d'injection de données de démo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter

from app_gradio.predict import compute_ratios, predict
from app_gradio.validation import validate
from src.config import HOME_CREDIT_REFERENCE_DATE
from src.database import log_prediction, log_prediction_error


# ---------------------------------------------------------------------------
# Résultat structuré retourné par le service
# ---------------------------------------------------------------------------

@dataclass
class ScoringResult:
    """Résultat d'un appel au service de scoring.

    - Si success=False : errors contient les erreurs de validation/techniques.
    - Si success=True : score, label, threshold et duration_ms sont remplis.
    """
    success: bool
    errors: list[str] = field(default_factory=list)
    score: float = 0.0
    label: str = ""
    threshold: float = 0.0
    features: dict = field(default_factory=dict)
    duration_ms: float | None = None


# ---------------------------------------------------------------------------
# Conversion dates UI -> DAYS techniques
# ---------------------------------------------------------------------------

def date_str_to_days(date_str: str) -> int:
    """Convertit une date 'YYYY-MM-DD' en nombre de jours relatif à la date de référence.

    Résultat négatif si la date est antérieure à la référence (cas normal).
    """
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (d - HOME_CREDIT_REFERENCE_DATE).days


# ---------------------------------------------------------------------------
# Fonction principale du service
# ---------------------------------------------------------------------------

def score_client(
    ext_source_1: float,
    ext_source_2: float,
    ext_source_3: float,
    date_naissance: str,
    date_embauche: str,
    date_id: str,
    amt_annuity: float,
    amt_goods_price: float,
    amt_credit: float,
    amt_income_total: float,
    is_married: str,
    logged_at=None,
) -> ScoringResult:
    """Valide les entrées, calcule le score et logge la prédiction.

    Parameters
    ----------
    Paramètres UI tels que saisis dans l'interface Gradio.
    logged_at : datetime, optional
        Timestamp explicite pour le log. Si None, utilise l'heure courante.

    Returns
    -------
    ScoringResult
        Résultat structuré avec succès/erreur, score, label, features.
        La latence réelle du flux de scoring est mesurée en millisecondes.
    """
    start_time = perf_counter()

    # -- Validation --
    errors = validate(
        date_naissance=date_naissance,
        date_embauche=date_embauche,
        date_id=date_id,
        amt_annuity=amt_annuity,
        amt_goods_price=amt_goods_price,
        amt_credit=amt_credit,
        amt_income_total=amt_income_total,
    )
    if errors:
        log_prediction_error(
            error_type="validation_error",
            error_message=" | ".join(errors),
            logged_at=logged_at,
        )
        return ScoringResult(success=False, errors=errors)

    try:
        # -- Construction du dictionnaire technique --
        user_input = {
            "EXT_SOURCE_1": ext_source_1,
            "EXT_SOURCE_2": ext_source_2,
            "EXT_SOURCE_3": ext_source_3,
            "DAYS_BIRTH": date_str_to_days(date_naissance),
            "DAYS_EMPLOYED": date_str_to_days(date_embauche),
            "DAYS_ID_PUBLISH": date_str_to_days(date_id),
            "AMT_ANNUITY": amt_annuity,
            "AMT_GOODS_PRICE": amt_goods_price,
            "AMT_CREDIT": amt_credit,
            "AMT_INCOME_TOTAL": amt_income_total,
            "NAME_FAMILY_STATUS_is_MARRIED": 1 if is_married == "Oui" else 0,
        }

        # -- Prédiction --
        result = predict(user_input)

        # -- Calcul des ratios + logging en base --
        features = compute_ratios(dict(user_input))
        duration_ms = round((perf_counter() - start_time) * 1000, 3)
        log_prediction(
            score=result["score"],
            label=result["label"],
            threshold=result["threshold"],
            features=features,
            duration_ms=duration_ms,
            logged_at=logged_at,
        )

        return ScoringResult(
            success=True,
            score=result["score"],
            label=result["label"],
            threshold=result["threshold"],
            features=features,
            duration_ms=duration_ms,
        )
    except Exception as exc:  # noqa: BLE001
        log_prediction_error(
            error_type="technical_error",
            error_message=str(exc),
            logged_at=logged_at,
        )
        return ScoringResult(
            success=False,
            errors=["Une erreur technique est survenue pendant le scoring."],
        )
