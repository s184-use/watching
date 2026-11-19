"""共用的版面、格式與樣式。台股慣例:紅漲綠跌。"""
import datetime as dt
from zoneinfo import ZoneInfo

import streamlit as st

TZ = ZoneInfo("Asia/Taipei")
UP, DOWN = "#e5484d", "#2f9e6f"


def now_tw() -> dt.datetime:
    return dt.datetime.now(TZ)


def today_tw() -> dt.date:
    return now_tw().date()


def is_trading_time() -> bool:
    n = now_tw()
    return n.weekday() < 5 and dt.time(9, 0) <= n.time() <= dt.time(13, 35)


CSS = """
<style>
.block-container {padding-top: 1.6rem; max-width: 1200px;}
[data-testid="stMetricLabel"] p {font-size: .82rem; color: #6b7280;}
[data-testid="stMetricValue"] {font-size: 1.45rem;}
h2, h3 {letter-spacing: .2px;}
.card {background:#f5f7fb; border-radius:12px; padding:14px 16px; margin-bottom:10px;}
.tag {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; margin-right:6px;}
.tag.bull {background:#fde8e9; color:#b4232a;}
.tag.bear {background:#e3f4ec; color:#1d7a54;}
.tag.neutral {background:#eceff4; color:#4b5563;}
table.lv {width:100%; border-collapse:collapse; font-variant-numeric: tabular-nums;}
table.lv th {font-size:.75rem; color:#6b7280; text-align:right; padding:4px 8px; font-weight:500;}
table.lv th:first-child {text-align:left;}
table.lv td {padding:5px 8px; text-align:right; border-bottom:1px solid #eef0f4; font-size:.95rem;}
table.lv td:first-child {text-align:left; color:#6b7280; font-size:.85rem;}
table.lv td.barcell {width:38%; padding:5px 0 5px 8px;}
table.lv .bar {height:10px; border-radius:3px; display:block;}
table.lv tr.last td {background:#f5f7fb; font-weight:600; font-size:1.05rem;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_title(title: str, sub: str = "") -> None:
    st.markdown(f"## {title}")
    if sub:
        st.caption(sub)


def disclaimer() -> None:
    st.caption("本站資訊與 AI 分析僅供參考,不構成任何買賣建議;投資有風險,請自行判斷並負責。")


def num(x, d: int = 2, suffix: str = "") -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    return f"{x:,.{d}f}{suffix}"


def pct(x) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    return f"{x:+.2f}%"


def big(x) -> str:
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    if abs(x) >= 1e12:
        return f"{x / 1e12:.2f} 兆"
    if abs(x) >= 1e8:
        return f"{x / 1e8:,.0f} 億"
    return f"{x:,.0f}"


def grade(score) -> tuple[str, str]:
    """分數 → (等級, 顏色)"""
    if score is None:
        return "資料不足", "#9ca3af"
    if score >= 80:
        return "優良", "#2f9e6f"
    if score >= 65:
        return "良好", "#3b82f6"
    if score >= 50:
        return "普通", "#f59e0b"
    return "需留意", "#e5484d"


def style_fig(fig, height: int = 420):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#eef0f4")
    return fig


def remember_symbol(code: str) -> None:
    rec = st.session_state.setdefault("recent", [])
    if code in rec:
        rec.remove(code)
    rec.insert(0, code)
    del rec[8:]
