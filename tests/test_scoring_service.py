"""Tests ciblés pour le service de scoring."""

import app_gradio.scoring_service as scoring_service


VALID_UI_INPUT = {
    "ext_source_1": 0.5,
    "ext_source_2": 0.6,
    "ext_source_3": 0.4,
    "date_naissance": "1985-06-10",
    "date_embauche": "2015-01-01",
    "date_id": "2018-01-01",
    "amt_annuity": 25000.0,
    "amt_goods_price": 300000.0,
    "amt_credit": 250000.0,
    "amt_income_total": 200000.0,
    "is_married": "Oui",
}


def test_score_client_logs_validation_error(monkeypatch):
    logged_errors = []

    monkeypatch.setattr(scoring_service, "validate", lambda **kwargs: ["Erreur de validation"])
    monkeypatch.setattr(
        scoring_service,
        "log_prediction_error",
        lambda **kwargs: logged_errors.append(kwargs),
    )
    monkeypatch.setattr(
        scoring_service,
        "log_prediction",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("log_prediction ne doit pas être appelé")),
    )

    result = scoring_service.score_client(**VALID_UI_INPUT)

    assert result.success is False
    assert result.errors == ["Erreur de validation"]
    assert len(logged_errors) == 1
    assert logged_errors[0]["error_type"] == "validation_error"


def test_score_client_logs_duration_on_success(monkeypatch):
    logged_predictions = []
    logged_errors = []

    monkeypatch.setattr(scoring_service, "validate", lambda **kwargs: [])
    monkeypatch.setattr(
        scoring_service,
        "predict",
        lambda user_input: {
            "score": 0.08,
            "label": "Crédit accordé",
            "threshold": 0.1,
            "message": "ok",
        },
    )
    monkeypatch.setattr(
        scoring_service,
        "log_prediction",
        lambda **kwargs: logged_predictions.append(kwargs),
    )
    monkeypatch.setattr(
        scoring_service,
        "log_prediction_error",
        lambda **kwargs: logged_errors.append(kwargs),
    )

    result = scoring_service.score_client(**VALID_UI_INPUT)

    assert result.success is True
    assert result.duration_ms is not None
    assert result.duration_ms >= 0
    assert len(logged_predictions) == 1
    assert logged_predictions[0]["duration_ms"] is not None
    assert logged_predictions[0]["duration_ms"] >= 0
    assert logged_errors == []


def test_score_client_logs_technical_error(monkeypatch):
    logged_errors = []

    monkeypatch.setattr(scoring_service, "validate", lambda **kwargs: [])
    monkeypatch.setattr(
        scoring_service,
        "predict",
        lambda user_input: (_ for _ in ()).throw(RuntimeError("boom technique")),
    )
    monkeypatch.setattr(
        scoring_service,
        "log_prediction_error",
        lambda **kwargs: logged_errors.append(kwargs),
    )
    monkeypatch.setattr(
        scoring_service,
        "log_prediction",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("log_prediction ne doit pas être appelé")),
    )

    result = scoring_service.score_client(**VALID_UI_INPUT)

    assert result.success is False
    assert len(logged_errors) == 1
    assert logged_errors[0]["error_type"] == "technical_error"
    assert "boom technique" in logged_errors[0]["error_message"]
    assert "erreur technique" in result.errors[0].lower()
