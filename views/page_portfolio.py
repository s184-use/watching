import plotly.graph_objects as go
import streamlit as st

from core import auth, db, health, ui
from core import market as mk

auth.require_login()
ui.page_title("持股管理", "記錄你的持股,並用技術、籌碼、基本三面幫你評估持股健康度")

hold = db.list_holdings()

tab_over, tab_list, tab_edit, tab_watch = st.tabs(["總覽與健康度", "持股明細", "新增 / 編輯", "自選股"])

# ---------------------------------------------------------------- 總覽
with tab_over:
    if hold.empty:
        st.info("還沒有持股,到「新增 / 編輯」分頁加入第一檔吧。")
    else:
        key = tuple(hold[["symbol", "shares", "cost"]].itertuples(index=False, name=None))
        if st.session_state.get("_ph_key") != key or st.button("重新計算", help="資料每 30 分鐘自動更新一次"):
            bar = st.progress(0, text="分析中…")
            st.session_state["_ph"] = health.portfolio_health(hold[["symbol", "shares", "cost"]], bar)
            st.session_state["_ph_key"] = key
            bar.empty()
        ph = st.session_state["_ph"]
        t = ph["table"]

        value, cost = t["value"].sum(), t["cost_total"].sum()
        pnl = value - cost
        label, color = ui.grade(ph["overall"])
        c = st.columns(4)
        c[0].metric("總市值", f"{value:,.0f}")
        c[1].metric("總成本", f"{cost:,.0f}")
        c[2].metric("未實現損益", f"{pnl:,.0f}", f"{pnl / cost * 100:+.2f}%" if cost else None, delta_color="inverse")
        c[3].metric("持股健康度", f"{ph['overall'] if ph['overall'] is not None else '—'} 分")
        st.markdown(f"整體評等:<b style='color:{color}'>{label}</b>"
                    f"　個股加權 {ph['weighted']} 分 · 分散度 {ph['diversification']} 分", unsafe_allow_html=True)

        if ph["warnings"]:
            st.markdown("<div class='card'><b>需要留意</b><br>" + "<br>".join("• " + w for w in ph["warnings"]) + "</div>", unsafe_allow_html=True)

        left, right = st.columns(2)
        with left:
            fig = go.Figure(go.Pie(labels=t["name"], values=t["value"], hole=.55, textinfo="label+percent"))
            fig.update_layout(title="持股比重", showlegend=False)
            st.plotly_chart(ui.style_fig(fig, 340), use_container_width=True)
        with right:
            s = t.dropna(subset=["health"]).sort_values("health")
            fig = go.Figure(go.Bar(x=s["health"], y=s["name"], orientation="h",
                                   marker_color=[ui.grade(v)[1] for v in s["health"]], text=s["health"], textposition="outside"))
            fig.update_layout(title="各檔健康度", xaxis=dict(range=[0, 105]))
            st.plotly_chart(ui.style_fig(fig, 340), use_container_width=True)

        st.markdown("##### 個股三面分數")
        show = t[["symbol", "name", "industry", "weight", "pnl_pct", "health", "tech", "chip", "fund"]].rename(columns={
            "symbol": "代號", "name": "名稱", "industry": "產業", "weight": "比重%", "pnl_pct": "損益%",
            "health": "健康度", "tech": "技術", "chip": "籌碼", "fund": "基本"})
        st.dataframe(show.round(1), hide_index=True, use_container_width=True)

        with st.expander("查看每一檔的評分依據"):
            for r in t.itertuples():
                d = r.detail
                st.markdown(f"**{r.symbol} {r.name}**(健康度 {r.health if r.health is not None else '—'})")
                tone = {"bull": "偏多", "bear": "偏空", "neutral": "中性"}
                st.markdown("技術:" + "；".join(f"{tone[a]}-{b}" for a, b in d["tech_notes"][:6]))
                st.markdown("籌碼:" + "；".join(d["chip_notes"]))
                st.markdown("基本:" + "；".join(d["fund_notes"]))
                st.divider()
        with st.expander("健康度怎麼算?"):
            st.markdown(
                "- **個股健康度** = 技術面 40% + 籌碼面 30% + 基本面 30%(缺資料的面向會自動重新配權)\n"
                "- **技術面**:股價與 20/60 日線、均線排列、MACD、KD、RSI、近期漲跌與量能\n"
                "- **籌碼面**:近 5 日三大法人 / 外資 / 投信買賣超\n"
                "- **基本面**:本益比、淨利率、ROE、營收成長、負債權益比\n"
                "- **整體健康度** = 個股市值加權 70% + 分散度 30%(單一持股集中度、檔數、產業數)\n"
                "- 80+ 優良、65+ 良好、50+ 普通、50 以下需留意。這是量化參考,不是買賣訊號。")
        ui.disclaimer()

