"""雲端資料存取(Supabase Postgres + Row Level Security,每人只能讀寫自己的資料)。
資料都在雲端,所以學校電腦重灌、換電腦都不會遺失。"""
import pandas as pd
import streamlit as st

from core import auth


def _uid() -> str:
    return auth.current_user()["id"]


def _t(name: str):
    return auth.sb().table(name)


def invalidate() -> None:
    st.session_state.pop("my_symbols", None)


# ---------------------------------------------------------------- 持股
def list_holdings() -> pd.DataFrame:
    rows = _t("holdings").select("*").order("created_at").execute().data
    return pd.DataFrame(rows, columns=["id", "user_id", "symbol", "shares", "cost", "note", "created_at"])


def add_holding(symbol: str, shares: float, cost: float, note: str = "") -> None:
    _t("holdings").insert({"user_id": _uid(), "symbol": symbol, "shares": shares, "cost": cost, "note": note}).execute()
    invalidate()


def update_holding(hid: int, shares: float, cost: float, note: str) -> None:
    _t("holdings").update({"shares": shares, "cost": cost, "note": note}).eq("id", hid).execute()


def delete_holding(hid: int) -> None:
    _t("holdings").delete().eq("id", hid).execute()
    invalidate()


# ---------------------------------------------------------------- 自選股
def list_watchlist() -> list[str]:
    return [r["symbol"] for r in _t("watchlist").select("symbol").order("created_at").execute().data]


def add_watch(symbol: str) -> None:
    _t("watchlist").upsert({"user_id": _uid(), "symbol": symbol}, on_conflict="user_id,symbol").execute()
    invalidate()


def remove_watch(symbol: str) -> None:
    _t("watchlist").delete().eq("symbol", symbol).execute()
    invalidate()


def my_symbols() -> list[str]:
    """持股 + 自選(快速選擇用),快取在 session。"""
    if not auth.current_user():
        return []
    if "my_symbols" not in st.session_state:
        try:
            syms = list(dict.fromkeys(list_holdings()["symbol"].tolist() + list_watchlist()))
        except Exception:
            syms = []
        st.session_state["my_symbols"] = syms
    return st.session_state["my_symbols"]
