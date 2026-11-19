import streamlit as st

from core import analysis, auth, db, ui
from core import market as mk

ui.page_title("個股分析", "用技術、籌碼、基本三面整理資料現況(僅供參考)")

user = auth.current_user()
mine = db.my_symbols() if user else []
opts = list(dict.fromkeys([mk.clean_code(st.session_state.get("symbol", "2330"))] + mine))
c1, c2 = st.columns([2, 3])
pick = c1.selectbox("選擇股票", opts + ["自行輸入…"])
code = mk.clean_code(c2.text_input("輸入代號") if pick == "自行輸入…" else pick)

if st.button("產生分析", type="primary", disabled=not code):
    if not mk.resolve_symbol(code):
        st.error(f"找不到代號「{code}」")
        st.stop()
    holding = None
    if user:
        h = db.list_holdings()
        row = h[h["symbol"] == code]
        if not row.empty:
            r = row.iloc[0]
            vals = []
            for x in h.itertuples():
                hx = mk.get_history(x.symbol, "5d")
                vals.append(x.shares * (float(hx["Close"].iloc[-1]) if not hx.empty else x.cost))
            hx = mk.get_history(code, "5d")
            price = float(hx["Close"].iloc[-1]) if not hx.empty else None
            mv = r.shares * price if price else None
            holding = {"shares": r.shares, "cost": r.cost,
                       "pnl_pct": (price / r.cost - 1) * 100 if price else None,
                       "weight": mv / sum(vals) * 100 if mv and sum(vals) else None}
    with st.spinner("整理資料中…"):
        st.markdown(analysis.build_report(code, holding))
else:
    st.caption("選好股票後按「產生分析」。登入並記錄持股後,分析會多一段針對你成本與比重的說明。")
ui.disclaimer()
