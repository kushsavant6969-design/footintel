"""
RightsIQ — Audience Rights Valuation Platform
What is your audience worth?
"""
from __future__ import annotations
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from rapidfuzz import fuzz as rfuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RightsIQ | Audience Rights Valuation",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'DM Mono',monospace;}
[data-testid="stAppViewContainer"]{background:#0a0c10;}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stSidebar"]{display:none;}
.block-container{padding:24px 32px 40px;}
[data-testid="stTabs"] [data-baseweb="tab-list"]{background:#13161d;border-radius:8px;padding:4px;gap:4px;}
[data-testid="stTabs"] [data-baseweb="tab"]{background:transparent;color:#6b7280;border-radius:6px;
  font-size:11px;padding:6px 14px;font-family:'DM Mono',monospace;}
[data-testid="stTabs"] [aria-selected="true"]{background:#c8f135;color:#0a0c10;font-weight:600;}
.stButton>button{background:#c8f135;color:#0a0c10;font-family:'DM Mono',monospace;font-size:11px;
  border:none;border-radius:6px;padding:8px 18px;font-weight:600;}
.stButton>button:hover{background:#b8e020;}
.stDownloadButton>button{background:#13161d;color:#c8f135;border:1px solid #c8f135;
  font-family:'DM Mono',monospace;font-size:11px;border-radius:6px;padding:8px 18px;}
[data-testid="stFileUploader"]{background:#13161d;border:1px dashed #2a2f3d;border-radius:10px;padding:16px;}
[data-testid="stTextInput"] input{background:#13161d;color:#e5e7eb;border:1px solid #2a2f3d;}
h1,h2,h3{font-family:'Syne',sans-serif;color:#e5e7eb;}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
BENCHMARK_AQI       = 58
BENCHMARK_OWNERSHIP = 24
BENCHMARK_RPS       = 52

MEMBERSHIP_TIER_SCORES: dict[str, int] = {
    "season ticket": 100, "season": 100, "season_ticket": 100,
    "platinum": 90, "gold": 75, "silver": 60,
    "standard": 45, "basic": 30, "free": 15,
    "none": 0, "": 0, "n/a": 0,
}

COUNTRY_REACH_SCORES: dict[str, int] = {
    "england": 50, "scotland": 55, "wales": 55, "northern ireland": 55, "ireland": 60,
    "usa": 85, "germany": 80, "spain": 75, "france": 75, "italy": 70,
    "australia": 70, "canada": 70, "japan": 65, "brazil": 65,
    "netherlands": 70, "portugal": 70, "norway": 60, "sweden": 60,
}

# ── Column aliases ────────────────────────────────────────────────────────────
COLUMN_ALIASES: dict[str, list[str]] = {
    "fan_id":             ["fan_id", "id", "fan id", "user_id", "userid", "customer_id", "member_id"],
    "age":                ["age", "fan_age", "age_years", "age_band"],
    "gender":             ["gender", "sex", "fan_gender", "gender_identity"],
    "last_attended":      ["last_attended", "last_visit", "last_match", "last_attendance_date", "last_game"],
    "tickets_purchased":  ["tickets_purchased", "tickets", "ticket_count", "tickets_bought", "games_attended"],
    "spend":              ["spend", "total_spend", "revenue", "amount_spent", "spending", "ltv"],
    "membership_type":    ["membership_type", "membership", "member_type", "tier", "membership_tier"],
    "engagement_score":   ["engagement_score", "engagement", "eng_score", "engagement_index"],
    "channel_preference": ["channel_preference", "channel", "preferred_channel", "comms_channel"],
    "country":            ["country", "region", "nationality", "fan_country", "location"],
}
CORE_COLUMNS  = list(COLUMN_ALIASES.keys())
MIN_CORE_COLS = 5


def auto_map_columns(uploaded_cols: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    norm = {c: c.strip().lower().replace(" ", "_").replace("-", "_") for c in uploaded_cols}
    for std, aliases in COLUMN_ALIASES.items():
        best_col, best_score = None, 0
        for alias in aliases:
            for orig, n in norm.items():
                if orig in used:
                    continue
                score = (max(rfuzz.ratio(alias, n), rfuzz.token_sort_ratio(alias, n))
                         if HAS_RAPIDFUZZ else (100 if alias == n else 0))
                if score > best_score:
                    best_score, best_col = score, orig
        if best_col and best_score >= 70:
            mapping[std] = best_col
            used.add(best_col)
    return mapping


# ── Utility ───────────────────────────────────────────────────────────────────

def _pdf_safe(t: str) -> str:
    for k, v in {"—": "-", "–": "-", "‘": "'", "’": "'",
                 "“": '"', "”": '"', "…": "...", "£": "GBP ",
                 "é": "e", "è": "e", "à": "a", "ü": "u"}.items():
        t = t.replace(k, v)
    return t.encode("latin-1", "ignore").decode("latin-1")


def card(content: str, bg: str = "#13161d", border: str = "#2a2f3d",
         padding: str = "16px 20px", radius: str = "10px") -> str:
    return (f'<div style="background:{bg};border:1px solid {border};'
            f'border-radius:{radius};padding:{padding};margin-bottom:12px">{content}</div>')


def kpi(label: str, value: str, sub: str = "", color: str = "#c8f135") -> str:
    return (
        f'<div style="background:#13161d;border:1px solid #2a2f3d;border-radius:10px;padding:16px 20px;text-align:center">'
        f'<div style="font-size:9px;color:#6b7280;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px">{label}</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:26px;font-weight:800;color:{color};line-height:1.1">{value}</div>'
        f'<div style="font-size:10px;color:#6b7280;margin-top:4px">{sub}</div>'
        f'</div>'
    )


def section_heading(title: str) -> None:
    st.markdown(
        f'<div style="font-family:\'Syne\',sans-serif;font-size:13px;font-weight:700;'
        f'color:#e5e7eb;margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid #1f2937">{title}</div>',
        unsafe_allow_html=True,
    )


def insight_banner(text: str, color: str = "#c8f135") -> None:
    bg = "#0f1a00" if color == "#c8f135" else ("#052e16" if color == "#22c55e" else "#1c1500")
    st.markdown(
        f'<div style="background:{bg};border-left:3px solid {color};border:1px solid {color}30;'
        f'border-radius:8px;padding:14px 18px;margin-bottom:16px">'
        f'<span style="font-size:9px;color:{color};text-transform:uppercase;letter-spacing:.1em;font-weight:600">Insight</span><br>'
        f'<span style="font-size:12px;color:#e5e7eb;line-height:1.7">{text}</span></div>',
        unsafe_allow_html=True,
    )


# ── Scoring ───────────────────────────────────────────────────────────────────

def _pct_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, na_option="bottom") * 100


def compute_ownership(df: pd.DataFrame, col: dict) -> dict:
    n = len(df)
    has_mem = "membership_type" in col and col["membership_type"] in df.columns
    has_tix = "tickets_purchased" in col and col["tickets_purchased"] in df.columns
    has_spd = "spend" in col and col["spend"] in df.columns

    if has_mem:
        mem = df[col["membership_type"]].astype(str).str.strip().str.lower()
        is_member = ~mem.isin(["", "none", "n/a", "nan", "no membership"])
    else:
        is_member = pd.Series([False] * n, index=df.index)

    has_transacted = (pd.to_numeric(df[col["tickets_purchased"]], errors="coerce").fillna(0) > 0
                      if has_tix else pd.Series([False] * n, index=df.index))
    has_spend_data = (pd.to_numeric(df[col["spend"]], errors="coerce").fillna(0) > 0
                      if has_spd else pd.Series([False] * n, index=df.index))

    fully     = is_member & (has_transacted | has_spend_data)
    partial   = (~fully) & (is_member | has_transacted | has_spend_data)
    anon      = ~(fully | partial)

    n_full, n_part, n_anon = int(fully.sum()), int(partial.sum()), int(anon.sum())
    score = round(min(max((n_full * 1.0 + n_part * 0.4) / max(n, 1) * 100, 0), 100), 1)

    return {
        "ownership_score":     score,
        "n_total":             n,
        "n_fully_owned":       n_full,
        "n_partially_known":   n_part,
        "n_anonymous_in_db":   n_anon,
        "est_anonymous_reach": n * 8,
        "owned_pct":           round((n_full + n_part) / max(n, 1) * 100, 1),
    }


def compute_loyalty_score(df: pd.DataFrame, col: dict) -> pd.Series:
    scores = pd.Series(50.0, index=df.index)
    if "last_attended" in col and col["last_attended"] in df.columns:
        today    = datetime.now()
        dates    = pd.to_datetime(df[col["last_attended"]], errors="coerce")
        days_ago = (today - dates).dt.days.fillna(730)
        recency  = (1 - days_ago.clip(0, 1095) / 1095) * 100
        scores   = scores * 0.4 + recency * 0.6
    if "tickets_purchased" in col and col["tickets_purchased"] in df.columns:
        tix    = pd.to_numeric(df[col["tickets_purchased"]], errors="coerce").fillna(0)
        scores = scores * 0.5 + _pct_rank(tix) * 0.5
    return scores.clip(0, 100)


def compute_commercial_score(df: pd.DataFrame, col: dict) -> pd.Series:
    scores = pd.Series(40.0, index=df.index)
    if "spend" in col and col["spend"] in df.columns:
        spd    = pd.to_numeric(df[col["spend"]], errors="coerce").fillna(0)
        scores = scores * 0.4 + _pct_rank(spd) * 0.6
    if "membership_type" in col and col["membership_type"] in df.columns:
        mem = df[col["membership_type"]].astype(str).str.strip().str.lower()
        def _tier(x) -> int:
            if not isinstance(x, str):
                return 0
            for k, v in MEMBERSHIP_TIER_SCORES.items():
                if k in x:
                    return v
            return 20
        scores = scores * 0.5 + mem.apply(_tier).astype(float) * 0.5
    return scores.clip(0, 100)


def compute_demographic_score(df: pd.DataFrame, col: dict) -> float:
    age_score = 58.0
    if "age" in col and col["age"] in df.columns:
        ages = pd.to_numeric(df[col["age"]], errors="coerce").dropna()
        if len(ages) > 0:
            def _av(a: float) -> int:
                return 90 if 18 <= a <= 35 else 70 if 36 <= a <= 50 else 50 if a > 50 else 40
            age_score = float(ages.apply(_av).mean())
    gender_score = 60.0
    if "gender" in col and col["gender"] in df.columns:
        g = df[col["gender"]].astype(str).str.lower().str.strip()
        f_pct = g.isin(["female", "f", "woman", "women"]).mean() * 100
        gender_score = 90.0 if 35 <= f_pct <= 55 else 75.0 if 20 <= f_pct <= 65 else 55.0
    return round(age_score * 0.70 + gender_score * 0.30, 1)


def compute_engagement_score(df: pd.DataFrame, col: dict) -> pd.Series:
    if "engagement_score" in col and col["engagement_score"] in df.columns:
        eng = pd.to_numeric(df[col["engagement_score"]], errors="coerce").fillna(50)
        return (eng / max(float(eng.max()), 100) * 100).clip(0, 100)
    base = pd.Series(40.0, index=df.index)
    if "tickets_purchased" in col and col["tickets_purchased"] in df.columns:
        tix  = pd.to_numeric(df[col["tickets_purchased"]], errors="coerce").fillna(0)
        base = base + _pct_rank(tix) * 0.30
    if "spend" in col and col["spend"] in df.columns:
        spd  = pd.to_numeric(df[col["spend"]], errors="coerce").fillna(0)
        base = base + _pct_rank(spd) * 0.20
    return base.clip(0, 100)


def compute_aqi(loyalty: pd.Series, commercial: pd.Series,
                demographic: float, engagement: pd.Series) -> dict:
    return {
        "aqi":         round(loyalty.mean()*0.30 + commercial.mean()*0.30 +
                             demographic*0.20 + engagement.mean()*0.20, 1),
        "loyalty":     round(float(loyalty.mean()), 1),
        "commercial":  round(float(commercial.mean()), 1),
        "demographic": round(demographic, 1),
        "engagement":  round(float(engagement.mean()), 1),
    }


def compute_geo_reach(df: pd.DataFrame, col: dict) -> float:
    if "country" not in col or col["country"] not in df.columns:
        return 50.0
    countries = df[col["country"]].astype(str).str.lower().str.strip()
    def _cs(c: str) -> int:
        for k, v in COUNTRY_REACH_SCORES.items():
            if k in c:
                return v
        return 55
    return round(min(float(countries.apply(_cs).mean()) + min(countries.nunique() * 2, 20), 100), 1)


def compute_valuation(ownership: dict, aqi: dict, geo: float) -> dict:
    owned = max(ownership["n_fully_owned"] + ownership["n_partially_known"] * 0.6, 1)
    return {
        "shirt":           round(owned * (aqi["commercial"] / 100) * 0.12, 0),
        "stadium":         round(owned * (aqi["aqi"] / 100) * 85, 0),
        "digital":         round(owned * (aqi["engagement"] / 100) * 45, 0),
        "broadcast_index": round(aqi["loyalty"] * 0.5 + geo * 0.5, 1),
    }


def compute_rps(ownership: dict, aqi: dict, valuation: dict) -> dict:
    total = valuation["shirt"] + valuation["stadium"] + valuation["digital"]
    val_i = min(total / max(ownership["n_total"], 1) / 10, 100)
    rps   = round(max(min(ownership["ownership_score"]*0.30 + aqi["aqi"]*0.40 + val_i*0.30, 100), 0), 1)

    up, down = [], []
    if aqi["aqi"] >= BENCHMARK_AQI:
        up.append(f"Audience quality ({aqi['aqi']:.0f}/100) above industry average ({BENCHMARK_AQI})")
    else:
        down.append(f"Audience quality ({aqi['aqi']:.0f}/100) below industry average ({BENCHMARK_AQI})")
    if ownership["owned_pct"] >= BENCHMARK_OWNERSHIP:
        up.append(f"Ownership ({ownership['owned_pct']:.0f}%) above industry average ({BENCHMARK_OWNERSHIP}%)")
    else:
        down.append(f"Fan data ownership ({ownership['owned_pct']:.0f}%) below industry average ({BENCHMARK_OWNERSHIP}%)")
    if valuation["broadcast_index"] >= 55:
        up.append(f"Broadcast index ({valuation['broadcast_index']:.0f}/100) shows strong geographic reach")
    else:
        down.append("Geographic reach limits broadcast rights premium")

    uplift = round((valuation["shirt"] / max(aqi["aqi"], 1)) * 10, 0)
    actions = [
        {
            "action": "Capture contact data for anonymous fans",
            "impact": "Increase Ownership Score by 15-20 points via email capture at ticketing and matchday",
            "value":  f"Estimated +GBP{int(valuation['shirt'] * 0.15):,} in shirt sponsorship value",
        },
        {
            "action": f"Improve Audience Quality Index by 10 points (currently {aqi['aqi']:.0f}/100)",
            "impact": "Increase Rights Premium Score by ~4 points through engagement and loyalty programmes",
            "value":  f"Estimated +GBP{int(uplift):,} in shirt rights value",
        },
        {
            "action": "Grow 18-35 demographic through digital-first fan engagement",
            "impact": "Demographic Value Score uplift improves sponsor commercial attractiveness",
            "value":  f"Estimated +GBP{int(valuation['digital'] * 0.12):,} in digital rights value",
        },
    ]
    return {"rps": rps, "drivers_up": up, "drivers_down": down, "actions": actions}


# ── Charts ────────────────────────────────────────────────────────────────────

_L = dict(
    paper_bgcolor="#13161d", plot_bgcolor="#13161d",
    font=dict(family="DM Mono, monospace", color="#9ca3af", size=11),
)
_M = dict(l=0, r=0, t=30, b=0)  # default margin — pass explicitly to avoid duplicate kwarg


def chart_ownership_donut(ownership: dict) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=["Fully Owned", "Partially Known", "Anonymous"],
        values=[ownership["n_fully_owned"], ownership["n_partially_known"], ownership["n_anonymous_in_db"]],
        hole=0.65,
        marker=dict(colors=["#c8f135", "#3d9cf0", "#374151"], line=dict(width=0)),
        textfont=dict(size=10), hovertemplate="<b>%{label}</b><br>%{value:,} fans (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"<b>{ownership['owned_pct']:.0f}%</b><br>Owned",
                       x=0.5, y=0.5, showarrow=False,
                       font=dict(size=14, color="#e5e7eb", family="Syne"))
    fig.update_layout(**_L, margin=_M, height=260,
                      legend=dict(orientation="v", x=1.0, y=0.5, font=dict(size=10, color="#9ca3af")))
    return fig


def chart_aqi_radar(aqi: dict) -> go.Figure:
    cats   = ["Loyalty", "Commercial", "Demographic", "Engagement"]
    values = [aqi["loyalty"], aqi["commercial"], aqi["demographic"], aqi["engagement"]]
    bench  = [BENCHMARK_AQI] * 4
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values + [values[0]], theta=cats + [cats[0]],
                                  fill="toself", fillcolor="rgba(200,241,53,0.12)",
                                  line=dict(color="#c8f135", width=2), name="Your Audience"))
    fig.add_trace(go.Scatterpolar(r=bench + [bench[0]], theta=cats + [cats[0]],
                                  fill="toself", fillcolor="rgba(61,156,240,0.06)",
                                  line=dict(color="#3d9cf0", width=1.5, dash="dash"), name="Industry Avg"))
    fig.update_layout(**{**_L, "margin": dict(l=40, r=40, t=30, b=40)},
                      height=320,
                      polar=dict(bgcolor="#0d1117",
                                 radialaxis=dict(visible=True, range=[0, 100],
                                                 tickfont=dict(size=9, color="#6b7280"),
                                                 gridcolor="#1f2937", linecolor="#1f2937"),
                                 angularaxis=dict(tickfont=dict(size=10, color="#9ca3af"),
                                                  gridcolor="#1f2937")),
                      legend=dict(font=dict(size=10, color="#9ca3af"), bgcolor="rgba(0,0,0,0)"))
    return fig


def chart_valuation_bars(valuation: dict) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=["Shirt\nSponsorship", "Stadium\nNaming", "Digital\nRights"],
        y=[valuation["shirt"], valuation["stadium"], valuation["digital"]],
        marker_color=["#c8f135", "#3d9cf0", "#a78bfa"], marker_line_width=0,
        text=[f"£{v:,.0f}" for v in [valuation["shirt"], valuation["stadium"], valuation["digital"]]],
        textposition="outside", textfont=dict(size=10, color="#e5e7eb"),
    ))
    fig.update_layout(**_L, margin=_M, height=260,
                      yaxis=dict(showgrid=False, showticklabels=False),
                      xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#9ca3af")))
    return fig


def chart_rps_gauge(rps: float) -> go.Figure:
    color = "#22c55e" if rps >= 70 else "#f59e0b" if rps >= 50 else "#ef4444"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=rps,
        number=dict(font=dict(size=40, color=color, family="Syne"), suffix="/100"),
        gauge=dict(axis=dict(range=[0, 100], tickfont=dict(size=10, color="#6b7280")),
                   bar=dict(color=color, thickness=0.3), bgcolor="#0d1117", borderwidth=0,
                   steps=[dict(range=[0, 50], color="#1f0a0a"),
                          dict(range=[50, 70], color="#1c1500"),
                          dict(range=[70, 100], color="#052e16")],
                   threshold=dict(line=dict(color="#9ca3af", width=2), thickness=0.75, value=BENCHMARK_RPS)),
    ))
    fig.update_layout(**_L, margin=dict(l=20, r=20, t=20, b=0), height=240)
    return fig


def chart_benchmark_position(rps: float) -> go.Figure:
    color = "#22c55e" if rps >= 70 else "#f59e0b" if rps >= 50 else "#ef4444"
    fig = go.Figure()
    for x0, x1, bg in [(0, 50, "#1f0a0a"), (50, 70, "#1c1500"), (70, 100, "#052e16")]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0.2, y1=0.8, fillcolor=bg, line_width=0)
    fig.add_shape(type="line", x0=BENCHMARK_RPS, x1=BENCHMARK_RPS, y0=0.05, y1=0.95,
                  line=dict(color="#6b7280", width=1.5, dash="dot"))
    fig.add_annotation(x=BENCHMARK_RPS, y=1.0, text="Market avg",
                       font=dict(size=9, color="#6b7280"), showarrow=False)
    fig.add_trace(go.Scatter(x=[rps], y=[0.5], mode="markers+text",
                             marker=dict(size=20, color=color, symbol="diamond"),
                             text=["You"], textposition="top center",
                             textfont=dict(size=10, color=color),
                             hovertemplate=f"Rights Premium Score: {rps:.0f}<extra></extra>"))
    for x, lbl in [(25, "Developing"), (60, "Market Rate"), (85, "Premium")]:
        fig.add_annotation(x=x, y=0.5, text=lbl, font=dict(size=9, color="#4b5563"), showarrow=False)
    fig.update_layout(**_L, margin=dict(l=10, r=10, t=30, b=20), height=130, showlegend=False,
                      xaxis=dict(range=[0, 100], showgrid=False, tickfont=dict(size=9, color="#6b7280")),
                      yaxis=dict(range=[0, 1.2], showgrid=False, showticklabels=False))
    return fig


