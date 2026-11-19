import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import market as mk
from core import ui
from core.indicators import add_indicators, cross, tech_summary

code = mk.clean_code(st.session_state.get("symbol") or "2330")
sym = mk.resolve_symbol(code)
if not sym:
    st.error(f"找不到代號「{code}」,請確認是上市(TWSE)或上櫃(TPEx)股票代號。")
    st.stop()
ui.remember_symbol(code)

name = mk.stock_name(code)
daily = mk.get_history(code, "5y")
if daily.empty:
    st.warning("暫時抓不到價量資料,請稍後再試。")
    st.stop()

# ---------------------------------------------------------------- 標頭
last, prev = daily.iloc[-1], daily.iloc[-2]
chg = last.Close - prev.Close
st.markdown(f"### {name} <span style='color:#9ca3af;font-size:1rem'>{code} · {'上櫃' if sym.endswith('.TWO') else '上市'} · {mk.stock_industry(code)}</span>", unsafe_allow_html=True)
c = st.columns(5)
c[0].metric("最新收盤", ui.num(last.Close), f"{chg:+.2f} ({chg / prev.Close * 100:+.2f}%)", delta_color="inverse")
c[1].metric("開盤", ui.num(last.Open))
c[2].metric("最高", ui.num(last.High))
c[3].metric("最低", ui.num(last.Low))
c[4].metric("成交量(張)", f"{last.Volume / 1000:,.0f}")
st.caption(f"資料日期 {daily.index[-1].date()}(歷史資料來源 Yahoo,盤中約延遲 15–20 分鐘;即時五檔請看「五檔報價」)")

tab_chart, tab_five, tab_chip, tab_basic = st.tabs(["走勢圖", "五檔報價", "籌碼", "基本資料"])


# ---------------------------------------------------------------- 走勢圖
def resample(df, rule):
    return df.resample(rule).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()


def build_chart(d, overlays, sub, show_signals, daily_like):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.58, 0.14, 0.28])
    fig.add_trace(go.Candlestick(
        x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close, name="K線",
        increasing_line_color=ui.UP, increasing_fillcolor=ui.UP,
        decreasing_line_color=ui.DOWN, decreasing_fillcolor=ui.DOWN), row=1, col=1)

    colors = {"MA5": "#f59e0b", "MA20": "#3b82f6", "MA60": "#8b5cf6"}
    for k in ("MA5", "MA20", "MA60"):
        if k in overlays:
            fig.add_trace(go.Scatter(x=d.index, y=d[k], name=k, line=dict(width=1.3, color=colors[k])), row=1, col=1)
    if "布林通道" in overlays:
        for k in ("BB_up", "BB_lo"):
            fig.add_trace(go.Scatter(x=d.index, y=d[k], name="布林" + ("上軌" if k == "BB_up" else "下軌"),
                                     line=dict(width=1, dash="dot", color="#9ca3af")), row=1, col=1)

    if show_signals:
        u, dn = cross(d["MA5"], d["MA20"])
        fig.add_trace(go.Scatter(x=d.index[u], y=d.Low[u] * 0.985, mode="markers", name="黃金交叉",
                                 marker=dict(symbol="triangle-up", size=11, color=ui.UP)), row=1, col=1)
        fig.add_trace(go.Scatter(x=d.index[dn], y=d.High[dn] * 1.015, mode="markers", name="死亡交叉",
                                 marker=dict(symbol="triangle-down", size=11, color=ui.DOWN)), row=1, col=1)

    vol_colors = [ui.UP if c >= o else ui.DOWN for o, c in zip(d.Open, d.Close)]
    fig.add_trace(go.Bar(x=d.index, y=d.Volume / 1000, marker_color=vol_colors, name="成交量(張)", showlegend=False), row=2, col=1)

    if sub == "MACD":
        fig.add_trace(go.Bar(x=d.index, y=d.MACD_hist, name="柱狀體",
                             marker_color=[ui.UP if v >= 0 else ui.DOWN for v in d.MACD_hist]), row=3, col=1)
        fig.add_trace(go.Scatter(x=d.index, y=d.MACD, name="MACD", line=dict(width=1.2, color="#3b82f6")), row=3, col=1)
        fig.add_trace(go.Scatter(x=d.index, y=d.MACD_signal, name="訊號線", line=dict(width=1.2, color="#f59e0b")), row=3, col=1)
    elif sub == "KD":
        fig.add_trace(go.Scatter(x=d.index, y=d.K, name="K", line=dict(width=1.2, color="#f59e0b")), row=3, col=1)
        fig.add_trace(go.Scatter(x=d.index, y=d.D, name="D", line=dict(width=1.2, color="#3b82f6")), row=3, col=1)
        fig.add_hline(y=80, line_dash="dot", line_color="#d1d5db", row=3, col=1)
        fig.add_hline(y=20, line_dash="dot", line_color="#d1d5db", row=3, col=1)
    else:
        fig.add_trace(go.Scatter(x=d.index, y=d.RSI, name="RSI", line=dict(width=1.3, color="#8b5cf6")), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#d1d5db", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#d1d5db", row=3, col=1)

    ui.style_fig(fig, 640)
    fig.update_xaxes(rangeslider_visible=False)
    if daily_like == "day":
        missing = pd.date_range(d.index[0], d.index[-1]).difference(d.index)
        fig.update_xaxes(rangebreaks=[dict(values=missing)])
    elif daily_like == "intraday":
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[13.5, 9], pattern="hour")])
    return fig


