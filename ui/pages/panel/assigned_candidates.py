import streamlit as st
import pandas as pd
from ui.components.auth_guard import require_role
from ui.api_client import api_get


def render(user: dict):
    require_role("panel")
    st.title("My Assigned Candidates")
    st.caption(f"Logged in as: **{user['name']}** (Panel)")

    assigned = api_get("/interviews/assigned") or []

    if not assigned:
        st.info("No candidates assigned to you yet. Contact your HR admin.")
        return

    st.success(f"{len(assigned)} candidate(s) assigned to you")

    for c in assigned:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.subheader(c.get("candidate_name", "Unknown"))
                st.write(f"**Role:** {c.get('latest_role', '—')}")
                st.write(f"**Experience:** {c.get('total_experience_yrs', 0)} years")
            with col2:
                st.write(f"**JD:** {c.get('jd_title', '—')}")
                st.write(f"**Stage:** {c.get('stage', '—')}")
                st.write(f"**Assigned:** {c.get('assigned_at', '—')[:10]}")
            with col3:
                if st.button("View", key=f"view_{c['candidate_id']}"):
                    st.session_state["panel_candidate_id"] = c["candidate_id"]
                    st.session_state["panel_jd_id"] = c["jd_id"]
                    st.session_state["panel_interview_stage"] = c.get("stage")
                    st.info("Navigate to 'Candidate Profile' to view this candidate.")
