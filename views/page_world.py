import plotly.graph_objects as go
import streamlit as st

from core import ui
from core import market as mk

ui.page_title("國際情勢", "全球主要指數、匯率、商品與新聞標題(資料約每 5 分鐘更新)")

data = mk.get_world("3mo")
if not data:
    st.warning("暫時抓不到國際行情,請稍後再試。")
    st.stop()

tab_mkt, tab_news = st.tabs(["全球市場", "新聞標題"])

with tab_mkt:
    names = list(data)
    for i in range(0, len(names), 4):
        cols = st.columns(4)
        for col, n in zip(cols, names[i:i + 4]):
            s = data[n]
            chg = (s.iloc[-1] / s.iloc[-2] - 1) * 100
            col.metric(n, f"{s.iloc[-1]:,.2f}", f"{chg:+.2f}%", delta_color="inverse")

    st.markdown("##### 走勢比較(近 3 個月,起點 = 100)")
    pick = st.multiselect("選擇項目", names, default=[n for n in ("加權指數", "S&P 500", "那斯達克") if n in names])
    if pick:
        fig = go.Figure()
        for n in pick:
            s = data[n]
            fig.add_trace(go.Scatter(x=s.index, y=s / s.iloc[0] * 100, name=n, line=dict(width=1.8)))
        st.plotly_chart(ui.style_fig(fig, 380), use_container_width=True)

with tab_news:
    news = mk.get_news()
    if not news:
        st.info("暫時沒有新聞資料。")
    for n in news:
        link = f"[{n['title']}]({n['url']})" if n["url"] else n["title"]
        st.markdown(f"{link}  \n<span style='color:#9ca3af;font-size:.8rem'>{n['source']} · {n['time']}</span>", unsafe_allow_html=True)
    st.caption("僅顯示標題與連結,內容版權屬原發布單位。")
