"""Premium, minimal skin for the Streamlit UI — RP Global brand colours.

Design language inspired by chroniclehq.com: calm light backgrounds, generous
whitespace, a clean modern sans-serif (Inter), softly rounded cards with subtle
drop-shadows, and restrained use of the brand accent. The base palette lives in
``.streamlit/config.toml``; this module layers the typography, spacing and the
card/button styling on top via ``st.markdown(unsafe_allow_html=True)``.

Selectors use stable ``data-testid`` / public class hooks rather than
Streamlit's hashed class names, so the theme survives version bumps.
"""

import streamlit as st

# RP Global "Colour Codes" brand sheet.
_NAVY = "#011d3f"    # Business Blue — headings / strong text
_INK = "#3b4a63"     # softened navy — body copy
_GREEN = "#00a438"   # Energy Green — primary accent
_GREEN_DK = "#005e00"  # Nature Green — accent hover
_LINE = "#e6e8ed"    # Light Blue — hairline borders
_MUTED = "#7c8aa0"   # muted labels/captions

# Soft, layered shadow + rounded corners = the Chronicle "premium card" feel.
_SHADOW = "0 1px 2px rgba(1,29,63,.04), 0 10px 30px rgba(1,29,63,.06)"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ---- Typography & rhythm ------------------------------------------- */
html, body, .stApp, .stApp p, .stApp label, .stApp li, .stApp .stMarkdown {{
    font-family: 'Inter', -apple-system, system-ui, sans-serif;
    color: {_INK};
}}
.stApp p, .stApp li {{ line-height: 1.65; }}

.stApp h1 {{ font-family: 'Inter', sans-serif; font-weight: 800;
             letter-spacing: -0.02em; color: {_NAVY}; font-size: 2.4rem; }}
.stApp h2 {{ font-family: 'Inter', sans-serif; font-weight: 700;
             letter-spacing: -0.01em; color: {_NAVY}; margin-top: 0.4rem; }}
.stApp h3 {{ font-family: 'Inter', sans-serif; font-weight: 600; color: {_NAVY}; }}
[data-testid="stCaptionContainer"], .stApp small {{ color: {_MUTED}; }}

/* Roomier main column — generous whitespace is core to the look. */
.block-container {{ padding-top: 3rem; max-width: 1180px; }}

/* ---- Buttons: solid brand accent, soft round, smooth hover --------- */
.stButton > button, .stDownloadButton > button {{
    font-family: 'Inter', sans-serif; font-weight: 600;
    color: #ffffff; background: {_GREEN};
    border: 0; border-radius: 10px;
    padding: 0.55rem 1.15rem;
    box-shadow: 0 1px 2px rgba(1,29,63,.10);
    transition: background .15s ease, transform .15s ease, box-shadow .15s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    color: #ffffff; background: {_GREEN_DK};
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0,164,56,.25);
}}
.stButton > button:active, .stDownloadButton > button:active {{ transform: translateY(0); }}

/* ---- Metric cards: white, rounded, soft shadow -------------------- */
[data-testid="stMetric"] {{
    background: #ffffff; border: 1px solid {_LINE};
    border-radius: 14px; padding: 1.1rem 1.25rem; box-shadow: {_SHADOW};
}}
[data-testid="stMetricValue"] {{ color: {_NAVY}; font-weight: 700; }}
[data-testid="stMetricLabel"] {{ color: {_MUTED}; }}

/* ---- Expanders & alerts: rounded, hairline border, soft shadow ---- */
[data-testid="stExpander"] details {{
    background: #ffffff; border: 1px solid {_LINE};
    border-radius: 14px; box-shadow: {_SHADOW}; overflow: hidden;
}}
[data-testid="stExpander"] summary {{ font-weight: 600; color: {_NAVY}; }}
.stAlert {{ border: 1px solid {_LINE}; border-radius: 12px; box-shadow: {_SHADOW}; }}

/* ---- Inputs: soft round, light border, green focus ---------------- */
.stNumberInput input, .stTextInput input,
.stSelectbox [data-baseweb="select"] > div {{
    border-radius: 8px !important; border: 1px solid {_LINE} !important;
}}
.stNumberInput input:focus, .stTextInput input:focus {{
    border-color: {_GREEN} !important;
    box-shadow: 0 0 0 3px rgba(0,164,56,.15) !important;
}}

/* ---- Tabs: clean underline with a green active indicator ---------- */
.stTabs [data-baseweb="tab-list"] {{ gap: 1.5rem; border-bottom: 1px solid {_LINE}; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; color: {_MUTED}; }}
.stTabs [aria-selected="true"] {{ color: {_NAVY}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {_GREEN}; }}

/* ---- Sidebar & dataframes: quiet, clean -------------------------- */
[data-testid="stSidebar"] {{ border-right: 1px solid {_LINE}; }}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
    border-radius: 12px; overflow: hidden; border: 1px solid {_LINE};
}}
</style>
"""


def inject_theme() -> None:
    """Inject the premium brand stylesheet. Call once, after set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)
