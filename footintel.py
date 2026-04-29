import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import io
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
    "Champions": {
        "color": "#c8f135", "bg": "#0d1a00", "icon": "⭐",
        "description": "Highly engaged, high-spend, long-term fans. Your most valuable asset.",
        "recommendation": "Offer VIP experiences, exclusive early access, and loyalty tier upgrades. Leverage as brand ambassadors and referral advocates — their NPS is your cheapest acquisition channel.",
        "actions": ["Early bird season ticket access", "Exclusive meet & greet events", "Loyalty tier upgrade", "Ambassador programme invite"],
        "risk": "LOW",
    },
    "Loyal Fans": {
        "color": "#22c55e", "bg": "#052e16", "icon": "💚",
        "description": "Long-term fans with consistent purchasing behaviour across multiple categories.",
        "recommendation": "Introduce premium membership tiers and season ticket bundles. Reward tenure with exclusive content drops, fan recognition moments, and anniversary perks.",
        "actions": ["Premium membership upsell", "Fan anniversary reward", "Behind-the-scenes content access", "Multi-year season ticket incentive"],
        "risk": "LOW",
    },
    "High Potential": {
        "color": "#3d9cf0", "bg": "#0a1a2e", "icon": "🚀",
        "description": "Highly engaged fans who have not yet been converted to commercial value.",
        "recommendation": "Convert engagement to revenue with first-purchase welcome offers, matchday ticket bundles, and merchandise discounts timed to peak engagement moments.",
        "actions": ["First-purchase welcome offer (15% off)", "Matchday ticket bundle", "Merch discount triggered by app activity", "Premium app tier free trial"],
        "risk": "MED",
    },
    "Rising Stars": {
        "color": "#a78bfa", "bg": "#1a0a2e", "icon": "🌟",
        "description": "New fans already showing strong engagement signals — high growth potential.",
        "recommendation": "Deliver an exceptional onboarding experience: welcome email series, community introductions, guided content discovery, and a compelling first-purchase incentive.",
        "actions": ["Welcome journey email series", "New fan merch discount (20%)", "Community forum / Discord access", "First matchday experience package"],
        "risk": "MED",
    },
    "At Risk": {
        "color": "#f59e0b", "bg": "#1c1500", "icon": "⚠️",
        "description": "Previously active fans showing declining engagement and purchase frequency.",
        "recommendation": "Trigger personalised re-engagement campaigns based on past behaviour. Time-limited win-back offers and match highlight reels to rekindle emotional connection.",
        "actions": ["Personalised re-engagement email", "Exclusive comeback offer (20% off)", "Match highlight reel push notification", "Loyalty bonus reinstatement"],
        "risk": "HIGH",
    },
    "Dormant": {
        "color": "#6b7280", "bg": "#111827", "icon": "💤",
        "description": "Long-tenure fans with very low recent activity across all channels.",
        "recommendation": "Nostalgia-driven campaigns, big match alerts, and limited-time membership reactivation offers. A survey with an incentive can surface the churn reason.",
        "actions": ["Nostalgia content campaign", "Big match push notification", "Reactivation offer (30% off)", "Churn survey with incentive"],
        "risk": "HIGH",
    },
    "Win Back": {
        "color": "#ef4444", "bg": "#1f0a0a", "icon": "🔄",
        "description": "Fans who have not made any purchase in over 12 months — highest churn risk.",
        "recommendation": "Last-chance win-back with compelling discount codes, a personalised video message from the club, and a low-friction reactivation path.",
        "actions": ["Win-back email: 25% discount code", "Personalised club video message", "Churn survey with prize draw entry", "Free match ticket (limited seats)"],
        "risk": "HIGH",
    },
    "Casual": {
        "color": "#64748b", "bg": "#0f172a", "icon": "👤",
        "description": "General fan base — moderate, consistent engagement across all dimensions.",
        "recommendation": "Gradual deepening through monthly newsletters, matchday push notifications, and social community building. Low-cost, high-volume nurture.",
        "actions": ["Monthly club newsletter", "Matchday push notifications", "Social community / fan forum invite", "Loyalty programme introduction"],
        "risk": "MED",
    },
}

