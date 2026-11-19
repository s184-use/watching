import streamlit as st

from core import auth, ui

ui.page_title("帳號", "註冊後可使用持股管理;資料存在雲端,換電腦也能看到")

if not auth.configured():
    st.warning("尚未設定資料庫(SUPABASE_URL / SUPABASE_ANON_KEY),登入功能暫時無法使用。設定方式請見 README。")
    st.stop()

user = auth.current_user()
if user:
    st.success(f"已登入:{user['email']}")
    if st.button("登出"):
        auth.sign_out()
        st.rerun()
    st.caption("提醒:重新整理網頁後需要重新登入,但你的資料不會消失。")
else:
    t_in, t_up = st.tabs(["登入", "註冊"])
    with t_in:
        with st.form("login"):
            name = st.text_input("帳號")
            pw = st.text_input("密碼", type="password")
            if st.form_submit_button("登入", type="primary"):
                err = auth.sign_in(name, pw)
                if err:
                    st.error(err)
                else:
                    st.rerun()
    with t_up:
        with st.form("signup"):
            name = st.text_input("帳號(3–20 碼英文、數字、底線)", key="su_name")
            pw = st.text_input("密碼(至少 6 碼)", type="password", key="su_pw")
            invite = st.text_input("邀請碼(向管理者索取)", key="su_invite")
            st.caption("不需要 email;請記住密碼,忘記時無法自行重設,要請管理者處理。")
            if st.form_submit_button("註冊"):
                ok, msg = auth.sign_up(name, pw, invite)
                (st.success if ok else st.error)(msg)
                if ok and auth.current_user():
                    st.rerun()
