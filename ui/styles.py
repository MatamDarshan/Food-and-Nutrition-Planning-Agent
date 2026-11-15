"""
ui/styles.py
------------
Theme styling and modern CSS for the AI Food and Nutrition Planning Agent.
Palette:
- Background: Very light cream/white (#F8FAF8 / #FFFFFF)
- Primary: Dark Forest Green (#1B4332, #2D6A4F)
- Accents: Emerald / Sage (#40916C, #52B788, #74C69D)
- Soft Tint: Mint (#E8F5E9, #D8F3DC)
- Text: Charcoal (#1F2937, #374151)
"""

THEME_CSS = """
<style>
/* ── Global Styles ── */
.stApp {
    background-color: #F8FAF8;
    color: #1F2937;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ── Typography & Headings ── */
h1, h2, h3, h4, h5, h6 {
    color: #1B4332 !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
}

/* ── Custom Cards ── */
.custom-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 2px 6px rgba(27, 67, 50, 0.04);
    margin-bottom: 1.25rem;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.custom-card:hover {
    box-shadow: 0 4px 12px rgba(27, 67, 50, 0.08);
}

.card-header {
    font-size: 1.15rem;
    font-weight: 600;
    color: #1B4332;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

/* ── Metric Cards ── */
.metric-box {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    text-align: left;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
}

.metric-label {
    font-size: 0.82rem;
    font-weight: 500;
    color: #6B7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.25rem;
}

.metric-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #1B4332;
    line-height: 1.2;
}

.metric-caption {
    font-size: 0.8rem;
    color: #4B5563;
    margin-top: 0.25rem;
}

/* ── Badges & Chips ── */
.status-pill {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 0.4rem;
}

.pill-success {
    background-color: #D8F3DC;
    color: #1B4332;
}

.pill-info {
    background-color: #E0E7FF;
    color: #3730A3;
}

.pill-warning {
    background-color: #FEF3C7;
    color: #92400E;
}

/* ── Meal Cards ── */
.meal-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-top: 4px solid #2D6A4F;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.meal-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1B4332;
    margin-bottom: 0.5rem;
}

.meal-subtotal {
    background-color: #F0FDF4;
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
    color: #166534;
    font-weight: 500;
    margin-top: 0.5rem;
}

/* ── Disclaimer Banner ── */
.disclaimer-banner {
    background-color: #F0FDF4;
    border-left: 4px solid #2D6A4F;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    font-size: 0.82rem;
    color: #166534;
    margin-bottom: 1.25rem;
}

/* ── Primary Action Button Styling ── */
div.stButton > button:first-child {
    background-color: #2D6A4F !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.25rem !important;
    transition: all 0.2s ease-in-out !important;
}

div.stButton > button:first-child:hover {
    background-color: #1B4332 !important;
    box-shadow: 0 4px 10px rgba(27, 67, 50, 0.2) !important;
    transform: translateY(-1px) !important;
}

/* ── Table Styling ── */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #E5E7EB;
}
</style>
"""