COLUMN_ALIASES: dict[str, list[str]] = {
    "user_id":              ["user_id", "userid", "user id", "id", "fan_id", "customer_id", "fan id"],
    "age":                  ["age", "age_years", "fan_age", "customer_age"],
    "gender":               ["gender", "sex"],
    "country":              ["country", "nation", "nationality", "location", "region"],
    "app_opens":            ["app_opens", "app opens", "appopens", "app_usage", "app_sessions", "sessions"],
    "email_opens":          ["email_opens", "email opens", "emailopens", "email_engagement"],
    "article_views":        ["article_views", "article views", "content_views", "page_views", "articles_read"],
    "in_app_clicks":        ["in_app_clicks", "in app clicks", "clicks", "in_app_actions", "tap_events"],
    "ticket_purchases":     ["ticket_purchases", "tickets", "ticket purchases", "ticket_count", "matches_attended"],
    "membership_purchases": ["membership_purchases", "memberships", "membership purchases", "subscriptions", "subs"],
    "retail_purchases":     ["retail_purchases", "retail", "retail purchases", "merchandise", "merch_purchases", "shop_orders"],
    "last_purchase_date":   ["last_purchase_date", "last purchase date", "last_purchase", "last_transaction_date", "last_order_date", "most_recent_purchase"],
    "join_date":            ["join_date", "joined_date", "first_seen", "registration_date", "signup_date", "date_joined", "created_at", "fan_since"],
    "total_revenue":        ["total_revenue", "revenue", "total_spend", "ltv", "spend", "total_value", "lifetime_value"],
}

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
        f'<div style="background:#13161d;border:1px solid #1f2937;border-radius:10px;'
        f'padding:18px 20px;">'
        f'<div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.1em;'
        f'margin-bottom:8px">{label}</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:30px;font-weight:800;'
        f'color:{color};line-height:1">{value}</div>'
        f'<div style="font-size:11px;color:#6b7280;margin-top:6px">{sub}</div>'
        f'</div>'
    )


def seg_pill(segment: str) -> str:
    info = SEGMENT_INFO.get(segment, {"color": "#6b7280", "bg": "#111827", "icon": "·"})
    return (
        f'<span style="background:{info["bg"]};color:{info["color"]};'
        f'border:1px solid {info["color"]};font-size:9px;padding:2px 8px;'
        f'border-radius:8px">{info["icon"]} {segment}</span>'
    )


# ── Data processing ───────────────────────────────────────────────────────────

def _norm(name: str) -> str:
    return str(name).lower().strip().replace(" ", "_").replace("-", "_")


