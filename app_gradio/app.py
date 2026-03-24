"""Application Gradio de scoring crédit.

Interface simple pour saisir un profil client
et obtenir la décision de crédit avec le score de risque.

Les dates saisies par l'utilisateur sont converties en nombre de jours
par rapport à la date de référence du challenge Kaggle Home Credit (2018-05-17).
"""

from __future__ import annotations

from datetime import datetime

import gradio as gr

from app_gradio.predict import predict
from src.config import HOME_CREDIT_REFERENCE_DATE


# ---------------------------------------------------------------------------
# Conversion dates -> jours (logique interne, invisible pour l'utilisateur)
# ---------------------------------------------------------------------------
def _date_str_to_days(date_str: str) -> int:
    """Convertit une date 'YYYY-MM-DD' en nombre de jours relatif à la date de référence.

    Résultat négatif si la date est antérieure à la référence (cas normal).
    """
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (d - HOME_CREDIT_REFERENCE_DATE).days


# ---------------------------------------------------------------------------
# Pont Gradio -> predict()
# ---------------------------------------------------------------------------
def gradio_predict(
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
) -> str:
    """Reçoit les champs UI lisibles et appelle predict() avec les features techniques."""
    user_input = {
        "EXT_SOURCE_1": ext_source_1,
        "EXT_SOURCE_2": ext_source_2,
        "EXT_SOURCE_3": ext_source_3,
        "DAYS_BIRTH": _date_str_to_days(date_naissance),
        "DAYS_EMPLOYED": _date_str_to_days(date_embauche),
        "DAYS_ID_PUBLISH": _date_str_to_days(date_id),
        "AMT_ANNUITY": amt_annuity,
        "AMT_GOODS_PRICE": amt_goods_price,
        "AMT_CREDIT": amt_credit,
        "AMT_INCOME_TOTAL": amt_income_total,
        "NAME_FAMILY_STATUS_is_MARRIED": 1 if is_married == "Oui" else 0,
    }

    result = predict(user_input)

    score = result["score"]
    label = result["label"]
    threshold = result["threshold"]

    return (
        f"## {label}\n\n"
        f"- **Score de risque** : {score:.4f}\n"
        f"- **Seuil de décision** : {threshold}\n\n"
        f"*Un score inférieur au seuil signifie que le crédit est accordé.*"
    )


# ---------------------------------------------------------------------------
# Exemples réalistes pour la démo (convertis depuis les DAYS du dataset)
# ---------------------------------------------------------------------------
EXAMPLES = [
    # Profil 1 : senior stable, faible risque
    [0.62, 0.71, 0.51, "1975-03-15", "2010-01-10", "2015-06-20",
     20_000, 250_000, 270_000, 250_000, "Oui"],
    # Profil 2 : jeune, emploi récent, risque élevé
    [0.10, 0.18, 0.12, "1992-08-20", "2017-11-01", "2016-03-10",
     40_000, 500_000, 550_000, 120_000, "Non"],
    # Profil 3 : profil intermédiaire
    [0.40, 0.42, 0.30, "1985-06-10", "2015-09-01", "2013-01-15",
     30_000, 350_000, 400_000, 180_000, "Oui"],
]


# ---------------------------------------------------------------------------
# Construction de l'interface
# ---------------------------------------------------------------------------
def build_app() -> gr.Blocks:
    with gr.Blocks(title="Scoring Crédit - Projet 8") as app:
        gr.Markdown("# Scoring Crédit\nSaisissez le profil client pour obtenir la décision.")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Sources externes")
                ext1 = gr.Slider(0, 1, value=0.5, step=0.01,
                                 label="Score source externe 1")
                ext2 = gr.Slider(0, 1, value=0.5, step=0.01,
                                 label="Score source externe 2")
                ext3 = gr.Slider(0, 1, value=0.5, step=0.01,
                                 label="Score source externe 3")

                gr.Markdown("### Informations personnelles")
                date_birth = gr.Textbox(value="1985-06-10",
                                        label="Date de naissance",
                                        info="Format AAAA-MM-JJ")
                date_employed = gr.Textbox(value="2015-09-01",
                                           label="Date de début d'emploi",
                                           info="Format AAAA-MM-JJ")
                date_id = gr.Textbox(value="2013-01-15",
                                     label="Date de mise à jour du document d'identité",
                                     info="Format AAAA-MM-JJ")
                married = gr.Radio(["Oui", "Non"], value="Oui",
                                   label="Marié(e)")

            with gr.Column():
                gr.Markdown("### Montants financiers")
                annuity = gr.Number(value=25_000, label="Annuité")
                goods = gr.Number(value=300_000, label="Prix du bien")
                credit = gr.Number(value=350_000, label="Montant du crédit")
                income = gr.Number(value=200_000, label="Revenu total")

                gr.Markdown("---")
                btn = gr.Button("Prédire", variant="primary")
                output = gr.Markdown(label="Résultat")

        all_inputs = [
            ext1, ext2, ext3,
            date_birth, date_employed, date_id,
            annuity, goods, credit, income,
            married,
        ]

        btn.click(fn=gradio_predict, inputs=all_inputs, outputs=output)

        gr.Examples(
            examples=EXAMPLES,
            inputs=all_inputs,
            label="Exemples de profils clients",
        )

    return app


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo = build_app()
    demo.launch()
