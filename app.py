import streamlit as st

from core import auth, db, ui

st.set_page_config(page_title="台股看盤與持股分析", page_icon="📈", layout="wide")
ui.inject_css()

pages = {
    "看盤": [
        st.Page("views/page_market.py", title="個股看盤", icon="📈", default=True),
        st.Page("views/page_world.py", title="國際情勢", icon="🌏"),
        st.Page("views/page_analysis.py", title="個股分析", icon="🔍"),
        st.Page("views/page_calendar.py", title="配息日程", icon="🗓️"),
    ],
    "我的": [
        st.Page("views/page_portfolio.py", title="持股管理", icon="💼"),
        st.Page("views/page_account.py", title="帳號", icon="👤"),
    ],
}

# ---- 側邊欄:全站共用的股票代號 ----
st.session_state.setdefault("symbol", "2330")


def _pick():
    v = st.session_state.get("_pick")
    if v and v != "—":
        st.session_state["symbol"] = v


with st.sidebar:
    st.markdown("### 📈 台股看盤")
    st.text_input("股票代號", key="symbol", help="輸入代號,例如 2330、0050、6488(上櫃)")
    options = list(dict.fromkeys(db.my_symbols() + st.session_state.get("recent", [])))
    if options:
        st.selectbox("快速選擇(持股/自選/最近查詢)", ["—"] + options, key="_pick", on_change=_pick)
    st.divider()
    u = auth.current_user()
    if u:
        st.caption(f"👤 {u['email']}")
    else:
        st.caption("訪客模式:可看盤與查個股分析。登入後可用持股管理。")
    ui.disclaimer()

st.navigation(pages).run()
