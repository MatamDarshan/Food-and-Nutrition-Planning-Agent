"""
ui/styles.py
------------
Central visual theme for the AI Nutrition Planner frontend.

The app deliberately uses a custom, colourful CSS layer because the brief asks
for a premium health-tech look that native Streamlit theming alone cannot
express.  All colours, radii, shadows and responsive rules live here so page
modules never need to invent their own styling.

Design tokens
-------------
* Green / teal: primary brand, success and "close to target" states.
* Orange: calories and friendly calls to action.
* Blue: carbohydrate and data accents.
* Purple: fat and premium detail accents.
* Cream: warm, appetising canvas instead of a clinical grey background.

The CSS uses custom ``np-*`` classes wherever possible.  A small number of
stable Streamlit test selectors are used only for global widget polish and to
guarantee that text wraps instead of truncating.
"""

from __future__ import annotations

# ── Python-side colour tokens (shared with components.py) ─────────────────────

GREEN = "#1F7A5A"
GREEN_DARK = "#14563F"
GREEN_LIGHT = "#E8F5EE"
TEAL = "#0E9384"
TEAL_LIGHT = "#E5F6F3"
ORANGE = "#E8792B"
ORANGE_LIGHT = "#FFF1E6"
BLUE = "#2F6FBF"
BLUE_LIGHT = "#EAF2FD"
PURPLE = "#7251B5"
PURPLE_LIGHT = "#F1ECFA"
AMBER = "#B7791F"
AMBER_LIGHT = "#FFF6DF"
RED = "#B8423B"
RED_LIGHT = "#FDECEA"
CREAM = "#FFFDF8"
SURFACE = "#FFFFFF"
TEXT = "#20302B"
MUTED = "#64756F"
BORDER = "#DCE9E1"

ACCENTS: dict[str, str] = {
    "green": GREEN,
    "teal": TEAL,
    "orange": ORANGE,
    "blue": BLUE,
    "purple": PURPLE,
    "amber": AMBER,
    "red": RED,
}

ACCENT_BACKGROUNDS: dict[str, str] = {
    "green": GREEN_LIGHT,
    "teal": TEAL_LIGHT,
    "orange": ORANGE_LIGHT,
    "blue": BLUE_LIGHT,
    "purple": PURPLE_LIGHT,
    "amber": AMBER_LIGHT,
    "red": RED_LIGHT,
}

MEAL_ACCENTS: dict[str, str] = {
    "breakfast": ORANGE,
    "lunch": GREEN,
    "snack": TEAL,
    "dinner": PURPLE,
}

MACRO_ACCENTS: dict[str, str] = {
    "calories": ORANGE,
    "protein": GREEN,
    "carbs": BLUE,
    "fats": PURPLE,
    "fibre": TEAL,
}

