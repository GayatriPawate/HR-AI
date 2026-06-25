import streamlit as st
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post


def render(user: dict):
    require_role("panel")
    st.title("Interview Feedback Submission")

    # Get assigned candidates to pick interview
    assigned = api_get("/interviews/assigned") or []
    if not assigned:
        st.info("No candidates assigned. Contact HR admin.")
        return

    # Candidate selector
    cand_options = {f"{c['candidate_name']} — {c['jd_title']}": c for c in assigned}
    selected_label = st.selectbox("Select Candidate", list(cand_options.keys()))
    selected_cand = cand_options[selected_label]

    candidate_id = selected_cand["candidate_id"]
    jd_id = selected_cand["jd_id"]

    # Get interviews for this candidate
    interviews = api_get("/interviews/list", params={"status": "pending"}) or []
    cand_interviews = [iv for iv in interviews if iv.get("candidate_id") == candidate_id]

    if not cand_interviews:
        st.info("No pending interviews found for this candidate.")
        st.write("Ask your HR admin to create an interview entry first.")
        return

    interview_options = {f"Stage: {iv.get('stage', '—')} | ID: {iv['id'][:8]}": iv["id"]
                         for iv in cand_interviews}
    selected_interview_label = st.selectbox("Select Interview", list(interview_options.keys()))
    interview_id = interview_options[selected_interview_label]

    st.divider()
    st.subheader("Feedback Form")

    with st.form("feedback_form"):
        st.write("**Rate the candidate (1=Poor, 5=Excellent):**")

        col1, col2 = st.columns(2)
        with col1:
            technical = st.slider("Technical Skills", 1, 5, 3)
            communication = st.slider("Communication", 1, 5, 3)
            problem_solving = st.slider("Problem Solving", 1, 5, 3)
        with col2:
            cultural_fit = st.slider("Cultural Fit", 1, 5, 3)
            overall = st.slider("Overall Rating", 1, 5, 3)

        recommendation = st.selectbox("Recommendation", [
            "Strongly Recommend",
            "Recommend",
            "Neutral",
            "Do Not Recommend",
            "Strongly Do Not Recommend",
        ])

        strengths = st.text_area("Strengths Observed", height=100,
                                 placeholder="What did the candidate do well?")
        improvements = st.text_area("Areas for Improvement", height=100,
                                    placeholder="What could the candidate improve?")
        rejection_reason = ""
        if "Do Not Recommend" in recommendation:
            rejection_reason = st.text_area("Rejection Reason (required for rejection)", height=80)
        comments = st.text_area("Additional Comments", height=80)

        submitted = st.form_submit_button("Submit Feedback", type="primary")

    if submitted:
        if "Do Not Recommend" in recommendation and not rejection_reason:
            st.warning("Please provide a rejection reason when recommending against the candidate.")
            return

        with st.spinner("Submitting feedback..."):
            result = api_post(f"/interviews/{interview_id}/feedback", json={
                "technical_rating": technical,
                "communication_rating": communication,
                "problem_solving_rating": problem_solving,
                "cultural_fit_rating": cultural_fit,
                "overall_rating": overall,
                "recommendation": recommendation,
                "rejection_reason": rejection_reason or None,
                "strengths": strengths or None,
                "areas_of_improvement": improvements or None,
                "comments": comments or None,
            })

        if result:
            st.success("Feedback submitted successfully!")
            st.write(f"**AI Signal:** {result.get('llm_signal', '—')}")
            if "generated_questions" in st.session_state:
                del st.session_state["generated_questions"]