def detect_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map internal field names to actual CSV column names via alias matching."""
    df_norm = {_norm(c): c for c in df.columns}
    mapping: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if _norm(alias) in df_norm:
                mapping[field] = df_norm[_norm(alias)]
                break
    return mapping


def _pct(series: pd.Series) -> pd.Series:
    """Percentile-rank a numeric series to 0–100. Returns 50 if all identical."""
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


def compute_engagement_score(df: pd.DataFrame, col: dict) -> pd.Series:
    weights = {"app_opens": 0.30, "email_opens": 0.25, "article_views": 0.25, "in_app_clicks": 0.20}
    score = pd.Series(0.0, index=df.index)
    missing_weight = 0.0
    for field, w in weights.items():
        if field in col:
            score += _pct(df[col[field]]) * w
        else:
            missing_weight += w
    # Redistribute missing weight as neutral 50
    if missing_weight > 0:
        score += 50.0 * missing_weight
    return score.clip(0, 100)


def compute_commercial_score(df: pd.DataFrame, col: dict) -> tuple[pd.Series, pd.Series]:
    """Returns (commercial_score, recency_days)."""
    today = datetime.today()

    # Revenue / proxy (40%)
    if "total_revenue" in col:
        rev = _pct(df[col["total_revenue"]]) * 0.40
    else:
        purchases = pd.Series(0.0, index=df.index)
        for f in ("ticket_purchases", "membership_purchases", "retail_purchases"):
            if f in col:
                purchases += pd.to_numeric(df[col[f]], errors="coerce").fillna(0)
        rev = _pct(purchases) * 0.40

    # Recency (35%) — exponential decay; 0 days = 100, 180 days ≈ 37, 365 days ≈ 13
    if "last_purchase_date" in col:
        dates = pd.to_datetime(df[col["last_purchase_date"]], errors="coerce")
        recency_days = (today - dates).dt.days.fillna(730)
    else:
        recency_days = pd.Series(365.0, index=df.index)
    recency_score = (100 * np.exp(-recency_days / 180)).clip(0, 100) * 0.35

    # Frequency (25%)
    freq = pd.Series(0.0, index=df.index)
    for f in ("ticket_purchases", "membership_purchases", "retail_purchases"):
        if f in col:
            freq += pd.to_numeric(df[col[f]], errors="coerce").fillna(0)
    freq_score = _pct(freq) * 0.25

    score = (rev + recency_score + freq_score).clip(0, 100)
    return score, recency_days


def compute_loyalty_score(df: pd.DataFrame, col: dict) -> tuple[pd.Series, pd.Series]:
    """Returns (loyalty_score, tenure_days)."""
    today = datetime.today()

    # Tenure (40%) — capped at 5 years = 100
    if "join_date" in col:
        join = pd.to_datetime(df[col["join_date"]], errors="coerce")
        tenure_days = (today - join).dt.days.fillna(0).clip(0)
    else:
        tenure_days = pd.Series(365.0, index=df.index)
    tenure_score = (tenure_days / 1825 * 100).clip(0, 100) * 0.40

    # Purchase diversity across 3 categories (35%) — full diversity = 100
    diversity = pd.Series(0.0, index=df.index)
    for f in ("ticket_purchases", "membership_purchases", "retail_purchases"):
        if f in col:
            has = (pd.to_numeric(df[col[f]], errors="coerce").fillna(0) > 0).astype(float)
            diversity += has * (100 / 3)
    if all(f not in col for f in ("ticket_purchases", "membership_purchases", "retail_purchases")):
        diversity = pd.Series(33.0, index=df.index)
    diversity_score = diversity * 0.35

    # Purchase frequency consistency (25%)
    total_purchases = pd.Series(0.0, index=df.index)
    for f in ("ticket_purchases", "membership_purchases", "retail_purchases"):
        if f in col:
            total_purchases += pd.to_numeric(df[col[f]], errors="coerce").fillna(0)
    freq_score = _pct(total_purchases) * 0.25

    score = (tenure_score + diversity_score + freq_score).clip(0, 100)
    return score, tenure_days


def assign_segment(row: pd.Series) -> str:
    e = row["engagement_score"]
    c = row["commercial_score"]
    l = row["loyalty_score"]
    tenure  = row.get("tenure_days",  365)
    recency = row.get("recency_days", 365)

    if e >= 70 and c >= 70 and l >= 70:
        return "Champions"
    if l >= 70 and c >= 50:
        return "Loyal Fans"
    if e >= 65 and c < 45:
        return "High Potential"
    if tenure <= 180 and e >= 45:
        return "Rising Stars"
    if l >= 55 and 120 < recency < 365:
        return "At Risk"
    if e < 30 and c < 30 and l >= 40:
        return "Dormant"
    if recency >= 365 and (l >= 30 or c >= 30):
        return "Win Back"
    return "Casual"


def process_data(df: pd.DataFrame, col: dict) -> pd.DataFrame:
    out = df.copy()
    out["age_group"]        = out[col["age"]].apply(assign_age_group) if "age" in col else "Unknown"
    out["engagement_score"] = compute_engagement_score(out, col).round(1)
    comm, recency_days      = compute_commercial_score(out, col)
    loy,  tenure_days       = compute_loyalty_score(out, col)
    out["commercial_score"] = comm.round(1)
    out["loyalty_score"]    = loy.round(1)
    out["recency_days"]     = recency_days.round(0)
    out["tenure_days"]      = tenure_days.round(0)
    out["composite_score"]  = ((out["engagement_score"] + out["commercial_score"] + out["loyalty_score"]) / 3).round(1)
    out["segment"]          = out.apply(assign_segment, axis=1)
    return out


# ── Sample CSV ────────────────────────────────────────────────────────────────

def generate_sample_csv() -> bytes:
    rng = np.random.default_rng(42)
    n = 400
    today = datetime(2025, 4, 1)

    ages = np.concatenate([
        rng.integers(6, 13, 40),
        rng.integers(13, 26, 120),
        rng.integers(26, 50, 160),
        rng.integers(50, 80, 80),
    ])
    rng.shuffle(ages)

    join_days   = rng.exponential(700, n).clip(30, 2190).astype(int)
    lp_days     = rng.exponential(160, n).clip(0, 730).astype(int)

    app_opens    = rng.lognormal(3.5, 1.2, n).clip(0, 600).astype(int)
    email_opens  = rng.lognormal(2.5, 1.1, n).clip(0, 120).astype(int)
    art_views    = rng.lognormal(3.0, 1.3, n).clip(0, 400).astype(int)
    clicks       = rng.lognormal(4.0, 1.2, n).clip(0, 1000).astype(int)

    tix   = rng.choice([0,1,2,3,5,8,10,15], n, p=[0.28,0.20,0.15,0.12,0.10,0.07,0.05,0.03])
    mship = rng.choice([0,1,2,3],            n, p=[0.50,0.26,0.14,0.10])
    retail= rng.choice([0,1,2,3,5,8],        n, p=[0.33,0.26,0.16,0.13,0.08,0.04])

    revenue = (
        tix   * rng.uniform(20, 65, n) +
        mship * rng.choice([49, 99, 149, 199], n) +
        retail* rng.uniform(15, 85, n)
    ).round(2)

    genders   = rng.choice(["M","F","Non-binary"], n, p=[0.54,0.41,0.05])
    countries = rng.choice(
        ["England","Scotland","Wales","Ireland","USA","Germany","Spain","Other"],
        n, p=[0.50,0.12,0.08,0.07,0.08,0.05,0.05,0.05],
    )

    df = pd.DataFrame({
        "User_ID":               [f"FAN{i:04d}" for i in range(1, n + 1)],
        "Age":                   ages,
        "Gender":                genders,
        "Country":               countries,
        "App_Opens":             app_opens,
        "Email_Opens":           email_opens,
        "Article_Views":         art_views,
        "In_App_Clicks":         clicks,
        "Ticket_Purchases":      tix,
        "Membership_Purchases":  mship,
        "Retail_Purchases":      retail,
        "Total_Revenue":         revenue,
        "Last_Purchase_Date":    [(today - timedelta(days=int(d))).strftime("%Y-%m-%d") for d in lp_days],
        "Join_Date":             [(today - timedelta(days=int(d))).strftime("%Y-%m-%d") for d in join_days],
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


# ── Charts ────────────────────────────────────────────────────────────────────

def _seg_colors(segments) -> list[str]:
    return [SEGMENT_INFO.get(s, {"color": "#6b7280"})["color"] for s in segments]


def chart_segment_donut(df: pd.DataFrame) -> go.Figure:
    counts = df["segment"].value_counts()
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values,
        hole=0.62,
        marker_colors=_seg_colors(counts.index),
        textinfo="label+percent",
        textfont_size=10,
        hovertemplate="<b>%{label}</b><br>%{value} fans (%{percent})<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_BASE, height=340,
                      title=dict(text="Fan Segment Distribution", x=0.02, y=0.97),
                      showlegend=False)
    return fig


def chart_age_segment_bar(df: pd.DataFrame) -> go.Figure:
    order = ["Child", "Young Adult", "Adult", "Senior", "Unknown"]
    pivot = df.groupby(["age_group", "segment"]).size().reset_index(name="count")
    fig = go.Figure()
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
    fig = go.Figure(go.Scatter(
        x=df["engagement_score"],
        y=df["commercial_score"],
        mode="markers",
        marker=dict(
            color=df["loyalty_score"],
            colorscale="Viridis",
            size=size,
            opacity=0.72,
            showscale=True,
            colorbar=dict(title="Loyalty", thickness=12, len=0.75, tickfont_size=9),
            line=dict(color="#0a0c10", width=0.4),
        ),
        text=df["segment"],
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Engagement: %{x:.0f}  |  Commercial: %{y:.0f}<br>"
            "Loyalty: %{marker.color:.0f}<extra></extra>"
        ),
    ))
    fig.add_hline(y=50, line_dash="dash", line_color="#2a2f3d", line_width=1)
    fig.add_vline(x=50, line_dash="dash", line_color="#2a2f3d", line_width=1)
    fig.update_layout(
        **PLOTLY_BASE, height=400,
        title=dict(text="Fan Landscape — Engagement × Commercial  (colour = Loyalty score)", x=0.02, y=0.97),
        xaxis=dict(title="Engagement Score", range=[0, 102], gridcolor="#1f2937"),
        yaxis=dict(title="Commercial Score", range=[0, 102], gridcolor="#1f2937"),
    )
    return fig


def chart_scores_by_segment(df: pd.DataFrame) -> go.Figure:
    means = (
        df.groupby("segment")[["engagement_score", "commercial_score", "loyalty_score"]]
        .mean()
        .reset_index()
    )
    fig = go.Figure()
    for col_name, color, label in [
        ("engagement_score", "#3d9cf0", "Engagement"),
        ("commercial_score", "#c8f135", "Commercial"),
        ("loyalty_score",    "#22c55e", "Loyalty"),
    ]:
        fig.add_trace(go.Bar(
            name=label, x=means["segment"], y=means[col_name].round(1),
            marker_color=color, opacity=0.85,
        ))
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
        .reset_index()
        .sort_values("avg_c")
    )
    fig = go.Figure(go.Bar(
        x=opp["avg_c"].round(1), y=opp["segment"],
        orientation="h",
        marker_color=_seg_colors(opp["segment"]),
        text=opp["fans"].astype(str) + " fans",
        textposition="outside",
        textfont_size=9,
        hovertemplate="<b>%{y}</b><br>Avg commercial score: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        **PLOTLY_BASE, height=360,
        title=dict(text="Commercial Score by Segment", x=0.02, y=0.97),
        xaxis=dict(title="Avg Commercial Score", range=[0, 115], gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
        margin=dict(l=8, r=60, t=44, b=8),
    )
    return fig


def chart_age_scores(df: pd.DataFrame) -> go.Figure:
    order = ["Child", "Young Adult", "Adult", "Senior"]
    means = (
        df[df["age_group"].isin(order)]
        .groupby("age_group")[["engagement_score", "commercial_score", "loyalty_score"]]
        .mean()
        .reset_index()
    )
    radar_df = means.set_index("age_group").reindex(order)
    categories = ["Engagement", "Commercial", "Loyalty"]
    fig = go.Figure()
    colors_ag = ["#a78bfa", "#3d9cf0", "#c8f135", "#22c55e"]
    for i, group in enumerate(order):
        if group not in radar_df.index:
            continue
        row = radar_df.loc[group]
        vals = [row["engagement_score"], row["commercial_score"], row["loyalty_score"]]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name=group,
            line_color=colors_ag[i],
            fillcolor=colors_ag[i],
            opacity=0.25,
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
            Fan_Count       =("composite_score", "count"),
            Avg_Engagement  =("engagement_score", "mean"),
            Avg_Commercial  =("commercial_score", "mean"),
            Avg_Loyalty     =("loyalty_score",    "mean"),
            Avg_Composite   =("composite_score",  "mean"),
        )
        .round(1)
        .reset_index()
    )
    s["Pct_of_Base"] = (s["Fan_Count"] / total * 100).round(1)
    s["Risk"]        = s["segment"].map({k: v["risk"] for k, v in SEGMENT_INFO.items()})
    s["Recommendation"] = s["segment"].map({k: v["recommendation"] for k, v in SEGMENT_INFO.items()})
    return s.sort_values("Avg_Composite", ascending=False)


# ── App ───────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="margin-bottom:24px">
  <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:4px">
    <span style="font-family:'Syne',sans-serif;font-size:30px;font-weight:800;color:#c8f135;letter-spacing:-1px">FootIntel</span>
    <span style="font-family:'Syne',sans-serif;font-size:16px;font-weight:400;color:#4b5563"> / Fan Segmentation &amp; LTV Analysis</span>
  </div>
  <div style="font-size:11px;color:#6b7280;letter-spacing:.04em">
    Upload fan data &nbsp;·&nbsp; Score engagement, commercial &amp; loyalty &nbsp;·&nbsp; Identify high-value segments &nbsp;·&nbsp; Act
  </div>
</div>
""", unsafe_allow_html=True)

