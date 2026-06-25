import streamlit as st
import json
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post


def render(user: dict):
    require_role("admin")

    st.title("Manager Agent — Orchestration Console")
    st.caption(
        "The ManagerAgent validates your role, routes the request to the right "
        "sub-agent or pipeline, and returns a unified result."
    )

    # ── Fetch available actions for this role ─────────────────────
    actions_data = api_get("/manager/actions") or {}
    available_actions = actions_data.get("available_actions", [])
    action_map = {a["action"]: a for a in available_actions}

    if not available_actions:
        st.warning("Could not load available actions. Is the backend running?")
        return

    # ── Sidebar: action picker ────────────────────────────────────
    st.subheader("Step 1 — Choose an Action")
    action_labels = [
        f"{a['action']}  —  {a['description']}" for a in available_actions
    ]
    selected_label = st.selectbox("Action", action_labels)
    selected_action = selected_label.split("  —  ")[0].strip()
    action_info = action_map[selected_action]

    st.info(
        f"**Required inputs:** "
        f"{', '.join(action_info['required_inputs']) or 'none'}"
    )

    # ── Dynamic payload form ──────────────────────────────────────
    st.subheader("Step 2 — Fill Required Inputs")

    payload: dict = {}

    # JD picker (shared by several actions)
    if "jd_id" in action_info["required_inputs"] or selected_action in (
        "jd_analyzer", "match_candidates", "skill_matcher",
        "assign_panel", "update_status", "generate_questions",
        "get_candidate_score_summary",
    ):
        jds = api_get("/jd/list") or []
        if selected_action == "jd_analyzer":
            # jd_analyzer creates a NEW jd — show text fields instead
            payload["title"] = st.text_input("Job Title")
            payload["raw_text"] = st.text_area("Job Description Text", height=200)
        elif jds:
            jd_options = {f"[{j['id']}] {j['title']}": j["id"] for j in jds}
            jd_label = st.selectbox("Job Description", list(jd_options.keys()))
            payload["jd_id"] = jd_options[jd_label]

    # Candidate picker
    if "candidate_id" in action_info["required_inputs"] and payload.get("jd_id"):
        ranked = api_get("/candidates/ranked", params={"jd_id": payload["jd_id"], "limit": 200}) or []
        if ranked:
            cand_options = {
                f"{c['full_name']}  (score: {c.get('total_score', 0):.0f})": c["candidate_id"]
                for c in ranked
            }
            cand_label = st.selectbox("Candidate", list(cand_options.keys()))
            payload["candidate_id"] = cand_options[cand_label]
            st.caption(f"Candidate ID: `{payload['candidate_id']}`")
        else:
            payload["candidate_id"] = st.text_input("Candidate ID (no ranked candidates yet)")

    # Panel member picker
    if "panel_user_id" in action_info["required_inputs"]:
        panel_members = api_get("/users/panel-members") or []
        if panel_members:
            panel_options = {
                f"{p['full_name']} ({p['email']})": p["id"] for p in panel_members
            }
            panel_label = st.selectbox("Panel Member", list(panel_options.keys()))
            payload["panel_user_id"] = panel_options[panel_label]

    # Stage
    if "stage" in action_info["required_inputs"]:
        payload["stage"] = st.selectbox("Interview Stage", ["screening", "technical", "final", "hr"])

    # Status
    if "status" in action_info["required_inputs"]:
        payload["status"] = st.selectbox("New Status", [
            "Screened", "Shortlisted", "Interview Pending",
            "Interview Scheduled", "Interview Completed", "Rejected", "Selected", "On Hold",
        ])
        payload["reason"] = st.text_input("Reason (optional)")

    # Interview ID for feedback_analyzer
    if selected_action == "feedback_analyzer":
        payload["interview_id"] = st.text_input("Interview ID")

    # Categories for question_generator
    if selected_action == "generate_questions":
        cats = st.multiselect(
            "Question Categories",
            ["conceptual", "practical", "scenario", "technical", "behavioral"],
            default=["technical", "behavioral"],
        )
        if cats:
            payload["categories"] = cats

    # ── Run ───────────────────────────────────────────────────────
    st.subheader("Step 3 — Run")

    col1, col2 = st.columns([2, 1])
    with col2:
        st.markdown("**Payload preview**")
        st.json(payload)

    with col1:
        if st.button("Run via Manager Agent", type="primary", use_container_width=True):
            with st.spinner("Manager Agent routing and executing..."):
                result = api_post("/manager/action", json={
                    "action": selected_action,
                    "payload": payload,
                })

            if result:
                agent_used = result.get("agent_used", "—")
                priority = result.get("priority", "—")
                inner = result.get("result", {})

                st.success(f"Routed to **{agent_used}** · priority: **{priority}**")

                if isinstance(inner, dict) and "error" in inner:
                    st.error(f"Agent error: {inner['error']}")
                    st.json(inner)
                else:
                    # Pretty-print specific result types
                    if selected_action == "generate_questions" and "questions" in inner:
                        st.markdown(f"**{inner['total']} questions generated for {inner.get('candidate_name', '')}**")
                        for i, q in enumerate(inner["questions"], 1):
                            with st.expander(f"Q{i}. [{q['category']}] {q['question'][:80]}..."):
                                st.markdown(f"**Question:** {q['question']}")
                                st.markdown(f"**Follow-up:** {q.get('follow_up', '—')}")
                                st.markdown(f"**Rubric hint:** {q.get('rubric_hint', '—')}")
                                st.caption(f"Difficulty: {q.get('difficulty')}  ·  Targets: {q.get('targets_skill')}")

                    elif selected_action == "match_candidates" and "results" in inner:
                        st.markdown(f"**{inner['total_matched']} candidates matched**")
                        import pandas as pd
                        rows = [{
                            "Name": r.get("candidate_name"),
                            "Score": r.get("total_score", 0),
                            "Tier": r.get("tier"),
                            "Matched Skills": ", ".join((r.get("matched_skills") or [])[:4]),
                        } for r in inner["results"]]
                        st.dataframe(pd.DataFrame(rows), use_container_width=True)

                    elif selected_action == "feedback_analyzer":
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Signal", inner.get("overall_signal", "—"))
                        c2.metric("Sentiment", inner.get("sentiment", "—"))
                        c3.metric("Flag for Review", "Yes" if inner.get("flag_for_review") else "No")
                        st.markdown(f"**Summary:** {inner.get('summary', '—')}")
                        if inner.get("flag_reasons"):
                            st.warning("Flag reasons: " + ", ".join(inner["flag_reasons"]))

                    else:
                        st.json(inner)

    # ── Agent wiring diagram ──────────────────────────────────────
    with st.expander("How the Manager Agent orchestrates sub-agents", expanded=False):
        st.markdown("""
| Action | Sub-Agent / Pipeline |
|--------|---------------------|
| `jd_analyzer` | `JDAnalyzerAgent` → `RubricAgent` → DB + ChromaDB |
| `match_candidates` | `ScoringService` (6 components) → `SkillMatcherAgent` |
| `skill_matcher` | `SkillMatcherAgent` (LLM explanation only) |
| `generate_questions` | `QuestionGeneratorAgent` |
| `feedback_analyzer` | `FeedbackAnalyzerAgent` |
| `assign_panel` | DB write (PanelAssignment) |
| `update_status` | DB write (CandidateStatus + StatusHistory) |
| `get_dashboard_metrics` | DB aggregation |
| `get_assigned_candidates` | DB read (panel's assignments) |
| `get_candidate_score_summary` | DB read (CandidateJobMatch) |

The ManagerAgent always calls the **Groq LLM first** to validate role permissions and
extract/validate inputs before dispatching — making routing dynamic rather than hardcoded.
        """)
