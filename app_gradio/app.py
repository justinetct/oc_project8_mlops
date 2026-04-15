"""Application Gradio de scoring crédit.

Interface simple pour saisir un profil client
et obtenir la décision de crédit avec le score de risque.

Les dates saisies par l'utilisateur sont converties en nombre de jours
par rapport à la date de référence du challenge Kaggle Home Credit (2018-05-17).
"""

from __future__ import annotations

import base64

import gradio as gr

from app_gradio.scoring_service import score_client
from app_gradio.themes import CSS, FAVICON_PATH, LOGO_PATH, THEME
from src.config import APP_ENV


def _env_badge_html() -> str:
    """Badge visuel de l'environnement (affiché uniquement en préprod)."""
    if APP_ENV == "preprod":
        return '<span class="env-badge">Préprod</span>'
    return ""


def _logo_html() -> str:
    """Génère le HTML pour afficher le logo SVG inline."""
    svg_bytes = LOGO_PATH.read_bytes()
    b64 = base64.b64encode(svg_bytes).decode()
    return (
        '<div class="logo-container">'
        f'<img src="data:image/svg+xml;base64,{b64}" alt="Prêt à Dépenser">'
        f'{_env_badge_html()}'
        "</div>"
    )


def _app_title() -> str:
    """Titre de la fenêtre, suffixé par l'environnement en préprod."""
    base = "Prêt à Dépenser — Scoring Crédit"
    if APP_ENV == "preprod":
        return f"{base} - preprod"
    return base