tab_upload, tab_dashboard, tab_report = st.tabs(["⬆  Upload & Configure", "📊  Dashboard", "📄  Report"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — UPLOAD
# ─────────────────────────────────────────────────────────────────────────────
with tab_upload:
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown(card(
            '<div style="font-size:12px;color:#9ca3af">Upload a CSV of fan data. '
            'FootIntel will auto-detect your columns, score every fan across three dimensions, '
            'and segment them instantly.</div>'
        ), unsafe_allow_html=True)

        uploaded = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")

        sample_bytes = generate_sample_csv()
        st.download_button(
            "⬇  Download sample CSV (400 fans)",
            data=sample_bytes,
            file_name="footintel_sample.csv",
            mime="text/csv",
        )

        if uploaded is not None:
            try:
                df_raw = pd.read_csv(uploaded)
                col_map = detect_columns(df_raw)
                st.session_state["df_raw"]   = df_raw
                st.session_state["col_map"]  = col_map

                mapped   = list(col_map.keys())
                unmapped = [f for f in COLUMN_ALIASES if f not in col_map]

                st.markdown(card(
                    f'<div style="font-size:10px;color:#22c55e;margin-bottom:6px">'
                    f'✓ Loaded {len(df_raw):,} fans · {len(df_raw.columns)} columns</div>'
                    f'<div style="font-size:10px;color:#6b7280">Detected: '
                    f'{", ".join(mapped) if mapped else "none auto-matched"}</div>'
                    + (
                        f'<div style="font-size:10px;color:#f59e0b;margin-top:4px">'
                        f'Not found: {", ".join(unmapped[:6])}</div>'
                        if unmapped else ""
                    ),
                    border="#22c55e",
                ), unsafe_allow_html=True)

                with st.spinner("Scoring and segmenting fans…"):
                    df_proc = process_data(df_raw, col_map)
                    st.session_state["df_processed"] = df_proc

                st.success(
                    f"Done — {len(df_proc):,} fans scored and assigned to "
                    f"{df_proc['segment'].nunique()} segments. "
                    "Switch to the Dashboard tab."
                )

            except Exception as exc:
                st.error(f"Could not process file: {exc}")

    with right:
        st.markdown(card(
            '<div style="font-size:11px;color:#9ca3af;font-weight:600;'
            'text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Expected columns</div>'
            '<div style="font-size:10px;color:#9ca3af;line-height:2">'
            '<span style="color:#c8f135">User_ID</span> &nbsp;·&nbsp; '
            '<span style="color:#c8f135">Age</span> &nbsp;·&nbsp; Gender &nbsp;·&nbsp; Country<br>'
            '<span style="color:#3d9cf0">App_Opens</span> &nbsp;·&nbsp; '
            '<span style="color:#3d9cf0">Email_Opens</span><br>'
            '<span style="color:#3d9cf0">Article_Views</span> &nbsp;·&nbsp; '
            '<span style="color:#3d9cf0">In_App_Clicks</span><br>'
            '<span style="color:#22c55e">Ticket_Purchases</span> &nbsp;·&nbsp; '
            '<span style="color:#22c55e">Membership_Purchases</span><br>'
            '<span style="color:#22c55e">Retail_Purchases</span> &nbsp;·&nbsp; '
            '<span style="color:#22c55e">Total_Revenue</span><br>'
            '<span style="color:#f59e0b">Last_Purchase_Date</span> &nbsp;·&nbsp; '
            '<span style="color:#f59e0b">Join_Date</span>'
            '</div>'
            '<div style="margin-top:10px;font-size:9px;color:#374151">'
            'Dates: YYYY-MM-DD · Missing columns are filled with neutral scores</div>'
        ), unsafe_allow_html=True)

        st.markdown(card(
            '<div style="font-size:11px;color:#9ca3af;font-weight:600;'
            'text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Scoring methodology</div>'
            '<div style="font-size:10px;color:#9ca3af;line-height:2.0">'
            '<span style="color:#3d9cf0">●</span> <b style="color:#e5e7eb">Engagement (0–100)</b><br>'
            '&nbsp;&nbsp;App opens 30% · Email opens 25% · Article views 25% · Clicks 20%<br>'
            '<span style="color:#c8f135">●</span> <b style="color:#e5e7eb">Commercial (0–100)</b><br>'
            '&nbsp;&nbsp;Revenue 40% · Recency (exp decay) 35% · Frequency 25%<br>'
            '<span style="color:#22c55e">●</span> <b style="color:#e5e7eb">Loyalty (0–100)</b><br>'
            '&nbsp;&nbsp;Tenure 40% · Purchase diversity 35% · Consistency 25%'
            '</div>'
        ), unsafe_allow_html=True)

        st.markdown(card(
            '<div style="font-size:11px;color:#9ca3af;font-weight:600;'
            'text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">Age segments</div>'
            '<div style="font-size:10px;color:#9ca3af;line-height:2">'
            '🧒 <b style="color:#e5e7eb">Child</b> — under 13<br>'
            '🎓 <b style="color:#e5e7eb">Young Adult</b> — 13–25<br>'
            '👔 <b style="color:#e5e7eb">Adult</b> — 26–49<br>'
            '🎖 <b style="color:#e5e7eb">Senior</b> — 50+'
            '</div>'
        ), unsafe_allow_html=True)


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
        df = st.session_state["df_processed"]
        total = len(df)

        # KPI strip
        champions_n = (df["segment"] == "Champions").sum()
        high_val_n  = df["segment"].isin(["Champions", "Loyal Fans"]).sum()
        at_risk_n   = df["segment"].isin(["At Risk", "Dormant", "Win Back"]).sum()
        avg_e = df["engagement_score"].mean()
        avg_c = df["commercial_score"].mean()
        avg_l = df["loyalty_score"].mean()

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1: st.markdown(kpi("Total Fans", f"{total:,}",           "in dataset"),              unsafe_allow_html=True)
        with k2: st.markdown(kpi("Avg Engagement",  f"{avg_e:.0f}",   "/ 100", "#3d9cf0"),         unsafe_allow_html=True)
        with k3: st.markdown(kpi("Avg Commercial",  f"{avg_c:.0f}",   "/ 100", "#c8f135"),         unsafe_allow_html=True)
        with k4: st.markdown(kpi("Avg Loyalty",     f"{avg_l:.0f}",   "/ 100", "#22c55e"),         unsafe_allow_html=True)
        with k5: st.markdown(kpi("At Risk / Dormant", f"{at_risk_n:,}", f"{at_risk_n/total*100:.0f}% of base", "#ef4444"), unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # Row 1 — donut + age bar
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            st.plotly_chart(chart_segment_donut(df),   use_container_width=True, config={"displayModeBar": False})
        with r1c2:
            st.plotly_chart(chart_age_segment_bar(df), use_container_width=True, config={"displayModeBar": False})

        # Row 2 — full-width scatter
        st.plotly_chart(chart_landscape(df), use_container_width=True, config={"displayModeBar": False})

        # Row 3 — grouped bar + commercial bar
        r3c1, r3c2 = st.columns(2)
        with r3c1:
            st.plotly_chart(chart_scores_by_segment(df),       use_container_width=True, config={"displayModeBar": False})
        with r3c2:
            st.plotly_chart(chart_commercial_opportunity(df),  use_container_width=True, config={"displayModeBar": False})

        # Row 4 — radar
        st.plotly_chart(chart_age_scores(df), use_container_width=True, config={"displayModeBar": False})

        # ── Segment insight cards ──────────────────────────────────────────────
        st.markdown(
            '<div style="font-family:\'Syne\',sans-serif;font-size:17px;font-weight:700;'
            'color:#e5e7eb;margin:24px 0 14px">Segment Insights &amp; Recommended Actions</div>',
            unsafe_allow_html=True,
        )
        seg_counts = df["segment"].value_counts()
        seg_keys = [s for s in SEGMENT_INFO if s in seg_counts.index]

        for i in range(0, len(seg_keys), 2):
            pair = seg_keys[i : i + 2]
            cols = st.columns(len(pair))
            for col_ui, seg in zip(cols, pair):
                info  = SEGMENT_INFO[seg]
                count = int(seg_counts.get(seg, 0))
                pct   = count / total * 100
                sub   = df[df["segment"] == seg]
                avg_e_s = sub["engagement_score"].mean()
                avg_c_s = sub["commercial_score"].mean()
                avg_l_s = sub["loyalty_score"].mean()

                actions_html = "".join(
                    f'<div style="font-size:9px;color:#9ca3af;margin-top:4px">→ {a}</div>'
                    for a in info["actions"]
                )

                with col_ui:
                    st.markdown(card(
                        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">'
                        f'  <div>'
                        f'    <span style="font-size:20px">{info["icon"]}</span>'
                        f'    <span style="font-family:\'Syne\',sans-serif;font-size:15px;font-weight:700;'
                        f'          color:{info["color"]};margin-left:8px">{seg}</span>'
                        f'  </div>'
                        f'  <span style="background:{info["bg"]};color:{info["color"]};'
                        f'        border:1px solid {info["color"]};font-size:10px;padding:3px 10px;'
                        f'        border-radius:8px">{count:,} fans · {pct:.0f}%</span>'
                        f'</div>'
                        f'<div style="font-size:10px;color:#6b7280;margin-bottom:8px">{info["description"]}</div>'
                        f'<div style="display:flex;gap:16px;margin-bottom:10px">'
                        f'  <div style="font-size:10px;color:#3d9cf0">E: {avg_e_s:.0f}</div>'
                        f'  <div style="font-size:10px;color:#c8f135">C: {avg_c_s:.0f}</div>'
                        f'  <div style="font-size:10px;color:#22c55e">L: {avg_l_s:.0f}</div>'
                        f'</div>'
                        f'<div style="font-size:10px;color:#9ca3af;border-left:2px solid {info["color"]};'
                        f'     padding-left:8px;margin-bottom:8px">{info["recommendation"]}</div>'
                        f'{actions_html}',
                        bg="#0d1117", border=info["color"],
                    ), unsafe_allow_html=True)

        # ── Top fans table ─────────────────────────────────────────────────────
        st.markdown(
            '<div style="font-family:\'Syne\',sans-serif;font-size:17px;font-weight:700;'
            'color:#e5e7eb;margin:24px 0 14px">Top 20 Fans by Composite Score</div>',
            unsafe_allow_html=True,
        )
        col_map_stored = st.session_state.get("col_map", {})
        display_cols   = (
            [col_map_stored["user_id"]] if "user_id" in col_map_stored else []
        ) + [
            c for c in ["age_group", "segment", "engagement_score", "commercial_score",
                        "loyalty_score", "composite_score"]
            if c in df.columns
        ]
        st.dataframe(
            df.nlargest(20, "composite_score")[display_cols]
              .reset_index(drop=True)
              .style.background_gradient(subset=["composite_score"], cmap="RdYlGn"),
            use_container_width=True,
            height=420,
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
        df    = st.session_state["df_processed"]
        total = len(df)
        today_str = datetime.today().strftime("%Y-%m-%d")

        st.markdown(
            '<div style="font-family:\'Syne\',sans-serif;font-size:17px;font-weight:700;'
            'color:#e5e7eb;margin-bottom:16px">Fan Segmentation Report</div>',
            unsafe_allow_html=True,
        )

        # Executive summary card
        high_val = df["segment"].isin(["Champions", "Loyal Fans"]).sum()
        at_risk  = df["segment"].isin(["At Risk", "Dormant", "Win Back"]).sum()
        pot      = df["segment"].isin(["High Potential", "Rising Stars"]).sum()
        st.markdown(card(
            f'<div style="font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:.08em;margin-bottom:14px">Executive Summary</div>'
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px">'
            f'  <div>'
            f'    <div style="font-size:10px;color:#6b7280">Fans Analysed</div>'
            f'    <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#c8f135">{total:,}</div>'
            f'  </div>'
            f'  <div>'
            f'    <div style="font-size:10px;color:#6b7280">High-Value</div>'
            f'    <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#22c55e">{high_val:,}</div>'
            f'    <div style="font-size:9px;color:#374151">{high_val/total*100:.0f}% of base</div>'
            f'  </div>'
            f'  <div>'
            f'    <div style="font-size:10px;color:#6b7280">Growth Potential</div>'
            f'    <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#3d9cf0">{pot:,}</div>'
            f'    <div style="font-size:9px;color:#374151">{pot/total*100:.0f}% of base</div>'
            f'  </div>'
            f'  <div>'
            f'    <div style="font-size:10px;color:#6b7280">Requires Action</div>'
            f'    <div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#ef4444">{at_risk:,}</div>'
            f'    <div style="font-size:9px;color:#374151">{at_risk/total*100:.0f}% of base</div>'
            f'  </div>'
            f'</div>'
        ), unsafe_allow_html=True)

        # Segment summary table
        st.markdown(
            '<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;'
            'color:#e5e7eb;margin:16px 0 8px">Segment Summary</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            segment_summary(df).drop(columns=["Recommendation"]),
            use_container_width=True,
            hide_index=True,
        )

        # Age group breakdown
        st.markdown(
            '<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;'
            'color:#e5e7eb;margin:16px 0 8px">Age Group Breakdown</div>',
            unsafe_allow_html=True,
        )
        age_table = (
            df.groupby("age_group")
            .agg(
                Count          =("composite_score", "count"),
                Avg_Engagement =("engagement_score", "mean"),
                Avg_Commercial =("commercial_score", "mean"),
                Avg_Loyalty    =("loyalty_score",    "mean"),
                Avg_Composite  =("composite_score",  "mean"),
            )
            .round(1)
            .reset_index()
        )
        st.dataframe(age_table, use_container_width=True, hide_index=True)

        # Recommendations per segment
        st.markdown(
            '<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;'
            'color:#e5e7eb;margin:16px 0 8px">Retention &amp; Commercial Recommendations</div>',
            unsafe_allow_html=True,
        )
        seg_counts = df["segment"].value_counts()
        for seg, info in SEGMENT_INFO.items():
            count = int(seg_counts.get(seg, 0))
            if count == 0:
                continue
            actions_str = " · ".join(info["actions"])
            st.markdown(card(
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
                f'  <span style="font-size:13px;font-weight:600;color:{info["color"]}">'
                f'    {info["icon"]} {seg}</span>'
                f'  <span style="font-size:10px;color:#6b7280">{count:,} fans &nbsp;|&nbsp; risk: '
                f'    <span style="color:{"#ef4444" if info["risk"]=="HIGH" else "#f59e0b" if info["risk"]=="MED" else "#22c55e"}">'
                f'      {info["risk"]}</span></span>'
                f'</div>'
                f'<div style="font-size:10px;color:#9ca3af;margin-bottom:6px">{info["recommendation"]}</div>'
                f'<div style="font-size:9px;color:#6b7280">{actions_str}</div>',
                bg="#0d1117", border=info["color"],
            ), unsafe_allow_html=True)

        # Downloads
        st.markdown(
            '<div style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;'
            'color:#e5e7eb;margin:20px 0 10px">Download</div>',
            unsafe_allow_html=True,
        )
        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                "⬇  Full fan data (CSV)",
                data=to_csv_bytes(df),
                file_name=f"footintel_fans_{today_str}.csv",
                mime="text/csv",
            )
        with dl2:
            st.download_button(
                "⬇  Segment summary (CSV)",
                data=to_csv_bytes(segment_summary(df)),
                file_name=f"footintel_segments_{today_str}.csv",
                mime="text/csv",
            )
        with dl3:
            st.download_button(
                "⬇  Age breakdown (CSV)",
                data=to_csv_bytes(age_table),
                file_name=f"footintel_age_{today_str}.csv",
                mime="text/csv",
            )
