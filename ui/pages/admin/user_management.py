import streamlit as st
import pandas as pd
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post
from ui.api_client import _headers
import requests

API_BASE = "http://localhost:8000"


def _patch(path: str) -> bool:
    try:
        resp = requests.patch(f"{API_BASE}{path}", headers=_headers(), timeout=15)
        return resp.status_code == 200
    except Exception:
        return False


def render(user: dict):
    require_role("admin")
    st.title("👥 User & Role Management")

    tab_all, tab_panel, tab_add = st.tabs(["All Users", "Panel Members", "Add User"])

    # ── All Users ─────────────────────────────────────────────────
    with tab_all:
        users = api_get("/users/list") or []
        if not users:
            st.info("No users found.")
        else:
            rows = []
            for u in users:
                role = u.get("role", "—")
                rows.append({
                    "Name": u.get("full_name"),
                    "Email": u.get("email"),
                    "Role": "🔑 Admin" if role == "admin" else "👥 Panel",
                    "Department": u.get("department") or "—",
                    "Active": "✅" if u.get("is_active") else "❌",
                    "Created": (u.get("created_at") or "")[:10],
                    "_id": u.get("id"),
                    "_active": u.get("is_active"),
                })

            df = pd.DataFrame(rows).drop(columns=["_id", "_active"])
            st.dataframe(df, use_container_width=True)

            # Activate / deactivate
            st.divider()
            st.subheader("Activate / Deactivate User")
            user_opts = {
                f"{r['Name']} ({r['Email']})": rows[i]
                for i, r in enumerate(rows)
                if rows[i]["_id"] != user["user_id"]   # can't deactivate yourself
            }
            if user_opts:
                selected_label = st.selectbox("Select User", list(user_opts.keys()))
                selected = user_opts[selected_label]
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅ Activate", use_container_width=True,
                                 disabled=selected["_active"]):
                        if _patch(f"/users/{selected['_id']}/activate"):
                            st.success(f"Activated {selected['Name']}")
                            st.rerun()
                with col_b:
                    if st.button("❌ Deactivate", use_container_width=True,
                                 disabled=not selected["_active"]):
                        if _patch(f"/users/{selected['_id']}/deactivate"):
                            st.warning(f"Deactivated {selected['Name']}")
                            st.rerun()

    # ── Panel Members ─────────────────────────────────────────────
    with tab_panel:
        panel = api_get("/users/panel-members") or []
        if not panel:
            st.info("No panel members found. Add users with 'panel' role from the Add User tab.")
        else:
            st.caption(f"{len(panel)} active panel member(s)")
            cols = st.columns(3)
            for i, p in enumerate(panel):
                with cols[i % 3]:
                    st.markdown(
                        f"""
                        <div style="
                            border:1px solid #e0e0e0;
                            border-radius:10px;
                            padding:16px;
                            margin-bottom:12px;
                            background:#f9f9fb;
                        ">
                            <h4 style="margin:0 0 6px 0;">👤 {p['full_name']}</h4>
                            <p style="margin:2px 0;font-size:0.85em;color:#555;">📧 {p['email']}</p>
                            <p style="margin:2px 0;font-size:0.85em;color:#555;">🏢 {p.get('department') or '—'}</p>
                            <p style="margin:2px 0;font-size:0.82em;color:#888;">
                                MS: {p.get('ms_email') or '<i>not set</i>'}
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # ── Add User ──────────────────────────────────────────────────
    with tab_add:
        st.subheader("Create New User")

        full_name = st.text_input("Full Name *")
        email = st.text_input("Email *")
        password = st.text_input("Password *", type="password")
        role = st.selectbox("Role *", ["panel", "admin"],
                            format_func=lambda r: "👥 Panel Member" if r == "panel" else "🔑 Admin")
        department = st.text_input("Department (optional)")
        ms_email = st.text_input(
            "Microsoft / Outlook Email (optional)",
            help="Used for interview scheduling via MS Graph",
        )

        st.write("")
        if st.button("Create User", type="primary", use_container_width=True):
            if not all([full_name.strip(), email.strip(), password.strip()]):
                st.warning("Full Name, Email, and Password are required.")
            else:
                result = api_post("/auth/register", json={
                    "email": email.strip(),
                    "password": password,
                    "full_name": full_name.strip(),
                    "role": role,
                    "department": department.strip() or None,
                    "ms_email": ms_email.strip() or None,
                })
                if result:
                    st.success(
                        f"✅ User created: **{result.get('email')}** "
                        f"({'Panel Member' if role == 'panel' else 'Admin'})"
                    )
                    st.rerun()
