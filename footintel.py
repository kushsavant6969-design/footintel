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
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


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

tab_upload, tab_dashboard, tab_report = st.tabs(["⬆  Upload & Configure", "📊  Dashboard", "📄  Report"])

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
        st.download_button(
            "⬇  Download sample CSV (400 fans)",
            data=sample_bytes, file_name="footintel_sample.csv", mime="text/csv",
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

    # ── Column mapping form ────────────────────────────────────────────────────
    if "df_raw" in st.session_state and "df_processed" not in st.session_state:
        df_raw       = st.session_state["df_raw"]
        col_map_auto = st.session_state.get("col_map_auto", {})
        csv_cols     = list(df_raw.columns)
        options      = ["— not mapped —"] + csv_cols

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        section_heading("Map Your Columns")
        st.markdown(card(
            f'<div style="font-size:11px;color:#9ca3af">'
            f'Review and confirm the column mapping. Fields auto-matched from your CSV are pre-filled. '
            f'<b style="color:#c8f135">Missing columns will use neutral scores — map as many as possible for accuracy.</b><br><br>'
            f'<span style="color:#22c55e">{len(df_raw):,} fans loaded</span> &nbsp;·&nbsp; '
            f'<span style="color:#22c55e">{len(df_raw.columns)} columns detected</span> &nbsp;·&nbsp; '
            f'<span style="color:#c8f135">{len(col_map_auto)} auto-matched</span>'
            f'</div>'
        ), unsafe_allow_html=True)

        def _idx(field: str) -> int:
            v = col_map_auto.get(field)
            return options.index(v) if v and v in options else 0

        GRP_STYLE = (
            '<div style="font-size:10px;color:#6b7280;text-transform:uppercase;'
            'letter-spacing:.08em;margin:14px 0 6px">'
        )

        with st.form("col_mapping_form"):
            st.markdown(GRP_STYLE + "Identifiers &amp; Demographics</div>", unsafe_allow_html=True)
            d1, d2, d3, d4 = st.columns(4)
            uid = d1.selectbox("User ID",         options, index=_idx("user_id"),  key="map_user_id")
            age = d2.selectbox("Age",              options, index=_idx("age"),      key="map_age")
            gen = d3.selectbox("Gender",           options, index=_idx("gender"),   key="map_gender")
            cty = d4.selectbox("Country / Region", options, index=_idx("country"),  key="map_country")

            st.markdown(GRP_STYLE + "Fan Profile</div>", unsafe_allow_html=True)
            p1, p2, p3, _ = st.columns(4)
            mcat = p1.selectbox("Membership Category", options, index=_idx("membership_category"), key="map_membership_category")
            ftyp = p2.selectbox("Fan Type",            options, index=_idx("fan_type"),            key="map_fan_type")
            happ = p3.selectbox("Has App (Yes/No)",    options, index=_idx("has_app"),             key="map_has_app")

            st.markdown(GRP_STYLE + "Email Channel</div>", unsafe_allow_html=True)
            e1, e2, e3, e4 = st.columns(4)
            emo  = e1.selectbox("Email Opens",              options, index=_idx("email_opens"),              key="map_email_opens")
            ecl  = e2.selectbox("Email Clicks",             options, index=_idx("email_clicks"),             key="map_email_clicks")
            ecr  = e3.selectbox("Email Campaigns Received", options, index=_idx("email_campaigns_received"), key="map_email_campaigns_received")
            leo  = e4.selectbox("Last Email Open",          options, index=_idx("last_email_open"),          key="map_last_email_open")

            st.markdown(GRP_STYLE + "In-App Channel</div>", unsafe_allow_html=True)
            i1, i2, i3, i4 = st.columns(4)
            iao  = i1.selectbox("InApp Opens",              options, index=_idx("inapp_opens"),              key="map_inapp_opens")
            icl  = i2.selectbox("InApp Clicks",             options, index=_idx("inapp_clicks"),             key="map_inapp_clicks")
            icr  = i3.selectbox("InApp Campaigns Received", options, index=_idx("inapp_campaigns_received"), key="map_inapp_campaigns_received")
            lao  = i4.selectbox("Last App Open",            options, index=_idx("last_app_open"),            key="map_last_app_open")

            st.markdown(GRP_STYLE + "Content &amp; Article Engagement</div>", unsafe_allow_html=True)
            c1, c2, c3, _ = st.columns(4)
            arv  = c1.selectbox("Article Views",        options, index=_idx("article_views"),    key="map_article_views")
            fav  = c2.selectbox("First Article View",   options, index=_idx("first_article_view"), key="map_first_article_view")
            lav  = c3.selectbox("Last Article View",    options, index=_idx("last_article_view"),  key="map_last_article_view")

            st.markdown(GRP_STYLE + "Commercial</div>", unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            tix  = m1.selectbox("Ticket Purchases",     options, index=_idx("ticket_purchases"),     key="map_ticket_purchases")
            msp  = m2.selectbox("Membership Purchases", options, index=_idx("membership_purchases"), key="map_membership_purchases")
            ret  = m3.selectbox("Retail Purchases",     options, index=_idx("retail_purchases"),     key="map_retail_purchases")
            rev  = m4.selectbox("Total Revenue",        options, index=_idx("total_revenue"),        key="map_total_revenue")

            st.markdown(GRP_STYLE + "Date Columns</div>", unsafe_allow_html=True)
            t1, t2, t3, t4 = st.columns(4)
            fpd  = t1.selectbox("First Purchase Date", options, index=_idx("first_purchase_date"), key="map_first_purchase_date")
            lpd  = t2.selectbox("Last Purchase Date",  options, index=_idx("last_purchase_date"),  key="map_last_purchase_date")
            fao  = t3.selectbox("First App Open",      options, index=_idx("first_app_open"),      key="map_first_app_open")
            jnd  = t4.selectbox("Join Date",           options, index=_idx("join_date"),           key="map_join_date")

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("✓  Confirm Mapping & Analyse Fans")

            if submitted:
                raw_sel = {
                    "user_id": uid, "age": age, "gender": gen, "country": cty,
                    "membership_category": mcat, "fan_type": ftyp, "has_app": happ,
                    "email_opens": emo, "email_clicks": ecl, "email_campaigns_received": ecr,
                    "last_email_open": leo,
                    "inapp_opens": iao, "inapp_clicks": icl, "inapp_campaigns_received": icr,
                    "last_app_open": lao,
                    "article_views": arv, "first_article_view": fav, "last_article_view": lav,
                    "ticket_purchases": tix, "membership_purchases": msp, "retail_purchases": ret,
                    "total_revenue": rev,
                    "first_purchase_date": fpd, "last_purchase_date": lpd,
                    "first_app_open": fao, "join_date": jnd,
                }
                confirmed_map = {f: v for f, v in raw_sel.items() if v != "— not mapped —"}
                st.session_state["col_map"] = confirmed_map
                df_proc = process_data(df_raw, confirmed_map)
                st.session_state["df_processed"] = df_proc
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab_dashboard:
    if "df_processed" not in st.session_state:
        st.markdown(card(
            '<div style="text-align:center;color:#6b7280;font-size:12px;padding:24px">'
            'Upload a CSV in the Upload tab to populate the dashboard.</div>'
        ), unsafe_allow_html=True)
    else:
        df_all         = st.session_state["df_processed"]
        col_map_stored = st.session_state.get("col_map", {})
        club_name      = st.session_state.get("club_name", "").strip()

        heading = f"{club_name} — Fan Dashboard" if club_name else "Fan Dashboard"
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

            # ── Top 20 fans ────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — REPORT
# ─────────────────────────────────────────────────────────────────────────────
with tab_report:
    if "df_processed" not in st.session_state:
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
