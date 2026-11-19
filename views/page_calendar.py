import datetime as dt

import pandas as pd
import streamlit as st

from core import auth, db, ui
from core import market as mk

ui.page_title("配息日程", "除權息日與股利發放日(資料來自公開資料庫,實際以公司公告為準)")
today = ui.today_tw()

user = auth.current_user()
mine = db.my_symbols() if user else []
default = ", ".join(mine) if mine else st.session_state.get("symbol", "2330")
codes_text = st.text_input("追蹤的股票代號(逗號分隔)", value=default, help="登入後預設帶入你的持股與自選股")
codes = [mk.clean_code(c) for c in codes_text.replace("、", ",").split(",") if c.strip()][:15]


def countdown(d: dt.date) -> str:
    n = (d - today).days
    return "今天" if n == 0 else f"{n} 天後" if n > 0 else f"{-n} 天前"


events = []
for c in codes:
    ev = mk.get_dividend_events(c)
    if not ev.empty:
        ev["name"] = mk.stock_name(c)
        events.append(ev)

if not events:
    st.info("查無這些股票的配息資料(ETF 或資料源忙碌時可能沒有)。")
    st.stop()

d = pd.concat(events).rename(columns={"symbol": "代號", "name": "名稱", "kind": "類型", "date": "日期", "detail": "內容"})
d["倒數"] = d["日期"].map(countdown)
up = d[d["日期"] >= today].sort_values("日期")
past = d[d["日期"] < today].sort_values("日期", ascending=False)

st.metric("未來配息事件", f"{len(up)} 筆")
tab_up, tab_past = st.tabs(["即將到來", "過去紀錄"])
with tab_up:
    if up.empty:
        st.caption("目前沒有已公告、尚未到來的配息事件。")
    else:
        st.dataframe(up[["日期", "倒數", "代號", "名稱", "類型", "內容"]], hide_index=True, use_container_width=True)
with tab_past:
    st.dataframe(past[["日期", "代號", "名稱", "類型", "內容"]].head(50), hide_index=True, use_container_width=True)
st.caption("除息日當天(含)以後買進,不能領該次股息;發放日為股息入帳日。")
