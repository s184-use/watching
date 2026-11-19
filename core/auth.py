"""簡化登入:帳號 + 密碼 +(註冊時)邀請碼。
帳號會在背後轉成一個假 email 交給 Supabase,所以不需要真的信箱、也不用收驗證信。
(需要在 Supabase 關閉 Confirm email。)忘記密碼無法自助重設。"""
import re

import streamlit as st
from supabase import create_client

from core.config import secret

_NAME = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def configured() -> bool:
    return bool(secret("SUPABASE_URL") and secret("SUPABASE_ANON_KEY"))


def sb():
    if "sb" not in st.session_state:
        st.session_state["sb"] = create_client(secret("SUPABASE_URL"), secret("SUPABASE_ANON_KEY"))
    return st.session_state["sb"]


def _email(username: str) -> str:
    return f"{username.lower()}@users.example.com"


def current_user():
    return st.session_state.get("user")


def sign_in(username: str, password: str) -> str | None:
    """成功回傳 None,失敗回傳錯誤訊息。"""
    username = username.strip()
    if not _NAME.match(username):
        return "帳號格式不正確"
    try:
        res = sb().auth.sign_in_with_password({"email": _email(username), "password": password})
        st.session_state["user"] = {"id": res.user.id, "email": username}
        return None
    except Exception as e:
        msg = str(e)
        if "not confirmed" in msg.lower():
            return "此帳號尚未啟用:請管理者到 Supabase 關閉 Confirm email 後重新註冊"
        return "帳號或密碼錯誤" if "Invalid login" in msg else f"登入失敗:{msg}"


def sign_up(username: str, password: str, invite: str) -> tuple[bool, str]:
    username = username.strip()
    code = secret("INVITE_CODE")
    if code and invite.strip() != code:
        return False, "邀請碼不正確"
    if not _NAME.match(username):
        return False, "帳號需為 3–20 碼的英文、數字或底線"
    if len(password) < 6:
        return False, "密碼至少 6 碼"
    try:
        res = sb().auth.sign_up({"email": _email(username), "password": password})
        if res.session:
            st.session_state["user"] = {"id": res.user.id, "email": username}
            return True, "註冊成功,已自動登入"
        return False, "註冊後需要驗證:請管理者到 Supabase 關閉「Confirm email」(見 README)"
    except Exception as e:
        return False, "這個帳號已經被使用" if "already" in str(e).lower() else f"註冊失敗:{e}"


def sign_out() -> None:
    try:
        sb().auth.sign_out()
    except Exception:
        pass
    for k in ("user", "sb", "my_symbols"):
        st.session_state.pop(k, None)


def require_login() -> dict:
    u = current_user()
    if u:
        return u
    st.info("🔒 這個功能需要登入。看盤、國際情勢、配息日程、個股分析不用登入;持股管理請先到「帳號」頁註冊 / 登入。")
    st.stop()
