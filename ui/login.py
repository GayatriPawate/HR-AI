import streamlit as st
from ui.api_client import login as api_login


def render():
    # ── Page header ───────────────────────────────────────────────
    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.25rem;'>👥 HR Hiring Platform</h2>"
        "<p style='text-align:center; color:gray; margin-top:0;'>Sign in to your workspace</p>",
        unsafe_allow_html=True,
    )
    st.write("")

    _, col, _ = st.columns([1, 1.6, 1])

    with col:
        tab_admin, tab_panel = st.tabs(["🔑 Admin / HR Login", "👥 Panel Login"])

        # ── Admin tab ─────────────────────────────────────────────
        with tab_admin:
            st.caption("For HR managers and administrators")
            st.write("")

            admin_email = st.text_input(
                "Email",
                placeholder="admin@hrplatform.com",
                key="admin_email_input",
            )
            admin_password = st.text_input(
                "Password",
                type="password",
                key="admin_password_input",
            )
            st.write("")

            if st.button("Sign In as Admin", use_container_width=True, key="admin_btn"):
                _do_login(admin_email, admin_password, expected_roles=("admin", "hr"))

        # ── Panel tab ─────────────────────────────────────────────
        with tab_panel:
            st.caption("For interview panel members")
            st.write("")

            panel_email = st.text_input(
                "Email",
                placeholder="panel@hrplatform.com",
                key="panel_email_input",
            )
            panel_password = st.text_input(
                "Password",
                type="password",
                key="panel_password_input",
            )
            st.write("")

            if st.button("Sign In as Panel Member", use_container_width=True, key="panel_btn"):
                _do_login(panel_email, panel_password, expected_roles=("panel",))


def _do_login(email: str, password: str, expected_roles: tuple):
    if not email or not password:
        st.warning("Please enter both email and password.")
        return

    with st.spinner("Authenticating…"):
        try:
            result = api_login(email.strip(), password)
        except ConnectionError as e:
            st.error(f"🔌 {e}")
            return
        except TimeoutError as e:
            st.warning(f"⏳ {e}")
            return

    if result is None:
        st.error("Invalid email or password. Please try again.")
        return

    if result.get("role") not in expected_roles:
        role_label = "Admin / HR" if "admin" in expected_roles else "Panel"
        st.error(f"This account does not have {role_label} access. Use the correct tab.")
        return

    st.session_state["jwt"] = result["token"]
    st.session_state["role"] = result["role"]
    st.session_state["user_id"] = result["user_id"]
    st.session_state["name"] = result["name"]
    st.success(f"Welcome, {result['name']}!")
    st.rerun()
