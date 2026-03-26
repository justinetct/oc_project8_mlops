"""Tests unitaires pour la validation des entrées utilisateur."""

import pytest

from app_gradio.validation import validate

# -- Entrées valides de référence --
VALID = dict(
    date_naissance="1985-06-10",
    date_embauche="2015-09-01",
    date_id="2013-01-15",
    amt_annuity=25_000,
    amt_goods_price=300_000,
    amt_credit=270_000,
    amt_income_total=200_000,
)


def _validate_with(**overrides) -> list[str]:
    """Appelle validate() avec les valeurs valides, sauf les overrides."""
    args = {**VALID, **overrides}
    return validate(**args)


# -------------------------------------------------------------------
# Cas valide
# -------------------------------------------------------------------
def test_valid_input_no_errors():
    assert _validate_with() == []


# -------------------------------------------------------------------
# Montants négatifs
# -------------------------------------------------------------------
@pytest.mark.parametrize("field,label", [
    ("amt_annuity", "échéance annuelle"),
    ("amt_goods_price", "prix du bien"),
    ("amt_credit", "montant du crédit"),
    ("amt_income_total", "revenu total"),
])
def test_negative_amount_rejected(field, label):
    errors = _validate_with(**{field: -100})
    assert len(errors) >= 1
    assert any(label.lower() in e.lower() for e in errors)


# -------------------------------------------------------------------
# Montants à zéro
# -------------------------------------------------------------------
@pytest.mark.parametrize("field", [
    "amt_annuity", "amt_goods_price", "amt_credit", "amt_income_total",
])
def test_zero_amount_rejected(field):
    errors = _validate_with(**{field: 0})
    assert len(errors) >= 1
    assert any("supérieur à zéro" in e for e in errors)


# -------------------------------------------------------------------
# Crédit > Prix du bien
# -------------------------------------------------------------------
def test_credit_exceeds_goods_price():
    errors = _validate_with(amt_credit=400_000, amt_goods_price=300_000)
    assert any("dépasser" in e for e in errors)


def test_credit_equal_to_goods_price_is_valid():
    errors = _validate_with(amt_credit=300_000, amt_goods_price=300_000)
    assert errors == []


# -------------------------------------------------------------------
# Dates : format invalide
# -------------------------------------------------------------------
def test_invalid_date_format():
    errors = _validate_with(date_naissance="10-06-1985")
    assert any("format invalide" in e.lower() for e in errors)


def test_impossible_date():
    errors = _validate_with(date_naissance="2015-25-01")
    assert any("format invalide" in e.lower() for e in errors)


def test_empty_date():
    errors = _validate_with(date_naissance="")
    assert any("obligatoire" in e for e in errors)


# -------------------------------------------------------------------
# Dates : future (>= date de référence 2018-05-17)
# -------------------------------------------------------------------
def test_future_date_rejected():
    errors = _validate_with(date_naissance="2025-01-01")
    assert any("antérieure" in e for e in errors)


# -------------------------------------------------------------------
# Dates : antérieure à 1900
# -------------------------------------------------------------------
def test_date_before_1900_rejected():
    errors = _validate_with(date_naissance="1899-12-31")
    assert any("1900" in e for e in errors)


def test_date_exactly_1900_is_valid():
    # 1900-01-01 est accepté (>= MIN_DATE), et >18 ans avant 2018
    errors = _validate_with(date_naissance="1900-01-01")
    # Pas d'erreur liée à la borne basse
    assert not any("1900" in e for e in errors)


# -------------------------------------------------------------------
# Dates : âge minimum 18 ans
# -------------------------------------------------------------------
def test_minor_rejected():
    # Né en 2005 → 13 ans à la date de référence (2018-05-17)
    errors = _validate_with(date_naissance="2005-01-01")
    assert any("18 ans" in e for e in errors)


def test_just_18_is_valid():
    # Né le 2000-05-17 → exactement 18 ans le 2018-05-17
    errors = _validate_with(date_naissance="2000-05-17")
    assert not any("18 ans" in e for e in errors)


def test_almost_18_rejected():
    # Né le 2000-05-18 → 17 ans et 364 jours le 2018-05-17
    errors = _validate_with(date_naissance="2000-05-18")
    assert any("18 ans" in e for e in errors)


# -------------------------------------------------------------------
# Dates : cohérence emploi / identité par rapport à naissance
# -------------------------------------------------------------------
def test_employment_before_birth_rejected():
    errors = _validate_with(
        date_naissance="1990-01-01",
        date_embauche="1985-06-01",
    )
    assert any("postérieure à la date de naissance" in e for e in errors)


def test_id_date_before_birth_rejected():
    errors = _validate_with(
        date_naissance="1990-01-01",
        date_id="1989-12-31",
    )
    assert any("postérieure à la date de naissance" in e for e in errors)


def test_employment_after_birth_is_valid():
    errors = _validate_with(
        date_naissance="1985-06-10",
        date_embauche="2010-01-01",
    )
    assert not any("postérieure" in e for e in errors)


# -------------------------------------------------------------------
# Types incorrects (None passé à la place d'un nombre)
# -------------------------------------------------------------------
@pytest.mark.parametrize("field", [
    "amt_annuity", "amt_goods_price", "amt_credit", "amt_income_total",
])
def test_none_amount_rejected(field):
    errors = _validate_with(**{field: None})
    assert len(errors) >= 1
    assert any("supérieur à zéro" in e for e in errors)


def test_none_date_rejected():
    errors = _validate_with(date_naissance=None)
    assert any("obligatoire" in e for e in errors)


# -------------------------------------------------------------------
# Cumul de plusieurs erreurs
# -------------------------------------------------------------------
def test_multiple_errors_at_once():
    errors = _validate_with(
        amt_annuity=-1,
        amt_credit=0,
        date_naissance="invalid",
    )
    assert len(errors) >= 3