def chart_age_distribution(df: pd.DataFrame, col: dict) -> go.Figure | None:
    if "age" not in col or col["age"] not in df.columns:
        return None
    ages   = pd.to_numeric(df[col["age"]], errors="coerce").dropna()
    bins   = [0, 17, 25, 35, 50, 65, 200]
    labels = ["<18", "18-24", "25-35", "36-50", "51-65", "65+"]
    counts = pd.cut(ages, bins=bins, labels=labels).value_counts().reindex(labels).fillna(0)
    fig = go.Figure(go.Bar(
        x=labels, y=counts.values,
        marker_color=["#374151", "#c8f135", "#c8f135", "#3d9cf0", "#6b7280", "#4b5563"],
        marker_line_width=0,
        text=counts.values.astype(int), textposition="outside",
        textfont=dict(size=10, color="#9ca3af"),
    ))
    fig.update_layout(**_L, margin=_M, height=220,
                      xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#9ca3af")),
                      yaxis=dict(showgrid=False, showticklabels=False))
    return fig


def chart_channel_split(df: pd.DataFrame, col: dict) -> go.Figure | None:
    if "channel_preference" not in col or col["channel_preference"] not in df.columns:
        return None
    ch = df[col["channel_preference"]].astype(str).str.strip().value_counts().head(6)
    colors = ["#c8f135", "#3d9cf0", "#a78bfa", "#f59e0b", "#22c55e", "#6b7280"]
    fig = go.Figure(go.Bar(
        y=ch.index.tolist(), x=ch.values, orientation="h",
        marker_color=colors[:len(ch)], marker_line_width=0,
        text=ch.values, textposition="outside", textfont=dict(size=10, color="#9ca3af"),
    ))
    fig.update_layout(**_L, margin=_M, height=200,
                      yaxis=dict(showgrid=False, tickfont=dict(size=10, color="#9ca3af")),
                      xaxis=dict(showgrid=False, showticklabels=False))
    return fig


