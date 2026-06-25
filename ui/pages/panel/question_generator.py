import streamlit as st
from ui.components.auth_guard import require_role
from ui.api_client import api_post, api_get

CATEGORY_ICONS = {
    "conceptual": "🧠",
    "practical": "🔧",
    "scenario": "🎯",
    "technical": "💻",
    "behavioral": "🤝",
}

DIFFICULTY_COLORS = {
    "easy": "green",
    "medium": "orange",
    "hard": "red",
}


def render(user: dict):
    require_role("panel")  # PANEL ONLY — admin access blocked at API + UI level
    st.title("Interview Question Generator")
    st.caption("AI-generated questions tailored to this candidate and JD")

    candidate_id = st.session_state.get("panel_candidate_id", "")
    jd_id = st.session_state.get("panel_jd_id")

    if not candidate_id or not jd_id:
        st.warning("Please select a candidate from 'Assigned Candidates' first.")
        return

    # Show candidate name
    detail = api_get(f"/candidates/{candidate_id}")
    if detail:
        st.info(f"Generating questions for: **{detail.get('full_name')}** | JD ID: {jd_id}")

    # Category selection
    st.subheader("Select Question Categories")
    cat_col1, cat_col2, cat_col3, cat_col4, cat_col5 = st.columns(5)
    include_conceptual  = cat_col1.checkbox("Conceptual",  value=True)
    include_practical   = cat_col2.checkbox("Practical",   value=True)
    include_scenario    = cat_col3.checkbox("Scenario",    value=True)
    include_technical   = cat_col4.checkbox("Technical",   value=True)
    include_behavioral  = cat_col5.checkbox("Behavioral",  value=True)

    categories = []
    if include_conceptual:  categories.append("conceptual")
    if include_practical:   categories.append("practical")
    if include_scenario:    categories.append("scenario")
    if include_technical:   categories.append("technical")
    if include_behavioral:  categories.append("behavioral")

    if st.button("Generate Questions", type="primary", disabled=not categories):
        if not categories:
            st.warning("Select at least one category.")
            return

        with st.spinner("AI is generating tailored interview questions..."):
            result = api_post("/questions/generate", json={
                "candidate_id": candidate_id,
                "jd_id": jd_id,
                "categories": categories,
            })

        if result:
            questions = result.get("questions", [])
            st.session_state["generated_questions"] = questions
            st.success(f"Generated {len(questions)} questions!")

    # Display questions
    if "generated_questions" in st.session_state:
        questions = st.session_state["generated_questions"]

        # Export
        if st.button("Export Questions (Text)"):
            text_export = "\n\n".join([
                f"[{q.get('category', '').upper()}] Q{i+1}: {q.get('question', '')}\n"
                f"  Follow-up: {q.get('follow_up', '')}\n"
                f"  Rubric: {q.get('rubric_hint', '')}\n"
                f"  Targets: {q.get('targets_skill', '')}"
                for i, q in enumerate(questions)
            ])
            st.download_button("Download", text_export, "interview_questions.txt")

        # Group by category
        by_category: dict = {}
        for q in questions:
            cat = q.get("category", "general")
            by_category.setdefault(cat, []).append(q)

        for cat, qs in by_category.items():
            icon = CATEGORY_ICONS.get(cat, "📋")
            st.subheader(f"{icon} {cat.title()} Questions")
            for i, q in enumerate(qs, 1):
                difficulty = q.get("difficulty", "medium")
                with st.expander(f"Q{i}: {q.get('question', '')[:80]}..."):
                    st.write(f"**Question:** {q.get('question')}")
                    st.write(f"**Follow-up:** {q.get('follow_up', '—')}")
                    st.write(f"**Rubric Hint:** {q.get('rubric_hint', '—')}")
                    st.write(f"**Targets Skill:** `{q.get('targets_skill', '—')}`")
                    diff_color = DIFFICULTY_COLORS.get(difficulty, "gray")
                    st.markdown(f"**Difficulty:** :{diff_color}[{difficulty.upper()}]")
