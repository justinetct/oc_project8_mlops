"""Thème visuel de l'application Gradio — Navy Gold.

Palette bleu nuit + or, logo M3 (cercle ouvert + 3 barres hiérarchisées).
Un seul thème : dark mode uniquement.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

ASSETS_DIR = Path(__file__).parent / "assets"

# -- Logo / Favicon ---------------------------------------------------------
LOGO_PATH = ASSETS_DIR / "logo_m3_gold.svg"
FAVICON_PATH = ASSETS_DIR / "favicon.svg"

# -- Couleurs de résultat ---------------------------------------------------
COLOR_GRANTED = "#5CB85C"
COLOR_REFUSED = "#D9534F"

# -- CSS complémentaire -----------------------------------------------------
CSS = """
.logo-container {
    text-align: center;
    padding: 20px 0 12px 0;
}
.logo-container img {
    height: 64px;
}
/* -- Carte de résultat -- */
.result-card {
    background: #1C2030;
    border-radius: 10px;
    padding: 24px 28px;
    margin-top: 12px;
}
.result-card.granted { border-left: 5px solid #5CB85C; }
.result-card.refused { border-left: 5px solid #D9534F; }

.result-decision {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0 0 18px 0;
}
.result-card.granted .result-decision { color: #5CB85C; }
.result-card.refused .result-decision { color: #D9534F; }

.risk-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #8B92A5;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 0 0 8px 0;
}

/* Jauge de risque */
.risk-gauge { margin: 0 0 14px 0; }
.risk-gauge-track {
    position: relative;
    height: 10px;
    background: #272C3A;
    border-radius: 5px;
}
.risk-gauge-fill {
    height: 100%;
    border-radius: 5px;
    transition: width 0.3s ease;
}
.risk-gauge-fill.granted { background: linear-gradient(90deg, #3a7a3a, #5CB85C); }
.risk-gauge-fill.refused { background: linear-gradient(90deg, #D4A843, #D9534F); }

/* Marqueur de seuil */
.risk-gauge-threshold {
    position: absolute;
    top: -6px;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    align-items: center;
}
.threshold-line {
    width: 2px;
    height: 22px;
    background: #E6E8ED;
    border-radius: 1px;
}
.threshold-label {
    font-size: 0.65rem;
    color: #8B92A5;
    margin-top: 2px;
    white-space: nowrap;
}

.risk-gauge-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #4B5060;
    margin-top: 4px;
}

/* Libellé de niveau */
.risk-level {
    font-size: 0.9rem;
    font-weight: 600;
    margin: 0 0 12px 0;
}
.risk-level.granted { color: #5CB85C; }
.risk-level.refused { color: #D9534F; }

.result-message {
    font-size: 0.9rem;
    color: #8B92A5;
    margin: 0;
    line-height: 1.5;
}
/* Carte d'erreur de validation */
.result-card.error { border-left: 5px solid #D4A843; }
.result-card.error .result-decision {
    color: #D4A843;
    font-size: 1.3rem;
}
.error-list {
    margin: 10px 0 0 0;
    padding-left: 20px;
    color: #E6E8ED;
    line-height: 1.8;
    font-size: 0.9rem;
}
.error-list li { margin-bottom: 2px; }
/* -- Bordures visibles sur les champs de saisie -- */
.gradio-container input[type="text"],
.gradio-container input[type="number"],
.gradio-container textarea {
    border: 1px solid #363B4A !important;
    border-radius: 6px !important;
}
.gradio-container input[type="text"]:focus,
.gradio-container input[type="number"]:focus,
.gradio-container textarea:focus {
    border-color: #D4A843 !important;
}
/* -- Flèches de saisie numérique (spinners) visibles -- */
.gradio-container input[type="number"]::-webkit-inner-spin-button,
.gradio-container input[type="number"]::-webkit-outer-spin-button {
    opacity: 1;
    filter: invert(0.85);
}
/* Bouton désactivé */
.gradio-container button.primary[disabled],
.gradio-container button.primary:disabled {
    opacity: 0.4 !important;
    cursor: not-allowed !important;
}
.gradio-container {
    max-width: 1100px !important;
}
/* Force le tableau d'exemples en dark mode */
.gradio-container table,
.gradio-container table th,
.gradio-container table td {
    background-color: #1C2030 !important;
    color: #E6E8ED !important;
    border-color: #272C3A !important;
}
.gradio-container .gr-samples-table tr:hover td {
    background-color: #272C3A !important;
}
"""

# -- Thème Gradio -----------------------------------------------------------
THEME = gr.themes.Base(
    primary_hue=gr.themes.Color(
        c50="#fdf6e6", c100="#f8e8c0", c200="#f0d696",
        c300="#e6c06b", c400="#D4A843", c500="#c4943a",
        c600="#a87d30", c700="#8c6526", c800="#6f4e1d",
        c900="#523814", c950="#3a240b",
    ),
    neutral_hue=gr.themes.Color(
        c50="#E6E8ED", c100="#C8CCD6", c200="#A5AAB8",
        c300="#8B92A5", c400="#6B7280", c500="#4B5060",
        c600="#363B4A", c700="#272C3A", c800="#1C2030",
        c900="#151924", c950="#111520",
    ),
).set(
    body_background_fill="#111520",
    body_background_fill_dark="#111520",
    block_background_fill="#1C2030",
    block_background_fill_dark="#1C2030",
    body_text_color="#E6E8ED",
    body_text_color_dark="#E6E8ED",
    body_text_color_subdued="#8B92A5",
    body_text_color_subdued_dark="#8B92A5",
    block_label_text_color="#8B92A5",
    block_label_text_color_dark="#8B92A5",
    block_title_text_color="#C8CCD6",
    block_title_text_color_dark="#C8CCD6",
    button_primary_background_fill="#D4A843",
    button_primary_background_fill_dark="#D4A843",
    button_primary_text_color="#111520",
    button_primary_text_color_dark="#111520",
    border_color_primary="#272C3A",
    border_color_primary_dark="#272C3A",
    input_background_fill="#1C2030",
    input_background_fill_dark="#1C2030",
    slider_color="#D4A843",
    slider_color_dark="#D4A843",
)