# ── PDF ───────────────────────────────────────────────────────────────────────

def generate_pdf(club: str, ownership: dict, aqi: dict,
                 valuation: dict, rps_data: dict) -> bytes:
    if not HAS_FPDF:
        return b""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    BG = (10, 12, 16); ACCENT = (200, 241, 53); WHITE = (229, 231, 235); GREY = (107, 114, 128)
    DARK = (19, 22, 29)
    total = valuation["shirt"] + valuation["stadium"] + valuation["digital"]
    H = lambda t: _pdf_safe(str(t))

    # Page 1 — Executive Summary
    pdf.add_page()
    pdf.set_fill_color(*BG); pdf.rect(0, 0, 210, 297, "F")
    pdf.set_font("Helvetica", "B", 22); pdf.set_text_color(*ACCENT)
    pdf.set_xy(15, 16); pdf.cell(0, 10, "RightsIQ", ln=True)
    pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*GREY)
    pdf.set_xy(15, 28)
    pdf.cell(0, 7, H(f"{club or 'Rights Holder'}  -  Audience Rights Valuation Report"), ln=True)
    pdf.set_xy(15, 36); pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%d %B %Y')}", ln=True)
    pdf.set_draw_color(*ACCENT); pdf.set_line_width(0.4); pdf.line(15, 44, 195, 44)

    def score_box(x: float, y: float, label: str, value: str, sub: str = "") -> None:
        pdf.set_fill_color(*DARK); pdf.rect(x, y, 54, 32, "F")
        pdf.set_font("Helvetica", "", 7); pdf.set_text_color(*GREY)
        pdf.set_xy(x+3, y+5); pdf.cell(48, 5, H(label.upper()))
        pdf.set_font("Helvetica", "B", 18); pdf.set_text_color(*ACCENT)
        pdf.set_xy(x+3, y+11); pdf.cell(48, 11, H(value))
        if sub:
            pdf.set_font("Helvetica", "", 7); pdf.set_text_color(*GREY)
            pdf.set_xy(x+3, y+24); pdf.cell(48, 5, H(sub))

    score_box(15,  50, "Ownership Score",      f"{ownership['ownership_score']:.0f}/100", f"{ownership['n_total']:,} fans")
    score_box(72,  50, "Audience Quality",     f"{aqi['aqi']:.0f}/100",                  f"vs {BENCHMARK_AQI} avg")
    score_box(129, 50, "Rights Premium Score", f"{rps_data['rps']:.0f}/100",             "Negotiation anchor")

    pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*WHITE)
    pdf.set_xy(15, 90); pdf.cell(0, 8, "Rights Category Valuations", ln=True)
    pdf.set_draw_color(31, 41, 55); pdf.set_line_width(0.2); pdf.line(15, 99, 195, 99)

    rows = [
        ("Shirt Sponsorship",     f"GBP {valuation['shirt']:,.0f}",   "Owned fans x commercial score"),
        ("Stadium Naming Rights", f"GBP {valuation['stadium']:,.0f}", "Owned fans x AQI"),
        ("Digital Rights",        f"GBP {valuation['digital']:,.0f}", "Owned fans x engagement"),
        ("Broadcast Index",       f"{valuation['broadcast_index']:.0f}/100", "Loyalty + geographic reach"),
        ("TOTAL RIGHTS VALUE",    f"GBP {total:,.0f}",                "Shirt + stadium + digital"),
    ]
    for i, (lbl, val, drv) in enumerate(rows):
        y = 103 + i * 19
        fill = DARK if i < 4 else (13, 25, 10)
        pdf.set_fill_color(*fill); pdf.rect(15, y, 180, 16, "F")
        pdf.set_font("Helvetica", "B" if i == 4 else "", 10); pdf.set_text_color(*WHITE)
        pdf.set_xy(18, y+4); pdf.cell(75, 6, H(lbl))
        pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(*ACCENT)
        pdf.set_xy(98, y+4); pdf.cell(40, 6, H(val))
        pdf.set_font("Helvetica", "", 8); pdf.set_text_color(*GREY)
        pdf.set_xy(142, y+4); pdf.cell(53, 6, H(drv))

    # Page 2 — Benchmark Comparison
    pdf.add_page()
    pdf.set_fill_color(*BG); pdf.rect(0, 0, 210, 297, "F")
    pdf.set_font("Helvetica", "B", 16); pdf.set_text_color(*WHITE)
    pdf.set_xy(15, 16); pdf.cell(0, 10, "Benchmark Comparison", ln=True)
    pdf.set_draw_color(*ACCENT); pdf.line(15, 28, 195, 28)

    for i, (lbl, yours, bench, unit) in enumerate([
        ("Audience Quality Index",  aqi["aqi"],                   58.0,  "/100"),
        ("Ownership Score",         ownership["ownership_score"],  24.0,  "%"),
        ("Rights Premium Score",    rps_data["rps"],               float(BENCHMARK_RPS), "/100"),
        ("Broadcast Index",         valuation["broadcast_index"],  55.0,  "/100"),
    ]):
        y = 34 + i * 22
        pdf.set_fill_color(*DARK); pdf.rect(15, y, 180, 18, "F")
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*GREY)
        pdf.set_xy(18, y+4); pdf.cell(70, 6, H(lbl))
        c_ = ACCENT if yours >= bench else (239, 68, 68)
        pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*c_)
        pdf.set_xy(92, y+4); pdf.cell(35, 6, H(f"{yours:.0f}{unit}"))
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*GREY)
        pdf.set_xy(135, y+4); pdf.cell(60, 6, H(f"Industry avg: {bench:.0f}{unit}"))

    pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*WHITE)
    pdf.set_xy(15, 130); pdf.cell(0, 8, "Audience Quality Sub-Scores", ln=True)
    pdf.set_draw_color(31, 41, 55); pdf.line(15, 139, 195, 139)

    for i, (lbl, val) in enumerate([("Loyalty", aqi["loyalty"]), ("Commercial", aqi["commercial"]),
                                     ("Demographic", aqi["demographic"]), ("Engagement", aqi["engagement"])]):
        y = 143 + i * 16
        bw = val / 100 * 120; bench_bw = BENCHMARK_AQI / 100 * 120
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*GREY)
        pdf.set_xy(15, y); pdf.cell(58, 6, H(lbl))
        pdf.set_fill_color(31, 41, 55); pdf.rect(75, y+1, 120, 5, "F")
        pdf.set_fill_color(*GREY); pdf.rect(75 + bench_bw, y-1, 0.5, 9, "F")
        c_ = ACCENT if val >= BENCHMARK_AQI else (239, 68, 68)
        pdf.set_fill_color(*c_); pdf.rect(75, y+1, bw, 5, "F")
        pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*WHITE)
        pdf.set_xy(197, y); pdf.cell(0, 6, f"{val:.0f}", align="R")

    # Page 3 — Recommended Actions
    pdf.add_page()
    pdf.set_fill_color(*BG); pdf.rect(0, 0, 210, 297, "F")
    pdf.set_font("Helvetica", "B", 16); pdf.set_text_color(*WHITE)
    pdf.set_xy(15, 16); pdf.cell(0, 10, "3 Actions to Increase Rights Value", ln=True)
    pdf.set_draw_color(*ACCENT); pdf.line(15, 28, 195, 28)

    for i, action in enumerate(rps_data["actions"]):
        y = 36 + i * 68
        pdf.set_fill_color(13, 17, 23); pdf.rect(15, y, 180, 60, "F")
        pdf.set_fill_color(*ACCENT); pdf.rect(15, y, 4, 60, "F")
        pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*WHITE)
        pdf.set_xy(24, y+7); pdf.cell(0, 7, H(f"Action {i+1}:  {action['action']}"), ln=True)
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*GREY)
        pdf.set_xy(24, y+18); pdf.multi_cell(163, 6, H(action["impact"]))
        pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*ACCENT)
        pdf.set_xy(24, y+46); pdf.cell(0, 6, H(action["value"]))

    pdf.set_font("Helvetica", "", 8); pdf.set_text_color(*GREY)
    pdf.set_xy(15, 245)
    pdf.multi_cell(180, 5, H(
        "This report was generated by RightsIQ. All valuations are estimates based on the uploaded "
        "fan data and industry benchmarks. Indicative only - use as a starting point for negotiation."
    ))

    try:
        out = pdf.output()
        return out if isinstance(out, bytes) else out.encode("latin-1")
    except Exception:
        return b""


