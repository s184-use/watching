"""讀取 secrets(雲端用 Streamlit Secrets,本機用 .streamlit/secrets.toml)。"""
import streamlit as st


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default
