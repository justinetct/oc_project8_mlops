"""Validation des entrées utilisateur avant prédiction.

Chaque règle retourne un message d'erreur lisible.
Si validate() retourne une liste vide, les données sont valides.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from src.config import HOME_CREDIT_REFERENCE_DATE

# -- Limites de dates --
MIN_DATE = date(1900, 1, 1)
MIN_AGE_YEARS = 18


def validate(
    date_naissance: str,
    date_embauche: str,
    date_id: str,
    amt_annuity: float,
    amt_goods_price: float,
    amt_credit: float,
    amt_income_total: float,
) -> list[str]:
    """Valide les entrées utilisateur et retourne la liste des erreurs."""
    errors: list[str] = []

    # -- Montants : strictement positifs --
    _check_positive(amt_annuity, "L'échéance annuelle", errors)
    _check_positive(amt_goods_price, "Le prix du bien", errors)
    _check_positive(amt_credit, "Le montant du crédit", errors)
    _check_positive(amt_income_total, "Le revenu total", errors)

    # -- Cohérence montants --
    if (amt_credit or 0) > 0 and (amt_goods_price or 0) > 0 and amt_credit > amt_goods_price:
        errors.append(
            "Le montant du crédit ne peut pas dépasser le prix du bien."
        )

    # -- Date de naissance (validée en premier car les autres en dépendent) --
    birth = _parse_date(date_naissance, "Date de naissance", errors)
    if birth is not None:
        _check_date_bounds(birth, "Date de naissance", errors)
        _check_min_age(birth, errors)

    # -- Date de début d'emploi --
    employed = _parse_date(date_embauche, "Date de début d'emploi", errors)
    if employed is not None:
        _check_date_bounds(employed, "Date de début d'emploi", errors)
        if birth is not None and employed < birth:
            errors.append(
                "Date de début d'emploi : doit être postérieure à la date de naissance."
            )

    # -- Date du document d'identité --
    id_date = _parse_date(date_id, "Date du document d'identité", errors)
    if id_date is not None:
        _check_date_bounds(id_date, "Date du document d'identité", errors)
        if birth is not None and id_date < birth:
            errors.append(
                "Date du document d'identité : doit être postérieure à la date de naissance."
            )

    return errors


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def _check_positive(value: float, label: str, errors: list[str]) -> None:
    """Vérifie qu'un montant est strictement positif."""
    if value is None or value <= 0:
        errors.append(f"{label} doit être supérieur à zéro.")


def _parse_date(
    date_str: str,
    label: str,
    errors: list[str],
) -> date | None:
    """Parse une date AAAA-MM-JJ. Retourne None si invalide (erreur ajoutée)."""
    if not date_str or not date_str.strip():
        errors.append(f"{label} : ce champ est obligatoire.")
        return None

    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        errors.append(f"{label} : format invalide (attendu AAAA-MM-JJ).")
        return None


def _check_date_bounds(d: date, label: str, errors: list[str]) -> None:
    """Vérifie qu'une date est entre 1900-01-01 et la date de référence (exclue)."""
    if d < MIN_DATE:
        errors.append(f"{label} : la date ne peut pas être antérieure au {MIN_DATE}.")
    if d >= HOME_CREDIT_REFERENCE_DATE:
        errors.append(
            f"{label} : la date doit être antérieure au {HOME_CREDIT_REFERENCE_DATE}."
        )


def _check_min_age(birth: date, errors: list[str]) -> None:
    """Vérifie que le demandeur a au moins 18 ans à la date de référence."""
    # On calcule la date 18 ans après la naissance
    try:
        eighteenth = birth.replace(year=birth.year + MIN_AGE_YEARS)
    except ValueError:
        # Né un 29 février → le 1er mars 18 ans plus tard
        eighteenth = birth.replace(year=birth.year + MIN_AGE_YEARS, month=3, day=1)

    if eighteenth > HOME_CREDIT_REFERENCE_DATE:
        errors.append("Le demandeur doit avoir au moins 18 ans.")
