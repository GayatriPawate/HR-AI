import streamlit as st
from ui.components.auth_guard import require_role
from ui.api_client import api_get


def render(user: dict):
    require_role("panel")
    st.title("Candidate Profile")

    candidate_id = st.session_state.get("panel_candidate_id", "")
    jd_id = st.session_state.get("panel_jd_id")

    if not candidate_id:
        st.info("Select a candidate from 'Assigned Candidates' first.")
        return

    params = {}
    if jd_id:
        params["jd_id"] = jd_id
    detail = api_get(f"/candidates/{candidate_id}", params=params)
    if not detail:
        st.error("Could not load candidate profile.")
        return

    # ── Profile ────────────────────────────────────────────────
    st.subheader(detail.get("full_name", "Unknown"))
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Email:** {detail.get('email', '—')}")
        st.write(f"**Phone:** {detail.get('phone', '—')}")
        st.write(f"**Location:** {detail.get('location', '—')}")
        st.write(f"**Latest Role:** {detail.get('latest_role', '—')}")
        st.write(f"**Company:** {detail.get('current_company', '—')}")
        st.write(f"**Experience:** {detail.get('total_experience_yrs', 0)} years")
    with col2:
        st.write("**Skills:**")
        for skill in (detail.get("skills_list") or [])[:20]:
            st.badge(skill)

    # ── Education ──────────────────────────────────────────────
    education = detail.get("education") or []
    if education:
        st.divider()
        st.subheader("Education")
        for edu in education:
            st.write(f"- **{edu.get('degree', '—')}** in {edu.get('field', '—')} "
                     f"from {edu.get('institution', '—')} ({edu.get('year', '—')})")

    # ── Certifications ─────────────────────────────────────────
    certs = detail.get("certifications") or []
    if certs:
        st.divider()
        st.subheader("Certifications")
        for cert in certs:
            st.write(f"- {cert}")

    # ── Score Summary (read-only) ──────────────────────────────
    match = detail.get("match")
    if match:
        st.divider()
        st.subheader("Match Score Summary")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Score", f"{match.get('total_score', 0):.1f}/100")
        col_b.metric("Tier", match.get("tier", "—"))
        col_c.metric("Matched Skills", len(match.get("matched_skills") or []))

        if match.get("match_explanation"):
            with st.expander("Match Explanation"):
                st.write(match["match_explanation"])