with tab_chart:
    a, b, c2, d2 = st.columns([1.3, 1.3, 2.2, 1.2])
    frame = a.segmented_control("週期", ["日K", "週K", "月K", "5分K"], default="日K", key="frame") or "日K"
    span_days = {"1個月": 30, "3個月": 90, "6個月": 180, "1年": 365, "2年": 730, "5年": 1825}
    span = b.selectbox("區間", list(span_days), index=2, disabled=(frame == "5分K"))
    overlays = c2.multiselect("疊加", ["MA5", "MA20", "MA60", "布林通道"], default=["MA5", "MA20", "MA60"])
    sub = d2.selectbox("副圖指標", ["MACD", "KD", "RSI"])
    show_sig = st.checkbox("標示 5 日線 / 20 日線交叉訊號", value=True)

    if frame == "5分K":
        raw = mk.get_history(code, "5d", "5m")
        kind = "intraday"
    else:
        raw = daily if frame == "日K" else resample(daily, "W-FRI" if frame == "週K" else "MS")
        kind = "day" if frame == "日K" else "other"

    if raw.empty:
        st.info("目前沒有這個週期的資料。")
    else:
        full = add_indicators(raw)
        view = full if frame == "5分K" else full[full.index >= full.index[-1] - pd.Timedelta(days=span_days[span])]
        st.plotly_chart(build_chart(view, overlays, sub, show_sig, kind), use_container_width=True)

    ts = tech_summary(add_indicators(daily))
    st.markdown("#### 智慧訊號(日線)")
    if ts["score"] is not None:
        label, color = ui.grade(ts["score"])
        st.markdown(f"技術面分數 **{ts['score']} / 100** <span style='color:{color}'>({label})</span>", unsafe_allow_html=True)
    tone_name = {"bull": "偏多", "bear": "偏空", "neutral": "中性"}
    html = "".join(f"<div><span class='tag {t}'>{tone_name[t]}</span>{txt}</div>" for t, txt in ts["notes"])
    st.markdown(f"<div class='card'>{html}</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- 五檔
@st.fragment(run_every=5 if ui.is_trading_time() else None)
def five_panel(code: str):
    q = mk.get_five_levels(code)
    if q.get("error"):
        st.warning(q["error"])
        return
    prev = q["prev"]

    def color(p):
        if p is None or prev is None or p == prev:
            return "#374151"
        return ui.UP if p > prev else ui.DOWN

    last_p = q["last"]
    c = st.columns(5)
    if last_p is not None and prev:
        d = last_p - prev
        c[0].metric("成交價", ui.num(last_p), f"{d:+.2f} ({d / prev * 100:+.2f}%)", delta_color="inverse")
    else:
        c[0].metric("成交價", ui.num(last_p))
    c[1].metric("開 / 昨收", f"{ui.num(q['open'])} / {ui.num(prev)}")
    c[2].metric("最高 / 最低", f"{ui.num(q['high'])} / {ui.num(q['low'])}")
    c[3].metric("累積成交量(張)", ui.num(q["volume"], 0))
    c[4].metric("漲停 / 跌停", f"{ui.num(q['limit_up'])} / {ui.num(q['limit_down'])}")

    asks, bids = q["asks"], q["bids"]
    maxv = max([v or 0 for _, v in asks + bids] + [1])

    def row(label, p, v, bar_color):
        w = (v or 0) / maxv * 100
        return (f"<tr><td>{label}</td><td style='color:{color(p)}'>{ui.num(p)}</td><td>{ui.num(v, 0)}</td>"
                f"<td class='barcell'><span class='bar' style='width:{w:.0f}%;background:{bar_color}'></span></td></tr>")

    body = "".join(row(f"賣{i}", p, v, "#bfe3d1") for i, (p, v) in reversed(list(enumerate(asks, 1))))
    body += f"<tr class='last'><td>成交</td><td style='color:{color(last_p)}'>{ui.num(last_p)}</td><td colspan='2'></td></tr>"
    body += "".join(row(f"買{i}", p, v, "#f6c9cb") for i, (p, v) in enumerate(bids, 1))
    st.markdown(f"<table class='lv'><tr><th>檔位</th><th>價格</th><th>張數</th><th></th></tr>{body}</table>", unsafe_allow_html=True)

    bt, at = sum(v or 0 for _, v in bids), sum(v or 0 for _, v in asks)
    if bt + at:
        st.progress(bt / (bt + at), text=f"委買 {bt:,.0f} 張 vs 委賣 {at:,.0f} 張(買方占 {bt / (bt + at) * 100:.0f}%)")
    stamp = f"{q.get('date', '')} {q.get('time', '')}".strip()
    st.caption(f"{stamp} · 來源:臺灣證券交易所 MIS" + ("" if ui.is_trading_time() else " · 目前非交易時段,顯示最後一筆資料"))


with tab_five:
    five_panel(code)

# ---------------------------------------------------------------- 籌碼
with tab_chip:
    inst = mk.get_institutional(code, 60)
    if inst.empty:
        st.info("暫時沒有法人籌碼資料(可能是 ETF、或資料源忙碌)。")
    else:
        t5, t20 = inst.tail(5).sum(), inst.tail(20).sum()
        c = st.columns(4)
        for col, key in zip(c, ["三大法人", "外資", "投信", "自營商"]):
            col.metric(f"{key}(近5日 / 近20日)", f"{t5[key]:,.0f} / {t20[key]:,.0f} 張")
        v = inst.tail(30)
        fig = go.Figure()
        for key, colr in (("外資", "#3b82f6"), ("投信", "#f59e0b"), ("自營商", "#8b5cf6")):
            fig.add_trace(go.Bar(x=v.index, y=v[key], name=key, marker_color=colr))
        fig.update_layout(barmode="relative", title="三大法人買賣超(張,近 30 日)")
        st.plotly_chart(ui.style_fig(fig, 340), use_container_width=True)

    mg = mk.get_margin(code, 60)
    if not mg.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=mg.index, y=mg["融資餘額"], name="融資餘額(張)", line=dict(color=ui.UP)))
        fig.add_trace(go.Scatter(x=mg.index, y=mg["融券餘額"], name="融券餘額(張)", line=dict(color=ui.DOWN), yaxis="y2"))
        fig.update_layout(title="融資 / 融券餘額", yaxis2=dict(overlaying="y", side="right", showgrid=False))
        st.plotly_chart(ui.style_fig(fig, 300), use_container_width=True)
    if not inst.empty:
        with st.expander("查看明細表"):
            st.dataframe(inst.tail(20).sort_index(ascending=False).round(0), use_container_width=True)

