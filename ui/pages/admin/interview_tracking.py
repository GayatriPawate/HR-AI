import streamlit as st
import pandas as pd
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post


def render(user: dict):
    require_role("admin")
    st.title("Interview Tracking")

    tab1, tab2, tab3 = st.tabs(["All Interviews", "Create Interview", "Panel Assignments"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("Filter by Status",
                ["all", "pending", "scheduled", "completed", "cancelled"])
        with col2:
            jds = api_get("/jd/list") or []
            jd_options = {"All JDs": None}
            jd_options.update({f"[{j['id']}] {j['title']}": j["id"] for j in jds})
            jd_label = st.selectbox("Filter by JD", list(jd_options.keys()))
            jd_id = jd_options[jd_label]

        params = {}
        if status_filter != "all":
            params["status"] = status_filter
        if jd_id:
            params["jd_id"] = jd_id

        interviews = api_get("/interviews/list", params=params) or []
        if not interviews:
            st.info("No interviews found.")
        else:
            df = pd.DataFrame([{
                "Interview ID": iv.get("id", "")[:8] + "...",
                "Candidate ID": iv.get("candidate_id", "")[:8] + "...",
                "JD ID": iv.get("jd_id"),
                "Stage": iv.get("stage"),
                "Status": iv.get("status"),
                "Scheduled At": iv.get("scheduled_at", "—"),
            } for iv in interviews])
            st.dataframe(df, use_container_width=True)

    with tab2:
        st.subheader("Schedule Interview")
        jds2 = api_get("/jd/list") or []
        panel_members = api_get("/users/panel-members") or []

        jd_sel = st.selectbox(
            "Job Description",
            [f"[{j['id']}] {j['title']}" for j in jds2] or ["—"],
            key="ci_jd_sel",
        )
        jd_id_new = int(jd_sel.split("]")[0].strip("[")) if jds2 else None

        # Load candidates ranked for this JD so admin can pick by name
        candidates_for_jd = []
        if jd_id_new:
            candidates_for_jd = api_get("/candidates/ranked", params={"jd_id": jd_id_new, "limit": 200}) or []

        cand_options = {
            f"{c['full_name']}  (score: {c.get('total_score', 0):.0f})": c["candidate_id"]
            for c in candidates_for_jd
        }

        with st.form("create_interview"):
            if cand_options:
                cand_label = st.selectbox("Candidate", list(cand_options.keys()))
                cand_id = cand_options[cand_label]
                st.caption(f"Candidate ID: `{cand_id}`")
            else:
                st.info("No ranked candidates yet for this JD. Run AI Matching on the Ranking page first.")
                cand_id = st.text_input("Or enter Candidate ID manually")

            panel_sel = st.selectbox(
                "Panel Member",
                [f"{p['full_name']} ({p['email']})" for p in panel_members] or ["—"],
            )
            panel_id = panel_members[[p["full_name"] for p in panel_members].index(
                panel_sel.split(" (")[0]
            )]["id"] if panel_members else None
            stage = st.selectbox("Stage", ["screening", "technical", "final", "hr"])

            if st.form_submit_button("Create Interview"):
                if cand_id and jd_id_new and panel_id:
                    result = api_post("/interviews/create", json={
                        "candidate_id": cand_id,
                        "jd_id": jd_id_new,
                        "panel_user_id": panel_id,
                        "stage": stage,
                    })
                    if result:
                        st.success(f"Interview created: {result.get('interview_id')}")
                else:
                    st.warning("Please fill all required fields.")

    with tab3:
        st.subheader("Assign Candidate to Panel Member")
        jds3 = api_get("/jd/list") or []
        panel_members3 = api_get("/users/panel-members") or []

        jd_sel2 = st.selectbox(
            "Job Description",
            [f"[{j['id']}] {j['title']}" for j in jds3] or ["—"],
            key="ap_jd_sel",
        )
        jd_id_assign = int(jd_sel2.split("]")[0].strip("[")) if jds3 else None

        candidates_for_jd2 = []
        if jd_id_assign:
            candidates_for_jd2 = api_get("/candidates/ranked", params={"jd_id": jd_id_assign, "limit": 200}) or []

        cand_options2 = {
            f"{c['full_name']}  (score: {c.get('total_score', 0):.0f})": c["candidate_id"]
            for c in candidates_for_jd2
        }

        with st.form("assign_panel"):
            if cand_options2:
                cand_label2 = st.selectbox("Candidate", list(cand_options2.keys()))
                cand_id2 = cand_options2[cand_label2]
                st.caption(f"Candidate ID: `{cand_id2}`")
            else:
                st.info("No ranked candidates yet for this JD. Run AI Matching on the Ranking page first.")
                cand_id2 = st.text_input("Or enter Candidate ID manually")

            panel_sel2 = st.selectbox(
                "Panel Member",
                [f"{p['full_name']} ({p['email']})" for p in panel_members3] or ["—"],
            )
            panel_id2 = panel_members3[[p["full_name"] for p in panel_members3].index(
                panel_sel2.split(" (")[0]
            )]["id"] if panel_members3 else None
            stage2 = st.selectbox("Interview Stage", ["screening", "technical", "final", "hr"])

            if st.form_submit_button("Assign Panel"):
                if cand_id2 and jd_id_assign and panel_id2:
                    result2 = api_post("/interviews/assign-panel", json={
                        "candidate_id": cand_id2,
                        "jd_id": jd_id_assign,
                        "panel_user_id": panel_id2,
                        "stage": stage2,
                    })
                    if result2:
                        st.success(f"Assignment created: {result2.get('assignment_id')}")
                else:
                    st.warning("Please fill all required fields.")
