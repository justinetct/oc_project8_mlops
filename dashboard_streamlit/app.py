"""Dashboard Streamlit de monitoring — Prêt à Dépenser.

Affiche les métriques issues des tables de monitoring PostgreSQL :
- KPIs globaux (volume, taux d'acceptation, scores, latence, erreurs)
- Évolution temporelle (volume et score moyen par jour)
- Distribution des scores par décision
- Tableaux des dernières prédictions et erreurs
"""

import base64
import sys
from pathlib import Path

# Streamlit ajoute le dossier du script au sys.path, pas la racine du projet.
# On ajoute la racine pour permettre `from src.database import ...`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from dashboard_streamlit.logic import compute_kpis, prepare_daily_data
from src.config import APP_ENV
from src.database import (
    count_prediction_errors,
    count_prediction_logs,
    ensure_tables,
    read_prediction_errors,
    read_prediction_logs,
)

# Création automatique de la table si besoin (idempotent, non-bloquant).
ensure_tables()

# ---------------------------------------------------------------------------
# Chemins assets
# ---------------------------------------------------------------------------
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo_m3_gold.svg"

# ---------------------------------------------------------------------------
# Palette (identique à l'app Gradio)
# ---------------------------------------------------------------------------
BG_BODY = "#111520"
BG_BLOCK = "#1C2030"
BG_BORDER = "#272C3A"
GOLD = "#D4A843"
GOLD_LIGHT = "#f0d696"
TEXT_PRIMARY = "#E6E8ED"
TEXT_SUBDUED = "#8B92A5"
GREEN = "#5CB85C"
RED = "#D9534F"

# ---------------------------------------------------------------------------
# CSS custom — thème dark navy + or
# ---------------------------------------------------------------------------
CUSTOM_CSS = f"""
<style>
    /* --- Import Inter font --- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    /* --- Global --- */
    .stApp {{
        background-color: {BG_BODY};
        color: {TEXT_PRIMARY};
        font-family: 'Inter', system-ui, sans-serif;
    }}

    /* --- Masquer le header Streamlit natif --- */
    header[data-testid="stHeader"] {{
        display: none !important;
    }}

    /* --- Barre fixe custom --- */
    .top-bar {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 56px;
        background-color: {BG_BLOCK};
        border-bottom: 1px solid {BG_BORDER};
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 24px;
        z-index: 999999;
    }}
    .top-bar img.bar-logo {{
        height: 44px;
    }}
    .top-bar .refresh-icon {{
        height: 28px;
        cursor: pointer;
        opacity: 0.8;
        transition: opacity 0.2s;
    }}
    .top-bar .refresh-icon:hover {{
        opacity: 1;
    }}
    .top-bar .right-group {{
        display: flex;
        align-items: center;
        gap: 14px;
    }}
    .top-bar .env-badge {{
        padding: 4px 10px;
        background: rgba(59, 130, 246, 0.12);
        color: #60A5FA;
        border: 1px solid #3B82F6;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
    }}

    /* --- Compenser la barre fixe --- */
    [data-testid="stMainBlockContainer"] {{
        padding-top: 64px !important;
    }}
    /* Masquer les éléments vides résiduels sous la barre */
    [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]:empty,
    [data-testid="stMainBlockContainer"] .stButton {{
        display: none !important;
    }}

    /* --- Section headers — taille réduite + espacement --- */
    .stApp h2 {{
        color: {GOLD} !important;
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        border-bottom: 1px solid {BG_BORDER};
        padding-bottom: 6px;
        margin-top: 2rem !important;
        margin-bottom: 1rem !important;
    }}
    .stApp h3 {{
        color: {TEXT_SUBDUED} !important;
        font-size: 0.9rem !important;
        font-weight: 400;
        margin-bottom: 0.4rem !important;
    }}

    /* --- KPI metrics --- */
    [data-testid="stMetric"] {{
        background-color: {BG_BLOCK};
        border: 1px solid {BG_BORDER};
        border-radius: 10px;
        padding: 16px 20px;
    }}
    [data-testid="stMetricLabel"] {{
        color: {TEXT_SUBDUED} !important;
    }}
    [data-testid="stMetricValue"] {{
        color: {GOLD} !important;
        font-weight: 700;
    }}

    /* --- Dataframe --- */
    [data-testid="stDataFrame"] {{
        border: 1px solid {BG_BORDER};
        border-radius: 10px;
    }}

    /* --- Warning box --- */
    .stAlert {{
        background-color: {BG_BLOCK} !important;
        color: {GOLD} !important;
        border: 1px solid {BG_BORDER};
        border-left: 4px solid {GOLD};
        border-radius: 8px;
    }}

    /* --- Altair charts — conteneur propre, centré --- */
    .vega-embed {{
        background-color: {BG_BLOCK} !important;
        border: 1px solid {BG_BORDER};
        border-radius: 10px;
        padding: 12px;
        overflow: hidden;
    }}
    .vega-embed canvas,
    .vega-embed svg {{
        border-radius: 8px;
        display: block;
        margin: 0 auto;
    }}
</style>
"""

# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------
_PAGE_TITLE = "Prêt à Dépenser — Monitoring"
if APP_ENV == "preprod":
    _PAGE_TITLE = f"{_PAGE_TITLE} - preprod"

st.set_page_config(
    page_title=_PAGE_TITLE,
    page_icon="📊",
    layout="wide",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Barre fixe : logo + icône refresh
# ---------------------------------------------------------------------------
REFRESH_ICON_PATH = ASSETS_DIR / "icon_refresh.svg"

logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode() if LOGO_PATH.exists() else ""
refresh_b64 = base64.b64encode(REFRESH_ICON_PATH.read_bytes()).decode() if REFRESH_ICON_PATH.exists() else ""

env_badge_html = '<span class="env-badge">Préprod</span>' if APP_ENV == "preprod" else ""

st.markdown(
    f'<div class="top-bar">'
    f'<img class="bar-logo" src="data:image/svg+xml;base64,{logo_b64}" alt="Prêt à Dépenser">'
    f'<div class="right-group">'
    f'{env_badge_html}'
    f'<a href="/" target="_self" title="Rafraîchir les données">'
    f'<img class="refresh-icon" src="data:image/svg+xml;base64,{refresh_b64}" alt="Rafraîchir">'
    f'</a>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

df = read_prediction_logs(limit=1000)
errors_df = read_prediction_errors(limit=1000)

if df.empty and errors_df.empty:
    st.warning(
        "Aucune donnée de monitoring disponible. "
        "Effectuez des prédictions via l'application Gradio pour alimenter ce dashboard."
    )
    st.stop()


def _format_ms(value):
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.1f} ms"


def _format_score(value):
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.4f}"

# ---------------------------------------------------------------------------
# Bloc A — KPIs globaux
# ---------------------------------------------------------------------------
st.header("Indicateurs clés")

total_predictions = count_prediction_logs()
total_errors = count_prediction_errors()
kpis = compute_kpis(df, total_predictions, total_errors)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Prédictions totales", f"{total_predictions}")
col2.metric("Taux d'acceptation", f"{kpis['acceptance_rate']:.1f} %")
col3.metric("Score moyen", _format_score(kpis["mean_score"]))
col4.metric("Score médian", _format_score(kpis["median_score"]))

col5, col6, col7, col8 = st.columns(4)
col5.metric("Latence moyenne", _format_ms(kpis["latency_mean"]))
col6.metric("Latence médiane", _format_ms(kpis["latency_median"]))
col7.metric("Latence max", _format_ms(kpis["latency_max"]))
col8.metric("Taux d'erreur", f"{kpis['error_rate']:.1f} %")

st.caption(
    f"Erreurs totales : {total_errors} | "
    f"Taux d'erreur = erreurs / (prédictions + erreurs)"
)

# ---------------------------------------------------------------------------
# Préparation des données temporelles
# ---------------------------------------------------------------------------
daily = prepare_daily_data(df)

# ---------------------------------------------------------------------------
# Bloc B — Évolution temporelle
# ---------------------------------------------------------------------------
st.header("Évolution temporelle")

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Volume par jour")
    if df.empty:
        st.info("Aucune prédiction valide disponible pour l'évolution temporelle.")
    else:
        chart_volume = (
            alt.Chart(daily)
            .mark_bar(color=GOLD, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=20)
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("volume:Q", title="Nombre de prédictions"),
                tooltip=["date:T", "volume:Q"],
            )
            .configure(background=BG_BLOCK)
            .configure_axis(
                labelColor=TEXT_SUBDUED, titleColor=TEXT_PRIMARY,
                gridColor=BG_BORDER, domainColor=BG_BORDER, tickColor=BG_BORDER,
            )
            .configure_view(stroke="transparent")
            .properties(height=220, padding={"top": 10, "bottom": 10, "left": 5, "right": 30})
        )
        st.altair_chart(chart_volume, width="stretch")

