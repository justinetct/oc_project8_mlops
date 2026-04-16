"""Logique de prédiction pour l'application Gradio.

Reçoit les 11 champs saisis par l'utilisateur,
recalcule les 3 ratios, et retourne le score + la décision.
"""

from __future__ import annotations

import pandas as pd

from app_gradio.loader import FEATURES, THRESHOLD, get_onnx_session, model


# -- Champs saisis par l'utilisateur --
USER_INPUT_FIELDS: list[str] = [
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
    "DAYS_BIRTH",
    "DAYS_EMPLOYED",
    "DAYS_ID_PUBLISH",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "AMT_CREDIT",
    "AMT_INCOME_TOTAL",
    "NAME_FAMILY_STATUS_is_MARRIED",
]


def compute_ratios(data: dict) -> dict:
    """Calcule les 3 ratios dérivés à partir des champs saisis."""
    amt_credit = data["AMT_CREDIT"]
    amt_annuity = data["AMT_ANNUITY"]
    amt_goods = data["AMT_GOODS_PRICE"]
    amt_income = data["AMT_INCOME_TOTAL"]

    data["RATIO_CREDIT_ANNUITY"] = amt_credit / amt_annuity if amt_annuity else 0.0
    data["RATIO_GOODS_CREDIT"] = amt_goods / amt_credit if amt_credit else 0.0
    data["RATIO_ANNUITY_INCOME"] = amt_annuity / amt_income if amt_income else 0.0

    return data


def _score_onnx(df) -> float | None:
    """Tente un scoring via ONNX Runtime. Retourne None si la session n'est pas dispo."""
    import numpy as np

    session = get_onnx_session()
    if session is None:
        return None
    input_name = session.get_inputs()[0].name
    X = df.to_numpy(dtype=np.float32)
    outputs = session.run(None, {input_name: X})
    probas = outputs[1] if len(outputs) > 1 else outputs[0]
    return float(probas[0][1])


def predict(user_input: dict) -> dict:
    """Prédiction à partir des 11 champs utilisateur.

    Utilise ONNX Runtime si USE_ONNX=1 et artefact disponible,
    sinon fallback sklearn (comportement par défaut, inchangé).

    Parameters
    ----------
    user_input : dict
        Dictionnaire contenant les 11 champs saisis.

    Returns
    -------
    dict avec les clés :
        - score : float (probabilité de défaut)
        - label : str ("Crédit accordé" ou "Crédit refusé")
        - threshold : float (seuil utilisé)
        - message : str (résumé lisible)
    """
    data = compute_ratios(dict(user_input))

    df = pd.DataFrame([data])[FEATURES]

    onnx_score = _score_onnx(df)
    if onnx_score is not None:
        proba = onnx_score
    else:
        proba = float(model.predict_proba(df)[0, 1])

    granted = proba < THRESHOLD
    label = "Crédit accordé" if granted else "Crédit refusé"
    message = f"{label} (score={proba:.4f}, seuil={THRESHOLD})"

    return {
        "score": round(proba, 6),
        "label": label,
        "threshold": THRESHOLD,
        "message": message,
    }
