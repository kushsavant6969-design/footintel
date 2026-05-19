try:
    from rapidfuzz import fuzz as rfuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import io
import hashlib
from datetime import datetime, timedelta

st.set_page_config(
    page_title="FootIntel — Fan Segmentation",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'DM Mono',monospace;}
[data-testid="stAppViewContainer"]{background:#0a0c10;}
[data-testid="stHeader"]{background:#0a0c10;}
section[data-testid="stSidebar"]{display:none;}
.block-container{padding:2rem 2rem 1rem!important;}
h1,h2,h3{font-family:'Syne',sans-serif!important;}
.stSpinner>div{border-top-color:#c8f135!important;}
div[data-testid="stButton"]>button{
    background:#13161d!important;border:1px solid #2a2f3d!important;
    color:#9ca3af!important;font-family:'DM Mono',monospace!important;
    font-size:12px!important;padding:6px 18px!important;border-radius:6px!important;
    transition:.15s!important;}
div[data-testid="stButton"]>button:hover{border-color:#c8f135!important;color:#c8f135!important;}
div[data-testid="stDownloadButton"]>button{
    background:#13161d!important;border:1px solid #2a2f3d!important;
    color:#9ca3af!important;font-family:'DM Mono',monospace!important;
    font-size:12px!important;padding:6px 18px!important;border-radius:6px!important;}
div[data-testid="stDownloadButton"]>button:hover{border-color:#c8f135!important;color:#c8f135!important;}
div[data-testid="stFileUploadDropzone"]{
    background:#0d1117!important;border:1px solid #2a2f3d!important;border-radius:8px!important;}
.stTabs [data-baseweb="tab-list"]{background:#0a0c10!important;gap:6px;}
.stTabs [data-baseweb="tab"]{
    background:#13161d!important;border:1px solid #1f2937!important;border-radius:6px!important;
    color:#6b7280!important;font-family:'DM Mono',monospace!important;font-size:12px!important;
    padding:6px 20px!important;}
.stTabs [aria-selected="true"]{background:#c8f135!important;color:#0a0c10!important;border-color:#c8f135!important;font-weight:600!important;}
div[data-testid="stSelectbox"]>div>div{
    background:#13161d!important;border-color:#2a2f3d!important;color:#e5e7eb!important;}
div[data-testid="stAlert"]{background:#0d1117!important;border-color:#2a2f3d!important;}
.stDataFrame{background:#0d1117!important;}
[data-testid="stMetric"]{background:#13161d;border:1px solid #1f2937;border-radius:10px;padding:16px;}
[data-testid="stMetricLabel"]{color:#6b7280!important;font-size:10px!important;text-transform:uppercase;letter-spacing:.08em;}
[data-testid="stMetricValue"]{color:#c8f135!important;font-family:'Syne',sans-serif!important;font-size:28px!important;font-weight:800!important;}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────

SEGMENT_INFO = {
    "Loyal Fans": {
        "color": "#22c55e", "bg": "#052e16", "icon": "💚",
        "description": "Committed, high-value fans with strong purchase history and high loyalty. Season Ticket or Paid members deeply invested in the club.",
        "recommendation": "Prioritise retention over acquisition. Reward tenure with exclusive content, VIP access, and early bird season ticket renewal. Leverage as brand ambassadors.",
        "actions": ["VIP early renewal access", "Fan anniversary reward", "Ambassador programme invite", "Exclusive behind-the-scenes content"],
        "risk": "LOW",
    },
    "High Potential": {
        "color": "#3d9cf0", "bg": "#0a1a2e", "icon": "🚀",
        "description": "Highly engaged fans not yet converted to commercial value. One targeted offer away from upgrading their membership tier.",
        "recommendation": "Convert engagement to revenue with a personalised membership upgrade offer. Time it to a peak engagement moment — matchday, transfer window, or content milestone.",
        "actions": ["Membership upgrade offer (15% off)", "Matchday ticket bundle", "First-purchase welcome incentive", "App-triggered merch discount"],
        "risk": "MED",
    },
    "Win Back": {
        "color": "#ef4444", "bg": "#1f0a0a", "icon": "🔄",
        "description": "High churn risk — previously active fans with sharp drop in engagement and purchases across all channels.",
        "recommendation": "Immediate personalised win-back campaign. Time-limited discount code, personalised highlight reel, and a low-friction reactivation path. Identify the churn trigger.",
        "actions": ["Win-back email: 25% discount code", "Personalised content push notification", "Churn survey with prize draw", "Free match ticket (limited availability)"],
        "risk": "HIGH",
    },
    "Dormant": {
        "color": "#6b7280", "bg": "#111827", "icon": "💤",
        "description": "Registered fans who never fully activated. Low engagement, no meaningful purchases, usually without a paid membership tier.",
        "recommendation": "Nostalgia and activation campaigns. Big match alerts, milestone content, and a low-barrier entry-point offer (Basic membership trial, free content access).",
        "actions": ["Big match push notification", "Free content access campaign", "Basic membership trial offer", "Onboarding email series restart"],
        "risk": "HIGH",
    },
    "Casual": {
        "color": "#64748b", "bg": "#0f172a", "icon": "👤",
        "description": "Moderate, consistent engagement — the broad base of the fan ecosystem. Potential to climb the loyalty ladder with the right nudge.",
        "recommendation": "Steady nurture through newsletters, matchday notifications, and social community building. Identify their preferred channel and maximise it.",
        "actions": ["Monthly club newsletter", "Matchday push notifications", "Social community / fan forum invite", "Channel-specific content drip"],
        "risk": "MED",
    },
}

COLUMN_ALIASES: dict[str, list[str]] = {
    "user_id":                  ["user_id", "userid", "user id", "id", "fan_id", "customer_id", "fan id"],
    "age":                      ["age", "age_years", "fan_age", "customer_age"],
    "gender":                   ["gender", "sex"],
    "country":                  ["country", "nation", "nationality", "location", "region"],
    "membership_category":      ["membership_category", "membership category", "member_category", "member_tier", "membership_tier", "tier"],
    "fan_type":                 ["fan_type", "fan type", "fantype", "fan_classification", "fan_category"],
    "has_app":                  ["has_app", "has app", "app_user", "app user", "hasapp", "app_installed"],
    "email_opens":              ["email_opens", "email opens", "emailopens", "email_engagement"],
    "email_clicks":             ["email_clicks", "email clicks", "emailclicks", "email_ctr_clicks"],
    "email_campaigns_received": ["email_campaigns_received", "email campaigns received", "campaigns_received", "emails_sent", "email_sends", "email_volume"],
    "inapp_opens":              ["inapp_opens", "inapp opens", "in_app_opens", "push_opens", "notification_opens"],
    "inapp_clicks":             ["inapp_clicks", "inapp clicks", "in_app_clicks", "in app clicks", "push_clicks"],
    "inapp_campaigns_received": ["inapp_campaigns_received", "in_app_campaigns_received", "push_campaigns_received", "push_sends"],
    "article_views":            ["article_views", "article views", "content_views", "page_views", "articles_read"],
    "ticket_purchases":         ["ticket_purchases", "tickets", "ticket purchases", "ticket_count", "matches_attended"],
    "membership_purchases":     ["membership_purchases", "memberships", "membership purchases", "subscriptions", "subs"],
    "retail_purchases":         ["retail_purchases", "retail", "retail purchases", "merchandise", "merch_purchases", "shop_orders"],
    "total_revenue":            ["total_revenue", "revenue", "total_spend", "ltv", "spend", "total_value", "lifetime_value"],
    "first_purchase_date":      ["first_purchase_date", "first purchase date", "first_transaction_date", "first_order_date", "earliest_purchase"],
    "last_purchase_date":       ["last_purchase_date", "last purchase date", "last_purchase", "last_transaction_date", "last_order_date", "most_recent_purchase"],
    "first_app_open":           ["first_app_open", "first app open", "app_first_open", "app_install_date"],
    "last_app_open":            ["last_app_open", "last app open", "app_last_open", "most_recent_app_open", "last_session_date"],
    "first_email_open":         ["first_email_open", "first email open", "email_first_open"],
    "last_email_open":          ["last_email_open", "last email open", "most_recent_email_open"],
    "first_article_view":       ["first_article_view", "first article view", "content_first_view"],
    "last_article_view":        ["last_article_view", "last article view", "content_last_view"],
    "join_date":                ["join_date", "joined_date", "first_seen", "registration_date", "signup_date", "date_joined", "created_at", "fan_since"],
}

FIELD_LABELS: dict[str, str] = {
    "user_id":                  "User ID",
    "age":                      "Age",
    "gender":                   "Gender",
    "country":                  "Country / Region",
    "membership_category":      "Membership Category",
    "fan_type":                 "Fan Type",
    "has_app":                  "Has App (Yes/No)",
    "email_opens":              "Email Opens",
    "email_clicks":             "Email Clicks",
    "email_campaigns_received": "Email Campaigns Received",
    "inapp_opens":              "In-App Opens",
    "inapp_clicks":             "In-App Clicks",
    "inapp_campaigns_received": "In-App Campaigns Received",
    "article_views":            "Article Views",
    "ticket_purchases":         "Ticket Purchases",
    "membership_purchases":     "Membership Purchases",
    "retail_purchases":         "Retail Purchases",
    "total_revenue":            "Total Revenue",
    "first_purchase_date":      "First Purchase Date",
    "last_purchase_date":       "Last Purchase Date",
    "first_app_open":           "First App Open Date",
    "last_app_open":            "Last App Open Date",
    "first_email_open":         "First Email Open Date",
    "last_email_open":          "Last Email Open Date",
    "first_article_view":       "First Article View Date",
    "last_article_view":        "Last Article View Date",
    "join_date":                "Join Date",
}

MEMBERSHIP_TIER_SCORE = {"none": 0, "basic": 25, "paid": 60, "season ticket": 100}

JOURNEY_STAGE_ORDER = [
    "Stage 1 — No Membership, Low Engagement",
    "Stage 2 — No Membership, Active",
    "Stage 3 — Basic Member, Engaged",
    "Stage 4 — Paid Member",
    "Stage 5 — Season Ticket Holder",
]
JOURNEY_STAGE_COLORS = ["#4b5563", "#f59e0b", "#3d9cf0", "#22c55e", "#c8f135"]

# ── Hybrid schema — core columns required for full dashboard ──────────────────
CORE_COLUMNS = {
    "email_opens", "email_clicks", "email_campaigns_received",
    "inapp_opens", "inapp_clicks", "inapp_campaigns_received",
    "article_views", "ticket_purchases", "membership_purchases",
    "retail_purchases", "total_revenue", "last_purchase_date",
    "last_app_open", "last_email_open", "join_date",
    "membership_category", "fan_type", "has_app",
}

# ISO alpha-3 country map for acquisition choropleth
COUNTRY_ISO: dict[str, str] = {
    "England": "GBR", "Scotland": "GBR", "Wales": "GBR", "Great Britain": "GBR",
    "United Kingdom": "GBR", "UK": "GBR",
    "Ireland": "IRL", "Northern Ireland": "IRL",
    "USA": "USA", "United States": "USA",
    "Germany": "DEU", "Spain": "ESP", "France": "FRA", "Italy": "ITA",
    "Netherlands": "NLD", "Belgium": "BEL", "Portugal": "PRT",
    "Sweden": "SWE", "Norway": "NOR", "Denmark": "DNK",
    "Brazil": "BRA", "Argentina": "ARG", "Mexico": "MEX",
    "Australia": "AUS", "Canada": "CAN", "Japan": "JPN",
    "South Korea": "KOR", "China": "CHN", "India": "IND",
}

SYNTHETIC_PLAYERS = [
    "Beth Mead", "Lauren Hemp", "Vivianne Miedema", "Sam Kerr",
    "Millie Bright", "Keira Walsh", "Lucy Bronze", "Alessia Russo",
    "Chloe Kelly", "Fran Kirby",
]

AGE_GROUPS = [
    ("Child",       0,  12),
    ("Young Adult", 13, 25),
    ("Adult",       26, 49),
    ("Senior",      50, 150),
]

PLOTLY_BASE = dict(
    paper_bgcolor="#0a0c10",
    plot_bgcolor="#0d1117",
    font=dict(family="DM Mono", color="#9ca3af", size=11),
    title_font=dict(family="Syne", color="#e5e7eb", size=14),
    margin=dict(l=8, r=8, t=44, b=8),
)

# ── UI helpers ────────────────────────────────────────────────────────────────

def card(body: str, bg="#13161d", border="#2a2f3d", pad="16px 18px", radius="10px") -> str:
    return (
        f'<div style="background:{bg};border:1px solid {border};border-radius:{radius};'
        f'padding:{pad};margin-bottom:14px">{body}</div>'
    )


def kpi(label: str, value: str, sub: str = "", color: str = "#c8f135") -> str:
    return (
        f'<div style="background:#13161d;border:1px solid #1f2937;border-radius:10px;padding:18px 20px;">'
        f'<div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">{label}</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:30px;font-weight:800;color:{color};line-height:1">{value}</div>'
        f'<div style="font-size:11px;color:#6b7280;margin-top:6px">{sub}</div>'
        f'</div>'
    )


def seg_pill(segment: str) -> str:
    info = SEGMENT_INFO.get(segment, {"color": "#6b7280", "bg": "#111827", "icon": "·"})
    return (
        f'<span style="background:{info["bg"]};color:{info["color"]};'
        f'border:1px solid {info["color"]};font-size:9px;padding:2px 8px;border-radius:8px">'
        f'{info["icon"]} {segment}</span>'
    )


def section_heading(text: str) -> None:
    st.markdown(
        f'<div style="font-family:\'Syne\',sans-serif;font-size:17px;font-weight:700;'
        f'color:#e5e7eb;margin:28px 0 14px">{text}</div>',
        unsafe_allow_html=True,
    )


def insight_banner(s1: str, s2: str) -> None:
    """Gold left-border dark insight card — 2 sentences."""
    st.markdown(
        '<div style="background:#13161d;border-left:4px solid #c8a800;'
        'border-radius:8px;padding:14px 20px;margin-bottom:20px">'
        '<span style="color:#c8a800;font-size:10px;text-transform:uppercase;'
        'letter-spacing:.12em;font-weight:600">AI Insight</span><br>'
        f'<span style="color:#f3f4f6;font-size:13px;line-height:1.7">'
        f'{s1} {s2}</span></div>',
        unsafe_allow_html=True,
    )


def detect_columns_scored(df) -> tuple:
    """(high_conf, low_conf, unmatched_set)."""
    df_norm = {_norm(c): c for c in df.columns}
    high_conf, low_conf, unmatched_set = {}, {}, set()
    for field, aliases in COLUMN_ALIASES.items():
        best_col, best_score = None, 0
        for alias in aliases:
            key = _norm(alias)
            if key in df_norm:
                best_col = df_norm[key]
                best_score = 100
                break
        if best_score < 85 and HAS_RAPIDFUZZ:
            for csv_norm, csv_orig in df_norm.items():
                s = max(rfuzz.ratio(csv_norm, _norm(a)) for a in aliases)
                if s > best_score:
                    best_score, best_col = s, csv_orig
        if best_score >= 85:
            high_conf[field] = best_col
        elif best_score >= 50 and best_col:
            low_conf[field] = (best_col, round(best_score))
        else:
            unmatched_set.add(field)
    return high_conf, low_conf, unmatched_set


def get_upload_state(col_map: dict) -> tuple[str, set]:
    """Returns ('full'|'partial'|'custom', set_of_missing_core_columns)."""
    missing = CORE_COLUMNS - set(col_map.keys())
    matched = CORE_COLUMNS & set(col_map.keys())
    if not missing:
        return "full", set()
    if len(matched) >= 5:
        return "partial", missing
    return "custom", missing


def _locked_tab_msg(reason: str = "") -> None:
    msg = reason or "This tab requires core fan data columns. Please upload a compatible CSV or download the template."
    st.markdown(card(
        f'<div style="text-align:center;padding:28px 16px">'
        f'<div style="font-size:22px;margin-bottom:10px">🔒</div>'
        f'<div style="font-size:12px;color:#6b7280">{msg}</div>'
        f'</div>',
        border="#2a2f3d",
    ), unsafe_allow_html=True)


def grayed_kpi(label: str, missing_col: str) -> str:
    tip = f"Add {missing_col} to unlock this metric."
    return (
        f'<div style="background:#0d1117;border:1px dashed #374151;border-radius:10px;padding:18px 20px;">'
        f'<div style="font-size:10px;color:#374151;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">{label}</div>'
        f'<div style="font-size:26px;color:#2a2f3d">— —</div>'
        f'<div style="font-size:10px;color:#374151;margin-top:6px" title="{tip}">⚠ {tip}</div>'
        f'</div>'
    )


# ── Data processing ───────────────────────────────────────────────────────────

def _norm(name: str) -> str:
    return str(name).lower().strip().replace(" ", "_").replace("-", "_")


def detect_columns(df: pd.DataFrame) -> dict[str, str]:
    df_norm = {_norm(c): c for c in df.columns}
    mapping: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if _norm(alias) in df_norm:
                mapping[field] = df_norm[_norm(alias)]
                break
    return mapping


def _pct(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    if s.std() == 0:
        return pd.Series(50.0, index=series.index)
    return s.rank(pct=True) * 100


def assign_age_group(age) -> str:
    try:
        a = float(age)
    except (ValueError, TypeError):
        return "Unknown"
    for label, lo, hi in AGE_GROUPS:
        if lo <= a <= hi:
            return label
    return "Unknown"


def _email_ctr(df: pd.DataFrame, col: dict) -> pd.Series:
    """Email click-through rate (0–1) or zeros if columns missing."""
    if "email_clicks" in col and "email_campaigns_received" in col:
        ec  = pd.to_numeric(df[col["email_clicks"]], errors="coerce").fillna(0)
        ecr = pd.to_numeric(df[col["email_campaigns_received"]], errors="coerce").fillna(1).clip(lower=1)
        return (ec / ecr).clip(0, 1)
    return pd.Series(0.0, index=df.index)


def _inapp_ctr(df: pd.DataFrame, col: dict) -> pd.Series:
    """In-app click-through rate (0–1) or zeros if columns missing."""
    if "inapp_clicks" in col and "inapp_campaigns_received" in col:
        ic  = pd.to_numeric(df[col["inapp_clicks"]], errors="coerce").fillna(0)
        icr = pd.to_numeric(df[col["inapp_campaigns_received"]], errors="coerce").fillna(1).clip(lower=1)
        return (ic / icr).clip(0, 1)
    return pd.Series(0.0, index=df.index)


def compute_engagement_score(df: pd.DataFrame, col: dict) -> pd.Series:
    """Email CTR 20% · InApp CTR 25% · Article Views 20% · App Recency 35%."""
    today = datetime.today()

    # Email CTR (20%)
    if "email_clicks" in col and "email_campaigns_received" in col:
        email_s = _pct(_email_ctr(df, col)) * 0.20
    elif "email_opens" in col:
        email_s = _pct(df[col["email_opens"]]) * 0.20
    else:
        email_s = pd.Series(10.0, index=df.index)

    # InApp CTR (25%)
    if "inapp_clicks" in col and "inapp_campaigns_received" in col:
        inapp_s = _pct(_inapp_ctr(df, col)) * 0.25
    elif "inapp_clicks" in col:
        inapp_s = _pct(df[col["inapp_clicks"]]) * 0.25
    else:
        inapp_s = pd.Series(12.5, index=df.index)

    # Article views (20%)
    if "article_views" in col:
        article_s = _pct(df[col["article_views"]]) * 0.20
    else:
        article_s = pd.Series(10.0, index=df.index)

    # App recency (35%) — decay over 60-day half-life
    if "last_app_open" in col:
        app_dates  = pd.to_datetime(df[col["last_app_open"]], errors="coerce")
        app_days   = (today - app_dates).dt.days.fillna(180)
        app_recency = (100 * np.exp(-app_days / 60)).clip(0, 100)
    elif "has_app" in col:
        has = df[col["has_app"]].astype(str).str.strip().str.lower().isin(["yes", "1", "true"])
        app_recency = pd.Series(np.where(has, 50.0, 10.0), index=df.index)
    else:
        app_recency = pd.Series(50.0, index=df.index)
    app_s = app_recency * 0.35

    return (email_s + inapp_s + article_s + app_s).clip(0, 100)


def compute_commercial_score(df: pd.DataFrame, col: dict) -> tuple[pd.Series, pd.Series]:
    """Revenue 40% · Recency 35% · Frequency 25%. Returns (score, recency_days)."""
    today = datetime.today()

    if "total_revenue" in col:
        rev_s = _pct(df[col["total_revenue"]]) * 0.40
    else:
        proxy = pd.Series(0.0, index=df.index)
        for f in ("ticket_purchases", "membership_purchases", "retail_purchases"):
            if f in col:
                proxy += pd.to_numeric(df[col[f]], errors="coerce").fillna(0)
        rev_s = _pct(proxy) * 0.40

    if "last_purchase_date" in col:
        dates       = pd.to_datetime(df[col["last_purchase_date"]], errors="coerce")
        recency_days = (today - dates).dt.days.fillna(730)
    else:
        recency_days = pd.Series(365.0, index=df.index)
    recency_s = (100 * np.exp(-recency_days / 180)).clip(0, 100) * 0.35

    freq = pd.Series(0.0, index=df.index)
    for f in ("ticket_purchases", "membership_purchases", "retail_purchases"):
        if f in col:
            freq += pd.to_numeric(df[col[f]], errors="coerce").fillna(0)
    freq_s = _pct(freq) * 0.25

    return (rev_s + recency_s + freq_s).clip(0, 100), recency_days


def compute_loyalty_score(df: pd.DataFrame, col: dict) -> tuple[pd.Series, pd.Series]:
    """Tenure 40% · Membership tier 35% · Purchase consistency 25%. Returns (score, tenure_days)."""
    today = datetime.today()

    if "join_date" in col:
        join        = pd.to_datetime(df[col["join_date"]], errors="coerce")
        tenure_days = (today - join).dt.days.fillna(0).clip(0)
    else:
        tenure_days = pd.Series(365.0, index=df.index)
    tenure_s = (tenure_days / 1825 * 100).clip(0, 100) * 0.40

    if "membership_category" in col:
        tier_val    = df[col["membership_category"]].astype(str).str.lower().str.strip().map(MEMBERSHIP_TIER_SCORE).fillna(0)
        member_s    = tier_val * 0.35
    else:
        diversity = pd.Series(0.0, index=df.index)
        for f in ("ticket_purchases", "membership_purchases", "retail_purchases"):
            if f in col:
                has = (pd.to_numeric(df[col[f]], errors="coerce").fillna(0) > 0).astype(float)
                diversity += has * (100 / 3)
        if all(f not in col for f in ("ticket_purchases", "membership_purchases", "retail_purchases")):
            diversity = pd.Series(33.0, index=df.index)
        member_s = diversity * 0.35

    purchases = pd.Series(0.0, index=df.index)
    for f in ("ticket_purchases", "membership_purchases", "retail_purchases"):
        if f in col:
            purchases += pd.to_numeric(df[col[f]], errors="coerce").fillna(0)
    freq_s = _pct(purchases) * 0.25

    return (tenure_s + member_s + freq_s).clip(0, 100), tenure_days


def compute_churn_risk_base(df: pd.DataFrame, col: dict) -> pd.Series:
    """Purchase recency 35% · App recency 30% · Email recency 20% (returns partial, 85% of total)."""
    today = datetime.today()

    if "last_purchase_date" in col:
        ld   = pd.to_datetime(df[col["last_purchase_date"]], errors="coerce")
        pd_  = (today - ld).dt.days.fillna(730)
    else:
        pd_  = pd.Series(365.0, index=df.index)
    purchase_risk = (pd_ / 365 * 100).clip(0, 100) * 0.35

    if "last_app_open" in col:
        ad   = pd.to_datetime(df[col["last_app_open"]], errors="coerce")
        adays = (today - ad).dt.days.fillna(365)
    else:
        adays = pd.Series(90.0, index=df.index)
    app_risk = (adays / 90 * 100).clip(0, 100) * 0.30

    if "last_email_open" in col:
        ed    = pd.to_datetime(df[col["last_email_open"]], errors="coerce")
        edays = (today - ed).dt.days.fillna(365)
    else:
        edays = pd.Series(90.0, index=df.index)
    email_risk = (edays / 90 * 100).clip(0, 100) * 0.20

    return (purchase_risk + app_risk + email_risk).clip(0, 85)


def compute_conversion_probability_base(df: pd.DataFrame, col: dict) -> pd.Series:
    """Email CTR pct 25% · InApp CTR pct 25% · Membership gap 25% (returns 75% of total)."""
    if "email_clicks" in col and "email_campaigns_received" in col:
        email_s = _pct(_email_ctr(df, col)) * 0.25
    else:
        email_s = pd.Series(12.5, index=df.index)

    if "inapp_clicks" in col and "inapp_campaigns_received" in col:
        inapp_s = _pct(_inapp_ctr(df, col)) * 0.25
    else:
        inapp_s = pd.Series(12.5, index=df.index)

    gap_map = {"none": 75.0, "basic": 50.0, "paid": 25.0, "season ticket": 0.0}
    if "membership_category" in col:
        gap     = df[col["membership_category"]].astype(str).str.lower().str.strip().map(gap_map).fillna(75.0)
        gap_s   = gap * 0.25
    else:
        gap_s   = pd.Series(18.75, index=df.index)

    return (email_s + inapp_s + gap_s).clip(0, 75)


def compute_channel_preference(df: pd.DataFrame, col: dict) -> pd.Series:
    threshold = 0.05
    e_ctr = _email_ctr(df, col)
    i_ctr = _inapp_ctr(df, col)

    def _pref(e, i):
        e_ok = e >= threshold
        i_ok = i >= threshold
        if e_ok and i_ok:
            ratio = e / max(i, 1e-6)
            if 0.8 <= ratio <= 1.25:
                return "Both"
            return "Email" if e > i else "App"
        if e_ok:
            return "Email"
        if i_ok:
            return "App"
        return "Neither"

    return pd.Series([_pref(e, i) for e, i in zip(e_ctr, i_ctr)], index=df.index)


def assign_journey_stage(row: pd.Series) -> str:
    tier = row.get("_membership_tier", 0)
    eng  = row["engagement_score"]
    if tier == 3:
        return "Stage 5 — Season Ticket Holder"
    if tier == 2:
        return "Stage 4 — Paid Member"
    if tier == 1 and eng >= 40:
        return "Stage 3 — Basic Member, Engaged"
    if tier == 0 and eng >= 40:
        return "Stage 2 — No Membership, Active"
    return "Stage 1 — No Membership, Low Engagement"


def assign_segment(row: pd.Series) -> str:
    e      = row["engagement_score"]
    c      = row["commercial_score"]
    l      = row["loyalty_score"]
    churn  = row["churn_risk_label"]   # HIGH / MED / LOW (percentile-based)
    tenure = row.get("tenure_days", 365)

    if l >= 60 and c >= 40:
        return "Loyal Fans"
    if e >= 65 and c < 42:            # rescue engaged-but-not-commercial fans before Win Back
        return "High Potential"
    if e < 32 and c < 32 and tenure > 90:   # truly unactivated fans before Win Back
        return "Dormant"
    if churn == "HIGH":
        return "Win Back"
    return "Casual"


def process_data(df: pd.DataFrame, col: dict) -> pd.DataFrame:
    out = df.copy()

    out["age_group"]        = out[col["age"]].apply(assign_age_group) if "age" in col else "Unknown"
    out["engagement_score"] = compute_engagement_score(out, col).round(1)

    comm, recency_days      = compute_commercial_score(out, col)
    out["commercial_score"] = comm.round(1)
    out["recency_days"]     = recency_days.round(0)

    loy, tenure_days        = compute_loyalty_score(out, col)
    out["loyalty_score"]    = loy.round(1)
    out["tenure_days"]      = tenure_days.round(0)

    # Churn risk = base (purchase + app + email recency) + low-engagement penalty
    out["churn_risk_index"] = (
        compute_churn_risk_base(out, col) + (100 - out["engagement_score"]) * 0.15
    ).clip(0, 100).round(1)
    # Percentile-based thirds so HIGH/MED/LOW are always roughly equal in size
    p33 = out["churn_risk_index"].quantile(0.33)
    p67 = out["churn_risk_index"].quantile(0.67)
    out["churn_risk_label"] = out["churn_risk_index"].apply(
        lambda x: "HIGH" if x >= p67 else ("MED" if x >= p33 else "LOW")
    )

    # Conversion probability = base (email CTR + inapp CTR + membership gap) + commercial component
    out["conversion_probability"] = (
        compute_conversion_probability_base(out, col) + out["commercial_score"] * 0.25
    ).clip(0, 100).round(1)

    # Channel preference
    out["channel_preference"] = compute_channel_preference(out, col)

    # Membership tier helper (numeric, for journey stage)
    tier_map = {"none": 0, "basic": 1, "paid": 2, "season ticket": 3}
    if "membership_category" in col:
        out["_membership_tier"] = (
            out[col["membership_category"]].astype(str).str.lower().str.strip()
            .map(tier_map).fillna(0).astype(int)
        )
    else:
        out["_membership_tier"] = 0

    out["journey_stage"]    = out.apply(assign_journey_stage, axis=1)
    out["composite_score"]  = (
        (out["engagement_score"] + out["commercial_score"] + out["loyalty_score"]) / 3
    ).round(1)
    out["segment"]          = out.apply(assign_segment, axis=1)

    return out


# ── Sample CSV ────────────────────────────────────────────────────────────────

def generate_sample_csv() -> bytes:
    rng   = np.random.default_rng(42)
    n     = 400
    today = datetime(2025, 4, 1)

    # Demographics (same distributions as before)
    ages = np.concatenate([
        rng.integers(6, 13, 40),
        rng.integers(13, 26, 120),
        rng.integers(26, 50, 160),
        rng.integers(50, 80, 80),
    ])
    rng.shuffle(ages)
    genders   = rng.choice(["M", "F", "Non-binary"], n, p=[0.54, 0.41, 0.05])
    countries = rng.choice(
        ["England", "Scotland", "Wales", "Ireland", "USA", "Germany", "Spain", "Other"],
        n, p=[0.50, 0.12, 0.08, 0.07, 0.08, 0.05, 0.05, 0.05],
    )

    # Fan profile
    mem_cats  = rng.choice(["None", "Basic", "Paid", "Season Ticket"], n, p=[0.40, 0.25, 0.20, 0.15])
    fan_types = rng.choice(["Fan", "Fantasy", "Follower"], n, p=[0.65, 0.20, 0.15])
    has_app   = rng.choice(["Yes", "No"], n, p=[0.70, 0.30])

    # Tenure
    join_days = rng.exponential(700, n).clip(30, 2190).astype(int)

    # Membership tier multiplier for commercial activity
    tier_mult = np.array([{"None": 0.3, "Basic": 0.7, "Paid": 1.2, "Season Ticket": 2.0}[m] for m in mem_cats])

    # Email channel
    email_campaigns = rng.integers(10, 52, n)
    open_rate       = rng.uniform(0.15, 0.65, n)
    click_rate      = rng.uniform(0.03, 0.25, n) * open_rate
    email_opens     = (email_campaigns * open_rate).astype(int)
    email_clicks    = (email_campaigns * click_rate).astype(int)

    # In-app channel (only active fans with app)
    app_mask         = has_app == "Yes"
    inapp_campaigns  = np.where(app_mask, rng.integers(20, 100, n), 0)
    inapp_open_rate  = np.where(app_mask, rng.uniform(0.20, 0.75, n), 0.0)
    inapp_click_rate = np.where(app_mask, rng.uniform(0.05, 0.40, n) * inapp_open_rate, 0.0)
    inapp_opens      = (inapp_campaigns * inapp_open_rate).astype(int)
    inapp_clicks     = (inapp_campaigns * inapp_click_rate).astype(int)

    # Content
    art_views = rng.lognormal(3.0, 1.3, n).clip(0, 400).astype(int)

    # Purchases
    tix    = (rng.choice([0,1,2,3,5,8,10,15], n, p=[0.28,0.20,0.15,0.12,0.10,0.07,0.05,0.03]) * tier_mult).astype(int)
    mship  = (rng.choice([0,1,2,3], n, p=[0.50,0.26,0.14,0.10]) * (tier_mult + 0.3)).clip(0, 5).astype(int)
    retail = (rng.choice([0,1,2,3,5,8], n, p=[0.33,0.26,0.16,0.13,0.08,0.04]) * tier_mult).astype(int)
    revenue = (
        tix    * rng.uniform(20, 65, n) +
        mship  * rng.choice([49, 99, 149, 199], n) +
        retail * rng.uniform(15, 85, n)
    ).round(2)

    has_purchases = (tix + mship + retail) > 0

    # Helper: convert days-ago float (or nan) to date string
    def _d(days_ago):
        if np.isnan(days_ago):
            return ""
        return (today - timedelta(days=int(days_ago))).strftime("%Y-%m-%d")

    # Membership tier shift: Season Ticket → more recent, None → older
    tier_shift_purchase = np.array([{"None": 55, "Basic": 20, "Paid": -10, "Season Ticket": -25}[m] for m in mem_cats])
    tier_shift_app      = np.array([{"None": 25, "Basic": 10, "Paid": -5,  "Season Ticket": -15}[m] for m in mem_cats])
    tier_shift_email    = np.array([{"None": 20, "Basic": 8,  "Paid": -5,  "Season Ticket": -10}[m] for m in mem_cats])

    def _piecewise(rng, n, breaks, probs, shift, lo_cap, hi_cap):
        """Piecewise uniform days with membership tier shift."""
        buckets = rng.choice(len(probs), size=n, p=probs)
        out = np.zeros(n, dtype=float)
        for i, (lo, hi) in enumerate(zip(breaks[:-1], breaks[1:])):
            mask = buckets == i
            if mask.any():
                out[mask] = rng.uniform(lo, hi, mask.sum())
        return np.clip(out + shift, lo_cap, hi_cap).astype(int)

    # Last_Purchase_Date: 30% ≤60d, 40% 61-180d, 30% >180d
    lp_all  = _piecewise(rng, n, [0, 60, 180, 730], [0.30, 0.40, 0.30], tier_shift_purchase, 0, 730)
    lp_days = np.where(has_purchases, lp_all.astype(float), np.nan)
    lp_safe = np.where(np.isnan(lp_days), 0, lp_days)
    fp_days = np.where(has_purchases, np.minimum(join_days - 1, lp_safe + rng.integers(30, 400, n)).clip(0), np.nan)

    # Last_App_Open: 40% ≤30d, 35% 31-90d, 25% >90d
    la_all  = _piecewise(rng, n, [0, 30, 90, 365], [0.40, 0.35, 0.25], tier_shift_app, 0, 365)
    la_days = np.where(app_mask, la_all.astype(float), np.nan)
    la_safe = np.where(np.isnan(la_days), 0, la_days)
    fa_days = np.where(app_mask, np.minimum(join_days - 1, la_safe + rng.integers(30, 300, n)).clip(0), np.nan)

    # Last_Email_Open: 45% ≤30d, 35% 31-90d, 20% >90d
    has_email = email_opens > 0
    le_all  = _piecewise(rng, n, [0, 30, 90, 365], [0.45, 0.35, 0.20], tier_shift_email, 0, 365)
    le_days = np.where(has_email, le_all.astype(float), np.nan)
    le_safe = np.where(np.isnan(le_days), 0, le_days)
    fe_days = np.where(has_email, np.minimum(join_days - 1, le_safe + rng.integers(30, 400, n)).clip(0), np.nan)

    # Article dates: 40% ≤14d, 40% 15-60d, 20% >60d
    has_art  = art_views > 0
    lar_all  = _piecewise(rng, n, [0, 14, 60, 180], [0.40, 0.40, 0.20], np.zeros(n, dtype=int), 0, 180)
    lar_days = np.where(has_art, lar_all.astype(float), np.nan)
    lar_safe = np.where(np.isnan(lar_days), 0, lar_days)
    far_days = np.where(has_art, np.minimum(join_days - 1, lar_safe + rng.integers(30, 365, n)).clip(0), np.nan)

    df_out = pd.DataFrame({
        "User_ID":                  [f"FAN{i:04d}" for i in range(1, n + 1)],
        "Age":                      ages,
        "Gender":                   genders,
        "Country":                  countries,
        "Membership_Category":      mem_cats,
        "Fan_Type":                 fan_types,
        "HAS_APP":                  has_app,
        "Email_Opens":              email_opens,
        "Email_Clicks":             email_clicks,
        "Email_Campaigns_Received": email_campaigns,
        "InApp_Opens":              inapp_opens,
        "InApp_Clicks":             inapp_clicks,
        "InApp_Campaigns_Received": inapp_campaigns,
        "Article_Views":            art_views,
        "Ticket_Purchases":         tix,
        "Membership_Purchases":     mship,
        "Retail_Purchases":         retail,
        "Total_Revenue":            revenue,
        "First_Purchase_Date":      [_d(d) for d in fp_days],
        "Last_Purchase_Date":       [_d(d) for d in lp_days],
        "First_App_Open":           [_d(d) for d in fa_days],
        "Last_App_Open":            [_d(d) for d in la_days],
        "First_Email_Open":         [_d(d) for d in fe_days],
        "Last_Email_Open":          [_d(d) for d in le_days],
        "First_Article_View":       [_d(d) for d in far_days],
        "Last_Article_View":        [_d(d) for d in lar_days],
        "Join_Date":                [(today - timedelta(days=int(d))).strftime("%Y-%m-%d") for d in join_days],
    })
    buf = io.BytesIO()
    df_out.to_csv(buf, index=False)
    return buf.getvalue()


# ── Charts ────────────────────────────────────────────────────────────────────

def _seg_colors(segments) -> list[str]:
    return [SEGMENT_INFO.get(s, {"color": "#6b7280"})["color"] for s in segments]


def chart_segment_donut(df: pd.DataFrame) -> go.Figure:
    counts = df["segment"].value_counts()
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=0.62,
        marker_colors=_seg_colors(counts.index),
        textinfo="label+percent", textfont_size=10,
        hovertemplate="<b>%{label}</b><br>%{value} fans (%{percent})<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_BASE, height=340,
                      title=dict(text="Fan Segment Distribution", x=0.02, y=0.97),
                      showlegend=False)
    return fig


def chart_age_segment_bar(df: pd.DataFrame) -> go.Figure:
    order = ["Child", "Young Adult", "Adult", "Senior", "Unknown"]
    pivot = df.groupby(["age_group", "segment"]).size().reset_index(name="count")
    fig   = go.Figure()
    for seg in SEGMENT_INFO:
        sub = pivot[pivot["segment"] == seg]
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            name=seg, x=sub["age_group"], y=sub["count"],
            marker_color=SEGMENT_INFO[seg]["color"],
            hovertemplate=f"<b>{seg}</b><br>%{{x}}: %{{y}} fans<extra></extra>",
        ))
    fig.update_layout(
        **PLOTLY_BASE, height=340, barmode="stack",
        title=dict(text="Age Group × Segment", x=0.02, y=0.97),
        xaxis=dict(categoryorder="array", categoryarray=order, gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
        legend=dict(bgcolor="#13161d", bordercolor="#1f2937", borderwidth=1, font_size=9),
    )
    return fig


def chart_landscape(df: pd.DataFrame) -> go.Figure:
    size = ((df["composite_score"] / 100) * 12 + 4).clip(4, 16)
    fig  = go.Figure(go.Scatter(
        x=df["engagement_score"], y=df["commercial_score"],
        mode="markers",
        marker=dict(
            color=df["loyalty_score"], colorscale="Viridis",
            size=size, opacity=0.72, showscale=True,
            colorbar=dict(title="Loyalty", thickness=12, len=0.75, tickfont_size=9),
            line=dict(color="#0a0c10", width=0.4),
        ),
        text=df["segment"],
        hovertemplate="<b>%{text}</b><br>Engagement: %{x:.0f}  |  Commercial: %{y:.0f}<br>Loyalty: %{marker.color:.0f}<extra></extra>",
    ))
    fig.add_hline(y=50, line_dash="dash", line_color="#2a2f3d", line_width=1)
    fig.add_vline(x=50, line_dash="dash", line_color="#2a2f3d", line_width=1)
    fig.update_layout(
        **PLOTLY_BASE, height=400,
        title=dict(text="Fan Landscape — Engagement × Commercial  (colour = Loyalty)", x=0.02, y=0.97),
        xaxis=dict(title="Engagement Score", range=[0, 102], gridcolor="#1f2937"),
        yaxis=dict(title="Commercial Score", range=[0, 102], gridcolor="#1f2937"),
    )
    return fig


def chart_scores_by_segment(df: pd.DataFrame) -> go.Figure:
    means = df.groupby("segment")[["engagement_score", "commercial_score", "loyalty_score"]].mean().reset_index()
    fig   = go.Figure()
    for col_name, color, label in [
        ("engagement_score", "#3d9cf0", "Engagement"),
        ("commercial_score", "#c8f135", "Commercial"),
        ("loyalty_score",    "#22c55e", "Loyalty"),
    ]:
        fig.add_trace(go.Bar(name=label, x=means["segment"], y=means[col_name].round(1),
                             marker_color=color, opacity=0.85))
    fig.update_layout(
        **PLOTLY_BASE, height=360, barmode="group",
        title=dict(text="Average Scores by Segment", x=0.02, y=0.97),
        xaxis=dict(gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937", range=[0, 105]),
        legend=dict(bgcolor="#13161d", bordercolor="#1f2937", borderwidth=1, font_size=10),
    )
    return fig


def chart_commercial_opportunity(df: pd.DataFrame) -> go.Figure:
    opp = (
        df.groupby("segment")
        .agg(fans=("composite_score", "count"), avg_c=("commercial_score", "mean"))
        .reset_index().sort_values("avg_c")
    )
    fig = go.Figure(go.Bar(
        x=opp["avg_c"].round(1), y=opp["segment"], orientation="h",
        marker_color=_seg_colors(opp["segment"]),
        text=opp["fans"].astype(str) + " fans", textposition="outside", textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Avg commercial score: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=360,
        title=dict(text="Commercial Score by Segment", x=0.02, y=0.97),
        xaxis=dict(title="Avg Commercial Score", range=[0, 115], gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
    )
    return fig


def chart_age_scores(df: pd.DataFrame) -> go.Figure:
    order    = ["Child", "Young Adult", "Adult", "Senior"]
    means    = df[df["age_group"].isin(order)].groupby("age_group")[["engagement_score", "commercial_score", "loyalty_score"]].mean().reset_index()
    radar_df = means.set_index("age_group").reindex(order)
    cats     = ["Engagement", "Commercial", "Loyalty"]
    fig      = go.Figure()
    colors_ag = ["#a78bfa", "#3d9cf0", "#c8f135", "#22c55e"]
    for i, group in enumerate(order):
        if group not in radar_df.index:
            continue
        row  = radar_df.loc[group]
        vals = [row["engagement_score"], row["commercial_score"], row["loyalty_score"]]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=cats + [cats[0]],
            fill="toself", name=group,
            line_color=colors_ag[i], fillcolor=colors_ag[i], opacity=0.25,
        ))
    fig.update_layout(
        **PLOTLY_BASE, height=360,
        title=dict(text="Score Profile by Age Group", x=0.02, y=0.97),
        polar=dict(
            bgcolor="#0d1117",
            radialaxis=dict(range=[0, 100], gridcolor="#2a2f3d", tickfont_size=8),
            angularaxis=dict(gridcolor="#2a2f3d"),
        ),
        legend=dict(bgcolor="#13161d", bordercolor="#1f2937", borderwidth=1, font_size=10),
    )
    return fig


# ── New v2 charts ─────────────────────────────────────────────────────────────

def chart_churn_by_segment(df: pd.DataFrame) -> go.Figure:
    counts = df.groupby(["segment", "churn_risk_label"]).size().reset_index(name="count")
    colors = {"HIGH": "#ef4444", "MED": "#f59e0b", "LOW": "#22c55e"}
    fig    = go.Figure()
    for risk in ["HIGH", "MED", "LOW"]:
        sub = counts[counts["churn_risk_label"] == risk]
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            name=risk, x=sub["segment"], y=sub["count"],
            marker_color=colors[risk],
            hovertemplate=f"<b>{risk}</b><br>%{{x}}: %{{y}} fans<extra></extra>",
        ))
    fig.update_layout(
        **PLOTLY_BASE, height=340, barmode="stack",
        title=dict(text="Churn Risk Distribution by Segment", x=0.02, y=0.97),
        xaxis=dict(gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
        legend=dict(bgcolor="#13161d", bordercolor="#1f2937", borderwidth=1, font_size=10),
    )
    return fig


def chart_journey_stage_funnel(df: pd.DataFrame) -> go.Figure:
    counts = df["journey_stage"].value_counts().reindex(JOURNEY_STAGE_ORDER, fill_value=0)
    fig    = go.Figure(go.Bar(
        x=counts.values, y=counts.index, orientation="h",
        marker_color=JOURNEY_STAGE_COLORS,
        text=counts.values, textposition="inside", textfont=dict(color="#0a0c10", size=10),
        hovertemplate="<b>%{y}</b><br>%{x} fans<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=280,
        title=dict(text="Fan Journey Stage Distribution", x=0.02, y=0.97),
        xaxis=dict(gridcolor="#1f2937"),
        yaxis=dict(autorange="reversed", gridcolor="#1f2937"),
    )
    return fig


def chart_channel_preference(df: pd.DataFrame) -> go.Figure:
    pivot     = df.groupby(["segment", "channel_preference"]).size().reset_index(name="count")
    seg_total = pivot.groupby("segment")["count"].transform("sum")
    pivot["pct"] = (pivot["count"] / seg_total * 100).round(1)
    ch_colors = {"Email": "#3d9cf0", "App": "#c8f135", "Both": "#22c55e", "Neither": "#6b7280"}
    fig = go.Figure()
    for ch in ["Email", "App", "Both", "Neither"]:
        sub = pivot[pivot["channel_preference"] == ch]
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            name=ch, x=sub["segment"], y=sub["pct"],
            marker_color=ch_colors[ch],
            text=sub["pct"].apply(lambda x: f"{x:.0f}%"),
            textposition="inside", textfont=dict(size=9, color="#0a0c10"),
            hovertemplate=f"<b>{ch}</b><br>%{{x}}: %{{y:.0f}}%<extra></extra>",
        ))
    fig.update_layout(
        **PLOTLY_BASE, height=340, barmode="stack",
        title=dict(text="Channel Preference by Segment (% of segment)", x=0.02, y=0.97),
        xaxis=dict(gridcolor="#1f2937"),
        yaxis=dict(range=[0, 105], title="% of segment", gridcolor="#1f2937"),
        legend=dict(bgcolor="#13161d", bordercolor="#1f2937", borderwidth=1, font_size=10),
    )
    return fig


def chart_conversion_by_stage(df: pd.DataFrame) -> go.Figure:
    means = (
        df[df["journey_stage"].isin(JOURNEY_STAGE_ORDER)]
        .groupby("journey_stage")["conversion_probability"]
        .mean().reindex(JOURNEY_STAGE_ORDER, fill_value=0).round(1)
    )
    fig = go.Figure(go.Bar(
        x=means.values, y=means.index, orientation="h",
        marker_color=JOURNEY_STAGE_COLORS,
        text=means.values.astype(str), textposition="outside", textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Avg Conversion Probability: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=280,
        title=dict(text="Avg Conversion Probability by Journey Stage", x=0.02, y=0.97),
        xaxis=dict(range=[0, 115], gridcolor="#1f2937"),
        yaxis=dict(autorange="reversed", gridcolor="#1f2937"),
    )
    return fig


# ── Report helpers ────────────────────────────────────────────────────────────

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def generate_csv_template() -> bytes:
    headers = [
        "User_ID", "Age", "Gender", "Country", "Membership_Category", "Fan_Type", "HAS_APP",
        "Email_Opens", "Email_Clicks", "Email_Campaigns_Received",
        "InApp_Opens", "InApp_Clicks", "InApp_Campaigns_Received", "Article_Views",
        "Ticket_Purchases", "Membership_Purchases", "Retail_Purchases", "Total_Revenue",
        "First_Purchase_Date", "Last_Purchase_Date", "First_App_Open", "Last_App_Open",
        "First_Email_Open", "Last_Email_Open", "First_Article_View", "Last_Article_View",
        "Join_Date",
    ]
    buf = io.StringIO()
    buf.write(",".join(headers) + "\n")
    return buf.getvalue().encode()


def segment_summary(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    s = (
        df.groupby("segment")
        .agg(
            Fan_Count           =("composite_score", "count"),
            Avg_Engagement      =("engagement_score", "mean"),
            Avg_Commercial      =("commercial_score", "mean"),
            Avg_Loyalty         =("loyalty_score",    "mean"),
            Avg_Composite       =("composite_score",  "mean"),
            Avg_Churn_Risk      =("churn_risk_index", "mean"),
            Avg_Conversion_Prob =("conversion_probability", "mean"),
        )
        .round(1).reset_index()
    )
    s["Pct_of_Base"]   = (s["Fan_Count"] / total * 100).round(1)
    s["Risk"]          = s["segment"].map({k: v["risk"] for k, v in SEGMENT_INFO.items()})
    s["Recommendation"] = s["segment"].map({k: v["recommendation"] for k, v in SEGMENT_INFO.items()})
    return s.sort_values("Avg_Composite", ascending=False)


def _pdf_safe(text: str) -> str:
    return (
        str(text)
        .replace("\u2014", " - ")   # em dash
        .replace("\u2013", "-")     # en dash
        .replace("\u2022", "-")     # bullet
        .replace("\u00b7", ".")     # middle dot
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )


def generate_pdf_report(df: pd.DataFrame, club_name: str) -> bytes:
    from fpdf import FPDF

    today_str = datetime.today().strftime("%Y-%m-%d")
    total     = len(df)
    high_val  = int(df["segment"].isin(["Loyal Fans"]).sum())
    at_risk   = int(df["segment"].isin(["Win Back", "Dormant"]).sum())
    pot       = int(df["segment"].isin(["High Potential"]).sum())
    avg_e     = df["engagement_score"].mean()
    avg_c     = df["commercial_score"].mean()
    avg_l     = df["loyalty_score"].mean()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    ew = pdf.w - pdf.l_margin - pdf.r_margin  # effective width

    # Title
    pdf.set_font("Helvetica", "B", 20)
    title = _pdf_safe(f"{club_name} — Fan Segmentation Report" if club_name else "Fan Segmentation Report")
    pdf.cell(0, 12, title, ln=True, align="C")
    pdf.set_font("Helvetica", size=9)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 7, f"Generated by FootIntel  |  {today_str}", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Executive summary
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Executive Summary", ln=True)
    pdf.set_font("Helvetica", size=10)
    for r in [
        f"Total fans analysed:               {total:,}",
        f"Loyal Fans (high-value):            {high_val:,}  ({high_val/total*100:.0f}% of base)",
        f"High Potential (growth):            {pot:,}  ({pot/total*100:.0f}% of base)",
        f"Win Back / Dormant (action needed): {at_risk:,}  ({at_risk/total*100:.0f}% of base)",
        f"Avg Engagement: {avg_e:.1f}   Avg Commercial: {avg_c:.1f}   Avg Loyalty: {avg_l:.1f}",
    ]:
        pdf.cell(0, 6, _pdf_safe(r), ln=True)
    pdf.ln(5)

    # Segment summary table
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Segment Summary", ln=True)
    col_w   = [38, 16, 22, 22, 22, 22, 20, 14]
    headers = ["Segment", "Fans", "Avg Eng", "Avg Com", "Avg Loy", "Avg Comp", "Churn Idx", "Risk"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", size=8)
    for _, row in segment_summary(df).iterrows():
        pdf.cell(col_w[0], 6, _pdf_safe(str(row["segment"])), border=1)
        pdf.cell(col_w[1], 6, str(int(row["Fan_Count"])), border=1, align="C")
        pdf.cell(col_w[2], 6, f"{row['Avg_Engagement']:.1f}", border=1, align="C")
        pdf.cell(col_w[3], 6, f"{row['Avg_Commercial']:.1f}", border=1, align="C")
        pdf.cell(col_w[4], 6, f"{row['Avg_Loyalty']:.1f}", border=1, align="C")
        pdf.cell(col_w[5], 6, f"{row['Avg_Composite']:.1f}", border=1, align="C")
        pdf.cell(col_w[6], 6, f"{row['Avg_Churn_Risk']:.1f}", border=1, align="C")
        pdf.cell(col_w[7], 6, _pdf_safe(str(row["Risk"])), border=1, align="C")
        pdf.ln()
    pdf.ln(5)

    # Churn risk summary
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Churn Risk Summary", ln=True)
    pdf.set_font("Helvetica", size=10)
    churn_counts = df["churn_risk_label"].value_counts()
    for label in ["HIGH", "MED", "LOW"]:
        cnt = int(churn_counts.get(label, 0))
        pdf.cell(0, 6, _pdf_safe(f"  {label}:  {cnt:,} fans  ({cnt/total*100:.0f}%)"), ln=True)
    pdf.ln(3)
    # High churn by segment
    hc = df[df["churn_risk_label"] == "HIGH"].groupby("segment").size().reset_index(name="count").sort_values("count", ascending=False)
    if not hc.empty:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, "HIGH risk fans by segment:", ln=True)
        pdf.set_font("Helvetica", size=9)
        for _, row in hc.iterrows():
            pdf.cell(0, 5, _pdf_safe(f"  {row['segment']}:  {int(row['count'])} fans"), ln=True)
    pdf.ln(5)

    # Conversion opportunity summary
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Conversion Opportunity Summary", ln=True)
    pdf.set_font("Helvetica", size=10)
    stage_counts = df["journey_stage"].value_counts()
    for stage in JOURNEY_STAGE_ORDER:
        cnt = int(stage_counts.get(stage, 0))
        avg_cp = df[df["journey_stage"] == stage]["conversion_probability"].mean() if cnt > 0 else 0
        pdf.cell(0, 6, _pdf_safe(f"  {stage}: {cnt:,} fans  (avg conversion score: {avg_cp:.1f})"), ln=True)
    candidates = int(df[df["journey_stage"].isin(["Stage 2 — No Membership, Active", "Stage 3 — Basic Member, Engaged"])].shape[0])
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, _pdf_safe(f"Stage 2+3 upgrade candidates: {candidates:,} fans"), ln=True)
    pdf.ln(5)

    # Channel preference breakdown
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Channel Preference Breakdown", ln=True)
    ch_counts = df["channel_preference"].value_counts()
    pdf.set_font("Helvetica", size=10)
    for ch in ["Email", "App", "Both", "Neither"]:
        cnt = int(ch_counts.get(ch, 0))
        pdf.cell(0, 6, _pdf_safe(f"  {ch}:  {cnt:,} fans  ({cnt/total*100:.0f}%)"), ln=True)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, "Dominant channel by segment:", ln=True)
    pdf.set_font("Helvetica", size=9)
    ch_seg = df.groupby(["segment", "channel_preference"]).size().reset_index(name="count")
    for seg in df["segment"].unique():
        sub = ch_seg[ch_seg["segment"] == seg].sort_values("count", ascending=False)
        if not sub.empty:
            dom = sub.iloc[0]["channel_preference"]
            pdf.cell(0, 5, _pdf_safe(f"  {seg}:  {dom}"), ln=True)
    pdf.ln(5)

    # Age breakdown table
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Age Group Breakdown", ln=True)
    age_table = (
        df.groupby("age_group")
        .agg(Count=("composite_score","count"), Avg_Engagement=("engagement_score","mean"),
             Avg_Commercial=("commercial_score","mean"), Avg_Loyalty=("loyalty_score","mean"),
             Avg_Composite=("composite_score","mean"))
        .round(1).reset_index()
    )
    age_w = [38, 18, 28, 28, 28, 28]
    age_h = ["Age Group", "Count", "Avg Eng", "Avg Com", "Avg Loy", "Avg Comp"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 230, 230)
    for i, h in enumerate(age_h):
        pdf.cell(age_w[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", size=8)
    for _, row in age_table.iterrows():
        pdf.cell(age_w[0], 6, _pdf_safe(str(row["age_group"])), border=1)
        pdf.cell(age_w[1], 6, str(int(row["Count"])), border=1, align="C")
        pdf.cell(age_w[2], 6, f"{row['Avg_Engagement']:.1f}", border=1, align="C")
        pdf.cell(age_w[3], 6, f"{row['Avg_Commercial']:.1f}", border=1, align="C")
        pdf.cell(age_w[4], 6, f"{row['Avg_Loyalty']:.1f}", border=1, align="C")
        pdf.cell(age_w[5], 6, f"{row['Avg_Composite']:.1f}", border=1, align="C")
        pdf.ln()
    pdf.ln(5)

    # Recommendations
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Segment Recommendations", ln=True)
    seg_counts = df["segment"].value_counts()
    for seg, info in SEGMENT_INFO.items():
        count = int(seg_counts.get(seg, 0))
        if count == 0:
            continue
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, _pdf_safe(f"{seg}  ({count:,} fans  |  Risk: {info['risk']})"), ln=True)
        pdf.set_font("Helvetica", size=8)
        pdf.multi_cell(ew, 5, _pdf_safe(info["recommendation"]))
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(ew, 5, _pdf_safe("Actions: " + "  |  ".join(info["actions"])))
        pdf.ln(2)

    # Footer
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, f"FootIntel  |  Fan Intelligence Platform  |  {today_str}", align="C")

    return bytes(pdf.output())


# ── Fan Acquisition functions ─────────────────────────────────────────────────

def compute_acquisition_data(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    if "country" not in col_map:
        return pd.DataFrame()
    country_col = col_map["country"]
    grp = df.groupby(country_col).agg(
        fan_count=("engagement_score", "count"),
        avg_engagement=("engagement_score", "mean"),
        avg_commercial=("commercial_score", "mean"),
        avg_loyalty=("loyalty_score", "mean"),
    ).reset_index()
    grp.columns = ["country", "fan_count", "avg_engagement", "avg_commercial", "avg_loyalty"]
    total = grp["fan_count"].sum()
    grp["fan_share"] = grp["fan_count"] / total * 100
    grp["growth_headroom"] = (100 - grp["fan_share"]).clip(0, 100)
    grp["acquisition_score"] = (
        grp["avg_engagement"] * 0.30 +
        grp["avg_commercial"] * 0.30 +
        grp["growth_headroom"] * 0.40
    ).round(1)
    grp["iso"] = grp["country"].map(COUNTRY_ISO)
    return grp.sort_values("acquisition_score", ascending=False).reset_index(drop=True)


def chart_acquisition_map(acq_df: pd.DataFrame) -> go.Figure:
    map_data = acq_df[acq_df["iso"].notna()].groupby("iso").agg(
        acquisition_score=("acquisition_score", "max"),
        country=("country", "first"),
    ).reset_index()
    fig = go.Figure(go.Choropleth(
        locations=map_data["iso"],
        z=map_data["acquisition_score"],
        text=map_data["country"],
        colorscale="Viridis",
        zmin=0, zmax=100,
        colorbar=dict(
            title="Priority Score", thickness=12, len=0.75,
            tickfont=dict(size=9, color="#9ca3af"),
            title_font=dict(color="#9ca3af"),
        ),
        hovertemplate="<b>%{text}</b><br>Priority Score: %{z:.1f}<extra></extra>",
        marker_line_color="#1f2937",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=380,
        title=dict(text="Fan Acquisition Opportunity Map", x=0.02, y=0.97),
        geo=dict(
            bgcolor="#0d1117", landcolor="#13161d",
            coastlinecolor="#2a2f3d", countrycolor="#2a2f3d",
            showframe=False, showcoastlines=True,
            projection_type="natural earth",
        ),
    )
    return fig


def chart_acquisition_priority_bar(acq_df: pd.DataFrame) -> go.Figure:
    d = acq_df[~acq_df["country"].isin(["Other"])].sort_values("acquisition_score")
    colors = ["#c8f135" if s >= 70 else "#f59e0b" if s >= 50 else "#3d9cf0" for s in d["acquisition_score"]]
    fig = go.Figure(go.Bar(
        x=d["acquisition_score"], y=d["country"], orientation="h",
        marker_color=colors,
        text=d["acquisition_score"].round(1), textposition="outside", textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Acquisition Score: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=320,
        title=dict(text="Acquisition Priority Score by Region (0–100)", x=0.02, y=0.97),
        xaxis=dict(range=[0, 115], gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
    )
    return fig


def chart_acquisition_landscape(acq_df: pd.DataFrame) -> go.Figure:
    d = acq_df[~acq_df["country"].isin(["Other"])].copy()
    if d.empty:
        return go.Figure()
    size = (d["fan_count"] / d["fan_count"].max() * 30 + 10).clip(10, 40)
    fig = go.Figure(go.Scatter(
        x=d["avg_engagement"], y=d["avg_commercial"],
        mode="markers+text", text=d["country"],
        textposition="top center",
        textfont=dict(size=9, color="#9ca3af"),
        marker=dict(
            size=size, color=d["acquisition_score"],
            colorscale="Viridis", showscale=True,
            colorbar=dict(title="Priority Score", thickness=10, len=0.75, tickfont_size=8),
        ),
        hovertemplate="<b>%{text}</b><br>Engagement: %{x:.1f}  Commercial: %{y:.1f}<extra></extra>",
    ))
    fig.add_hline(y=d["avg_commercial"].mean(), line_dash="dash", line_color="#2a2f3d", line_width=1)
    fig.add_vline(x=d["avg_engagement"].mean(), line_dash="dash", line_color="#2a2f3d", line_width=1)
    fig.update_layout(
        **PLOTLY_BASE, height=360,
        title=dict(text="Market Landscape — Engagement × Commercial  (size = fan count, colour = priority)", x=0.02, y=0.97),
        xaxis=dict(title="Avg Engagement Score", gridcolor="#1f2937"),
        yaxis=dict(title="Avg Commercial Score", gridcolor="#1f2937"),
    )
    return fig


def chart_demographic_gaps(df: pd.DataFrame) -> go.Figure:
    ag = df.groupby("age_group").agg(
        count=("composite_score", "count"),
        avg_commercial=("commercial_score", "mean"),
    ).reindex(["Child", "Young Adult", "Adult", "Senior"], fill_value=0).reset_index()
    total = ag["count"].sum()
    ag["share_pct"] = (ag["count"] / max(total, 1) * 100).round(1)
    colors_ag = ["#a78bfa", "#3d9cf0", "#c8f135", "#22c55e"]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Fan Share %", x=ag["age_group"], y=ag["share_pct"],
        marker_color=colors_ag, opacity=0.6, yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        name="Avg Commercial Score", x=ag["age_group"], y=ag["avg_commercial"].round(1),
        mode="lines+markers",
        line=dict(color="#c8f135", width=2), marker=dict(size=8, color="#c8f135"),
        yaxis="y2",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=320,
        title=dict(text="Demographic Gaps — Fan Share vs. Commercial Value", x=0.02, y=0.97),
        yaxis=dict(title="Fan Share %", gridcolor="#1f2937"),
        yaxis2=dict(title="Avg Commercial Score", overlaying="y", side="right", showgrid=False),
        legend=dict(bgcolor="#13161d", bordercolor="#1f2937", borderwidth=1, font_size=10),
    )
    return fig


# ── Player Intelligence functions ─────────────────────────────────────────────

def assign_synthetic_players(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(77)
    seg_weights = {
        "Loyal Fans":     [0.20, 0.15, 0.20, 0.10, 0.10, 0.05, 0.05, 0.05, 0.05, 0.05],
        "High Potential": [0.15, 0.20, 0.10, 0.15, 0.05, 0.10, 0.05, 0.10, 0.05, 0.05],
        "Win Back":       [0.10, 0.10, 0.15, 0.10, 0.15, 0.10, 0.10, 0.05, 0.10, 0.05],
        "Dormant":        [0.10, 0.08, 0.10, 0.12, 0.12, 0.12, 0.12, 0.08, 0.08, 0.08],
        "Casual":         [0.10, 0.12, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.09, 0.09],
    }
    players = []
    for _, row in df.iterrows():
        w = seg_weights.get(row["segment"], [1/10]*10)
        players.append(rng.choice(SYNTHETIC_PLAYERS, p=w))
    out = df.copy()
    out["_player"] = players
    return out


def compute_player_scores(df_p: pd.DataFrame) -> pd.DataFrame:
    stats = df_p.groupby("_player").agg(
        fan_count=("composite_score", "count"),
        avg_engagement=("engagement_score", "mean"),
        avg_commercial=("commercial_score", "mean"),
        avg_loyalty=("loyalty_score", "mean"),
        loyal_fan_pct=("segment", lambda x: (x == "Loyal Fans").mean() * 100),
        high_potential_pct=("segment", lambda x: (x == "High Potential").mean() * 100),
        avg_conversion=("conversion_probability", "mean"),
    ).round(1).reset_index()
    stats.columns = ["player", "fan_count", "avg_engagement", "avg_commercial",
                     "avg_loyalty", "loyal_fan_pct", "high_potential_pct", "avg_conversion"]
    stats["commercial_value_score"] = (
        stats["avg_engagement"] * 0.30 +
        stats["avg_commercial"] * 0.30 +
        stats["loyal_fan_pct"] * 0.20 +
        stats["avg_conversion"] * 0.20
    ).round(1)
    return stats.sort_values("commercial_value_score", ascending=False).reset_index(drop=True)


def chart_player_value_bar(player_df: pd.DataFrame) -> go.Figure:
    d = player_df.sort_values("commercial_value_score")
    colors = ["#c8f135" if s >= 70 else "#22c55e" if s >= 55 else "#3d9cf0" for s in d["commercial_value_score"]]
    fig = go.Figure(go.Bar(
        x=d["commercial_value_score"], y=d["player"], orientation="h",
        marker_color=colors,
        text=d["commercial_value_score"].round(1), textposition="outside", textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Commercial Value Score: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=340,
        title=dict(text="Player Commercial Value Score (0–100)", x=0.02, y=0.97),
        xaxis=dict(range=[0, 115], gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
    )
    return fig


def chart_player_affinity_heatmap(df_p: pd.DataFrame) -> go.Figure:
    pivot = df_p.groupby(["_player", "segment"])["engagement_score"].mean().unstack(fill_value=0).round(1)
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale="Viridis",
        text=pivot.values.round(1), texttemplate="%{text}", textfont=dict(size=9),
        hovertemplate="<b>%{y} → %{x}</b><br>Avg Engagement: %{z:.1f}<extra></extra>",
        colorbar=dict(title="Avg Engagement", thickness=10, tickfont_size=8),
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=360,
        title=dict(text="Player–Fan Affinity Matrix (avg engagement score per segment)", x=0.02, y=0.97),
    )
    return fig


# ── Sponsorship Intelligence functions ────────────────────────────────────────

def compute_sponsorship_pitch_score(df: pd.DataFrame) -> float:
    loyal_pct    = (df["segment"] == "Loyal Fans").mean() * 100
    high_pot_pct = (df["segment"] == "High Potential").mean() * 100
    avg_c        = df["commercial_score"].mean()
    avg_e        = df["engagement_score"].mean()
    low_churn    = (df["churn_risk_label"] == "LOW").mean() * 100
    return round(min(
        avg_c * 0.35 + avg_e * 0.25 + loyal_pct * 0.20 + high_pot_pct * 0.10 + low_churn * 0.10,
        100,
    ), 1)


def get_sponsor_recommendations(df: pd.DataFrame, col_map: dict) -> list[dict]:
    recs = []
    if "age" in col_map:
        ages = pd.to_numeric(df[col_map["age"]], errors="coerce").dropna()
        young_pct = (ages < 30).mean() * 100
        mid_pct   = ((ages >= 30) & (ages < 50)).mean() * 100
        if young_pct >= 35:
            recs.append({"category": "Gaming & Esports", "fit": "HIGH",
                "reason": f"{young_pct:.0f}% of fanbase is under 30",
                "examples": "EA Sports, Twitch, Epic Games, PlayStation"})
            recs.append({"category": "Energy Drinks & Nutrition", "fit": "HIGH",
                "reason": "Young, active fanbase — high affinity for performance brands",
                "examples": "Red Bull, Monster, Lucozade, Grenade"})
        if mid_pct >= 30:
            recs.append({"category": "Financial Services", "fit": "HIGH",
                "reason": f"{mid_pct:.0f}% of fanbase is 30–50 — prime financial demographic",
                "examples": "Halifax, Revolut, AXA, Barclays"})
    avg_c = df["commercial_score"].mean()
    if avg_c >= 45:
        recs.append({"category": "Premium Sportswear", "fit": "HIGH",
            "reason": f"High commercial score ({avg_c:.0f}/100) — strong purchase intent",
            "examples": "Nike, Adidas, New Balance, Umbro"})
    loyal_pct = (df["segment"] == "Loyal Fans").mean() * 100
    if loyal_pct >= 12:
        recs.append({"category": "Travel & Hospitality", "fit": "MED",
            "reason": f"{loyal_pct:.0f}% Loyal Fans — premium audience for travel brands",
            "examples": "Expedia, Marriott, Hilton, National Express"})
    recs.append({"category": "Streaming & Entertainment", "fit": "MED",
        "reason": "Sports fans over-index on streaming platform subscriptions",
        "examples": "Amazon Prime, DAZN, Sky Sports, TNT Sports"})
    return recs[:5]


def chart_sponsor_age_donut(df: pd.DataFrame) -> go.Figure:
    ag = df["age_group"].value_counts().reindex(["Child", "Young Adult", "Adult", "Senior"], fill_value=0)
    fig = go.Figure(go.Pie(
        labels=ag.index, values=ag.values, hole=0.55,
        marker_colors=["#a78bfa", "#3d9cf0", "#c8f135", "#22c55e"],
        textfont_size=10,
        hovertemplate="<b>%{label}</b><br>%{value} fans (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=300,
        title=dict(text="Fan Age Distribution", x=0.02, y=0.97),
        legend=dict(bgcolor="#13161d", bordercolor="#1f2937", borderwidth=1, font_size=10),
    )
    return fig


def chart_sponsor_commercial_dist(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Histogram(
        x=df["commercial_score"], nbinsx=20,
        marker_color="#c8f135", opacity=0.8,
        hovertemplate="Score ~%{x:.0f}<br>Fans: %{y}<extra></extra>",
    ))
    avg_c = df["commercial_score"].mean()
    fig.add_vline(x=avg_c, line_dash="dash", line_color="#ef4444",
                  annotation_text=f"Avg: {avg_c:.1f}",
                  annotation_font=dict(size=9, color="#ef4444"))
    fig.update_layout(
        **PLOTLY_BASE, height=280,
        title=dict(text="Commercial Score Distribution — Audience Quality for Sponsors", x=0.02, y=0.97),
        xaxis=dict(title="Commercial Score", gridcolor="#1f2937"),
        yaxis=dict(title="Fans", gridcolor="#1f2937"),
    )
    return fig


def chart_sponsor_segment_value(df: pd.DataFrame) -> go.Figure:
    seg_s = df.groupby("segment").agg(
        fans=("composite_score", "count"),
        avg_commercial=("commercial_score", "mean"),
        avg_engagement=("engagement_score", "mean"),
    ).round(1).reset_index().sort_values("avg_commercial", ascending=True)
    colors = _seg_colors(seg_s["segment"])
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Avg Commercial", x=seg_s["avg_commercial"], y=seg_s["segment"],
        orientation="h", marker_color=colors, opacity=0.9,
        text=seg_s["fans"].apply(lambda v: f"{v:,} fans"), textposition="outside", textfont_size=9,
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=300,
        title=dict(text="Audience Quality by Segment — Commercial Score", x=0.02, y=0.97),
        xaxis=dict(range=[0, 115], title="Avg Commercial Score", gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
    )
    return fig


def generate_sponsor_pdf(df: pd.DataFrame, club_name: str) -> bytes:
    from fpdf import FPDF
    today_str   = datetime.today().strftime("%Y-%m-%d")
    total       = len(df)
    pitch_score = compute_sponsorship_pitch_score(df)
    loyal_pct   = (df["segment"] == "Loyal Fans").mean() * 100
    hp_pct      = (df["segment"] == "High Potential").mean() * 100
    avg_c       = df["commercial_score"].mean()
    avg_e       = df["engagement_score"].mean()
    low_churn   = (df["churn_risk_label"] == "LOW").mean() * 100

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=15)
    ew = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, _pdf_safe(f"{club_name} — Sponsorship Intelligence Deck" if club_name else "Sponsorship Intelligence Deck"), ln=True, align="C")
    pdf.set_font("Helvetica", size=9)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 6, f"Generated by FootIntel  |  {today_str}  |  {total:,} fans analysed", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 14)
    score_label = "Excellent" if pitch_score >= 75 else "Good" if pitch_score >= 55 else "Developing"
    pdf.cell(0, 8, _pdf_safe(f"Sponsorship Pitch Score: {pitch_score}/100  -  {score_label}"), ln=True, align="C")
    pdf.ln(4)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Audience Summary", ln=True)
    pdf.set_font("Helvetica", size=10)
    for line in [
        f"Total Fanbase:              {total:,} fans",
        f"Loyal Fans (premium):       {loyal_pct:.0f}% — committed, high-spend audience",
        f"High Potential:             {hp_pct:.0f}% — engaged, conversion-ready",
        f"Low Churn Risk:             {low_churn:.0f}% — stable, long-term audience",
        f"Avg Engagement Score:       {avg_e:.1f}/100",
        f"Avg Commercial Score:       {avg_c:.1f}/100 (purchase propensity indicator)",
    ]:
        pdf.cell(0, 6, _pdf_safe(line), ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Audience Quality by Segment", ln=True)
    seg_s = df.groupby("segment").agg(count=("composite_score","count"), avg_e=("engagement_score","mean"), avg_c=("commercial_score","mean")).round(1).reset_index()
    cw = [50, 22, 28, 28]
    hdrs = ["Segment", "Fans", "Avg Eng.", "Avg Com."]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for i, h in enumerate(hdrs):
        pdf.cell(cw[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", size=9)
    for _, row in seg_s.iterrows():
        pdf.cell(cw[0], 6, _pdf_safe(str(row["segment"])), border=1)
        pdf.cell(cw[1], 6, str(int(row["count"])), border=1, align="C")
        pdf.cell(cw[2], 6, f"{row['avg_e']:.1f}", border=1, align="C")
        pdf.cell(cw[3], 6, f"{row['avg_c']:.1f}", border=1, align="C")
        pdf.ln()
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Key Demographics", ln=True)
    pdf.set_font("Helvetica", size=10)
    ag = df["age_group"].value_counts()
    for g in ["Child", "Young Adult", "Adult", "Senior"]:
        cnt = int(ag.get(g, 0))
        pdf.cell(0, 6, _pdf_safe(f"  {g}:  {cnt:,}  ({cnt/total*100:.0f}%)"), ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Top Sponsor Category Recommendations", ln=True)
    pdf.set_font("Helvetica", size=9)
    for r in get_sponsor_recommendations(df, {}):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, _pdf_safe(f"{r['category']}  [{r['fit']}]"), ln=True)
        pdf.set_font("Helvetica", size=9)
        pdf.multi_cell(ew, 5, _pdf_safe(f"  {r['reason']}"))
        pdf.multi_cell(ew, 5, _pdf_safe(f"  Examples: {r['examples']}"))
        pdf.ln(2)

    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, _pdf_safe(f"FootIntel  |  {today_str}  |  CONFIDENTIAL - NOT FOR DISTRIBUTION"), align="C")
    return bytes(pdf.output())


# ── Matchday Intelligence functions ───────────────────────────────────────────

_SEGMENT_MATCHDAY_SPEND = {
    "Loyal Fans": 85.0, "High Potential": 48.0,
    "Casual": 28.0, "Win Back": 15.0, "Dormant": 6.0,
}


def compute_matchday_data(df: pd.DataFrame, col_map: dict) -> dict:
    df_md = df.copy()
    df_md["matchday_spend_est"] = (
        df_md["segment"].map(_SEGMENT_MATCHDAY_SPEND).fillna(20.0)
        * (df_md["commercial_score"] / 50).clip(0.3, 2.0)
    ).round(2)

    if "ticket_purchases" in col_map:
        tix = pd.to_numeric(df[col_map["ticket_purchases"]], errors="coerce").fillna(0)
        hosp_mask = df_md["segment"].isin(["Loyal Fans", "High Potential"]) & (tix == 0)
    else:
        hosp_mask = df_md["segment"] == "High Potential"

    hospitality_targets = df_md[hosp_mask].nlargest(20, "conversion_probability")

    rev_by_seg = df_md.groupby("segment").agg(
        fan_count=("matchday_spend_est", "count"),
        total_est_revenue=("matchday_spend_est", "sum"),
        avg_spend=("matchday_spend_est", "mean"),
    ).round(2).reset_index()

    ch = df_md["channel_preference"].value_counts()
    both = int(ch.get("Both", 0))
    windows = {
        "Pre-match (Email / Push)": int(ch.get("Email", 0) + both // 2),
        "During Match (App)":       int(ch.get("App", 0) + both // 2),
        "Post-match (Content)":     int(len(df_md) * 0.72),
    }

    hp_count = int((df_md["segment"] == "High Potential").sum())
    return {
        "df_md": df_md,
        "rev_by_seg": rev_by_seg,
        "hospitality_targets": hospitality_targets,
        "windows": windows,
        "hp_count": hp_count,
        "hp_avg_spend": _SEGMENT_MATCHDAY_SPEND["High Potential"],
        "total_est_revenue": df_md["matchday_spend_est"].sum(),
    }


def chart_matchday_revenue_by_segment(rev_df: pd.DataFrame) -> go.Figure:
    d = rev_df.sort_values("total_est_revenue")
    fig = go.Figure(go.Bar(
        x=d["total_est_revenue"].round(0), y=d["segment"], orientation="h",
        marker_color=_seg_colors(d["segment"]),
        text=["£" + f"{v:,.0f}" for v in d["total_est_revenue"]],
        textposition="outside", textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Est. Revenue: £%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=320,
        title=dict(text="Estimated Matchday Revenue by Segment", x=0.02, y=0.97),
        xaxis=dict(title="Estimated Revenue (£)", gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
    )
    return fig


def chart_engagement_windows(windows: dict) -> go.Figure:
    labels, values = list(windows.keys()), list(windows.values())
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=["#3d9cf0", "#c8f135", "#22c55e"],
        text=values, textposition="outside", textfont_size=10,
        hovertemplate="<b>%{x}</b><br>Active fans: %{y:,}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=280,
        title=dict(text="Fan Engagement Windows — Matchday Activity Estimate", x=0.02, y=0.97),
        xaxis=dict(gridcolor="#1f2937"),
        yaxis=dict(title="Estimated Active Fans", gridcolor="#1f2937"),
    )
    return fig


def chart_matchday_avg_spend(rev_df: pd.DataFrame) -> go.Figure:
    d = rev_df.sort_values("avg_spend")
    fig = go.Figure(go.Bar(
        x=d["avg_spend"].round(2), y=d["segment"], orientation="h",
        marker_color=_seg_colors(d["segment"]),
        text=["£" + f"{v:.0f}" for v in d["avg_spend"]],
        textposition="outside", textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Avg spend per fan: £%{x:.2f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=320,
        title=dict(text="Avg Estimated Spend per Fan on Matchday", x=0.02, y=0.97),
        xaxis=dict(title="Avg Spend (£)", gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
    )
    return fig


# ── Custom Metrics Explorer ───────────────────────────────────────────────────

def render_custom_metrics_explorer(df: pd.DataFrame, col_map: dict) -> None:
    mapped_csv = set(col_map.values())
    extra = [c for c in df.columns if c not in mapped_csv and not c.startswith("_")]
    # also exclude computed columns
    computed = {"engagement_score","commercial_score","loyalty_score","churn_risk_index",
                "churn_risk_label","conversion_probability","channel_preference",
                "journey_stage","composite_score","segment","age_group","recency_days",
                "tenure_days","_membership_tier"}
    extra = [c for c in extra if c not in computed]

    if not extra:
        st.info("No extra columns detected beyond the mapped fields.")
        return

    section_heading("Custom Metrics Explorer")
    st.markdown(card(
        '<div style="font-size:11px;color:#9ca3af">Extra columns from your CSV that are not part of the standard '
        'mapping. Numeric columns show distributions and correlation with composite score. '
        'Categorical columns show segment breakdowns.</div>'
    ), unsafe_allow_html=True)

    for col_name in extra[:8]:
        col_data = df[col_name].dropna()
        if len(col_data) == 0:
            continue
        numeric_frac = pd.to_numeric(col_data, errors="coerce").notna().mean()
        if numeric_frac > 0.8:
            num_data = pd.to_numeric(df[col_name], errors="coerce").dropna()
            corr_txt = ""
            if "composite_score" in df.columns:
                corr = num_data.corr(df["composite_score"].reindex(num_data.index))
                if not np.isnan(corr):
                    corr_txt = f"  |  Corr. with composite: {corr:+.2f}"
            fig = go.Figure(go.Histogram(x=num_data, nbinsx=20, marker_color="#3d9cf0", opacity=0.8))
            fig.update_layout(**PLOTLY_BASE, height=220,
                              title=dict(text=f"{col_name} — Distribution{corr_txt}", x=0.02, y=0.97),
                              xaxis=dict(gridcolor="#1f2937"), yaxis=dict(gridcolor="#1f2937"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                            key=f"custom_{col_name}_hist")
        else:
            if "segment" in df.columns:
                pivot = df.groupby([col_name, "segment"]).size().reset_index(name="count")
                fig = go.Figure()
                for seg in SEGMENT_INFO:
                    sub = pivot[pivot["segment"] == seg]
                    if sub.empty:
                        continue
                    fig.add_trace(go.Bar(name=seg, x=sub[col_name].astype(str), y=sub["count"],
                                         marker_color=SEGMENT_INFO[seg]["color"]))
                fig.update_layout(**PLOTLY_BASE, height=240, barmode="stack",
                                  title=dict(text=f"{col_name} — Segment Breakdown", x=0.02, y=0.97),
                                  xaxis=dict(gridcolor="#1f2937"), yaxis=dict(gridcolor="#1f2937"),
                                  legend=dict(bgcolor="#13161d", bordercolor="#1f2937", borderwidth=1, font_size=9))
            else:
                vc = df[col_name].astype(str).value_counts().head(10)
                fig = go.Figure(go.Bar(x=vc.index, y=vc.values, marker_color="#c8f135"))
                fig.update_layout(**PLOTLY_BASE, height=220,
                                  title=dict(text=f"{col_name} — Value Counts", x=0.02, y=0.97),
                                  xaxis=dict(gridcolor="#1f2937"), yaxis=dict(gridcolor="#1f2937"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                            key=f"custom_{col_name}_bar")


# ── App ───────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="margin-bottom:24px">
  <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:4px">
    <span style="font-family:'Syne',sans-serif;font-size:30px;font-weight:800;color:#c8f135;letter-spacing:-1px">FootIntel</span>
    <span style="font-family:'Syne',sans-serif;font-size:16px;font-weight:400;color:#4b5563"> / Fan Segmentation &amp; LTV Analysis</span>
  </div>
  <div style="font-size:11px;color:#6b7280;letter-spacing:.04em">
    Upload fan data &nbsp;·&nbsp; Score engagement, commercial, loyalty, churn &amp; conversion &nbsp;·&nbsp; Identify high-value segments &nbsp;·&nbsp; Act
  </div>
</div>
""", unsafe_allow_html=True)

tab_upload, tab_howto, tab_dashboard, tab_acquisition, tab_player, tab_sponsor, tab_matchday, tab_report = st.tabs([
    "⬆  Upload & Configure",
    "📖  How To Use",
    "📊  Dashboard",
    "🌍  Fan Acquisition",
    "⚽  Player Intelligence",
    "💼  Sponsorship",
    "🏟  Matchday Intelligence",
    "📄  Report",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — UPLOAD
# ─────────────────────────────────────────────────────────────────────────────
with tab_upload:

    cn_col, _ = st.columns([2, 3])
    with cn_col:
        st.text_input("Enter your club name", placeholder="e.g. Chelsea FC", key="club_name")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown(card(
            '<div style="font-size:12px;color:#9ca3af">Upload a CSV of fan data. '
            'FootIntel will auto-detect your columns, let you confirm the mapping, '
            'then score every fan across five dimensions and segment them instantly.</div>'
        ), unsafe_allow_html=True)

        uploaded = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")

        sample_bytes = generate_sample_csv()
        _dl1, _dl2 = st.columns(2)
        with _dl1:
            st.download_button(
                "⬇  Download sample CSV (400 fans)",
                data=sample_bytes, file_name="footintel_sample.csv", mime="text/csv",
            )
        with _dl2:
            st.download_button(
                "⬇  Download CSV template (headers only)",
                data=generate_csv_template(), file_name="footintel_template.csv", mime="text/csv",
            )

        if uploaded is not None:
            try:
                file_hash = hashlib.md5(uploaded.getvalue()).hexdigest()
                if st.session_state.get("_file_hash") != file_hash:
                    df_raw       = pd.read_csv(io.BytesIO(uploaded.getvalue()))
                    col_map_auto = detect_columns(df_raw)
                    st.session_state["_file_hash"]   = file_hash
                    st.session_state["df_raw"]       = df_raw
                    st.session_state["col_map_auto"] = col_map_auto
                    st.session_state.pop("df_processed", None)
                    st.session_state.pop("col_map", None)
                    st.session_state.pop("schema_mode", None)

                df_raw       = st.session_state["df_raw"]
                col_map_auto = st.session_state.get("col_map_auto", {})
                mapped       = list(col_map_auto.keys())
                unmapped     = [f for f in COLUMN_ALIASES if f not in col_map_auto]

                st.markdown(card(
                    f'<div style="font-size:10px;color:#22c55e;margin-bottom:6px">'
                    f'✓ Loaded {len(df_raw):,} fans &nbsp;·&nbsp; {len(df_raw.columns)} columns detected</div>'
                    f'<div style="font-size:10px;color:#6b7280">Auto-matched: '
                    f'{", ".join(mapped) if mapped else "none"}</div>'
                    + (
                        f'<div style="font-size:10px;color:#f59e0b;margin-top:4px">'
                        f'Not matched: {", ".join(unmapped[:8])}</div>' if unmapped else ""
                    ),
                    border="#22c55e",
                ), unsafe_allow_html=True)

                if "df_processed" in st.session_state:
                    df_proc = st.session_state["df_processed"]
                    st.success(
                        f"Done — {len(df_proc):,} fans scored across 5 dimensions, "
                        f"assigned to {df_proc['segment'].nunique()} segments. "
                        "Switch to the Dashboard tab."
                    )
            except Exception as exc:
                st.error(f"Could not process file: {exc}")

    with right:
        st.markdown(card(
            '<div style="font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Expected columns</div>'
            '<div style="font-size:10px;color:#9ca3af;line-height:2">'
            '<span style="color:#c8f135">User_ID</span> · <span style="color:#c8f135">Age</span> · Gender · Country<br>'
            '<span style="color:#a78bfa">Membership_Category</span> · <span style="color:#a78bfa">Fan_Type</span> · <span style="color:#a78bfa">HAS_APP</span><br>'
            '<span style="color:#3d9cf0">Email_Clicks</span> · <span style="color:#3d9cf0">Email_Campaigns_Received</span><br>'
            '<span style="color:#3d9cf0">InApp_Clicks</span> · <span style="color:#3d9cf0">InApp_Campaigns_Received</span><br>'
            '<span style="color:#3d9cf0">Article_Views</span> · <span style="color:#3d9cf0">Last_App_Open</span><br>'
            '<span style="color:#22c55e">Ticket_Purchases</span> · <span style="color:#22c55e">Membership_Purchases</span><br>'
            '<span style="color:#22c55e">Retail_Purchases</span> · <span style="color:#22c55e">Total_Revenue</span><br>'
            '<span style="color:#f59e0b">Last_Purchase_Date</span> · <span style="color:#f59e0b">Last_Email_Open</span><br>'
            '<span style="color:#f59e0b">Join_Date</span></div>'
            '<div style="margin-top:10px;font-size:9px;color:#374151">Dates: YYYY-MM-DD · Missing columns use neutral scores</div>'
        ), unsafe_allow_html=True)

        st.markdown(card(
            '<div style="font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Five scoring dimensions</div>'
            '<div style="font-size:10px;color:#9ca3af;line-height:2.0">'
            '<span style="color:#3d9cf0">●</span> <b style="color:#e5e7eb">Engagement</b> — Email CTR · InApp CTR · Articles · App recency<br>'
            '<span style="color:#c8f135">●</span> <b style="color:#e5e7eb">Commercial</b> — Revenue · Recency · Frequency<br>'
            '<span style="color:#22c55e">●</span> <b style="color:#e5e7eb">Loyalty</b> — Tenure · Membership tier · Consistency<br>'
            '<span style="color:#ef4444">●</span> <b style="color:#e5e7eb">Churn Risk</b> — Purchase / App / Email recency (higher = worse)<br>'
            '<span style="color:#a78bfa">●</span> <b style="color:#e5e7eb">Conversion Probability</b> — Channel engagement + membership gap'
            '</div>'
        ), unsafe_allow_html=True)

        st.markdown(card(
            '<div style="font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Journey stages</div>'
            '<div style="font-size:10px;color:#9ca3af;line-height:2">'
            '<span style="color:#4b5563">●</span> Stage 1 — No membership, low engagement<br>'
            '<span style="color:#f59e0b">●</span> Stage 2 — No membership, active<br>'
            '<span style="color:#3d9cf0">●</span> Stage 3 — Basic member, engaged<br>'
            '<span style="color:#22c55e">●</span> Stage 4 — Paid member<br>'
            '<span style="color:#c8f135">●</span> Stage 5 — Season ticket holder'
            '</div>'
        ), unsafe_allow_html=True)

    # ── Smart column mapping ─────────────────────────────────────────────────
    if "df_raw" in st.session_state and "df_processed" not in st.session_state:
        df_raw       = st.session_state["df_raw"]
        col_map_auto = st.session_state.get("col_map_auto", {})
        high_conf, low_conf, unmatched_set = detect_columns_scored(df_raw)
        csv_cols = list(df_raw.columns)
        opts     = ["— not mapped —"] + csv_cols
        needs_human = bool(low_conf or unmatched_set)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if not needs_human:
            # All columns matched at high confidence — success screen
            st.markdown(
                '<div style="background:#052e16;border:1px solid #166534;'
                'border-radius:10px;padding:16px 20px;margin-bottom:20px">'
                '<span style="color:#22c55e;font-size:14px;font-weight:700">'
                '&#10003; All columns matched successfully.</span></div>',
                unsafe_allow_html=True,
            )
            rows_html = ""
            for field, csv_col in sorted(high_conf.items()):
                label = FIELD_LABELS.get(field, field.replace("_", " ").title())
                rows_html += (
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:8px 0;border-bottom:1px solid #1f2937">'
                    f'<span style="color:#9ca3af;font-size:12px">{label}</span>'
                    f'<span style="color:#22c55e;font-size:12px;font-weight:600">{csv_col}</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="background:#13161d;border:1px solid #2a2f3d;'
                f'border-radius:10px;padding:16px 20px;margin-bottom:24px">{rows_html}</div>',
                unsafe_allow_html=True,
            )
            confirmed_map = dict(high_conf)
            if st.button("\u2713  Confirm and Analyse Fans", key="confirm_all_matched"):
                _sc, _ms = get_upload_state(confirmed_map)
                if _sc == "custom":
                    st.session_state.pop("df_processed", None)
                    st.session_state["schema_mode"] = "custom"
                else:
                    st.session_state["df_processed"] = process_data(df_raw, confirmed_map)
                    st.session_state["schema_mode"] = _sc
                st.session_state["col_map"] = confirmed_map
                st.rerun()

        else:
            # Mixed — read-only list for high_conf, dropdowns for the rest
            section_heading("Map Your Columns")
            st.markdown(
                f'<div style="font-size:11px;color:#9ca3af;margin-bottom:14px">'
                f'{len(high_conf)} field(s) matched automatically. '
                f'Resolve the fields below before proceeding.</div>',
                unsafe_allow_html=True,
            )
            if high_conf:
                rows_html = "".join(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:6px 0;border-bottom:1px solid #1f2937">'
                    f'<span style="color:#6b7280;font-size:11px">'
                    f'{FIELD_LABELS.get(fld, fld.replace("_"," ").title())}</span>'
                    f'<span style="color:#22c55e;font-size:11px">{col} &#10003;</span>'
                    f'</div>'
                    for fld, col in sorted(high_conf.items())
                )
                st.markdown(
                    f'<div style="background:#13161d;border:1px solid #2a2f3d;'
                    f'border-radius:8px;padding:12px 16px;margin-bottom:14px">'
                    f'<span style="color:#22c55e;font-size:10px;font-weight:600;'
                    f'text-transform:uppercase;letter-spacing:.1em">Auto Matched</span>'
                    f'{rows_html}</div>',
                    unsafe_allow_html=True,
                )
            confirmed_map = dict(high_conf)
            if low_conf:
                st.markdown(
                    f'<div style="background:#1c1500;border:1px solid #92400e;'
                    f'border-radius:8px;padding:10px 16px;margin-bottom:10px">'
                    f'<span style="color:#f59e0b;font-size:11px;font-weight:600">'
                    f'\u26a0 LOW CONFIDENCE \u2014 {len(low_conf)} field(s) need confirmation'
                    f'</span></div>',
                    unsafe_allow_html=True,
                )
                for field, (csv_col, score) in sorted(low_conf.items()):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        st.markdown(
                            f'<div style="color:#f59e0b;font-size:12px;padding:8px 0">'
                            f'<strong>{FIELD_LABELS.get(field, field.replace("_"," ").title())}</strong></div>',
                            unsafe_allow_html=True,
                        )
                    with c2:
                        idx = opts.index(csv_col) if csv_col in opts else 0
                        sel = st.selectbox("_lc_"+field, opts, index=idx,
                                           label_visibility="collapsed", key="mlc_"+field)
                    with c3:
                        st.markdown(f'<div style="color:#f59e0b;font-size:11px;padding:8px 0">{score}%</div>',
                                    unsafe_allow_html=True)
                    if sel != "— not mapped —":
                        confirmed_map[field] = sel
            if unmatched_set:
                st.markdown(
                    f'<div style="background:#1f0a0a;border:1px solid #991b1b;'
                    f'border-radius:8px;padding:10px 16px;margin-bottom:10px;margin-top:6px">'
                    f'<span style="color:#ef4444;font-size:11px;font-weight:600">'
                    f'\u2717 UNMATCHED \u2014 {len(unmatched_set)} field(s) \u2014 assign or leave unmapped'
                    f'</span></div>',
                    unsafe_allow_html=True,
                )
                for field in sorted(unmatched_set):
                    c1, c2 = st.columns([2, 3])
                    with c1:
                        st.markdown(
                            f'<div style="color:#ef4444;font-size:12px;padding:8px 0">'
                            f'<strong>{FIELD_LABELS.get(field, field.replace("_"," ").title())}</strong></div>',
                            unsafe_allow_html=True,
                        )
                    with c2:
                        sel = st.selectbox("_um_"+field, opts, index=0,
                                           label_visibility="collapsed", key="mum_"+field)
                    if sel != "— not mapped —":
                        confirmed_map[field] = sel
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("\u2713  Confirm Mapping & Analyse Fans", key="confirm_mapping_mixed"):
                _sc, _ms = get_upload_state(confirmed_map)
                if _sc == "custom":
                    st.session_state.pop("df_processed", None)
                    st.session_state["schema_mode"] = "custom"
                else:
                    st.session_state["df_processed"] = process_data(df_raw, confirmed_map)
                    st.session_state["schema_mode"] = _sc
                st.session_state["col_map"] = confirmed_map
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# HOW TO USE
# ─────────────────────────────────────────────────────────────────────────────
with tab_howto:
    st.markdown(
        '<h2 style="font-family:\'Syne\',sans-serif;color:#e5e7eb;font-size:26px;'
        'font-weight:800;margin-bottom:4px">How To Use FootIntel</h2>'
        '<p style="color:#6b7280;font-size:13px;margin-bottom:28px">'
        'A step-by-step guide for marketing managers.</p>',
        unsafe_allow_html=True,
    )
    _HT_STEPS = [
        ("Prepare Your Data",
         "Your CSV needs fan-level data with one row per fan. The more columns you include, "
         "the richer your analysis. At minimum you need a Fan ID, Membership Category, "
         "and some engagement or purchase history."),
        ("Upload and Confirm Mapping",
         "Upload your CSV and FootIntel will automatically detect and map your columns. "
         "Review the auto-matched fields, confirm any amber ones, assign any red ones manually. "
         "Hit Confirm and Analyse Fans to proceed."),
        ("Understand Your Fan Dashboard",
         "Your dashboard shows how your fanbase splits across 5 segments and scores every fan "
         "across Engagement, Commercial, Loyalty, Churn Risk, and Conversion. "
         "Start here to get the big picture."),
        ("Identify Your At-Risk Fans",
         "The Dashboard's Churn Risk panel shows fans most likely to lapse in the next 90 days, "
         "ranked by churn risk score. This is your weekly action list. "
         "Focus on Win Back and Dormant fans first."),
        ("Build Your Sponsorship Pitch",
         "Go to Sponsorship Intelligence and scroll to the Sponsor Category Recommendations. "
         "Download the Sponsorship Deck PDF and take it directly into your next sponsor conversation."),
        ("Export and Act",
         "Use the Campaign Generator on the Fan Dashboard to download a targeted fan list "
         "and a ready-to-use email template for any segment. "
         "Upload the fan list to your CRM and send the email. Done."),
    ]
    for _i, (_title, _body) in enumerate(_HT_STEPS, 1):
        st.markdown(
            f'<div style="display:flex;gap:20px;align-items:flex-start;'
            f'background:#13161d;border:1px solid #2a2f3d;border-radius:10px;'
            f'padding:20px 22px;margin-bottom:12px">'
            f'<div style="min-width:38px;height:38px;background:#c8a800;'
            f'border-radius:50%;display:flex;align-items:center;justify-content:center;'
            f'font-family:\'Syne\',sans-serif;font-weight:800;color:#0a0c10;'
            f'font-size:16px;flex-shrink:0">{_i}</div>'
            f'<div>'
            f'<div style="font-family:\'Syne\',sans-serif;font-weight:700;'
            f'color:#e5e7eb;font-size:15px;margin-bottom:6px">{_title}</div>'
            f'<div style="color:#9ca3af;font-size:12px;line-height:1.75">{_body}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div style="background:#052e16;border:1px solid #166534;border-radius:10px;'
        'padding:16px 22px;margin-top:16px;text-align:center">'
        '<span style="color:#22c55e;font-size:13px">'
        'Need help or want to connect your own data? '
        'Built by <strong>Kush Savant</strong>, MSc Sports Analytics, '
        'Loughborough University London.</span></div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab_dashboard:
    if st.session_state.get("schema_mode") == "custom":
        _locked_tab_msg()
    elif "df_processed" not in st.session_state:
        st.markdown(card(
            '<div style="text-align:center;color:#6b7280;font-size:12px;padding:24px">'
            'Upload a CSV in the Upload tab to populate the dashboard.</div>'
        ), unsafe_allow_html=True)
    else:
        df_all         = st.session_state["df_processed"]
        col_map_stored = st.session_state.get("col_map", {})
        club_name      = st.session_state.get("club_name", "").strip()

        # ── Schema state banner ────────────────────────────────────────────────
        _state, _missing = get_upload_state(col_map_stored)
        if _state == "full":
            st.markdown(
                '<div style="background:#052e16;border:1px solid #166534;border-radius:8px;'
                'padding:7px 16px;margin-bottom:14px;font-size:10px;color:#22c55e">'
                '✓ Full schema matched — all scoring dimensions and features unlocked.</div>',
                unsafe_allow_html=True,
            )
        elif _state == "partial":
            missing_labels = ", ".join(FIELD_LABELS.get(m, m) for m in sorted(_missing))
            st.markdown(
                f'<div style="background:#1c1500;border:1px solid #92400e;border-radius:8px;'
                f'padding:7px 16px;margin-bottom:14px;font-size:10px;color:#f59e0b">'
                f'⚠ Partial match — {len(_missing)} core column(s) missing: <b>{missing_labels}</b>. '
                f'Affected scores use neutral values. Map more columns for higher accuracy.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:#1c1500;border:1px solid #92400e;border-radius:8px;'
                'padding:7px 16px;margin-bottom:14px;font-size:10px;color:#f59e0b">'
                '⚠ Custom data mode — limited standard columns detected. '
                'See the Custom Metrics Explorer in the Report tab for your data.</div>',
                unsafe_allow_html=True,
            )

        heading = f"{club_name} — Fan Dashboard" if club_name else "Fan Dashboard"

        # ── Insight banner ──────────────────────────────────────────────────
        _sc = df_all["segment"].value_counts()
        _ts = _sc.idxmax(); _tn = int(_sc.max())
        _ac = df_all[df_all["segment"] == _ts]["churn_risk_index"].mean()
        _s1 = (f"{_tn:,} of your fans are in the {_ts} segment with an average "
               f"churn risk of {_ac:.0f} \u2014 your biggest volume risk this period.")
        if "age_group" in df_all.columns:
            _ta = df_all.groupby("age_group")["churn_risk_index"].mean().idxmax()
            _s2 = f"Focus retention spend on the {_ta} age group where churn pressure is highest."
        else:
            _s2 = "Add demographic data to unlock age-level churn targeting recommendations."
        insight_banner(_s1, _s2)
        st.markdown(
            f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
            f'color:#e5e7eb;margin-bottom:12px">{heading}</div>',
            unsafe_allow_html=True,
        )

        # Country filter
        if "country" in col_map_stored:
            country_col    = col_map_stored["country"]
            all_countries  = sorted(df_all[country_col].dropna().astype(str).unique().tolist())
            sel_countries  = st.multiselect("Filter by Country / Region", options=all_countries,
                                            default=all_countries, key="country_filter")
            df = df_all[df_all[country_col].astype(str).isin(sel_countries)] if sel_countries else df_all
        else:
            df = df_all

        total = len(df)

        if total == 0:
            st.warning("No fans match the selected country filter.")
        else:
            # ── KPI strip ─────────────────────────────────────────────────────
            high_churn_n = (df["churn_risk_label"] == "HIGH").sum()
            conv_cands   = df["journey_stage"].isin(["Stage 2 — No Membership, Active", "Stage 3 — Basic Member, Engaged"]).sum()
            avg_e = df["engagement_score"].mean()
            avg_c = df["commercial_score"].mean()
            avg_l = df["loyalty_score"].mean()

            k1, k2, k3, k4, k5 = st.columns(5)
            with k1: st.markdown(kpi("Total Fans",        f"{total:,}",         "in selection"),                            unsafe_allow_html=True)
            with k2: st.markdown(kpi("Avg Engagement",    f"{avg_e:.0f}",       "/ 100", "#3d9cf0"),                        unsafe_allow_html=True)
            with k3: st.markdown(kpi("Avg Commercial",    f"{avg_c:.0f}",       "/ 100", "#c8f135"),                        unsafe_allow_html=True)
            with k4: st.markdown(kpi("HIGH Churn Risk",   f"{high_churn_n:,}",  f"{high_churn_n/total*100:.0f}% of base", "#ef4444"), unsafe_allow_html=True)
            with k5: st.markdown(kpi("Conv. Candidates",  f"{conv_cands:,}",    "Stage 2–3 fans", "#a78bfa"),               unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            # ── Row 1 — donut + age bar ────────────────────────────────────────
            r1c1, r1c2 = st.columns(2)
            with r1c1: st.plotly_chart(chart_segment_donut(df),   use_container_width=True, config={"displayModeBar": False}, key="segment_donut")
            with r1c2: st.plotly_chart(chart_age_segment_bar(df), use_container_width=True, config={"displayModeBar": False}, key="age_segment_bar")

            # ── Row 2 — scatter ────────────────────────────────────────────────
            st.plotly_chart(chart_landscape(df), use_container_width=True, config={"displayModeBar": False}, key="landscape")

            # ── Row 3 — scores + commercial ───────────────────────────────────
            r3c1, r3c2 = st.columns(2)
            with r3c1: st.plotly_chart(chart_scores_by_segment(df),      use_container_width=True, config={"displayModeBar": False}, key="scores_by_segment")
            with r3c2: st.plotly_chart(chart_commercial_opportunity(df), use_container_width=True, config={"displayModeBar": False}, key="commercial_opportunity")

            # ── Row 4 — age radar ──────────────────────────────────────────────
            st.plotly_chart(chart_age_scores(df), use_container_width=True, config={"displayModeBar": False}, key="age_scores_radar")

            # ──────────────────────────────────────────────────────────────────
            # CHURN RISK PANEL
            # ──────────────────────────────────────────────────────────────────
            section_heading("Churn Risk Panel")

            # Filter controls
            cr_f1, cr_f2 = st.columns([2, 2])
            with cr_f1:
                seg_options = ["All Segments"] + sorted(df["segment"].unique().tolist())
                cr_seg = st.selectbox("Filter by Segment", seg_options, key="cr_seg_filter")
            with cr_f2:
                if "membership_category" in col_map_stored:
                    mc_col    = col_map_stored["membership_category"]
                    mc_opts   = ["All Tiers"] + sorted(df[mc_col].dropna().astype(str).unique().tolist())
                    cr_mc     = st.selectbox("Filter by Membership", mc_opts, key="cr_mc_filter")
                else:
                    cr_mc = "All Tiers"

            df_cr = df.copy()
            if cr_seg != "All Segments":
                df_cr = df_cr[df_cr["segment"] == cr_seg]
            if cr_mc != "All Tiers" and "membership_category" in col_map_stored:
                df_cr = df_cr[df_cr[col_map_stored["membership_category"]].astype(str) == cr_mc]

            # Churn KPI tiles
            cr_tot = len(df_cr)
            cr_high = (df_cr["churn_risk_label"] == "HIGH").sum()
            cr_med  = (df_cr["churn_risk_label"] == "MED").sum()
            cr_low  = (df_cr["churn_risk_label"] == "LOW").sum()

            ck1, ck2, ck3, ck4 = st.columns(4)
            with ck1: st.markdown(kpi("Fans in Filter",  f"{cr_tot:,}",  ""),                                                                  unsafe_allow_html=True)
            with ck2: st.markdown(kpi("HIGH Risk",       f"{cr_high:,}", f"{cr_high/max(cr_tot,1)*100:.0f}% of filter", "#ef4444"),             unsafe_allow_html=True)
            with ck3: st.markdown(kpi("MED Risk",        f"{cr_med:,}",  f"{cr_med/max(cr_tot,1)*100:.0f}% of filter",  "#f59e0b"),             unsafe_allow_html=True)
            with ck4: st.markdown(kpi("LOW Risk",        f"{cr_low:,}",  f"{cr_low/max(cr_tot,1)*100:.0f}% of filter",  "#22c55e"),             unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.plotly_chart(chart_churn_by_segment(df_cr), use_container_width=True, config={"displayModeBar": False}, key="churn_by_segment_panel")

            # High-risk fans table
            st.markdown(
                '<div style="font-size:12px;color:#9ca3af;margin:10px 0 6px">Top 20 HIGH Churn Risk Fans</div>',
                unsafe_allow_html=True,
            )
            high_risk_df = df_cr[df_cr["churn_risk_label"] == "HIGH"].nlargest(20, "churn_risk_index")
            disp_cr = (
                [col_map_stored["user_id"]] if "user_id" in col_map_stored else []
            ) + [c for c in ["segment", "journey_stage", "churn_risk_index", "engagement_score",
                              "commercial_score", "recency_days"] if c in high_risk_df.columns]
            if not high_risk_df.empty:
                st.dataframe(
                    high_risk_df[disp_cr].reset_index(drop=True)
                    .style.background_gradient(subset=["churn_risk_index"], cmap="RdYlGn_r"),
                    use_container_width=True, height=380,
                )
            else:
                st.info("No HIGH churn risk fans in the current filter.")

            # ──────────────────────────────────────────────────────────────────
            # CONVERSION OPPORTUNITY PANEL
            # ──────────────────────────────────────────────────────────────────
            section_heading("Conversion Opportunity Panel")

            stage_cands = df[df["journey_stage"].isin([
                "Stage 2 — No Membership, Active", "Stage 3 — Basic Member, Engaged"
            ])]
            avg_cp_cands = stage_cands["conversion_probability"].mean() if len(stage_cands) > 0 else 0

            co1, co2, co3 = st.columns(3)
            with co1: st.markdown(kpi("Stage 2+3 Candidates", f"{len(stage_cands):,}", "ready to upgrade", "#a78bfa"), unsafe_allow_html=True)
            with co2: st.markdown(kpi("Avg Conv. Probability", f"{avg_cp_cands:.0f}",  "/ 100 for Stage 2–3", "#c8f135"), unsafe_allow_html=True)
            with co3: st.markdown(kpi("Season Ticket Holders", f"{(df['journey_stage'] == 'Stage 5 — Season Ticket Holder').sum():,}", "Stage 5 fans", "#22c55e"), unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            cop1, cop2 = st.columns(2)
            with cop1: st.plotly_chart(chart_journey_stage_funnel(df),    use_container_width=True, config={"displayModeBar": False}, key="journey_stage_funnel")
            with cop2: st.plotly_chart(chart_conversion_by_stage(df),     use_container_width=True, config={"displayModeBar": False}, key="conversion_by_stage")

            # Top conversion candidates table
            st.markdown(
                '<div style="font-size:12px;color:#9ca3af;margin:10px 0 6px">Top 20 Conversion Candidates (Stage 2–3, ranked by Conversion Probability)</div>',
                unsafe_allow_html=True,
            )
            top_conv = stage_cands.nlargest(20, "conversion_probability")
            disp_cv  = (
                [col_map_stored["user_id"]] if "user_id" in col_map_stored else []
            ) + [c for c in ["journey_stage", "conversion_probability", "engagement_score",
                              "commercial_score", "churn_risk_label"] if c in top_conv.columns]
            if not top_conv.empty:
                st.dataframe(
                    top_conv[disp_cv].reset_index(drop=True)
                    .style.background_gradient(subset=["conversion_probability"], cmap="RdYlGn"),
                    use_container_width=True, height=380,
                )
            else:
                st.info("No Stage 2–3 fans found.")

            # ──────────────────────────────────────────────────────────────────
            # CHANNEL PREFERENCE INDEX
            # ──────────────────────────────────────────────────────────────────
            section_heading("Channel Preference Index")

            ch_counts = df["channel_preference"].value_counts()
            ch_total  = len(df)
            ch1, ch2, ch3, ch4 = st.columns(4)
            for col_ui, ch, color in [
                (ch1, "Email",   "#3d9cf0"),
                (ch2, "App",     "#c8f135"),
                (ch3, "Both",    "#22c55e"),
                (ch4, "Neither", "#6b7280"),
            ]:
                cnt = int(ch_counts.get(ch, 0))
                with col_ui:
                    st.markdown(kpi(f"{ch} Preferred", f"{cnt:,}", f"{cnt/ch_total*100:.0f}% of fans", color), unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.plotly_chart(chart_channel_preference(df), use_container_width=True, config={"displayModeBar": False}, key="channel_preference_dashboard")

            # ──────────────────────────────────────────────────────────────────
            # SEGMENT INSIGHT CARDS
            # ──────────────────────────────────────────────────────────────────
            section_heading("Segment Insights &amp; Recommended Actions")
            seg_counts = df["segment"].value_counts()
            seg_keys   = [s for s in SEGMENT_INFO if s in seg_counts.index]

            for i in range(0, len(seg_keys), 2):
                pair = seg_keys[i : i + 2]
                cols = st.columns(len(pair))
                for col_ui, seg in zip(cols, pair):
                    info  = SEGMENT_INFO[seg]
                    count = int(seg_counts.get(seg, 0))
                    pct   = count / total * 100
                    sub   = df[df["segment"] == seg]
                    avg_e_s  = sub["engagement_score"].mean()
                    avg_c_s  = sub["commercial_score"].mean()
                    avg_l_s  = sub["loyalty_score"].mean()
                    avg_cr_s = sub["churn_risk_index"].mean()
                    avg_cp_s = sub["conversion_probability"].mean()

                    actions_html = "".join(
                        f'<div style="font-size:9px;color:#9ca3af;margin-top:4px">→ {a}</div>'
                        for a in info["actions"]
                    )
                    with col_ui:
                        st.markdown(card(
                            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">'
                            f'  <div><span style="font-size:20px">{info["icon"]}</span>'
                            f'    <span style="font-family:\'Syne\',sans-serif;font-size:15px;font-weight:700;'
                            f'          color:{info["color"]};margin-left:8px">{seg}</span></div>'
                            f'  <span style="background:{info["bg"]};color:{info["color"]};'
                            f'        border:1px solid {info["color"]};font-size:10px;padding:3px 10px;'
                            f'        border-radius:8px">{count:,} fans · {pct:.0f}%</span>'
                            f'</div>'
                            f'<div style="font-size:10px;color:#6b7280;margin-bottom:8px">{info["description"]}</div>'
                            f'<div style="display:flex;gap:14px;margin-bottom:10px;flex-wrap:wrap">'
                            f'  <div style="font-size:10px;color:#3d9cf0">E: {avg_e_s:.0f}</div>'
                            f'  <div style="font-size:10px;color:#c8f135">C: {avg_c_s:.0f}</div>'
                            f'  <div style="font-size:10px;color:#22c55e">L: {avg_l_s:.0f}</div>'
                            f'  <div style="font-size:10px;color:#ef4444">Churn: {avg_cr_s:.0f}</div>'
                            f'  <div style="font-size:10px;color:#a78bfa">Conv: {avg_cp_s:.0f}</div>'
                            f'</div>'
                            f'<div style="font-size:10px;color:#9ca3af;border-left:2px solid {info["color"]};'
                            f'     padding-left:8px;margin-bottom:8px">{info["recommendation"]}</div>'
                            f'{actions_html}',
                            bg="#0d1117", border=info["color"],
                        ), unsafe_allow_html=True)

            # ── Campaign Generator ─────────────────────────────────────────
            section_heading("Campaign Generator")
            st.markdown(card(
                '<div style="font-size:11px;color:#9ca3af">Download a targeted fan list and '
                'ready-to-use email template for any segment.</div>'
            ), unsafe_allow_html=True)
            _cg_segs   = list(SEGMENT_INFO.keys())
            _cg_choice = st.selectbox("Select Segment", _cg_segs, key="cg_seg_select")
            _cg_fans   = df_all[df_all["segment"] == _cg_choice].copy()
            _cg_cols   = [c for c in [
                col_map_stored.get("user_id"), "segment", "engagement_score",
                "commercial_score", "churn_risk_index", "channel_preference",
                col_map_stored.get("membership_category"),
            ] if c and c in _cg_fans.columns]
            if _cg_cols:
                _cg_csv = _cg_fans[list(dict.fromkeys(_cg_cols))].to_csv(index=False).encode()
                st.download_button(
                    f"Download {_cg_choice} Fan List ({len(_cg_fans):,} fans)",
                    data=_cg_csv,
                    file_name=f"{club_name or 'footintel'}_{_cg_choice.lower().replace(' ','_')}_fans.csv",
                    mime="text/csv", key="cg_download_btn",
                )
            _cg_fn  = _EMAIL_TEMPLATES.get(_cg_choice)
            _cg_txt = _cg_fn(club_name or "Your Club") if _cg_fn else ""
            st.text_area("Email Template", value=_cg_txt, height=280, key="cg_email_tmpl")
            st.caption("Copy the template above, paste into your email platform, and personalise [First Name].")

            # ── Top 20 fans ────────────────────────────────────────────────
            section_heading("Top 20 Fans by Composite Score")
            display_cols = (
                [col_map_stored["user_id"]] if "user_id" in col_map_stored else []
            ) + [c for c in ["age_group", "segment", "journey_stage", "engagement_score",
                              "commercial_score", "loyalty_score", "churn_risk_index",
                              "conversion_probability", "composite_score", "channel_preference"]
                 if c in df.columns]
            st.dataframe(
                df.nlargest(20, "composite_score")[display_cols]
                  .reset_index(drop=True)
                  .style.background_gradient(subset=["composite_score"], cmap="RdYlGn"),
                use_container_width=True, height=420,
            )




_EMAIL_TEMPLATES = {
    "Win Back":       lambda c: f"Subject: We miss you at {c}\n\nHi [First Name],\n\n"
                                f"It's been a while since we last saw you at {c} and we wanted to reach out personally.\n\n"
                                f"This season has been one to remember. Use code MISSYOU20 for 20% off your next ticket.\n\n"
                                f"Come back and remind yourself why you love {c}.\n\nWarm regards,\n{c} Fan Engagement Team",
    "High Potential": lambda c: f"Subject: Your next step with {c}\n\nHi [First Name],\n\n"
                                f"You're one of our most engaged fans and we think it's time to make it official.\n\n"
                                f"Becoming a member of {c} means early access, exclusive events and priority seating.\n\n"
                                f"We're offering a new member trial — your first month is on us.\n\n{c} Membership Team",
    "Loyal Fans":     lambda c: f"Subject: Thank you for your loyalty to {c}\n\nHi [First Name],\n\n"
                                f"We don't say it often enough — but thank you. Your support means everything.\n\n"
                                f"As a loyal member you get priority ticket selection, an exclusive gift, "
                                f"and an invitation to our pre-season event.\n\nYour Early Access window opens soon.\n\nWith gratitude,\n{c} Club Management",
    "Dormant":        lambda c: f"Subject: It's been a while — we'd love to see you at {c}\n\nHi [First Name],\n\n"
                                f"We miss having you in the stands at {c}.\n\n"
                                f"We're offering a Welcome Back package — a pair of tickets at half price.\n\n"
                                f"Reply to claim your offer.\n\n{c} Fan Engagement Team",
    "Casual":         lambda c: f"Subject: Make your mark at {c} this season\n\nHi [First Name],\n\n"
                                f"Every great fan story starts with showing up more often.\n\n"
                                f"We've put together multi-match bundles so you can plan your season and save.\n\n"
                                f"Check out our bundle offers at {c} — the stands are better with you in them.\n\n{c} Fan Engagement Team",
}

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — REPORT
# ─────────────────────────────────────────────────────────────────────────────
with tab_report:
    if st.session_state.get("schema_mode") == "custom":
        _locked_tab_msg()
        # Still show custom metrics explorer for custom-mode uploads
        if "df_raw" in st.session_state and "col_map" in st.session_state:
            render_custom_metrics_explorer(
                st.session_state["df_raw"],
                st.session_state["col_map"],
            )
    elif "df_processed" not in st.session_state:
        st.markdown(card(
            '<div style="text-align:center;color:#6b7280;font-size:12px;padding:24px">'
            'Upload a CSV in the Upload tab to generate the report.</div>'
        ), unsafe_allow_html=True)
    else:
        df        = st.session_state["df_processed"]
        club_name = st.session_state.get("club_name", "").strip()
        total     = len(df)
        today_str = datetime.today().strftime("%Y-%m-%d")

        report_title = f"{club_name} Fan Segmentation Report" if club_name else "Fan Segmentation Report"

        # ── Insight banner ──────────────────────────────────────────────────
        _rp_loyal = int((df["segment"] == "Loyal Fans").sum())
        _rp_hp    = int((df["segment"] == "High Potential").sum())
        _rp_avg   = df["commercial_score"].mean()
        _rp_s1 = (f"This report covers {total:,} fans: {_rp_loyal:,} Loyal Fans and "
                  f"{_rp_hp:,} High Potential fans, with an average commercial score of {_rp_avg:.0f}.")
        _rp_s2 = ("Use the segment breakdown below to identify conversion opportunities "
                  "and share this report with commercial and ticketing stakeholders.")
        insight_banner(_rp_s1, _rp_s2)
        st.markdown(
            f'<div style="font-family:\'Syne\',sans-serif;font-size:17px;font-weight:700;'
            f'color:#e5e7eb;margin-bottom:16px">{report_title}</div>',
            unsafe_allow_html=True,
        )

        # Executive summary card
        high_val = df["segment"].isin(["Loyal Fans"]).sum()
        at_risk  = df["segment"].isin(["Win Back", "Dormant"]).sum()
        pot      = df["segment"].isin(["High Potential"]).sum()
        high_ch  = (df["churn_risk_label"] == "HIGH").sum()
        st.markdown(card(
            f'<div style="font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px">Executive Summary</div>'
            f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px">'
            f'  <div><div style="font-size:10px;color:#6b7280">Fans Analysed</div>'
            f'       <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#c8f135">{total:,}</div></div>'
            f'  <div><div style="font-size:10px;color:#6b7280">Loyal Fans</div>'
            f'       <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#22c55e">{high_val:,}</div>'
            f'       <div style="font-size:9px;color:#374151">{high_val/total*100:.0f}% of base</div></div>'
            f'  <div><div style="font-size:10px;color:#6b7280">High Potential</div>'
            f'       <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#3d9cf0">{pot:,}</div>'
            f'       <div style="font-size:9px;color:#374151">{pot/total*100:.0f}% of base</div></div>'
            f'  <div><div style="font-size:10px;color:#6b7280">Requires Action</div>'
            f'       <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#ef4444">{at_risk:,}</div>'
            f'       <div style="font-size:9px;color:#374151">{at_risk/total*100:.0f}% of base</div></div>'
            f'  <div><div style="font-size:10px;color:#6b7280">HIGH Churn Risk</div>'
            f'       <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#f59e0b">{high_ch:,}</div>'
            f'       <div style="font-size:9px;color:#374151">{high_ch/total*100:.0f}% of base</div></div>'
            f'</div>'
        ), unsafe_allow_html=True)

        # Segment summary table
        st.markdown('<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:#e5e7eb;margin:16px 0 8px">Segment Summary</div>', unsafe_allow_html=True)
        st.dataframe(segment_summary(df).drop(columns=["Recommendation"]), use_container_width=True, hide_index=True)

        # Churn risk summary
        st.markdown('<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:#e5e7eb;margin:16px 0 8px">Churn Risk Summary</div>', unsafe_allow_html=True)
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            churn_tbl = df.groupby("churn_risk_label").size().reset_index(name="Fan_Count")
            churn_tbl["Pct"] = (churn_tbl["Fan_Count"] / total * 100).round(1)
            churn_tbl["Avg_Churn_Index"] = churn_tbl["churn_risk_label"].map(
                df.groupby("churn_risk_label")["churn_risk_index"].mean().round(1)
            )
            st.dataframe(churn_tbl, use_container_width=True, hide_index=True)
        with r1c2:
            st.plotly_chart(chart_churn_by_segment(df), use_container_width=True, config={"displayModeBar": False}, key="churn_by_segment_report")

        # Conversion opportunity summary
        st.markdown('<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:#e5e7eb;margin:16px 0 8px">Conversion Opportunity Summary</div>', unsafe_allow_html=True)
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            stage_tbl = df.groupby("journey_stage").agg(
                Fan_Count=("composite_score", "count"),
                Avg_Conv_Prob=("conversion_probability", "mean"),
            ).round(1).reindex(JOURNEY_STAGE_ORDER).reset_index()
            stage_tbl.columns = ["Journey Stage", "Fan Count", "Avg Conv. Prob"]
            st.dataframe(stage_tbl, use_container_width=True, hide_index=True)
        with r2c2:
            st.plotly_chart(chart_journey_stage_funnel(df), use_container_width=True, config={"displayModeBar": False}, key="journey_stage_report")

        # Channel preference breakdown
        st.markdown('<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:#e5e7eb;margin:16px 0 8px">Channel Preference Breakdown</div>', unsafe_allow_html=True)
        r3c1, r3c2 = st.columns(2)
        with r3c1:
            ch_tbl = df.groupby("channel_preference").size().reset_index(name="Fan_Count")
            ch_tbl["Pct"] = (ch_tbl["Fan_Count"] / total * 100).round(1)
            st.dataframe(ch_tbl, use_container_width=True, hide_index=True)
        with r3c2:
            st.plotly_chart(chart_channel_preference(df), use_container_width=True, config={"displayModeBar": False}, key="channel_preference_report")

        # Age breakdown
        st.markdown('<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:#e5e7eb;margin:16px 0 8px">Age Group Breakdown</div>', unsafe_allow_html=True)
        age_table = (
            df.groupby("age_group")
            .agg(Count=("composite_score","count"), Avg_Engagement=("engagement_score","mean"),
                 Avg_Commercial=("commercial_score","mean"), Avg_Loyalty=("loyalty_score","mean"),
                 Avg_Composite=("composite_score","mean"))
            .round(1).reset_index()
        )
        st.dataframe(age_table, use_container_width=True, hide_index=True)

        # Recommendations per segment
        st.markdown('<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:#e5e7eb;margin:16px 0 8px">Retention &amp; Commercial Recommendations</div>', unsafe_allow_html=True)
        seg_counts = df["segment"].value_counts()
        for seg, info in SEGMENT_INFO.items():
            count = int(seg_counts.get(seg, 0))
            if count == 0:
                continue
            actions_str = " · ".join(info["actions"])
            st.markdown(card(
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
                f'  <span style="font-size:13px;font-weight:600;color:{info["color"]}">{info["icon"]} {seg}</span>'
                f'  <span style="font-size:10px;color:#6b7280">{count:,} fans &nbsp;|&nbsp; risk: '
                f'    <span style="color:{"#ef4444" if info["risk"]=="HIGH" else "#f59e0b" if info["risk"]=="MED" else "#22c55e"}">{info["risk"]}</span></span>'
                f'</div>'
                f'<div style="font-size:10px;color:#9ca3af;margin-bottom:6px">{info["recommendation"]}</div>'
                f'<div style="font-size:9px;color:#6b7280">{actions_str}</div>',
                bg="#0d1117", border=info["color"],
            ), unsafe_allow_html=True)

        # Downloads
        st.markdown('<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:#e5e7eb;margin:20px 0 10px">Download</div>', unsafe_allow_html=True)
        dl1, dl2, dl3, dl4 = st.columns(4)
        with dl1:
            st.download_button("⬇  Full fan data (CSV)", data=to_csv_bytes(df),
                               file_name=f"footintel_fans_{today_str}.csv", mime="text/csv")
        with dl2:
            st.download_button("⬇  Segment summary (CSV)", data=to_csv_bytes(segment_summary(df)),
                               file_name=f"footintel_segments_{today_str}.csv", mime="text/csv")
        with dl3:
            st.download_button("⬇  Age breakdown (CSV)", data=to_csv_bytes(age_table),
                               file_name=f"footintel_age_{today_str}.csv", mime="text/csv")
        with dl4:
            pdf_bytes = generate_pdf_report(df, club_name)
            st.download_button("⬇  PDF Report", data=pdf_bytes,
                               file_name=f"footintel_report_{today_str}.pdf", mime="application/pdf")

        # Custom metrics explorer — shown in report tab if extra columns exist
        if "df_processed" in st.session_state and "col_map" in st.session_state:
            render_custom_metrics_explorer(
                st.session_state["df_processed"],
                st.session_state["col_map"],
            )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — FAN ACQUISITION
# ─────────────────────────────────────────────────────────────────────────────
with tab_acquisition:
    if st.session_state.get("schema_mode") == "custom":
        _locked_tab_msg()
    elif "df_processed" not in st.session_state:
        st.markdown(card(
            '<div style="text-align:center;color:#6b7280;font-size:12px;padding:24px">'
            'Upload a CSV in the Upload tab to unlock Fan Acquisition intelligence.</div>'
        ), unsafe_allow_html=True)
    else:
        df_acq     = st.session_state["df_processed"]
        col_acq    = st.session_state.get("col_map", {})
        club_name  = st.session_state.get("club_name", "").strip()
        heading    = f"{club_name} — Fan Acquisition" if club_name else "Fan Acquisition"
        st.markdown(
            f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
            f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
            f'<div style="font-size:11px;color:#6b7280;margin-bottom:18px">'
            f'Identify which regions have the highest fan growth potential and where to focus acquisition spend.</div>',
            unsafe_allow_html=True,
        )

        acq_df = compute_acquisition_data(df_acq, col_acq)

        if not acq_df.empty:
            _at = acq_df.iloc[0]
            _s1 = (f"{_at['country']} is your highest-priority acquisition market "
                   f"with a priority score of {_at['acquisition_score']:.0f} "
                   f"and {int(_at['fan_count']):,} fans already in your database.")
            _hi = acq_df[acq_df["acquisition_score"] >= 70]
            _s2 = (f"You have {len(_hi)} market(s) scoring above 70 \u2014 "
                   f"prioritise digital acquisition campaigns in these regions first."
                   if len(_hi) > 1 else
                   "Focus acquisition budget on your top market before expanding to lower-priority regions.")
            insight_banner(_s1, _s2)

        if acq_df.empty:
            st.markdown(card(
                '<div style="font-size:11px;color:#9ca3af;padding:12px">Map a <b style="color:#c8f135">Country / Region</b> '
                'column to unlock the Fan Acquisition tab.</div>'
            ), unsafe_allow_html=True)
        else:
            # ── KPIs ──────────────────────────────────────────────────────────
            top_market   = acq_df[~acq_df["country"].isin(["Other"])].iloc[0]
            total_mkts   = acq_df[~acq_df["country"].isin(["Other"])].shape[0]
            high_prio    = (acq_df["acquisition_score"] >= 70).sum()

            aq1, aq2, aq3, aq4 = st.columns(4)
            with aq1: st.markdown(kpi("Markets Tracked", str(total_mkts), "distinct regions"), unsafe_allow_html=True)
            with aq2: st.markdown(kpi("Top Acquisition Market", top_market["country"], f"Score: {top_market['acquisition_score']:.0f}", "#c8f135"), unsafe_allow_html=True)
            with aq3: st.markdown(kpi("High-Priority Markets", str(high_prio), "score ≥ 70", "#22c55e"), unsafe_allow_html=True)
            with aq4: st.markdown(kpi("Avg Acquisition Score", f"{acq_df['acquisition_score'].mean():.0f}", "across all regions", "#3d9cf0"), unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            # ── Map + priority bar ─────────────────────────────────────────────
            mp1, mp2 = st.columns([3, 2])
            with mp1:
                st.plotly_chart(chart_acquisition_map(acq_df), use_container_width=True,
                                config={"displayModeBar": False}, key="acq_map")
            with mp2:
                st.plotly_chart(chart_acquisition_priority_bar(acq_df), use_container_width=True,
                                config={"displayModeBar": False}, key="acq_priority_bar")

            # ── Market landscape scatter ───────────────────────────────────────
            st.plotly_chart(chart_acquisition_landscape(acq_df), use_container_width=True,
                            config={"displayModeBar": False}, key="acq_landscape")

            # ── Demographic gaps ───────────────────────────────────────────────
            section_heading("Demographic Gap Analysis")
            st.plotly_chart(chart_demographic_gaps(df_acq), use_container_width=True,
                            config={"displayModeBar": False}, key="acq_demo_gaps")

            # ── Top 5 recommended acquisition target markets ───────────────────
            section_heading("Top 5 Acquisition Target Markets")
            _acq_country_segs = df_acq.groupby("segment").size()
            _dominant_seg = _acq_country_segs.idxmax() if not _acq_country_segs.empty else "Casual"

            _ACTIVATION_TEMPLATES = {
                "USA": ("Young Adults in USA", "High engagement, growing market, low commercial conversion",
                        "First-purchase welcome offer + app download incentive"),
                "Germany": ("Adults in Germany", "High commercial score, under-represented in fan base",
                            "Premium membership drive with localised content"),
                "Spain": ("Young Adults in Spain", "Strong engagement index, low current fan density",
                          "Social media activation + local influencer campaign"),
                "Ireland": ("All ages in Ireland", "Cultural proximity — high loyalty potential",
                            "Season ticket trial + local club partnership"),
                "France": ("Adults in France", "High headroom market with growing football interest",
                           "Digital-first fan engagement campaign"),
            }

            top5 = acq_df[~acq_df["country"].isin(["Other"])].head(5)
            for _, mkt_row in top5.iterrows():
                country = mkt_row["country"]
                tpl = _ACTIVATION_TEMPLATES.get(country, (
                    f"Fans in {country}",
                    f"Engagement: {mkt_row['avg_engagement']:.0f}/100 — Commercial: {mkt_row['avg_commercial']:.0f}/100",
                    "Targeted digital campaign with localised matchday content",
                ))
                score_color = "#c8f135" if mkt_row["acquisition_score"] >= 70 else "#f59e0b" if mkt_row["acquisition_score"] >= 50 else "#3d9cf0"
                st.markdown(card(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                    f'  <span style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:{score_color}">{country}</span>'
                    f'  <span style="background:#13161d;color:{score_color};border:1px solid {score_color};'
                    f'      font-size:11px;padding:3px 12px;border-radius:8px">Priority Score: {mkt_row["acquisition_score"]:.0f}</span>'
                    f'</div>'
                    f'<div style="font-size:11px;color:#9ca3af;margin-bottom:4px"><b style="color:#e5e7eb">{tpl[0]}</b> — {tpl[1]}</div>'
                    f'<div style="display:flex;gap:18px;font-size:10px;color:#6b7280;margin-bottom:8px">'
                    f'  <span>Fans: <b style="color:#e5e7eb">{int(mkt_row["fan_count"]):,}</b></span>'
                    f'  <span>Avg Engagement: <b style="color:#3d9cf0">{mkt_row["avg_engagement"]:.0f}</b></span>'
                    f'  <span>Avg Commercial: <b style="color:#c8f135">{mkt_row["avg_commercial"]:.0f}</b></span>'
                    f'  <span>Growth Headroom: <b style="color:#22c55e">{mkt_row["growth_headroom"]:.0f}%</b></span>'
                    f'</div>'
                    f'<div style="font-size:10px;color:#6b7280;border-left:2px solid {score_color};padding-left:8px">'
                    f'  Recommended activation: <span style="color:#9ca3af">{tpl[2]}</span></div>',
                    bg="#0d1117", border=score_color,
                ), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — PLAYER INTELLIGENCE
# ─────────────────────────────────────────────────────────────────────────────
with tab_player:
    if st.session_state.get("schema_mode") == "custom":
        _locked_tab_msg()
    elif "df_processed" not in st.session_state:
        st.markdown(card(
            '<div style="text-align:center;color:#6b7280;font-size:12px;padding:24px">'
            'Upload a CSV in the Upload tab to unlock Player Intelligence.</div>'
        ), unsafe_allow_html=True)
    else:
        df_pl      = st.session_state["df_processed"]
        col_pl     = st.session_state.get("col_map", {})
        club_name  = st.session_state.get("club_name", "").strip()

        # Check for Favourite_Player column
        _fav_player_col = None
        _df_raw_pl = st.session_state.get("df_raw")
        if _df_raw_pl is not None:
            for raw_col in _df_raw_pl.columns:
                if raw_col.strip().lower().replace(" ", "_") in ("favourite_player", "favorite_player",
                                                                  "fav_player", "preferred_player",
                                                                  "favourite_player_name", "favorite_player_name"):
                    _fav_player_col = raw_col
                    break

        has_player_col = _fav_player_col is not None

        heading   = f"{club_name} - Player Intelligence" if club_name else "Player Intelligence"

        # ── Insight banner ──────────────────────────────────────────────────
        _pl_loyal  = int((df_pl["segment"] == "Loyal Fans").sum())
        _pl_hp     = int((df_pl["segment"] == "High Potential").sum())
        _pl_wb     = int((df_pl["segment"] == "Win Back").sum())
        _pl_s1 = (f"You have {_pl_loyal:,} Loyal Fans and {_pl_hp:,} High Potential fans \u2014 "
                  f"your most commercially valuable audience for player-led campaigns.")
        _pl_s2 = (f"Target Win Back fans ({_pl_wb:,}) with personalised player content "
                  f"to re-engage lapsed supporters at low acquisition cost.")
        insight_banner(_pl_s1, _pl_s2)

        st.markdown(
            f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
            f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
            f'<div style="font-size:11px;color:#6b7280;margin-bottom:6px">'
            f'Player commercial value scores and fan affinity mapping.</div>',
            unsafe_allow_html=True,
        )

        if not has_player_col:
            _locked_tab_msg(
                "Add a <b>Favourite_Player</b> column to your CSV to unlock Player Intelligence. "
                "This column should contain the name of each fan's favourite player."
            )
        else:
            # Real player column found — use it
            df_pl = df_pl.copy()
            df_pl["_player"] = st.session_state["df_raw"][_fav_player_col].astype(str).values
            player_df = compute_player_scores(df_pl)

            st.markdown(
                f'<div style="background:#052e16;border:1px solid #166534;border-radius:6px;padding:6px 14px;'
                f'margin-bottom:16px;font-size:10px;color:#22c55e">'
                f'Live data from column: <b>{_fav_player_col}</b></div>',
                unsafe_allow_html=True,
            )

        if has_player_col:
            df_with_players = df_pl  # already has _player

        if has_player_col:
            # ── KPIs ──────────────────────────────────────────────────────────
            top_player = player_df.iloc[0]
            pl1, pl2, pl3, pl4 = st.columns(4)
            with pl1: st.markdown(kpi("Players Tracked", str(len(player_df)), "in fan dataset"), unsafe_allow_html=True)
            with pl2: st.markdown(kpi("Top Commercial Value", top_player["player"].split()[0], f"Score: {top_player['commercial_value_score']:.0f}", "#c8f135"), unsafe_allow_html=True)
            with pl3: st.markdown(kpi("Avg Loyal Fan Share", f"{player_df['loyal_fan_pct'].mean():.0f}%", "per player's fanbase", "#22c55e"), unsafe_allow_html=True)
            with pl4: st.markdown(kpi("Avg Conversion Score", f"{player_df['avg_conversion'].mean():.0f}", "per player's fanbase", "#a78bfa"), unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            # ── Charts row ────────────────────────────────────────────────────
            plc1, plc2 = st.columns(2)
            with plc1:
                st.plotly_chart(chart_player_value_bar(player_df), use_container_width=True,
                                config={"displayModeBar": False}, key="player_value_bar")
            with plc2:
                st.plotly_chart(chart_player_affinity_heatmap(df_with_players), use_container_width=True,
                                config={"displayModeBar": False}, key="player_affinity_heatmap")

            # ── Player data table ─────────────────────────────────────────────
            section_heading("Player Commercial Value Table")
            st.dataframe(
                player_df.rename(columns={
                    "player": "Player", "fan_count": "Fans",
                    "avg_engagement": "Avg Engagement", "avg_commercial": "Avg Commercial",
                    "avg_loyalty": "Avg Loyalty", "loyal_fan_pct": "Loyal Fan %",
                    "high_potential_pct": "High Potential %", "avg_conversion": "Avg Conversion",
                    "commercial_value_score": "Commercial Value Score",
                }).style.background_gradient(subset=["Commercial Value Score"], cmap="RdYlGn"),
                use_container_width=True, height=360, hide_index=True,
            )

            # ── Recommended commercial actions per player ─────────────────────
            section_heading("Recommended Commercial Actions per Player")

            for _, prow in player_df.head(5).iterrows():
                score = prow["commercial_value_score"]
                loyal = prow["loyal_fan_pct"]
                hp    = prow["high_potential_pct"]
                conv  = prow["avg_conversion"]
                eng   = prow["avg_engagement"]

                if loyal >= 20:
                    action = f"Highest affinity with Loyal Fans ({loyal:.0f}%) - ideal for premium membership or season ticket renewal campaign."
                elif hp >= 18:
                    action = f"Strong High Potential fanbase ({hp:.0f}%) - target with first-purchase conversion offer or membership upgrade."
                elif conv >= 60:
                    action = f"High conversion probability ({conv:.0f}/100) - prioritise for limited-edition retail or matchday hospitality upsell."
                else:
                    action = f"Broad casual fan appeal (engagement: {eng:.0f}) - best suited for awareness campaigns and social media activation."

                score_c = "#c8f135" if score >= 70 else "#22c55e" if score >= 55 else "#3d9cf0"
                st.markdown(card(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                    f'  <span style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:{score_c}">{prow["player"]}</span>'
                    f'  <span style="background:#13161d;color:{score_c};border:1px solid {score_c};'
                    f'      font-size:11px;padding:3px 12px;border-radius:8px">Value Score: {score:.0f}</span>'
                    f'</div>'
                    f'<div style="display:flex;gap:16px;font-size:10px;color:#6b7280;margin-bottom:8px">'
                    f'  <span>Fans: <b style="color:#e5e7eb">{int(prow["fan_count"]):,}</b></span>'
                    f'  <span>Loyal: <b style="color:#22c55e">{loyal:.0f}%</b></span>'
                    f'  <span>High Potential: <b style="color:#3d9cf0">{hp:.0f}%</b></span>'
                    f'  <span>Avg Conversion: <b style="color:#a78bfa">{conv:.0f}</b></span>'
                    f'</div>'
                    f'<div style="font-size:10px;color:#9ca3af;border-left:2px solid {score_c};padding-left:8px">{action}</div>',
                    bg="#0d1117", border=score_c,
                ), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — SPONSORSHIP INTELLIGENCE
# ─────────────────────────────────────────────────────────────────────────────
with tab_sponsor:
    if st.session_state.get("schema_mode") == "custom":
        _locked_tab_msg()
    elif "df_processed" not in st.session_state:
        st.markdown(card(
            '<div style="text-align:center;color:#6b7280;font-size:12px;padding:24px">'
            'Upload a CSV in the Upload tab to unlock Sponsorship Intelligence.</div>'
        ), unsafe_allow_html=True)
    else:
        df_sp     = st.session_state["df_processed"]
        col_sp    = st.session_state.get("col_map", {})
        club_name = st.session_state.get("club_name", "").strip()
        heading   = f"{club_name} — Sponsorship Intelligence" if club_name else "Sponsorship Intelligence"
        st.markdown(
            f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
            f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
            f'<div style="font-size:11px;color:#6b7280;margin-bottom:18px">'
            f'Fan demographic breakdown, audience quality metrics, and sponsor category recommendations '
            f'ready to present to commercial partners.</div>',
            unsafe_allow_html=True,
        )

        # ── Insight banner ──────────────────────────────────────────────────
        _sp_pitch = compute_sponsorship_pitch_score(df_sp)
        _sp_loyal = df_sp[df_sp["segment"] == "Loyal Fans"]["commercial_score"].mean()
        _sp_hp    = int((df_sp["segment"] == "High Potential").sum())
        _sp_s1 = (f"Your Loyal Fans average a commercial score of {_sp_loyal:.0f} "
                  f"and your overall pitch score is {_sp_pitch:.0f}/100 \u2014 "
                  f"a strong foundation for premium brand and financial services partners.")
        _sp_s2 = (f"Converting your {_sp_hp:,} High Potential fans to membership "
                  f"would meaningfully lift your commercial score and sponsorship valuation.")
        insight_banner(_sp_s1, _sp_s2)

        pitch_score = compute_sponsorship_pitch_score(df_sp)
        pitch_color = "#22c55e" if pitch_score >= 70 else "#f59e0b" if pitch_score >= 50 else "#ef4444"
        pitch_label = "Excellent" if pitch_score >= 70 else "Good" if pitch_score >= 50 else "Developing"

        # ── Sponsorship Pitch Score hero ───────────────────────────────────────
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid {pitch_color}40;border-radius:12px;'
            f'padding:24px 28px;margin-bottom:18px;display:flex;align-items:center;gap:28px">'
            f'  <div>'
            f'    <div style="font-size:10px;color:#4b5563;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">Sponsorship Pitch Score</div>'
            f'    <div style="font-family:\'Syne\',sans-serif;font-size:52px;font-weight:800;color:{pitch_color};line-height:1">{pitch_score}</div>'
            f'    <div style="font-size:13px;color:{pitch_color};margin-top:4px">/ 100 — {pitch_label}</div>'
            f'  </div>'
            f'  <div style="font-size:11px;color:#6b7280;line-height:1.8;flex:1">'
            f'    Commercial attractiveness score for sponsors based on fan engagement, '
            f'    purchase propensity, segment quality and churn stability.<br>'
            f'    <span style="color:#9ca3af">Engagement 25% · Commercial 35% · Loyal Fan % 20% · High Potential % 10% · Low Churn % 10%</span>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── KPIs ──────────────────────────────────────────────────────────────
        total_sp   = len(df_sp)
        loyal_pct  = (df_sp["segment"] == "Loyal Fans").mean() * 100
        hp_pct     = (df_sp["segment"] == "High Potential").mean() * 100
        low_ch_pct = (df_sp["churn_risk_label"] == "LOW").mean() * 100

        sp1, sp2, sp3, sp4 = st.columns(4)
        with sp1: st.markdown(kpi("Fan Base Size", f"{total_sp:,}", "analysed fans"), unsafe_allow_html=True)
        with sp2: st.markdown(kpi("Loyal Fans", f"{loyal_pct:.0f}%", "premium audience tier", "#22c55e"), unsafe_allow_html=True)
        with sp3: st.markdown(kpi("High Potential", f"{hp_pct:.0f}%", "conversion-ready fans", "#3d9cf0"), unsafe_allow_html=True)
        with sp4: st.markdown(kpi("Low Churn", f"{low_ch_pct:.0f}%", "stable audience", "#c8f135"), unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── Charts row 1: age donut + commercial dist ─────────────────────────
        spc1, spc2 = st.columns(2)
        with spc1:
            st.plotly_chart(chart_sponsor_age_donut(df_sp), use_container_width=True,
                            config={"displayModeBar": False}, key="sponsor_age_donut")
        with spc2:
            st.plotly_chart(chart_sponsor_commercial_dist(df_sp), use_container_width=True,
                            config={"displayModeBar": False}, key="sponsor_commercial_dist")

        # ── Segment value for sponsors ─────────────────────────────────────────
        st.plotly_chart(chart_sponsor_segment_value(df_sp), use_container_width=True,
                        config={"displayModeBar": False}, key="sponsor_seg_value")

        # ── Sponsor category recommendations ──────────────────────────────────
        section_heading("Top 5 Sponsor Category Recommendations")
        sponsor_recs = get_sponsor_recommendations(df_sp, col_sp)
        fit_colors   = {"HIGH": "#22c55e", "MED": "#f59e0b", "LOW": "#3d9cf0"}
        fit_bg       = {"HIGH": "#052e16", "MED": "#1c1500", "LOW": "#0a1a2e"}

        for rec in sponsor_recs:
            fc = fit_colors.get(rec["fit"], "#6b7280")
            fb = fit_bg.get(rec["fit"], "#13161d")
            st.markdown(card(
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                f'  <span style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:#e5e7eb">{rec["category"]}</span>'
                f'  <span style="background:{fb};color:{fc};border:1px solid {fc};font-size:10px;padding:3px 10px;border-radius:8px">{rec["fit"]} FIT</span>'
                f'</div>'
                f'<div style="font-size:11px;color:#9ca3af;margin-bottom:6px">{rec["reason"]}</div>'
                f'<div style="font-size:10px;color:#6b7280">Example brands: <span style="color:#9ca3af">{rec["examples"]}</span></div>',
                bg="#0d1117", border=fc,
            ), unsafe_allow_html=True)

        # ── Download sponsorship PDF ───────────────────────────────────────────
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        section_heading("Download Sponsorship Deck")
        today_str_sp = datetime.today().strftime("%Y-%m-%d")
        sponsor_pdf = generate_sponsor_pdf(df_sp, club_name)
        st.download_button(
            "⬇  Download One-Page Sponsorship Deck (PDF)",
            data=sponsor_pdf,
            file_name=f"sponsorship_deck_{club_name.replace(' ', '_').lower() if club_name else 'footintel'}_{today_str_sp}.pdf",
            mime="application/pdf",
            key="sponsor_pdf_download",
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 7 — MATCHDAY INTELLIGENCE
# ─────────────────────────────────────────────────────────────────────────────
with tab_matchday:
    if st.session_state.get("schema_mode") == "custom":
        _locked_tab_msg()
    elif "df_processed" not in st.session_state:
        st.markdown(card(
            '<div style="text-align:center;color:#6b7280;font-size:12px;padding:24px">'
            'Upload a CSV in the Upload tab to unlock Matchday Intelligence.</div>'
        ), unsafe_allow_html=True)
    else:
        df_md_tab  = st.session_state["df_processed"]
        col_md     = st.session_state.get("col_map", {})
        club_name  = st.session_state.get("club_name", "").strip()
        heading    = f"{club_name} — Matchday Intelligence" if club_name else "Matchday Intelligence"
        st.markdown(
            f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
            f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
            f'<div style="font-size:11px;color:#6b7280;margin-bottom:18px">'
            f'Expected matchday revenue, hospitality upsell opportunities, and engagement windows. '
            f'Revenue figures are <b style="color:#f59e0b">estimated</b> from segment-level commercial scores.</div>',
            unsafe_allow_html=True,
        )

        # ── Insight banner ──────────────────────────────────────────────────
        _md_tmp = compute_matchday_data(df_md_tab, col_md)
        _md_rev = _md_tmp["rev_by_seg"]["estimated_revenue"].sum() if "estimated_revenue" in _md_tmp["rev_by_seg"].columns else 0
        _md_hosp = len(_md_tmp.get("hospitality_targets", []))
        _md_s1 = (f"Estimated matchday revenue across all segments is \u00a3{_md_rev:,.0f} \u2014 "
                  f"with hospitality upsell opportunities identified for {_md_hosp} fan profiles.")
        _md_s2 = ("Focus pre-match communications on High Potential and Loyal Fan segments "
                  "to maximise hospitality conversion and merchandise spend per head.")
        insight_banner(_md_s1, _md_s2)

        md_data = compute_matchday_data(df_md_tab, col_md)
        rev_df  = md_data["rev_by_seg"]
        hosp    = md_data["hospitality_targets"]
        windows = md_data["windows"]

        # ── KPIs ──────────────────────────────────────────────────────────────
        top_seg_row = rev_df.sort_values("total_est_revenue", ascending=False).iloc[0]
        hp_opp      = md_data["hp_count"]
        hp_conv_rev = hp_opp * md_data["hp_avg_spend"] * 0.10  # 10% conversion estimate

        md1, md2, md3, md4 = st.columns(4)
        with md1: st.markdown(kpi("Total Est. Matchday Revenue", f"£{md_data['total_est_revenue']:,.0f}", "per fixture (all fans)", "#c8f135"), unsafe_allow_html=True)
        with md2: st.markdown(kpi("Top Revenue Segment", top_seg_row["segment"], f"£{top_seg_row['total_est_revenue']:,.0f} est.", "#22c55e"), unsafe_allow_html=True)
        with md3: st.markdown(kpi("Hospitality Upsell Targets", f"{len(hosp):,}", "Loyal/High Potential, no tickets yet", "#3d9cf0"), unsafe_allow_html=True)
        with md4: st.markdown(kpi("High Potential Fans", f"{hp_opp:,}", "conversion opportunity", "#a78bfa"), unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── Revenue charts ─────────────────────────────────────────────────────
        mdc1, mdc2 = st.columns(2)
        with mdc1:
            st.plotly_chart(chart_matchday_revenue_by_segment(rev_df), use_container_width=True,
                            config={"displayModeBar": False}, key="matchday_rev_seg")
        with mdc2:
            st.plotly_chart(chart_matchday_avg_spend(rev_df), use_container_width=True,
                            config={"displayModeBar": False}, key="matchday_avg_spend")

        # ── Engagement windows ─────────────────────────────────────────────────
        section_heading("Pre / During / Post-Match Engagement Windows")
        st.plotly_chart(chart_engagement_windows(windows), use_container_width=True,
                        config={"displayModeBar": False}, key="matchday_windows")

        # ── Revenue opportunity callout ────────────────────────────────────────
        st.markdown(
            f'<div style="background:#0a1a2e;border:1px solid #1d4ed8;border-radius:10px;'
            f'padding:18px 22px;margin:14px 0">'
            f'  <div style="font-size:11px;color:#3d9cf0;font-weight:600;margin-bottom:6px">💡 Revenue Opportunity</div>'
            f'  <div style="font-size:12px;color:#9ca3af;line-height:1.8">'
            f'    You have <b style="color:#e5e7eb">{hp_opp:,} High Potential fans</b> who are highly engaged '
            f'    but not yet converted to matchday attendance.<br>'
            f'    Converting just <b style="color:#c8f135">10%</b> of this group at an estimated '
            f'    <b style="color:#c8f135">£{md_data["hp_avg_spend"]:.0f}</b> avg spend = '
            f'    <b style="color:#22c55e">£{hp_conv_rev:,.0f} estimated additional revenue</b> per fixture.'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Top 20 fans for matchday hospitality upgrade ───────────────────────
        section_heading("Top 20 Hospitality Upgrade Targets")
        st.markdown(
            '<div style="font-size:11px;color:#6b7280;margin-bottom:8px">'
            'Loyal Fans and High Potential fans with no ticket purchase history, ranked by conversion probability.</div>',
            unsafe_allow_html=True,
        )
        if not hosp.empty:
            col_md_stored = col_md
            disp_md = (
                [col_md_stored["user_id"]] if "user_id" in col_md_stored else []
            ) + [c for c in ["segment", "journey_stage", "conversion_probability",
                              "engagement_score", "commercial_score", "churn_risk_label",
                              "matchday_spend_est"] if c in hosp.columns]
            st.dataframe(
                hosp[disp_md].reset_index(drop=True)
                .style.background_gradient(subset=["conversion_probability"], cmap="RdYlGn"),
                use_container_width=True, height=400,
            )
        else:
            st.info("No Loyal or High Potential fans without ticket history found.")

        # ── Segment revenue table ──────────────────────────────────────────────
        section_heading("Matchday Revenue Summary by Segment")
        rev_display = rev_df.copy()
        rev_display["total_est_revenue"] = rev_display["total_est_revenue"].apply(lambda v: f"£{v:,.0f}")
        rev_display["avg_spend"]         = rev_display["avg_spend"].apply(lambda v: f"£{v:.2f}")
        rev_display.columns              = ["Segment", "Fan Count", "Est. Total Revenue", "Est. Avg Spend"]
        st.dataframe(rev_display, use_container_width=True, hide_index=True)
