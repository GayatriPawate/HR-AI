import streamlit as st


def require_auth():
    if not st.session_state.get("jwt"):
        st.error("Please log in to access this page.")
        st.stop()
    return st.session_state.get("role")


def require_role(*roles: str):
    role = require_auth()
    if role not in roles:
        st.error(f"Access denied. This page requires role: {list(roles)}")
        st.stop()
    return role