# ── Sample CSV ────────────────────────────────────────────────────────────────

def generate_sample_csv(n: int = 200) -> bytes:
    rng  = np.random.default_rng(42)
    base = date(2024, 5, 1)
    tix  = rng.integers(0, 21, n)
    eng  = np.clip(rng.integers(10, 101, n).astype(float) * 0.6 + tix * 2.5, 0, 100)
    df = pd.DataFrame({
        "Fan_ID":            [f"FAN{str(i+1).zfill(4)}" for i in range(n)],
        "Age":               rng.integers(18, 71, n),
        "Gender":            rng.choice(["Male", "Female", "Non-binary"], n, p=[0.63, 0.32, 0.05]),
        "Last_Attended":     [(base - timedelta(days=int(d))).strftime("%Y-%m-%d")
                              for d in rng.integers(0, 1095, n)],
        "Tickets_Purchased": tix,
        "Spend":             np.where(tix == 0, 0.0, np.round(rng.uniform(20, 600, n), 2)),
        "Membership_Type":   rng.choice(["Season Ticket", "Gold", "Standard", "Basic", "None"],
                                         n, p=[0.15, 0.18, 0.35, 0.22, 0.10]),
        "Engagement_Score":  np.round(eng, 1),
        "Channel_Preference":rng.choice(["Email", "App", "Social Media", "SMS"],
                                         n, p=[0.40, 0.28, 0.22, 0.10]),
        "Country":           rng.choice(
            ["England", "Scotland", "Ireland", "Wales", "USA",
             "Germany", "Spain", "Australia", "Norway", "France"],
            n, p=[0.70, 0.08, 0.04, 0.04, 0.04, 0.03, 0.03, 0.02, 0.01, 0.01],
        ),
    })
    return df.to_csv(index=False).encode()


