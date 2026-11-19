"""持股健康度:個股(技術/籌碼/基本)+ 組合(分散度)。分數越高越健康,僅為量化參考。"""
import pandas as pd
import streamlit as st

from core import market as mk
from core.indicators import add_indicators, tech_summary


def fundamental_score(info: dict):
    """用 yfinance 的估值/獲利/成長/負債指標,各 20 分;資料缺的項目不計。"""
    pts, avail, notes = 0, 0, []

    pe = info.get("trailingPE")
    if pe is not None:
        avail += 1
        if 0 < pe <= 20:
            pts += 20; notes.append(f"本益比 {pe:.1f},估值合理")
        elif 0 < pe <= 30:
            pts += 12; notes.append(f"本益比 {pe:.1f},估值偏高")
        elif pe > 30:
            pts += 5; notes.append(f"本益比 {pe:.1f},估值偏貴")
        else:
            notes.append("目前虧損,本益比不適用")

    pm = info.get("profitMargins")
    if pm is not None:
        avail += 1
        pts += 20 if pm > 0.10 else 10 if pm > 0 else 0
        notes.append(f"淨利率 {pm * 100:.1f}%")

    roe = info.get("returnOnEquity")
    if roe is not None:
        avail += 1
        pts += 20 if roe > 0.10 else 10 if roe > 0 else 0
        notes.append(f"ROE {roe * 100:.1f}%")

    rg = info.get("revenueGrowth")
    if rg is not None:
        avail += 1
        pts += 20 if rg > 0.10 else 10 if rg > 0 else 0
        notes.append(f"營收成長 {rg * 100:+.1f}%")

    de = info.get("debtToEquity")
    if de is not None:
        avail += 1
        pts += 20 if de < 80 else 10 if de < 150 else 0
        notes.append(f"負債權益比 {de:.0f}%")

    if avail == 0:
        return None, ["基本面資料不足"]
    return round(pts / (20 * avail) * 100), notes


def chip_score(code: str):
    """近 5 個交易日法人買賣超。"""
    p = mk.get_institutional(code, 30)
    if p.empty or len(p) < 3:
        return None, ["籌碼資料不足"]
    t = p.tail(5).sum()
    pts, notes = 0, []
    for key, w in (("三大法人", 50), ("外資", 30), ("投信", 20)):
        v = t[key]
        if v > 0:
            pts += w
        notes.append(f"{key}近 5 日{'買超' if v > 0 else '賣超'} {abs(v):,.0f} 張")
    return pts, notes


@st.cache_data(ttl=1800, show_spinner=False)
def stock_health(code: str) -> dict:
    hist = mk.get_history(code, "1y")
    tech = tech_summary(add_indicators(hist)) if not hist.empty else {"score": None, "notes": []}
    f_score, f_notes = fundamental_score(mk.get_info(code))
    c_score, c_notes = chip_score(code)

    parts = {"tech": (tech["score"], 0.4), "chip": (c_score, 0.3), "fund": (f_score, 0.3)}
    avail = {k: v for k, v in parts.items() if v[0] is not None}
    total = None
    if avail:
        w = sum(v[1] for v in avail.values())
        total = round(sum(s * wt for s, wt in avail.values()) / w)
    return {
        "score": total, "tech": tech["score"], "chip": c_score, "fund": f_score,
        "tech_notes": tech["notes"], "chip_notes": c_notes, "fund_notes": f_notes,
        "price": float(hist["Close"].iloc[-1]) if not hist.empty else None,
    }


def portfolio_health(holdings: pd.DataFrame, progress=None) -> dict:
    """holdings 欄位:symbol, shares, cost(每股成本)。"""
    rows = []
    n = len(holdings)
    for i, h in enumerate(holdings.itertuples(), 1):
        hs = stock_health(h.symbol)
        price = hs["price"]
        value = (price or 0) * h.shares
        cost_total = h.cost * h.shares
        rows.append({
            "symbol": h.symbol, "name": mk.stock_name(h.symbol), "industry": mk.stock_industry(h.symbol),
            "shares": h.shares, "cost": h.cost, "price": price, "value": value, "cost_total": cost_total,
            "pnl_pct": (price / h.cost - 1) * 100 if price and h.cost else None,
            "health": hs["score"], "tech": hs["tech"], "chip": hs["chip"], "fund": hs["fund"],
            "detail": hs,
        })
        if progress:
            progress.progress(i / n, text=f"分析 {h.symbol} ({i}/{n})")
    df = pd.DataFrame(rows)
    total_value = df["value"].sum()
    df["weight"] = df["value"] / total_value * 100 if total_value else 0

    # 分散度(滿分 100)
    top = df["weight"].max() if total_value else 100
    div, div_notes = 0, []
    if top <= 30:
        div += 40; div_notes.append(f"單一持股最高占 {top:.0f}%,集中度低")
    elif top <= 50:
        div += 25; div_notes.append(f"單一持股最高占 {top:.0f}%,略為集中")
    else:
        div += 10; div_notes.append(f"單一持股最高占 {top:.0f}%,過度集中")
    cnt = len(df)
    div += 30 if cnt >= 5 else 20 if cnt >= 3 else 8
    div_notes.append(f"持有 {cnt} 檔")
    inds = df["industry"].nunique()
    div += 30 if inds >= 3 else 18 if inds == 2 else 8
    div_notes.append(f"涵蓋 {inds} 個產業")

    valid = df.dropna(subset=["health"])
    weighted = (valid["health"] * valid["value"]).sum() / valid["value"].sum() if not valid.empty and valid["value"].sum() else None
    overall = round(weighted * 0.7 + div * 0.3) if weighted is not None else None

    warnings = []
    for r in df.itertuples():
        if r.health is not None and r.health < 50:
            warnings.append(f"{r.symbol} {r.name} 健康度偏低({r.health} 分)")
        if r.weight > 40 and cnt > 1:
            warnings.append(f"{r.symbol} {r.name} 占組合 {r.weight:.0f}%,比重偏高")
        if r.pnl_pct is not None and r.pnl_pct <= -20:
            warnings.append(f"{r.symbol} {r.name} 未實現虧損 {r.pnl_pct:.1f}%")
    return {"overall": overall, "diversification": div, "div_notes": div_notes,
            "weighted": round(weighted) if weighted is not None else None, "table": df, "warnings": warnings}
