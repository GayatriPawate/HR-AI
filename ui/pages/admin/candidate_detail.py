import streamlit as st
import plotly.graph_objects as go
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post

STATUSES = ["New", "Screened", "Shortlisted", "Interview Pending",
            "Interview Scheduled", "Interview Completed", "Rejected", "Selected", "On Hold"]


def render(user: dict):
    require_role("admin")
    st.title("Candidate Detail")

    # Load from session state (set by Ranking page)
    session_candidate_id = st.session_state.get("view_candidate_id")
    session_jd_id = st.session_state.get("view_jd_id")

    col_input1, col_input2 = st.columns(2)

    with col_input2:
        jds = api_get("/jd/list") or []
        jd_options = {"None": None}
        jd_options.update({f"[{j['id']}] {j['title']}": j["id"] for j in jds})
        # Pre-select JD from session if available
        jd_keys = list(jd_options.keys())
        default_jd_idx = 0
        if session_jd_id:
            for i, k in enumerate(jd_keys):
                if jd_options[k] == session_jd_id:
                    default_jd_idx = i
                    break
        jd_label = st.selectbox("Job Description", jd_keys, index=default_jd_idx)
        jd_id = jd_options[jd_label]

    with col_input1:
        # Fetch shortlisted candidates for the selected JD
        params = {}
        if jd_id:
            params["jd_id"] = jd_id
        shortlisted = api_get("/candidates/shortlisted", params=params) or []

        if shortlisted:
            cand_options = {
                f"{c['serial_no']} — {c['full_name']} (Score: {c['total_score']})": c["candidate_id"]
                for c in shortlisted
            }
            # Pre-select from session if available
            cand_keys = list(cand_options.keys())
            default_cand_idx = 0
            if session_candidate_id:
                for i, k in enumerate(cand_keys):
                    if cand_options[k] == session_candidate_id:
                        default_cand_idx = i
                        break
            selected_label = st.selectbox("Candidate ID (Shortlisted)", cand_keys, index=default_cand_idx)
            candidate_id = cand_options[selected_label]
        else:
            st.selectbox("Candidate ID (Shortlisted)", ["— No shortlisted candidates —"], disabled=True)
            st.info("No shortlisted candidates yet. Shortlist candidates from the Ranking page first.")
            return

    if not candidate_id:
        st.info("Select a candidate to view details.")
        return

    params = {}
    if jd_id:
        params["jd_id"] = jd_id
    detail = api_get(f"/candidates/{candidate_id}", params=params)
    if not detail:
        st.error("Candidate not found.")
        return

    # ── Profile Header ─────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(detail.get("full_name", "Unknown"))
        st.write(f"**Email:** {detail.get('email', '—')}")
        st.write(f"**Phone:** {detail.get('phone', '—')}")
        st.write(f"**Location:** {detail.get('location', '—')}")
        st.write(f"**Latest Role:** {detail.get('latest_role', '—')}")
        st.write(f"**Company:** {detail.get('current_company', '—')}")
        st.write(f"**Experience:** {detail.get('total_experience_yrs', 0)} years")
    with col2:
        st.write("**Skills:**")
        for skill in (detail.get("skills_list") or [])[:15]:
            st.badge(skill)

    # ── Score Breakdown ────────────────────────────────────────
    match = detail.get("match")
    if match:
        st.divider()
        st.subheader("Match Score")
        tier_color = {"Highly Suitable": "green", "Suitable": "blue",
                      "Manual Review": "orange", "Not Suitable": "red"}.get(match.get("tier"), "gray")
        st.metric("Total Score", f"{match.get('total_score', 0):.1f}/100",
                  delta=match.get("tier"))

        breakdown = match.get("score_breakdown") or {}
        if breakdown:
            categories = list(breakdown.keys())
            values = [breakdown[c]["weighted"] for c in categories]
            fig = go.Figure(go.Bar(x=categories, y=values, marker_color="#3498db"))
            fig.update_layout(title="Score Breakdown by Category",
                              yaxis_title="Weighted Score", height=300,
                              margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

        col_m, col_miss = st.columns(2)
        with col_m:
            st.write("**Matched Skills:**")
            for s in match.get("matched_skills") or []:
                st.markdown(f"✅ {s}")
        with col_miss:
            st.write("**Missing Skills:**")
            for s in match.get("missing_skills") or []:
                st.markdown(f"❌ {s}")

        if match.get("risk_flags"):
            st.warning("**Risk Flags:** " + " | ".join(match["risk_flags"]))

        if match.get("match_explanation"):
            with st.expander("Match Explanation"):
                st.write(match["match_explanation"])

    # ── Status Update ──────────────────────────────────────────
    if jd_id:
        st.divider()
        st.subheader("Update Status")
        with st.form("status_form"):
            new_status = st.selectbox("New Status", STATUSES)
            reason = st.text_input("Reason (optional)")
            if st.form_submit_button("Update Status"):
                result = api_post(
                    f"/candidates/{candidate_id}/status",
                    json={"jd_id": jd_id, "status": new_status, "reason": reason},
                )
                if result:
                    st.success(f"Status updated to: {new_status}")

    # ── Status History ─────────────────────────────────────────
    history = detail.get("status_history", [])
    if history:
        st.divider()
        st.subheader("Status History")
        for h in history:
            st.write(f"**{h.get('changed_at', '')}** — {h.get('from_status', 'Start')} → **{h.get('to_status')}**"
                     + (f" ({h.get('reason')})" if h.get('reason') else ""))

    # ── Interview History ──────────────────────────────────────
    interviews = detail.get("interviews", [])
    if interviews:
        st.divider()
        st.subheader("Interview History")
        for iv in interviews:
            with st.expander(f"Stage: {iv.get('stage', '—')} | Status: {iv.get('status')}"):
                st.write(f"**Scheduled:** {iv.get('scheduled_at', '—')}")
                feedback = iv.get("feedback")
                if feedback:
                    st.write(f"**Overall Rating:** {feedback.get('overall_rating', '—')}/5")
                    st.write(f"**Recommendation:** {feedback.get('recommendation', '—')}")
                    if feedback.get("rejection_reason"):
                        st.write(f"**Rejection Reason:** {feedback['rejection_reason']}")
                    if feedback.get("strengths"):
                        st.write(f"**Strengths:** {feedback['strengths']}")