def generate_template_csv() -> bytes:
    return pd.DataFrame(columns=[
        "Fan_ID", "Age", "Gender", "Last_Attended", "Tickets_Purchased",
        "Spend", "Membership_Type", "Engagement_Score", "Channel_Preference", "Country",
    ]).to_csv(index=False).encode()


# ── Upload screen ─────────────────────────────────────────────────────────────

COLUMN_UNLOCKS = [
    ("Fan_ID",             "Required — base for all features"),
    ("Age",                "Unlocks Audience Demographics"),
    ("Gender",             "Unlocks Gender Split analysis"),
    ("Last_Attended",      "Unlocks Audience Loyalty Score"),
    ("Tickets_Purchased",  "Unlocks Commercial Behaviour Index"),
    ("Spend",              "Unlocks Revenue Depth Score"),
    ("Membership_Type",    "Unlocks Ownership Tier Analysis"),
    ("Engagement_Score",   "Unlocks Audience Depth Index"),
    ("Channel_Preference", "Unlocks Activation Readiness"),
    ("Country",            "Unlocks Geographic Reach Analysis"),
]


def render_upload() -> None:
    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:4px">'
        '<span style="font-family:\'Syne\',sans-serif;font-size:30px;font-weight:800;color:#c8f135">RightsIQ</span>'
        '</div>'
        '<div style="font-size:15px;color:#6b7280;margin-bottom:36px">What is your audience worth?</div>',
        unsafe_allow_html=True,
    )
    col_up, col_info = st.columns([3, 2], gap="large")

    with col_up:
        st.markdown(
            '<div style="font-size:10px;color:#6b7280;text-transform:uppercase;'
            'letter-spacing:.1em;margin-bottom:10px">Upload Fan Database</div>',
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader("Drop your CSV here", type=["csv"],
                                    label_visibility="collapsed", key="upload_file")

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button("⬇  Sample CSV (200 fans)", data=generate_sample_csv(200),
                               file_name="rightsiq_sample_fans.csv", mime="text/csv", key="dl_sample")
        with dl2:
            st.download_button("⬇  CSV Template (headers)", data=generate_template_csv(),
                               file_name="rightsiq_template.csv", mime="text/csv", key="dl_template")

        if uploaded:
            try:
                df_raw = pd.read_csv(uploaded)
            except Exception as e:
                st.error(f"Could not read file: {e}")
                return

            col_map   = auto_map_columns(list(df_raw.columns))
            n_matched = sum(1 for k in CORE_COLUMNS if k in col_map)

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            if n_matched >= MIN_CORE_COLS:
                st.markdown(card(
                    f'<div style="color:#22c55e;font-size:12px;font-weight:600">'
                    f'✓ {n_matched} of {len(CORE_COLUMNS)} columns matched — full analysis unlocked</div>'
                    f'<div style="font-size:10px;color:#6b7280;margin-top:4px">{len(df_raw):,} fans detected</div>',
                    border="#22c55e",
                ), unsafe_allow_html=True)
                club_name = st.text_input("Club / Organisation name (optional)",
                                          placeholder="e.g. Manchester City FC",
                                          key="club_name_input")
                if st.button("Analyse Audience  →", key="analyse_btn"):
                    st.session_state.update({"df_raw": df_raw, "col_map": col_map,
                                             "club_name": club_name.strip(), "schema_mode": "full"})
                    st.rerun()
            else:
                st.markdown(card(
                    f'<div style="color:#f59e0b;font-size:12px;font-weight:600">'
                    f'⚠ Only {n_matched} core columns matched</div>'
                    f'<div style="font-size:10px;color:#6b7280;margin-top:4px">'
                    f'Showing Custom Metrics Explorer only. Need at least {MIN_CORE_COLS} columns for full analysis.</div>',
                    border="#f59e0b",
                ), unsafe_allow_html=True)
                if st.button("Continue with limited data  →", key="analyse_custom_btn"):
                    st.session_state.update({"df_raw": df_raw, "col_map": col_map,
                                             "club_name": "", "schema_mode": "custom"})
                    st.rerun()

    with col_info:
        st.markdown(
            '<div style="font-size:10px;color:#6b7280;text-transform:uppercase;'
            'letter-spacing:.1em;margin-bottom:10px">Recommended Columns</div>',
            unsafe_allow_html=True,
        )
        for col_name, unlock in COLUMN_UNLOCKS:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
                f'padding:8px 0;border-bottom:1px solid #1f2937">'
                f'<code style="color:#c8f135;font-size:10px;background:none">{col_name}</code>'
                f'<span style="font-size:10px;color:#6b7280;text-align:right;max-width:210px">{unlock}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── Custom Explorer ───────────────────────────────────────────────────────────

def render_custom_explorer(df: pd.DataFrame) -> None:
    section_heading("Custom Metrics Explorer")
    st.markdown('<div style="font-size:11px;color:#6b7280;margin-bottom:16px">'
                'Limited columns detected. Explore your data below.</div>', unsafe_allow_html=True)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        st.info("No numeric columns found.")
        return
    c1, c2 = st.columns(2)
    with c1: x_col = st.selectbox("X axis", numeric_cols, key="cme_x")
    with c2: y_col = st.selectbox("Y axis", numeric_cols, index=min(1, len(numeric_cols)-1), key="cme_y")
    fig = go.Figure(go.Scatter(x=df[x_col], y=df[y_col], mode="markers",
                               marker=dict(color="#c8f135", size=5, opacity=0.6)))
    fig.update_layout(**_L, margin=_M, height=280,
                      xaxis=dict(title=x_col, tickfont=dict(size=9, color="#6b7280"), showgrid=False),
                      yaxis=dict(title=y_col, tickfont=dict(size=9, color="#6b7280"), showgrid=False))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="cme_scatter")
    st.dataframe(df.describe().round(2), use_container_width=True)


# ── Tab 1 — Audience Ownership ────────────────────────────────────────────────

