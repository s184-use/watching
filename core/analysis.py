"""免費的規則式個股分析:把技術、籌碼、基本面資料整理成易讀的參考說明。
不呼叫任何付費服務,也不給買賣建議,只描述資料現況與「觀察條件」。"""
from core import health, ui
from core import market as mk
from core.indicators import add_indicators, tech_summary

TONE = {"bull": "偏多", "bear": "偏空", "neutral": "中性"}


def _stance(score):
    if score is None:
        return "資料不足,無法綜合判讀"
    if score >= 65:
        return "資料面偏多"
    if score >= 45:
        return "資料面中性"
    return "資料面偏弱"


def build_report(code: str, holding: dict | None = None) -> str:
    name = mk.stock_name(code)
    hist = mk.get_history(code, "2y")
    hs = health.stock_health(code)
    info = mk.get_info(code)
    out = [f"### {name} ({code}) 三面分析", f"_資料日期:{hist.index[-1].date() if not hist.empty else '—'}_"]

    # ---- 技術面
    d = add_indicators(hist) if not hist.empty else hist
    ts = tech_summary(d) if not hist.empty else {"score": None, "notes": [], "latest": {}}
    out.append(f"#### 技術面　{ts['score'] if ts['score'] is not None else '—'} / 100")
    out += [f"- **{TONE[t]}**:{txt}" for t, txt in ts["notes"]] or ["- 資料不足"]

    # ---- 籌碼面
    out.append(f"#### 籌碼面　{hs['chip'] if hs['chip'] is not None else '—'} / 100")
    p = mk.get_institutional(code, 30)
    if p.empty:
        out.append("- 沒有法人買賣超資料(ETF 或資料源忙碌時可能沒有)")
    else:
        for label, n in (("近 5 日", 5), ("近 20 日", 20)):
            t = p.tail(n).sum()
            out.append(f"- {label}累計:外資 {t['外資']:,.0f}、投信 {t['投信']:,.0f}、自營商 {t['自營商']:,.0f}(張,正數為買超)")
    m = mk.get_margin(code, 30)
    if not m.empty and len(m) > 5:
        dm = m["融資餘額"].iloc[-1] - m["融資餘額"].iloc[-6]
        out.append(f"- 融資餘額 5 日{'增加' if dm > 0 else '減少'} {abs(dm):,.0f} 張(融資增加代表散戶槓桿升高)")

    # ---- 基本面
    out.append(f"#### 基本面　{hs['fund'] if hs['fund'] is not None else '—'} / 100")
    out += [f"- {n}" for n in hs["fund_notes"]]
    rev = mk.get_month_revenue(code)
    if not rev.empty:
        r = rev.tail(3)
        out.append("- 近 3 個月營收年增率:" + "、".join(f"{x[1]}:{ui.num(x[3], 1)}%" for x in r.itertuples()))
    eps = mk.get_eps(code)
    if not eps.empty:
        out.append("- 近 4 季 EPS:" + "、".join(f"{x.季底}:{x.EPS}" for x in eps.tail(4).itertuples()))

    # ---- 綜合
    out.append("#### 綜合")
    out.append(f"- 綜合分數 **{hs['score'] if hs['score'] is not None else '—'} / 100**,{_stance(hs['score'])}。")
    out.append("- 三面分數差距大時(例如技術強、基本弱),代表訊號分歧,解讀要更保守。")

    # ---- 觀察條件
    lv = ts.get("latest", {})
    if lv:
        out.append("#### 可以觀察的條件")
        out.append(f"- 收盤是否守住 20 日線({lv['MA20']:.2f}):守住代表短線趨勢維持,跌破則轉弱。")
        out.append(f"- 收盤是否守住 60 日線({lv['MA60']:.2f}):這是中期趨勢的參考位置。")
        if lv.get("RSI", 50) > 70:
            out.append("- RSI 偏高,短線過熱時常出現震盪或拉回。")
        elif lv.get("RSI", 50) < 30:
            out.append("- RSI 偏低,屬超賣區,但弱勢股也可能持續偏弱。")

    # ---- 個人持股
    if holding:
        out.append("#### 你的持股")
        out.append(f"- 持有 {holding['shares']:,.0f} 股,成本 {holding['cost']:.2f},目前損益 {ui.pct(holding.get('pnl_pct'))}。")
        if holding.get("weight") is not None:
            out.append(f"- 占你的投資組合 {holding['weight']:.0f}%" + ("(比重偏高,留意單一個股風險)" if holding["weight"] > 40 else "。"))
        if lv:
            gap = (lv["Close"] / lv["MA60"] - 1) * 100
            out.append(f"- 目前股價距離 60 日線 {gap:+.1f}%。")

    out.append("\n> 以上為依公開資料自動整理的參考,不是買賣建議,也不保證未來走勢。")
    return "\n".join(out)