# ---------------------------------------------------------------- 明細
with tab_list:
    if hold.empty:
        st.caption("尚無持股。")
    else:
        d = hold[["symbol", "shares", "cost", "note"]].copy()
        d.insert(1, "名稱", [mk.stock_name(s) for s in d["symbol"]])
        d.columns = ["代號", "名稱", "股數", "平均成本", "備註"]
        st.dataframe(d, hide_index=True, use_container_width=True)
        st.caption("股數單位為「股」(1 張 = 1,000 股),成本為每股平均成本。")

# ---------------------------------------------------------------- 新增/編輯
with tab_edit:
    st.markdown("##### 新增持股")
    with st.form("add_hold", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        code = c1.text_input("股票代號", placeholder="2330")
        shares = c2.number_input("股數(股)", min_value=1, value=1000, step=100)
        cost = c3.number_input("每股平均成本", min_value=0.0, value=0.0, step=0.5, format="%.2f")
        note = st.text_input("備註(選填)")
        if st.form_submit_button("新增", type="primary"):
            code = mk.clean_code(code)
            if not mk.resolve_symbol(code):
                st.error(f"找不到代號「{code}」")
            elif cost <= 0:
                st.error("請輸入成本")
            else:
                db.add_holding(code, shares, cost, note)
                st.rerun()

    if not hold.empty:
        st.markdown("##### 修改 / 刪除")
        labels = {int(r.id): f"{r.symbol} {mk.stock_name(r.symbol)}" for r in hold.itertuples()}
        hid = st.selectbox("選擇持股", list(labels), format_func=labels.get)
        r = hold[hold["id"] == hid].iloc[0]
        with st.form("edit_hold"):
            c1, c2 = st.columns(2)
            ns = c1.number_input("股數(股)", min_value=1, value=int(r.shares), step=100)
            nc = c2.number_input("每股平均成本", min_value=0.01, value=float(r.cost), step=0.5, format="%.2f")
            nn = st.text_input("備註", value=r.note or "")
            b1, b2 = st.columns(2)
            if b1.form_submit_button("儲存修改", type="primary"):
                db.update_holding(int(hid), ns, nc, nn)
                st.rerun()
            if b2.form_submit_button("刪除這檔"):
                db.delete_holding(int(hid))
                st.rerun()

# ---------------------------------------------------------------- 自選股
with tab_watch:
    wl = db.list_watchlist()
    c1, c2 = st.columns([3, 1])
    new = c1.text_input("加入自選股", placeholder="輸入代號,例如 2454", label_visibility="collapsed")
    if c2.button("加入") and new:
        code = mk.clean_code(new)
        if mk.resolve_symbol(code):
            db.add_watch(code)
            st.rerun()
        else:
            st.error("找不到這個代號")
    if not wl:
        st.caption("還沒有自選股。")
    for s in wl:
        h = mk.get_history(s, "5d")
        a, b, c, d = st.columns([2, 2, 2, 1])
        a.markdown(f"**{s}** {mk.stock_name(s)}")
        if len(h) >= 2:
            chg = (h.Close.iloc[-1] / h.Close.iloc[-2] - 1) * 100
            b.write(ui.num(h.Close.iloc[-1]))
            c.markdown(f"<span style='color:{ui.UP if chg >= 0 else ui.DOWN}'>{chg:+.2f}%</span>", unsafe_allow_html=True)
        if d.button("移除", key=f"rm_{s}"):
            db.remove_watch(s)
            st.rerun()
