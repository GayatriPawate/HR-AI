import streamlit as st
import pandas as pd
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post


def render(user: dict):
    require_role("admin")
    st.title("Upload Resumes")

    # JD selector
    jds = api_get("/jd/list") or []
    jd_options = {"None (no JD)": None}
    jd_options.update({f"[{j['id']}] {j['title']}": j["id"] for j in jds})
    selected_jd_label = st.selectbox("Associate with Job Description (optional)", list(jd_options.keys()))
    jd_id = jd_options[selected_jd_label]

    st.info("Upload PDF or DOCX resume files. Multiple files supported.")
    uploaded_files = st.file_uploader(
        "Select Resume Files",
        type=["pdf", "docx", "doc"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("Upload & Parse Resumes", type="primary"):
        st.info(f"Processing {len(uploaded_files)} file(s)...")
        progress = st.progress(0)

        files_payload = [
            ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
            for f in uploaded_files
        ]
        data = {}
        if jd_id:
            data["jd_id"] = str(jd_id)

        result = api_post("/resumes/upload", files=files_payload, data=data)
        progress.progress(100)

        if result:
            st.success(f"Processed {result['total']} files: {result['success']} success, {result['failed']} failed")

            rows = []
            for r in result.get("results", []):
                rows.append({
                    "Filename": r.get("filename"),
                    "Status": r.get("status"),
                    "Candidate Name": r.get("candidate_name", "—"),
                    "Skills Found": r.get("skills_found", 0),
                    "Duplicate": "Yes" if r.get("is_duplicate") else "No",
                    "Error": r.get("error", ""),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)

    # Show existing candidates
    st.divider()
    st.subheader("All Candidates")
    candidates = api_get("/resumes/candidates", params={"limit": 200}) or {}
    cands_list = candidates.get("candidates", [])
    if cands_list:
        df2 = pd.DataFrame([{
            "Name": c.get("full_name"),
            "Email": c.get("email"),
            "Experience (yrs)": c.get("total_experience_yrs"),
            "Latest Role": c.get("latest_role"),
            "Location": c.get("location"),
            "Skills Count": len(c.get("skills_list") or []),
        } for c in cands_list])
        st.dataframe(df2, use_container_width=True)
    else:
        st.info("No candidates uploaded yet.")