def render_tab_ownership(df: pd.DataFrame, col: dict, ownership: dict) -> None:
    club    = st.session_state.get("club_name", "")
    heading = f"{club} — Audience Ownership" if club else "Audience Ownership"
    st.markdown(
        f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
        f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
        f'<div style="font-size:11px;color:#6b7280;margin-bottom:18px">'
        f'How much of this audience does the rights holder actually own and know?</div>',
        unsafe_allow_html=True,
    )
    own_color = "#22c55e" if ownership["owned_pct"] >= BENCHMARK_OWNERSHIP else "#f59e0b"
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Fan Ownership Score", f"{ownership['ownership_score']:.0f}", "/100", "#c8f135"), unsafe_allow_html=True)
    with k2: st.markdown(kpi("Fans in Database", f"{ownership['n_total']:,}", "owned records"), unsafe_allow_html=True)
    with k3: st.markdown(kpi("Est. Total Reach", f"{ownership['est_anonymous_reach']:,}", "incl. anonymous (8x)"), unsafe_allow_html=True)
    with k4: st.markdown(kpi("Owned Audience", f"{ownership['owned_pct']:.0f}%",
                             f"vs {BENCHMARK_OWNERSHIP}% industry avg", own_color), unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    cmp_ = "above" if ownership["owned_pct"] >= BENCHMARK_OWNERSHIP else "below"
    insight_banner(
        f'You own {ownership["owned_pct"]:.0f}% of your estimated total audience — '
        f'{cmp_} the industry average of {BENCHMARK_OWNERSHIP}%. '
        f'Your database of {ownership["n_total"]:,} known fans represents an estimated '
        f'{ownership["n_total"]:,} of {ownership["est_anonymous_reach"]:,} total reach. '
        f'The {ownership["est_anonymous_reach"] - ownership["n_total"]:,} anonymous fans '
        f'are commercial value waiting to be captured.',
        own_color,
    )

    section_heading("Owned vs Anonymous Audience Split")
    ch1, ch2 = st.columns([2, 3])
    with ch1:
        st.plotly_chart(chart_ownership_donut(ownership), use_container_width=True,
                        config={"displayModeBar": False}, key="ownership_donut")
    with ch2:
        for label_, count_, color_, desc_ in [
            ("Fully Owned",       ownership["n_fully_owned"],      "#c8f135", "Membership + transaction history on file"),
            ("Partially Known",   ownership["n_partially_known"],  "#3d9cf0", "Some data held — incomplete profile"),
            ("Anonymous (in DB)", ownership["n_anonymous_in_db"],  "#6b7280", "Fan ID only — no enrichment data"),
        ]:
            pct_ = count_ / max(ownership["n_total"], 1) * 100
            st.markdown(
                f'<div style="background:#13161d;border:1px solid #1f2937;border-radius:8px;padding:12px 16px;margin-bottom:10px">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:6px">'
                f'<span style="font-size:12px;color:{color_};font-weight:600">{label_}</span>'
                f'<span style="font-size:11px;color:#e5e7eb">{count_:,} fans ({pct_:.0f}%)</span></div>'
                f'<div style="background:#0d1117;border-radius:3px;height:4px;margin-bottom:6px">'
                f'<div style="width:{int(pct_)}%;height:100%;background:{color_};border-radius:3px"></div></div>'
                f'<div style="font-size:10px;color:#6b7280">{desc_}</div></div>',
                unsafe_allow_html=True,
            )

    section_heading("Anonymous Audience Context")
    anon = ownership["est_anonymous_reach"] - ownership["n_total"]
    st.markdown(card(
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px">'
        f'<div><div style="font-size:9px;color:#6b7280;text-transform:uppercase;margin-bottom:4px">Est. Anonymous Fans</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:22px;font-weight:700;color:#e5e7eb">{anon:,}</div>'
        f'<div style="font-size:9px;color:#6b7280">8x database multiplier (industry research)</div></div>'
        f'<div><div style="font-size:9px;color:#6b7280;text-transform:uppercase;margin-bottom:4px">Industry Finding</div>'
        f'<div style="font-size:11px;color:#9ca3af;line-height:1.6">76% of sports fans are <span style="color:#f59e0b">anonymous</span> '
        f'to the organisations they support</div></div>'
        f'<div><div style="font-size:9px;color:#6b7280;text-transform:uppercase;margin-bottom:4px">Capture Opportunity</div>'
        f'<div style="font-size:11px;color:#9ca3af;line-height:1.6">Each 1% improvement in ownership is '
        f'<span style="color:#c8f135">~{ownership["est_anonymous_reach"]//100:,} additional known fans</span></div></div>'
        f'</div>'
    ), unsafe_allow_html=True)

    age_fig = chart_age_distribution(df, col)
    ch_fig  = chart_channel_split(df, col)
    if age_fig or ch_fig:
        section_heading("Audience Profile")
        figs_ = [(l_, f_, k_) for l_, f_, k_ in
                 [("Age Distribution", age_fig, "age_dist"), ("Channel Preference", ch_fig, "ch_split")]
                 if f_ is not None]
        containers_ = st.columns(len(figs_)) if len(figs_) > 1 else [st.container()]
        for (l_, f_, k_), c_ in zip(figs_, containers_):
            with c_:
                st.markdown(f'<div style="font-size:10px;color:#6b7280;margin-bottom:6px">{l_}</div>',
                            unsafe_allow_html=True)
                st.plotly_chart(f_, use_container_width=True,
                                config={"displayModeBar": False}, key=k_)


# ── Tab 2 — Audience Quality Index ────────────────────────────────────────────

def render_tab_quality(df: pd.DataFrame, col: dict, aqi: dict) -> None:
    club    = st.session_state.get("club_name", "")
    heading = f"{club} — Audience Quality Index" if club else "Audience Quality Index"
    st.markdown(
        f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
        f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
        f'<div style="font-size:11px;color:#6b7280;margin-bottom:18px">'
        f'How good is the owned audience — not just how big.</div>',
        unsafe_allow_html=True,
    )
    aqi_color = "#22c55e" if aqi["aqi"] >= 70 else "#f59e0b" if aqi["aqi"] >= 50 else "#ef4444"
    gap       = aqi["aqi"] - BENCHMARK_AQI
    pct_rank  = min(int(aqi["aqi"]), 99)

    k1, k2, k3 = st.columns([2, 1, 1])
    with k1: st.markdown(kpi("Audience Quality Index", f"{aqi['aqi']:.0f}",
                             f"Top {100-pct_rank}% of comparable properties", aqi_color), unsafe_allow_html=True)
    with k2: st.markdown(kpi("Industry Average", f"{BENCHMARK_AQI}", "/100 benchmark"), unsafe_allow_html=True)
    with k3: st.markdown(kpi("vs Benchmark", f"{'+' if gap >= 0 else ''}{gap:.0f} pts",
                             "above / below", "#22c55e" if gap >= 0 else "#ef4444"), unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    subs = [aqi["loyalty"], aqi["commercial"], aqi["demographic"], aqi["engagement"]]
    sub_labels = ["Loyalty", "Commercial Behaviour", "Demographic Value", "Engagement Depth"]
    insight_banner(
        f'AQI {aqi["aqi"]:.0f}/100 — {"above" if aqi["aqi"] >= BENCHMARK_AQI else "below"} '
        f'the industry average of {BENCHMARK_AQI}. '
        f'Strongest driver: {sub_labels[subs.index(max(subs))]}. '
        f'Greatest opportunity: {sub_labels[subs.index(min(subs))]}.',
        aqi_color,
    )

    section_heading("Quality Sub-Scores")
    sc1, sc2 = st.columns([2, 3])
    with sc1:
        for lbl_, sc_, col_, desc_, wt_ in [
            ("Loyalty Score",        aqi["loyalty"],     "#c8f135", "Recency + frequency of attendance", "30%"),
            ("Commercial Behaviour", aqi["commercial"],  "#3d9cf0", "Spend + membership tier",           "30%"),
            ("Demographic Value",    aqi["demographic"], "#a78bfa", "Age bracket + gender diversity",     "20%"),
            ("Engagement Depth",     aqi["engagement"],  "#f59e0b", "Direct engagement signals",         "20%"),
        ]:
            vs_ = sc_ - BENCHMARK_AQI
            vc_ = "#22c55e" if vs_ >= 0 else "#ef4444"
            st.markdown(
                f'<div style="background:#13161d;border:1px solid #1f2937;border-radius:8px;padding:12px 16px;margin-bottom:10px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
                f'<span style="font-size:11px;color:{col_};font-weight:600">{lbl_}</span>'
                f'<span style="font-size:9px;color:{vc_}">{"+" if vs_>=0 else ""}{vs_:.0f} vs avg</span></div>'
                f'<div style="background:#0d1117;border-radius:3px;height:5px;margin-bottom:6px;position:relative">'
                f'<div style="width:{int(sc_)}%;height:100%;background:{col_};border-radius:3px"></div>'
                f'<div style="position:absolute;left:{int(BENCHMARK_AQI)}%;top:-2px;width:1px;height:9px;background:#6b7280"></div></div>'
                f'<div style="display:flex;justify-content:space-between">'
                f'<span style="font-size:9px;color:#6b7280">{desc_}</span>'
                f'<span style="font-size:10px;color:#e5e7eb;font-weight:600">{sc_:.0f}/100</span></div>'
                f'<div style="font-size:9px;color:#374151;margin-top:3px">Weight: {wt_} of AQI</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    with sc2:
        st.plotly_chart(chart_aqi_radar(aqi), use_container_width=True,
                        config={"displayModeBar": False}, key="aqi_radar")

    section_heading("AQI Improvement Impact")
    st.markdown(card(
        f'<div style="font-size:11px;color:#9ca3af;margin-bottom:14px">'
        f'Impact of improving AQI by 10 points (from {aqi["aqi"]:.0f} to {aqi["aqi"]+10:.0f}):</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">'
        f'<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center">'
        f'<div style="font-size:9px;color:#6b7280;margin-bottom:4px">Rights Premium Score</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;color:#c8f135">+4 pts</div></div>'
        f'<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center">'
        f'<div style="font-size:9px;color:#6b7280;margin-bottom:4px">Sponsorship Value</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;color:#3d9cf0">~10%</div></div>'
        f'<div style="background:#0d1117;border-radius:8px;padding:14px;text-align:center">'
        f'<div style="font-size:9px;color:#6b7280;margin-bottom:4px">Negotiation Leverage</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;color:#a78bfa">High</div></div>'
        f'</div>'
    ), unsafe_allow_html=True)


# ── Tab 3 — Sponsorship Valuation ─────────────────────────────────────────────

def render_tab_valuation(ownership: dict, aqi: dict, valuation: dict) -> None:
    club    = st.session_state.get("club_name", "")
    heading = f"{club} — Sponsorship Rights Valuation" if club else "Sponsorship Rights Valuation"
    st.markdown(
        f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
        f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
        f'<div style="font-size:11px;color:#6b7280;margin-bottom:18px">'
        f'What is this audience worth to a sponsor?</div>',
        unsafe_allow_html=True,
    )
    total = valuation["shirt"] + valuation["stadium"] + valuation["digital"]
    bc_c  = "#22c55e" if valuation["broadcast_index"] >= 55 else "#ef4444"

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(kpi("Total Est. Rights Value", f"£{total:,.0f}", "shirt + stadium + digital", "#c8f135"), unsafe_allow_html=True)
    with k2: st.markdown(kpi("Shirt Sponsorship",       f"£{valuation['shirt']:,.0f}", "per annum estimate"), unsafe_allow_html=True)
    with k3: st.markdown(kpi("Stadium Naming Rights",   f"£{valuation['stadium']:,.0f}", "per annum estimate"), unsafe_allow_html=True)
    with k4: st.markdown(kpi("Broadcast Index",         f"{valuation['broadcast_index']:.0f}", "/100 vs 55 avg", bc_c), unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    insight_banner(
        f'Total estimated rights value £{total:,.0f} per annum. '
        f'Audience quality (AQI {aqi["aqi"]:.0f}/100) is the primary driver. '
        f'Improving owned fan data capture is the highest-leverage action available.'
    )

    section_heading("Rights Category Breakdown")
    st.plotly_chart(chart_valuation_bars(valuation), use_container_width=True,
                    config={"displayModeBar": False}, key="val_bars")

    section_heading("Rights Category Detail")
    owned_count = ownership["n_fully_owned"] + ownership["n_partially_known"]
    for item in [
        {"label": "Shirt Sponsorship",     "value": f"£{valuation['shirt']:,.0f}",   "color": "#c8f135",
         "driver": f"Owned fans ({owned_count:,}) x Commercial Behaviour ({aqi['commercial']:.0f}/100) x shirt multiplier",
         "bench": "Comparable range: £50k–£500k depending on property tier"},
        {"label": "Stadium Naming Rights", "value": f"£{valuation['stadium']:,.0f}", "color": "#3d9cf0",
         "driver": f"Owned fans x Audience Quality Index ({aqi['aqi']:.0f}/100) x naming rights multiplier",
         "bench": "Comparable range: £200k–£5m depending on stadium size"},
        {"label": "Digital Rights",        "value": f"£{valuation['digital']:,.0f}", "color": "#a78bfa",
         "driver": f"Owned fans x Engagement Depth Score ({aqi['engagement']:.0f}/100) x digital multiplier",
         "bench": "Digital rights now 25–40% of total sponsorship value"},
        {"label": "Broadcast Rights Index","value": f"{valuation['broadcast_index']:.0f}/100", "color": "#f59e0b",
         "driver": f"Loyalty Score ({aqi['loyalty']:.0f}) + Geographic Reach — index not a pound value",
         "bench": "Industry average broadcast index: 55/100"},
    ]:
        st.markdown(card(
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">'
            f'<span style="font-family:\'Syne\',sans-serif;font-size:14px;font-weight:700;color:{item["color"]}">{item["label"]}</span>'
            f'<span style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:800;color:{item["color"]}">{item["value"]}</span></div>'
            f'<div style="font-size:10px;color:#6b7280;margin-bottom:6px">{item["driver"]}</div>'
            f'<div style="font-size:10px;color:#4b5563;border-left:2px solid {item["color"]};padding-left:8px">{item["bench"]}</div>',
            border=item["color"] + "30",
        ), unsafe_allow_html=True)

    section_heading("Premium Uplift Calculator")
    st.markdown(card(
        f'<div style="font-size:11px;color:#9ca3af;margin-bottom:14px">'
        f'Additional rights value per 10-point improvement in Audience Quality Index:</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">'
        f'<div style="background:#0d1117;border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:9px;color:#6b7280;margin-bottom:4px">Shirt Sponsorship</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:18px;font-weight:700;color:#c8f135">'
        f'+£{int(valuation["shirt"]*0.10):,}</div>'
        f'<div style="font-size:9px;color:#4b5563">per 10 AQI points</div></div>'
        f'<div style="background:#0d1117;border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:9px;color:#6b7280;margin-bottom:4px">Stadium Naming</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:18px;font-weight:700;color:#3d9cf0">'
        f'+£{int(valuation["stadium"]*0.10):,}</div>'
        f'<div style="font-size:9px;color:#4b5563">per 10 AQI points</div></div>'
        f'<div style="background:#0d1117;border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:9px;color:#6b7280;margin-bottom:4px">Digital Rights</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:18px;font-weight:700;color:#a78bfa">'
        f'+£{int(valuation["digital"]*0.10):,}</div>'
        f'<div style="font-size:9px;color:#4b5563">per 10 AQI points</div></div>'
        f'</div>'
    ), unsafe_allow_html=True)


# ── Tab 4 — Rights Premium Score ──────────────────────────────────────────────

def render_tab_rps(ownership: dict, aqi: dict, valuation: dict, rps_data: dict) -> None:
    club    = st.session_state.get("club_name", "")
    heading = f"{club} — Rights Premium Score" if club else "Rights Premium Score"
    st.markdown(
        f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
        f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
        f'<div style="font-size:11px;color:#6b7280;margin-bottom:18px">'
        f'Your negotiation anchor — what this property commands.</div>',
        unsafe_allow_html=True,
    )
    rps = rps_data["rps"]
    rps_color = "#22c55e" if rps >= 70 else "#f59e0b" if rps >= 50 else "#ef4444"
    if rps >= 70:
        tier_label, tier_desc = "Premium Property", "Your audience quality commands above-market rights fees."
    elif rps >= 50:
        tier_label, tier_desc = "Market Rate Property", "Your rights are fairly valued at current market rates."
    else:
        tier_label, tier_desc = "Developing Property", "Audience quality improvements would unlock significant value uplift."

    g1, g2 = st.columns([2, 3])
    with g1:
        st.plotly_chart(chart_rps_gauge(rps), use_container_width=True,
                        config={"displayModeBar": False}, key="rps_gauge")
        st.markdown(
            f'<div style="text-align:center;margin-top:-10px">'
            f'<div style="font-family:\'Syne\',sans-serif;font-size:15px;font-weight:700;color:{rps_color}">{tier_label}</div>'
            f'<div style="font-size:10px;color:#6b7280;margin-top:4px">{tier_desc}</div></div>',
            unsafe_allow_html=True,
        )
    with g2:
        section_heading("Score Drivers")
        if rps_data["drivers_up"]:
            st.markdown('<div style="font-size:10px;color:#22c55e;margin-bottom:8px">↑ Pushing score up</div>', unsafe_allow_html=True)
            for d in rps_data["drivers_up"]:
                st.markdown(f'<div style="background:#052e16;border-left:3px solid #22c55e;border-radius:4px;'
                            f'padding:8px 12px;margin-bottom:6px;font-size:10px;color:#9ca3af">{d}</div>',
                            unsafe_allow_html=True)
        if rps_data["drivers_down"]:
            st.markdown('<div style="font-size:10px;color:#ef4444;margin:8px 0">↓ Pulling score down</div>', unsafe_allow_html=True)
            for d in rps_data["drivers_down"]:
                st.markdown(f'<div style="background:#1f0a0a;border-left:3px solid #ef4444;border-radius:4px;'
                            f'padding:8px 12px;margin-bottom:6px;font-size:10px;color:#9ca3af">{d}</div>',
                            unsafe_allow_html=True)

    section_heading("Market Positioning")
    st.plotly_chart(chart_benchmark_position(rps), use_container_width=True,
                    config={"displayModeBar": False}, key="rps_benchmark")

    section_heading("Score Components")
    total = valuation["shirt"] + valuation["stadium"] + valuation["digital"]
    val_i = min(total / max(ownership["n_total"], 1) / 10, 100)
    c1_, c2_, c3_ = st.columns(3)
    for (lbl_, val_, wt_, col_), cnt_ in zip(
        [("Audience Ownership", ownership["ownership_score"], 0.30, "#c8f135"),
         ("Audience Quality",   aqi["aqi"],                   0.40, "#3d9cf0"),
         ("Valuation Index",    val_i,                        0.30, "#a78bfa")],
        [c1_, c2_, c3_],
    ):
        with cnt_:
            st.markdown(
                f'<div style="background:#13161d;border:1px solid #2a2f3d;border-radius:8px;padding:14px;text-align:center">'
                f'<div style="font-size:9px;color:#6b7280;margin-bottom:4px">{lbl_}</div>'
                f'<div style="font-family:\'Syne\',sans-serif;font-size:22px;font-weight:700;color:{col_}">{val_:.0f}</div>'
                f'<div style="font-size:9px;color:#6b7280">Weight: {int(wt_*100)}%</div>'
                f'<div style="font-size:9px;color:{col_};margin-top:4px">Contributes {val_*wt_:.1f} pts</div></div>',
                unsafe_allow_html=True,
            )

    section_heading("3 Actions to Increase Rights Premium Score")
    for i, action in enumerate(rps_data["actions"]):
        st.markdown(card(
            f'<div style="display:flex;gap:16px;align-items:flex-start">'
            f'<div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#c8f135;min-width:32px;line-height:1.1">0{i+1}</div>'
            f'<div><div style="font-size:12px;color:#e5e7eb;font-weight:600;margin-bottom:4px">{action["action"]}</div>'
            f'<div style="font-size:10px;color:#6b7280;margin-bottom:6px">{action["impact"]}</div>'
            f'<div style="font-size:10px;color:#c8f135;background:#0f1a00;border-radius:4px;padding:3px 8px;display:inline-block">'
            f'{action["value"].replace("GBP", "£")}</div></div></div>',
            border="#c8f13530",
        ), unsafe_allow_html=True)


# ── Tab 5 — Negotiation Pack ──────────────────────────────────────────────────

def render_tab_report(ownership: dict, aqi: dict, valuation: dict, rps_data: dict) -> None:
    club    = st.session_state.get("club_name", "")
    heading = f"{club} — Negotiation Pack" if club else "Negotiation Pack"
    st.markdown(
        f'<div style="font-family:\'Syne\',sans-serif;font-size:20px;font-weight:700;'
        f'color:#e5e7eb;margin-bottom:4px">{heading}</div>'
        f'<div style="font-size:11px;color:#6b7280;margin-bottom:18px">'
        f'Download your complete rights valuation pack for sponsorship negotiations.</div>',
        unsafe_allow_html=True,
    )
    total = valuation["shirt"] + valuation["stadium"] + valuation["digital"]

    st.markdown(card(
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:16px;margin-bottom:16px">'
        f'<div style="text-align:center"><div style="font-size:9px;color:#6b7280;margin-bottom:4px">Ownership Score</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#c8f135">{ownership["ownership_score"]:.0f}</div></div>'
        f'<div style="text-align:center"><div style="font-size:9px;color:#6b7280;margin-bottom:4px">Quality Index</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#3d9cf0">{aqi["aqi"]:.0f}</div></div>'
        f'<div style="text-align:center"><div style="font-size:9px;color:#6b7280;margin-bottom:4px">Rights Premium</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#a78bfa">{rps_data["rps"]:.0f}</div></div>'
        f'<div style="text-align:center"><div style="font-size:9px;color:#6b7280;margin-bottom:4px">Total Value Est.</div>'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:24px;font-weight:800;color:#f59e0b">£{total:,.0f}</div></div>'
        f'</div>'
        f'<div style="font-size:10px;color:#4b5563;text-align:center">'
        f'3-page PDF: Executive Summary · Benchmark Comparison · Recommended Actions</div>'
    ), unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if HAS_FPDF:
        pdf_bytes = generate_pdf(club, ownership, aqi, valuation, rps_data)
        fname = f"rightsiq_{club.lower().replace(' ','_') or 'report'}_{datetime.now().strftime('%Y%m%d')}.pdf"
        st.download_button("⬇  Download Negotiation Pack PDF", data=pdf_bytes,
                           file_name=fname, mime="application/pdf", key="dl_pdf_report")
    else:
        st.warning("PDF generation requires fpdf2. Run: pip install fpdf2")

    section_heading("Report Contents")
    for pg, title_, desc_ in [
        ("Page 1", "Executive Summary",
         f"Ownership {ownership['ownership_score']:.0f} · AQI {aqi['aqi']:.0f} · RPS {rps_data['rps']:.0f} · Total £{total:,.0f}"),
        ("Page 2", "Benchmark Comparison",
         "How your property compares to industry averages across all 4 quality dimensions"),
        ("Page 3", "Recommended Actions",
         "3 specific actions to increase rights value with estimated commercial impact"),
    ]:
        st.markdown(card(
            f'<div style="display:flex;align-items:flex-start;gap:16px">'
            f'<div style="font-size:9px;color:#6b7280;min-width:44px;padding-top:2px">{pg}</div>'
            f'<div><div style="font-size:12px;color:#e5e7eb;font-weight:600;margin-bottom:3px">{title_}</div>'
            f'<div style="font-size:10px;color:#6b7280">{desc_}</div></div></div>'
        ), unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if "df_raw" not in st.session_state:
        render_upload()
        return

    df_raw = st.session_state["df_raw"]
    col    = st.session_state["col_map"]
    club   = st.session_state.get("club_name", "")
    schema = st.session_state.get("schema_mode", "custom")

    club_span = (f'<span style="font-size:12px;color:#6b7280;margin-left:10px">{club}</span>'
                 if club else "")
    st.markdown(
        f'<div style="display:flex;align-items:center;margin-bottom:16px">'
        f'<span style="font-family:\'Syne\',sans-serif;font-size:22px;font-weight:800;color:#c8f135">RightsIQ</span>'
        f'{club_span}</div>',
        unsafe_allow_html=True,
    )

    if st.button("↩  New Upload", key="new_upload_btn"):
        for k in ["df_raw", "col_map", "club_name", "schema_mode"]:
            st.session_state.pop(k, None)
        st.rerun()

    if schema == "custom":
        render_custom_explorer(df_raw)
        return

    df         = df_raw.copy()
    loyalty    = compute_loyalty_score(df, col)
    commercial = compute_commercial_score(df, col)
    demographic= compute_demographic_score(df, col)
    engagement = compute_engagement_score(df, col)
    ownership  = compute_ownership(df, col)
    aqi        = compute_aqi(loyalty, commercial, demographic, engagement)
    geo        = compute_geo_reach(df, col)
    valuation  = compute_valuation(ownership, aqi, geo)
    rps_data   = compute_rps(ownership, aqi, valuation)

    tab_own, tab_qual, tab_val, tab_rps, tab_rep = st.tabs([
        "🏆  Audience Ownership",
        "📊  Audience Quality Index",
        "💷  Sponsorship Valuation",
        "⭐  Rights Premium Score",
        "📄  Negotiation Pack",
    ])

    with tab_own:  render_tab_ownership(df, col, ownership)
    with tab_qual: render_tab_quality(df, col, aqi)
    with tab_val:  render_tab_valuation(ownership, aqi, valuation)
    with tab_rps:  render_tab_rps(ownership, aqi, valuation, rps_data)
    with tab_rep:  render_tab_report(ownership, aqi, valuation, rps_data)


main()