# ---------------------------------------------------------------- 基本資料
with tab_basic:
    info = mk.get_info(code)
    left, right = st.columns(2)
    with left:
        st.markdown("##### 公司")
        st.markdown(
            f"- 名稱:{info.get('longName') or name}\n- 產業:{mk.stock_industry(code)}\n"
            f"- 員工數:{ui.num(info.get('fullTimeEmployees'), 0)}\n- 網站:{info.get('website') or '—'}\n"
            f"- 市值:{ui.big(info.get('marketCap'))}"
        )
        st.markdown("##### 估值")
        dy = info.get("dividendYield")
        dy = dy if dy is None or dy > 1 else dy * 100  # yfinance 版本間單位不一致
        st.markdown(
            f"- 本益比:{ui.num(info.get('trailingPE'))}\n- 股價淨值比:{ui.num(info.get('priceToBook'))}\n"
            f"- EPS(近四季):{ui.num(info.get('trailingEps'))}\n- 殖利率:{ui.num(dy)}%\n"
            f"- 52 週區間:{ui.num(info.get('fiftyTwoWeekLow'))} ~ {ui.num(info.get('fiftyTwoWeekHigh'))}\n"
            f"- Beta:{ui.num(info.get('beta'))}"
        )
    with right:
        st.markdown("##### 獲利能力")
        pctf = lambda k: ui.num((info.get(k) or 0) * 100, 1, "%") if info.get(k) is not None else "—"
        st.markdown(
            f"- 毛利率:{pctf('grossMargins')}\n- 營業利益率:{pctf('operatingMargins')}\n"
            f"- 淨利率:{pctf('profitMargins')}\n- ROE:{pctf('returnOnEquity')}\n- ROA:{pctf('returnOnAssets')}"
        )
    rev = mk.get_month_revenue(code)
    if not rev.empty:
        r = rev.tail(24)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=r["期間"], y=r["營收(億)"], name="月營收(億)", marker_color="#93c5fd"), secondary_y=False)
        fig.add_trace(go.Scatter(x=r["期間"], y=r["年增率%"], name="年增率%", line=dict(color=ui.UP)), secondary_y=True)
        fig.update_layout(title="月營收與年增率")
        st.plotly_chart(ui.style_fig(fig, 320), use_container_width=True)
    eps = mk.get_eps(code)
    if not eps.empty:
        e = eps.tail(8)
        fig = go.Figure(go.Bar(x=e["季底"], y=e["EPS"], marker_color="#a5b4fc"))
        fig.update_layout(title="單季 EPS(元)")
        st.plotly_chart(ui.style_fig(fig, 280), use_container_width=True)
    if rev.empty and eps.empty:
        st.caption("暫時沒有營收 / EPS 資料(ETF 通常沒有這類資料)。")
