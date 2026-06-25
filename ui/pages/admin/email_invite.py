import streamlit as st
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post


def render(user: dict):
    require_role("admin")
    st.title("📧 Email Interview Invite")
    st.caption(
        "Compose and send an AI-drafted interview invitation to a candidate via Microsoft Outlook."
    )

    # ── Load data ─────────────────────────────────────────────────
    jds = api_get("/jd/list") or []
    if not jds:
        st.warning("No Job Descriptions found. Create a JD first.")
        return

    jd_options = {f"[{j['id']}] {j['title']}": j["id"] for j in jds}

    col1, col2 = st.columns(2)

    with col1:
        jd_label = st.selectbox("Job Description", list(jd_options.keys()))
        jd_id = jd_options[jd_label]
        position_title = jd_label.split("] ", 1)[-1] if "] " in jd_label else jd_label

    with col2:
        shortlisted = api_get("/candidates/shortlisted", params={"jd_id": jd_id}) or []
        if not shortlisted:
            st.info("No shortlisted candidates for this JD. Shortlist from Ranking page first.")
            return
        cand_options = {
            f"{c['serial_no']} — {c['full_name']}": c
            for c in shortlisted
        }
        cand_label = st.selectbox("Candidate", list(cand_options.keys()))
        candidate = cand_options[cand_label]

    st.divider()

    # ── Interview details form ────────────────────────────────────
    st.subheader("Interview Details")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        interview_date = st.date_input("Interview Date")
    with col_b:
        interview_time = st.time_input("Interview Time")
    with col_c:
        duration = st.selectbox("Duration (minutes)", [30, 45, 60, 90, 120], index=2)

    interviewer_raw = st.text_input(
        "Interviewer Names (comma-separated)",
        placeholder="e.g. Priya Sharma, Rahul Mehta",
    )
    interviewer_names = [n.strip() for n in interviewer_raw.split(",") if n.strip()]

    teams_join_url = st.text_input(
        "Teams Meeting Link (optional)",
        placeholder="https://teams.microsoft.com/l/meetup-join/...",
    )

    to_email = st.text_input(
        "Candidate Email",
        value=candidate.get("email", "") if isinstance(candidate, dict) else "",
        placeholder="candidate@email.com",
    )

    cc_raw = st.text_input(
        "CC (comma-separated, optional)",
        placeholder="hr@company.com, panel@company.com",
    )
    cc_emails = [e.strip() for e in cc_raw.split(",") if e.strip()]

    extra_notes = st.text_area(
        "Additional Notes for the Email (optional)",
        placeholder="e.g. Please bring a portfolio. The interview will be conducted in English.",
        height=80,
    )

    company_name = st.text_input("Company Name", value="HR Platform")

    st.divider()

    # ── Preview + Send ────────────────────────────────────────────
    col_prev, col_send = st.columns(2)

    with col_prev:
        if st.button("✍️ Preview AI Draft", use_container_width=True):
            if not to_email:
                st.warning("Please enter the candidate's email.")
            else:
                with st.spinner("Composing email with AI…"):
                    result = api_post("/interviews/email/compose", json={
                        "candidate_name": candidate["full_name"],
                        "position_title": position_title,
                        "interview_date": str(interview_date),
                        "interview_time": str(interview_time),
                        "duration_minutes": duration,
                        "interviewer_names": interviewer_names,
                        "teams_join_url": teams_join_url or None,
                        "company_name": company_name,
                        "extra_notes": extra_notes,
                    })
                if result:
                    st.session_state["email_preview"] = result

    if st.session_state.get("email_preview"):
        preview = st.session_state["email_preview"]
        st.subheader("Email Preview")
        st.markdown(f"**Subject:** {preview.get('subject', '')}")
        st.markdown("**Body:**")
        st.components.v1.html(preview.get("body_html", ""), height=400, scrolling=True)

    with col_send:
        if st.button("📤 Compose & Send via Outlook", type="primary", use_container_width=True):
            if not to_email:
                st.warning("Please enter the candidate's email.")
            elif not interview_date or not interview_time:
                st.warning("Please fill in interview date and time.")
            else:
                with st.spinner("Composing and sending email via Microsoft Outlook…"):
                    result = api_post("/interviews/email/send", json={
                        "to_email": to_email,
                        "cc_emails": cc_emails,
                        "candidate_name": candidate["full_name"],
                        "position_title": position_title,
                        "interview_date": str(interview_date),
                        "interview_time": str(interview_time),
                        "duration_minutes": duration,
                        "interviewer_names": interviewer_names,
                        "teams_join_url": teams_join_url or None,
                        "company_name": company_name,
                        "extra_notes": extra_notes,
                    })
                if result:
                    st.success(
                        f"✅ Invitation sent to **{to_email}**!\n\n"
                        f"**Subject:** {result.get('subject', '')}"
                    )
                    st.session_state["email_preview"] = None