def _error_html(errors: list[str]) -> str:
    """Génère le HTML pour afficher les erreurs de validation."""
    items = "".join(f"<li>{e}</li>" for e in errors)
    return (
        '<div class="result-card error">'
        '<p class="result-decision">⚠\ufe0f Saisie invalide</p>'
        f'<ul class="error-list">{items}</ul>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# Pont Gradio -> validate() -> predict()
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
    """Reçoit les champs UI lisibles, appelle le service métier et formate le HTML."""
    result = score_client(
        ext_source_1=ext_source_1,
        ext_source_2=ext_source_2,
        ext_source_3=ext_source_3,
        date_naissance=date_naissance,
        date_embauche=date_embauche,
        date_id=date_id,
        amt_annuity=amt_annuity,
        amt_goods_price=amt_goods_price,
        amt_credit=amt_credit,
        amt_income_total=amt_income_total,
        is_married=is_married,
    )

    if not result.success:
        return _error_html(result.errors)

    return _result_html(result.score, result.label, result.threshold)


def _result_html(score: float, label: str, threshold: float) -> str:
    """Formate le HTML du résultat de scoring avec la jauge de risque."""
    granted = label == "Crédit accordé"

    # Position du score et du seuil sur la jauge (normalisés sur 0–50%)
    score_pct = min(score / 0.5 * 100, 100)
    threshold_pct = threshold / 0.5 * 100

    status = "granted" if granted else "refused"
    emoji = "✅" if granted else "❌"
    level_label = "Sous le seuil accepté" if granted else "Au-dessus du seuil accepté"

    if granted:
        message = "Le profil présente un risque acceptable. La demande est acceptée."
    elif score < 0.3:
        message = "Le risque dépasse le seuil autorisé. La demande est refusée."
    else:
        message = "Le profil présente un risque élevé. La demande est refusée."

    return f"""<div class="result-card {status}">
  <p class="result-decision">{emoji} {label}</p>
  <p class="risk-title">Risque</p>
  <div class="risk-gauge">
    <div class="risk-gauge-track">
      <div class="risk-gauge-fill {status}" style="width:{score_pct:.0f}%"></div>
      <div class="risk-gauge-threshold" style="left:{threshold_pct:.0f}%">
        <div class="threshold-line"></div>
        <span class="threshold-label">seuil</span>
      </div>
    </div>
    <div class="risk-gauge-labels">
      <span>Faible</span>
      <span>Élevé</span>
    </div>
  </div>
  <p class="risk-level {status}">{level_label}</p>
  <p class="result-message">{message}</p>
</div>"""


# ---------------------------------------------------------------------------
# Exemples réalistes pour la démo (convertis depuis les DAYS du dataset)
# ---------------------------------------------------------------------------
EXAMPLES = [
    # Profil 1 : senior stable, faible risque
    [0.62, 0.71, 0.51, "1975-03-15", "2010-01-10", "2015-06-20",
     20_000, 250_000, 230_000, 250_000, "Oui"],
    # Profil 2 : jeune, emploi récent, risque élevé
    [0.10, 0.18, 0.12, "1992-08-20", "2017-11-01", "2016-03-10",
     40_000, 500_000, 480_000, 120_000, "Non"],
    # Profil 3 : profil intermédiaire
    [0.40, 0.42, 0.30, "1985-06-10", "2015-09-01", "2013-01-15",
     30_000, 350_000, 330_000, 180_000, "Oui"],
]


# ---------------------------------------------------------------------------
# JS d'initialisation (dark mode + désactivation bouton si champs vides)
# ---------------------------------------------------------------------------
INIT_JS = """() => {
    document.body.classList.add('dark');
    function checkFields() {
        const btn = document.querySelector('button.primary');
        if (!btn) return;
        const texts = document.querySelectorAll('textarea, input[type="text"]');
        const numbers = document.querySelectorAll('input[type="number"]');
        let empty = false;
        texts.forEach(el => { if (!el.value.trim()) empty = true; });
        numbers.forEach(el => { if (el.value === '') empty = true; });
        btn.disabled = empty;
    }
    const obs = new MutationObserver(checkFields);
    obs.observe(document.body, {childList: true, subtree: true});
    document.body.addEventListener('input', checkFields);
    setTimeout(checkFields, 500);
}"""


# ---------------------------------------------------------------------------
# Construction de l'interface
# ---------------------------------------------------------------------------
def build_app() -> gr.Blocks:
    """Construit l'application Gradio."""
    with gr.Blocks(title=_app_title(),
                    theme=THEME, css=CSS, js=INIT_JS) as app:
        gr.HTML(_logo_html())

        # Valeurs par défaut = premier exemple (profil senior stable)
        ex = EXAMPLES[0]

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Sources externes")
                ext1 = gr.Slider(0, 1, value=ex[0], step=0.01,
                                 label="Score source externe 1")
                ext2 = gr.Slider(0, 1, value=ex[1], step=0.01,
                                 label="Score source externe 2")
                ext3 = gr.Slider(0, 1, value=ex[2], step=0.01,
                                 label="Score source externe 3")

                gr.Markdown("### Informations personnelles")
                date_birth = gr.Textbox(value=ex[3],
                                        label="Date de naissance",
                                        info="Format AAAA-MM-JJ")
                date_employed = gr.Textbox(value=ex[4],
                                           label="Date de début d'emploi",
                                           info="Format AAAA-MM-JJ")
                date_id = gr.Textbox(value=ex[5],
                                     label="Date de mise à jour du document d'identité",
                                     info="Format AAAA-MM-JJ")
                married = gr.Radio(["Oui", "Non"], value=ex[10],
                                   label="Marié(e)")

            with gr.Column():
                gr.Markdown("### Montants financiers")
                annuity = gr.Number(value=ex[6], label="Échéance annuelle")
                goods = gr.Number(value=ex[7], label="Prix du bien")
                credit = gr.Number(value=ex[8], label="Montant du crédit")
                income = gr.Number(value=ex[9], label="Revenu total")

                gr.Markdown("---")
                btn = gr.Button("Prédire", variant="primary")
                output = gr.Markdown(sanitize_html=False)

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
    import os

    from src.database import ensure_tables

    # Création automatique de la table si besoin (idempotent, non-bloquant).
    ensure_tables()

    port = int(os.environ.get("PORT", 7860))
    demo = build_app()
    demo.launch(server_name="0.0.0.0", server_port=port, favicon_path=str(FAVICON_PATH))
