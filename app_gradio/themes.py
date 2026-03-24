"""Thème visuel de l'application Gradio — Navy Gold.

Palette bleu nuit + or, logo M3 (cercle ouvert + 3 barres hiérarchisées).
Un seul thème : dark mode uniquement.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

ASSETS_DIR = Path(__file__).parent / "assets"

# -- Logo -------------------------------------------------------------------
LOGO_PATH = ASSETS_DIR / "logo_m3_gold.svg"

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
.result-card.refused  { border-left: 5px solid #D9534F; }

.result-decision {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0 0 16px 0;
    line-height: 1.3;
}
.result-card.granted .result-decision { color: #5CB85C; }
.result-card.refused .result-decision  { color: #D9534F; }

/* Barre de risque */
.risk-bar-container {
    margin: 16px 0;
}
.risk-bar-label {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: #8B92A5;
    margin-bottom: 6px;
}
.risk-bar-track {
    position: relative;
    height: 8px;
    background: #272C3A;
    border-radius: 4px;
    overflow: visible;
}
.risk-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
}
.risk-bar-fill.low    { background: linear-gradient(90deg, #5CB85C, #8BD18B); }
.risk-bar-fill.medium { background: linear-gradient(90deg, #D4A843, #E6C06B); }
.risk-bar-fill.high   { background: linear-gradient(90deg, #D9534F, #E88480); }

.risk-score-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #E6E8ED;
    margin-right: 6px;
}
.risk-score-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 4px;
}
.risk-score-label {
    font-size: 0.85rem;
    color: #8B92A5;
}

.result-message {
    font-size: 0.95rem;
    color: #C8CCD6;
    margin: 14px 0 0 0;
    line-height: 1.5;
}
.result-technical {
    font-size: 0.75rem;
    color: #4B5060;
    margin-top: 14px;
    padding-top: 10px;
    border-top: 1px solid #272C3A;
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
