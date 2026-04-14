"""Tests d'intégration : gradio_predict() de bout en bout.

Vérifie la chaîne complète : UI → validation → prédiction → HTML de sortie.
Teste aussi les helpers internes et la construction de l'app.
"""

import pytest

from app_gradio.app import (
    gradio_predict,
    build_app,
    EXAMPLES,
    _error_html,
    _logo_html,
)
from app_gradio.scoring_service import date_str_to_days


# -- Données de test réutilisées depuis les exemples de l'app --
EXAMPLE_GRANTED = EXAMPLES[0]   # profil senior stable → crédit accordé
EXAMPLE_REFUSED = EXAMPLES[1]   # profil jeune risqué → crédit refusé


# -------------------------------------------------------------------
# Cas valide : crédit accordé
# -------------------------------------------------------------------
def test_gradio_predict_granted():
    result = gradio_predict(*EXAMPLE_GRANTED)
    assert "Crédit accordé" in result
    assert "result-card" in result


# -------------------------------------------------------------------
# Cas valide : crédit refusé
# -------------------------------------------------------------------
def test_gradio_predict_refused():
    result = gradio_predict(*EXAMPLE_REFUSED)
    assert "Crédit refusé" in result
    assert "result-card" in result


# -------------------------------------------------------------------
# Validation bloquante : montant négatif → erreur, pas de prédiction
# -------------------------------------------------------------------
def test_gradio_predict_invalid_returns_error():
    # On prend l'exemple valide mais on force un montant négatif
    args = list(EXAMPLE_GRANTED)
    args[7] = -1  # amt_goods_price = -1
    result = gradio_predict(*args)
    assert "Saisie invalide" in result
    assert "supérieur à zéro" in result
    # Pas de résultat de prédiction
    assert "Crédit accordé" not in result
    assert "Crédit refusé" not in result


# -------------------------------------------------------------------
# Validation bloquante : date invalide → erreur
# -------------------------------------------------------------------
def test_gradio_predict_bad_date_returns_error():
    args = list(EXAMPLE_GRANTED)
    args[3] = "pas-une-date"  # date_naissance invalide
    result = gradio_predict(*args)
    assert "Saisie invalide" in result
    assert "format invalide" in result


# -------------------------------------------------------------------
# Tous les exemples pré-enregistrés sont valides
# -------------------------------------------------------------------
@pytest.mark.parametrize("example", EXAMPLES, ids=["profil_1", "profil_2", "profil_3"])
def test_all_examples_produce_valid_result(example):
    result = gradio_predict(*example)
    assert "result-card" in result
    assert "Saisie invalide" not in result
    assert ("Crédit accordé" in result) or ("Crédit refusé" in result)


# ===================================================================
# Helpers internes de app.py
# ===================================================================

# -------------------------------------------------------------------
# _date_str_to_days : conversion date → jours
# -------------------------------------------------------------------
def test_date_str_to_days_past():
    """Une date antérieure à la référence donne un nombre négatif."""
    days = date_str_to_days("2018-05-16")  # veille de la référence
    assert days == -1


def test_date_str_to_days_reference():
    """La date de référence elle-même donne 0."""
    days = date_str_to_days("2018-05-17")
    assert days == 0


def test_date_str_to_days_known_value():
    """Vérifie un calcul connu : 1975-03-15 → -15769 jours."""
    days = date_str_to_days("1975-03-15")
    assert days == -15769


# -------------------------------------------------------------------
# _logo_html : génération du logo inline
# -------------------------------------------------------------------
def test_logo_html_contains_img_tag():
    html = _logo_html()
    assert "<img" in html
    assert "logo-container" in html
    assert "base64" in html


# -------------------------------------------------------------------
# _error_html : génération du bloc d'erreur
# -------------------------------------------------------------------
def test_error_html_single_error():
    html = _error_html(["Le revenu total doit être positif."])
    assert "Saisie invalide" in html
    assert "Le revenu total doit être positif." in html
    assert "<li>" in html


def test_error_html_multiple_errors():
    errors = ["Erreur 1.", "Erreur 2.", "Erreur 3."]
    html = _error_html(errors)
    assert html.count("<li>") == 3


# -------------------------------------------------------------------
# EXAMPLES : structure et cohérence
# -------------------------------------------------------------------
def test_examples_count():
    assert len(EXAMPLES) >= 2


def test_examples_have_11_fields():
    for i, ex in enumerate(EXAMPLES):
        assert len(ex) == 11, f"L'exemple {i} a {len(ex)} champs au lieu de 11"


def test_examples_married_field_is_valid():
    for ex in EXAMPLES:
        assert ex[10] in ("Oui", "Non")


# -------------------------------------------------------------------
# build_app : construction de l'interface Gradio
# -------------------------------------------------------------------
def test_build_app_returns_blocks():
    """build_app() retourne un objet gr.Blocks sans erreur."""
    import gradio as gr
    app = build_app()
    assert isinstance(app, gr.Blocks)
