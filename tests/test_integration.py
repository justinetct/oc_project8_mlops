"""Tests d'intégration : gradio_predict() de bout en bout.

Vérifie la chaîne complète : UI → validation → prédiction → HTML de sortie.
"""

import pytest

from app_gradio.app import gradio_predict, EXAMPLES


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