with col_right:
    st.subheader("Score moyen par jour")
    if df.empty:
        st.info("Aucune prédiction valide disponible pour le score moyen.")
    else:
        chart_score = (
            alt.Chart(daily)
            .mark_line(point=True, color=GOLD)
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("score_moyen:Q", title="Score moyen"),
                tooltip=["date:T", alt.Tooltip("score_moyen:Q", format=".4f")],
            )
            .configure(background=BG_BLOCK)
            .configure_axis(
                labelColor=TEXT_SUBDUED, titleColor=TEXT_PRIMARY,
                gridColor=BG_BORDER, domainColor=BG_BORDER, tickColor=BG_BORDER,
            )
            .configure_view(stroke="transparent")
            .properties(height=220, padding={"top": 10, "bottom": 10, "left": 5, "right": 30})
        )
        st.altair_chart(chart_score, width="stretch")

# ---------------------------------------------------------------------------
# Bloc C — Distribution du score
# ---------------------------------------------------------------------------
st.header("Distribution des scores")

if df.empty:
    st.info("Aucune prédiction valide disponible pour la distribution des scores.")
else:
    threshold_value = df["threshold"].iloc[0]

    hist = (
        alt.Chart(df)
        .mark_bar(opacity=0.8)
        .encode(
            x=alt.X("score:Q", bin=alt.Bin(maxbins=30), title="Score"),
            y=alt.Y("count()", title="Nombre"),
            color=alt.Color(
                "label:N",
                scale=alt.Scale(
                    domain=["Crédit accordé", "Crédit refusé"],
                    range=[GREEN, RED],
                ),
                title="Décision",
            ),
            tooltip=["label:N", "count()"],
        )
    )

    threshold_line = (
        alt.Chart(pd.DataFrame({"threshold": [threshold_value]}))
        .mark_rule(color=GOLD, strokeDash=[6, 3], strokeWidth=2)
        .encode(x="threshold:Q")
    )

    threshold_text = (
        alt.Chart(pd.DataFrame({"threshold": [threshold_value], "text": ["seuil"]}))
        .mark_text(align="left", dx=5, dy=-10, fontSize=12, fontWeight="bold", color=GOLD)
        .encode(x="threshold:Q", text="text:N")
    )

    chart_dist = (
        (hist + threshold_line + threshold_text)
        .configure(background=BG_BLOCK)
        .configure_axis(
            labelColor=TEXT_SUBDUED, titleColor=TEXT_PRIMARY,
            gridColor=BG_BORDER, domainColor=BG_BORDER, tickColor=BG_BORDER,
        )
        .configure_legend(
            labelColor=TEXT_PRIMARY, titleColor=TEXT_SUBDUED,
            orient="top", direction="horizontal",
        )
        .configure_view(stroke="transparent")
        .properties(height=260, padding={"top": 10, "bottom": 10, "left": 5, "right": 5})
    )

    st.altair_chart(chart_dist, width="stretch")

# ---------------------------------------------------------------------------
# Bloc D — Dernières prédictions
# ---------------------------------------------------------------------------
st.header("Dernières prédictions")

if df.empty:
    st.info("Aucune prédiction valide disponible pour le tableau détaillé.")
else:
    display_df = df[
        ["id", "timestamp", "score", "label", "threshold", "duration_ms"]
    ].head(20).copy()
    display_df["timestamp"] = pd.to_datetime(display_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID"),
            "timestamp": st.column_config.TextColumn("Date"),
            "score": st.column_config.NumberColumn("Score", format="%.4f"),
            "label": st.column_config.TextColumn("Décision"),
            "threshold": st.column_config.NumberColumn("Seuil", format="%.2f"),
            "duration_ms": st.column_config.NumberColumn("Latence (ms)", format="%.1f"),
        },
    )

# ---------------------------------------------------------------------------
# Bloc E — Dernières erreurs
# ---------------------------------------------------------------------------
st.header("Dernières erreurs")

if errors_df.empty:
    st.info("Aucune erreur enregistrée pour l'environnement courant.")
else:
    error_display_df = errors_df[
        ["id", "timestamp", "error_type", "error_message"]
    ].head(20).copy()
    error_display_df["timestamp"] = pd.to_datetime(error_display_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(
        error_display_df,
        width="stretch",
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID"),
            "timestamp": st.column_config.TextColumn("Date"),
            "error_type": st.column_config.TextColumn("Type d'erreur"),
            "error_message": st.column_config.TextColumn("Message"),
        },
    )