THEME_CSS = """
<style>
:root {
    --np-green: #1F7A5A;
    --np-green-dark: #14563F;
    --np-green-light: #E8F5EE;
    --np-teal: #0E9384;
    --np-teal-light: #E5F6F3;
    --np-orange: #E8792B;
    --np-orange-light: #FFF1E6;
    --np-blue: #2F6FBF;
    --np-blue-light: #EAF2FD;
    --np-purple: #7251B5;
    --np-purple-light: #F1ECFA;
    --np-amber: #B7791F;
    --np-amber-light: #FFF6DF;
    --np-red: #B8423B;
    --np-red-light: #FDECEA;
    --np-canvas: #FFFDF8;
    --np-surface: #FFFFFF;
    --np-text: #20302B;
    --np-muted: #64756F;
    --np-border: #DCE9E1;
    --np-radius: 16px;
    --np-shadow: 0 8px 24px rgba(20, 86, 63, 0.07);
    --np-shadow-hover: 0 12px 30px rgba(20, 86, 63, 0.12);
}

/* ── Canvas, type and layout ──────────────────────────────────────────────── */
.stApp {
    background: var(--np-canvas) !important;
    color: var(--np-text);
    font-family: "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--np-green-dark) !important;
    font-weight: 750 !important;
    letter-spacing: -0.02em;
    line-height: 1.25 !important;
}

p, label, span, div {
    color: var(--np-text);
}

a { color: var(--np-green) !important; }

/* Keep every app block narrow enough to breathe on very wide monitors. */
div[data-testid="stAppViewContainer"] > .main {
    padding-top: 1.1rem;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

/* Hide the default deploy affordance in local/demo use. */
[data-testid="stAppDeployButton"],
.stAppDeployButton { display: none !important; }

/* ── Custom hero and section headers ───────────────────────────────────────── */
.np-hero {
    position: relative;
    overflow: hidden;
    background: linear-gradient(115deg, #FFFFFF 0%, #F3FBF6 58%, #FFF6E9 100%);
    border: 1px solid var(--np-border);
    border-radius: 22px;
    padding: 1.35rem 1.5rem;
    margin: 0.2rem 0 1.15rem 0;
    box-shadow: var(--np-shadow);
}

.np-hero::after {
    content: "";
    position: absolute;
    right: -38px;
    top: -48px;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    background: rgba(232, 121, 43, 0.10);
}

.np-hero-eyebrow {
    display: inline-block;
    color: var(--np-green-dark);
    background: var(--np-green-light);
    border-radius: 999px;
    padding: 0.22rem 0.7rem;
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.55rem;
}

.np-hero h1 {
    margin: 0 0 0.35rem 0 !important;
    font-size: clamp(1.65rem, 2.6vw, 2.35rem) !important;
}

.np-hero p {
    margin: 0 !important;
    color: var(--np-muted);
    font-size: clamp(0.9rem, 1.3vw, 1.02rem);
    line-height: 1.55;
    max-width: 72ch;
}

.np-section-bar {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin: 1.25rem 0 0.55rem 0;
}

.np-section-kicker {
    color: var(--np-orange);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.np-page-card {
    background: var(--np-surface);
    border: 1px solid var(--np-border);
    border-radius: var(--np-radius);
    padding: 1rem 1.1rem;
    box-shadow: var(--np-shadow);
    margin-bottom: 1rem;
}

/* ── Badges ────────────────────────────────────────────────────────────────── */
.np-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin: 0.9rem 0 0.2rem 0;
}

.np-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    max-width: 100%;
    padding: 0.34rem 0.7rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1.35;
    white-space: normal;
    overflow-wrap: anywhere;
    border: 1px solid transparent;
}

.np-badge--green  { color: #14563F; background: #E8F5EE; border-color: #C7E6D5; }
.np-badge--teal   { color: #0B6B61; background: #E5F6F3; border-color: #BCE8E0; }
.np-badge--orange { color: #9E4F16; background: #FFF1E6; border-color: #F7D6B8; }
.np-badge--blue   { color: #1E5595; background: #EAF2FD; border-color: #C9DDF5; }
.np-badge--purple { color: #553A8C; background: #F1ECFA; border-color: #DCCFF3; }
.np-badge--amber  { color: #8A5B10; background: #FFF6DF; border-color: #F2DCA8; }
.np-badge--red    { color: #94322D; background: #FDECEA; border-color: #F3C9C5; }

/* ── Metric cards ──────────────────────────────────────────────────────────── */
.np-metric-accent {
    height: 4px;
    border-radius: 999px;
    background: var(--np-accent, var(--np-green));
    margin: -0.1rem 0 0.45rem 0;
    width: 100%;
}

div[data-testid="stMetric"] {
    background: var(--np-surface) !important;
    border: 1px solid var(--np-border) !important;
    border-radius: 14px !important;
    padding: 0.7rem 0.8rem !important;
    box-shadow: 0 5px 16px rgba(20, 86, 63, 0.05);
    min-width: 0;
    transition: transform 140ms ease, box-shadow 140ms ease;
}

div[data-testid="stMetric"]:hover {
    transform: translateY(-1px);
    box-shadow: var(--np-shadow-hover);
}

div[data-testid="stMetricLabel"] p {
    color: var(--np-muted) !important;
    font-size: 0.74rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.01em !important;
    text-transform: none !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
}

div[data-testid="stMetricValue"] {
    font-size: clamp(1.2rem, 1.8vw, 1.55rem) !important;
    line-height: 1.25 !important;
    color: var(--np-green-dark) !important;
}

div[data-testid="stMetricValue"] > div,
div[data-testid="stMetricDelta"] > div {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    overflow-wrap: anywhere !important;
}

/* ── Progress bars ─────────────────────────────────────────────────────────── */
.np-progress-wrap {
    background: var(--np-surface);
    border: 1px solid var(--np-border);
    border-radius: 13px;
    padding: 0.7rem 0.8rem;
    margin: 0.45rem 0;
    box-shadow: 0 4px 14px rgba(20, 86, 63, 0.04);
}

.np-progress-meta {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
    flex-wrap: wrap;
    font-size: 0.76rem;
    color: var(--np-muted);
}

.np-progress-meta strong {
    color: var(--np-text);
    font-size: 0.86rem;
}

.np-progress-track {
    position: relative;
    height: 8px;
    margin: 0.5rem 0 0.4rem 0;
    border-radius: 999px;
    background: #EDF3EE;
    overflow: hidden;
}

.np-progress-fill {
    height: 100%;
    border-radius: 999px;
    background: var(--np-green);
    transition: width 280ms ease;
}

.np-progress-note {
    font-size: 0.73rem;
    color: var(--np-muted);
    overflow-wrap: anywhere;
}

/* ── Meal cards ────────────────────────────────────────────────────────────── */
.np-meal-card {
    position: relative;
    overflow: hidden;
}

.np-meal-accent {
    height: 5px;
    border-radius: 999px;
    background: var(--np-accent, var(--np-green));
    margin: -0.2rem 0 0.65rem 0;
}

.np-meal-calories {
    text-align: right;
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--np-green-dark);
    line-height: 1.2;
    overflow-wrap: anywhere;
}

.np-meal-calories span {
    display: block;
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--np-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--np-surface) !important;
    border: 1px solid var(--np-border) !important;
    border-radius: var(--np-radius) !important;
    box-shadow: var(--np-shadow);
    transition: box-shadow 140ms ease;
}

div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: var(--np-shadow-hover);
}

/* ── Buttons and forms ─────────────────────────────────────────────────────── */
div.stButton > button,
div.stFormSubmitButton > button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 0.86rem !important;
    white-space: normal !important;
    height: auto !important;
    min-height: 2.5rem;
    padding: 0.45rem 0.75rem !important;
    border: 1px solid var(--np-border) !important;
    background: var(--np-surface) !important;
    color: var(--np-green-dark) !important;
    transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
}

div.stButton > button:hover,
div.stFormSubmitButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(20, 86, 63, 0.12);
    background: var(--np-green-light) !important;
}

div.stButton > button[kind="primary"],
div.stFormSubmitButton > button[kind="primaryFormSubmit"] {
    background: var(--np-green) !important;
    color: #FFFFFF !important;
    border-color: var(--np-green) !important;
    box-shadow: 0 6px 16px rgba(31, 122, 90, 0.22);
}

div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button[kind="primaryFormSubmit"]:hover {
    background: var(--np-green-dark) !important;
    color: #FFFFFF !important;
}

div.stButton > button p,
div.stFormSubmitButton > button p {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    line-height: 1.3 !important;
    overflow-wrap: anywhere !important;
}

/* ── Tables, charts, expanders and alerts ──────────────────────────────────── */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--np-border) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 4px 14px rgba(20, 86, 63, 0.04);
}

div[data-testid="stExpander"] {
    background: var(--np-surface) !important;
    border: 1px solid var(--np-border) !important;
    border-radius: 13px !important;
    box-shadow: 0 4px 14px rgba(20, 86, 63, 0.04);
}

div[data-testid="stExpander"] summary p {
    font-weight: 700 !important;
    color: var(--np-green-dark) !important;
}

div[data-testid="stAlert"] {
    border-radius: 12px !important;
}

div[data-testid="stProgress"] > div > div > div > div {
    background: var(--np-green) !important;
}

/* ── Sidebar ───────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #F7FCF8 100%) !important;
    border-right: 1px solid var(--np-border) !important;
}

.np-sidebar-brand {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    margin-bottom: 0.4rem;
}

.np-sidebar-mark {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    flex: 0 0 40px;
    border-radius: 13px;
    background: var(--np-green);
    color: white;
    font-size: 1.25rem;
    box-shadow: 0 6px 16px rgba(31, 122, 90, 0.25);
}

.np-sidebar-brand h2 {
    margin: 0 !important;
    font-size: 1.15rem !important;
}

.np-sidebar-brand p {
    margin: 0 !important;
    color: var(--np-muted);
    font-size: 0.7rem;
    line-height: 1.35;
}

section[data-testid="stSidebar"] .stRadio label p {
    font-size: 0.9rem !important;
    font-weight: 700 !important;
    overflow-wrap: anywhere !important;
}

section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stRadio label {
    overflow-wrap: anywhere !important;
}

.np-mode-card {
    border-radius: 12px;
    padding: 0.7rem 0.8rem;
    border: 1px solid transparent;
    line-height: 1.45;
    font-size: 0.78rem;
}

.np-mode-card strong { display: block; font-size: 0.84rem; }
.np-mode-card span { display: block; font-size: 0.72rem; opacity: 0.85; overflow-wrap: anywhere; }
.np-mode-card--live { background: var(--np-green-light); border-color: #C7E6D5; color: #14563F; }
.np-mode-card--offline { background: #EEF3F7; border-color: #D7E2EA; color: #34495E; }

/* ── Empty and informational states ───────────────────────────────────────── */
.np-empty {
    text-align: center;
    background: var(--np-surface);
    border: 1px dashed #BFD8C9;
    border-radius: var(--np-radius);
    padding: 1.8rem 1.2rem;
    margin: 1rem 0;
}

.np-empty-icon { font-size: 2.2rem; line-height: 1; }
.np-empty h3 { margin: 0.6rem 0 0.35rem 0 !important; }
.np-empty p { color: var(--np-muted); margin: 0 auto 0.9rem auto !important; max-width: 58ch; }

.np-callout {
    border-left: 4px solid var(--np-accent, var(--np-green));
    background: var(--np-callout-bg, var(--np-green-light));
    border-radius: 12px;
    padding: 0.8rem 1rem;
    margin: 0.7rem 0;
    line-height: 1.55;
    overflow-wrap: anywhere;
}

.np-source-note {
    color: var(--np-muted);
    font-size: 0.76rem;
    line-height: 1.5;
    margin-top: 0.8rem;
    overflow-wrap: anywhere;
}

/* ── Chat ──────────────────────────────────────────────────────────────────── */
.np-chat-context {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.8rem 0 1rem 0;
}

div[data-testid="stChatMessage"] {
    background: var(--np-surface) !important;
    border: 1px solid var(--np-border) !important;
    border-radius: 15px !important;
    padding: 0.55rem 0.8rem !important;
    box-shadow: 0 4px 14px rgba(20, 86, 63, 0.04);
}

div[data-testid="stChatMessage"] p,
div[data-testid="stChatMessage"] li {
    font-size: 0.93rem;
    line-height: 1.6;
    overflow-wrap: anywhere;
}

.np-typing {
    display: inline-flex;
    gap: 0.25rem;
    align-items: center;
    color: var(--np-muted);
    font-size: 0.8rem;
}

.np-typing i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--np-green);
    display: inline-block;
    opacity: 0.65;
}

/* ── Responsive behaviour ──────────────────────────────────────────────────── */
@media (max-width: 1200px) {
    .np-hero { padding: 1.1rem 1.2rem; }
    div[data-testid="stMetric"] { padding: 0.6rem 0.65rem !important; }
    div[data-testid="stMetricLabel"] p { font-size: 0.7rem !important; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }
}

@media (max-width: 820px) {
    .np-hero { border-radius: 16px; padding: 1rem; }
    .np-hero h1 { font-size: 1.45rem !important; }
    .np-badge { font-size: 0.72rem; }
    div[data-testid="stMetric"] { padding: 0.55rem !important; }
    div[data-testid="stMetricLabel"] p { font-size: 0.66rem !important; }
    div[data-testid="stMetricValue"] { font-size: 1.05rem !important; }
    .np-meal-calories { font-size: 1rem; }
    div.stButton > button,
    div.stFormSubmitButton > button { font-size: 0.8rem !important; }
}
</style>
"""
