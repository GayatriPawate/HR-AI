import streamlit as st
import pandas as pd
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post

TIER_COLORS = {
    "Highly Suitable": "🟢",
    "Suitable": "🔵",
    "Manual Review": "🟡",
    "Not Suitable": "🔴",
}


def _init_chat():
    if "cv_chat_history" not in st.session_state:
        st.session_state["cv_chat_history"] = []   # list of {role, content, citations}


def render(user: dict):
    require_role("admin")
    _init_chat()

    st.title("Candidate Ranking")

    jds = api_get("/jd/list") or []
    if not jds:
        st.warning("No Job Descriptions found. Please create a JD first.")
        return

    jd_options = {f"[{j['id']}] {j['title']}": j["id"] for j in jds}
    selected_label = st.selectbox("Select Job Description", list(jd_options.keys()))
    jd_id = jd_options[selected_label]

    col1, col2 = st.columns([2, 1])
    with col2:
        if st.button("Run AI Matching", type="primary"):
            with st.spinner("Matching candidates against JD..."):
                result = api_post("/candidates/match", json={"jd_id": jd_id})
            if result:
                st.success(f"Matched {result.get('total_matched', 0)} candidates!")
                st.rerun()

    # Filters
    with st.sidebar:
        st.subheader("Filters")
        tier_filter = st.multiselect(
            "Tier",
            ["Highly Suitable", "Suitable", "Manual Review", "Not Suitable"],
        )
        min_score = st.slider("Minimum Score", 0, 100, 0)

    # Get ranked candidates
    params = {"jd_id": jd_id, "min_score": min_score, "limit": 200}
    if tier_filter and len(tier_filter) == 1:
        params["tier"] = tier_filter[0]

    ranked = api_get("/candidates/ranked", params=params) or []
    if tier_filter and len(tier_filter) > 1:
        ranked = [r for r in ranked if r.get("tier") in tier_filter]

    # ── Ranked table ──────────────────────────────────────────
    if not ranked:
        st.info("No candidates found. Run AI Matching to start.")
    else:
        st.subheader(f"Ranked Candidates ({len(ranked)} found)")

        if st.button("Export to CSV"):
            df_export = pd.DataFrame(ranked)
            csv = df_export.to_csv(index=False)
            st.download_button("Download CSV", csv, "candidates.csv", "text/csv")

        rows = []
        for c in ranked:
            rows.append({
                "Candidate ID": c.get("serial_no", "—"),
                "Tier": f"{TIER_COLORS.get(c.get('tier', ''), '⚪')} {c.get('tier', '—')}",
                "Score": c.get("total_score", 0),
                "Name": c.get("full_name"),
                "Role": c.get("latest_role", "—"),
                "Exp (yrs)": c.get("total_experience_yrs", 0),
                "Matched Skills": ", ".join((c.get("matched_skills") or [])[:5]),
                "Missing Skills": ", ".join((c.get("missing_skills") or [])[:3]),
                "Shortlisted": "✅" if c.get("is_shortlisted") else "",
                "_uuid": c.get("candidate_id"),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df.drop(columns=["_uuid"]), use_container_width=True)

        # Candidate actions
        st.divider()
        st.subheader("Candidate Actions")
        cand_options = {
            f"{r['Candidate ID']} — {r['Name']} (Score: {r['Score']})": r["_uuid"]
            for r in rows
        }
        selected_cand = st.selectbox("Select Candidate", list(cand_options.keys()))
        selected_cand_id = cand_options[selected_cand]

        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button("Shortlist"):
                result = api_post(f"/candidates/{selected_cand_id}/shortlist", json={"jd_id": jd_id})
                if result:
                    st.success("Candidate shortlisted!")
                    st.rerun()
        with action_col2:
            new_status = st.selectbox("Update Status", [
                "Screened", "Shortlisted", "Interview Pending", "Rejected", "On Hold", "Selected"
            ])
            if st.button("Update Status"):
                result = api_post(
                    f"/candidates/{selected_cand_id}/status",
                    json={"jd_id": jd_id, "status": new_status, "reason": ""},
                )
                if result:
                    st.success(f"Status updated to: {new_status}")
                    st.rerun()
        with action_col3:
            if st.button("View Detail"):
                st.session_state["view_candidate_id"] = selected_cand_id
                st.session_state["view_jd_id"] = jd_id
                st.info(f"Navigate to 'Candidate Detail' to view {selected_cand}")

    # ═══════════════════════════════════════════════════════════
    # CV CHAT — Ask AI about candidates using RAG
    # ═══════════════════════════════════════════════════════════
    st.divider()

    with st.expander("💬 Ask AI about Candidates (RAG Chat)", expanded=True):
        st.caption(
            "Ask anything about the candidates — the AI searches their CVs and answers "
            "with citations so you can trace every claim back to the source."
        )

        # ── Chat history display ──────────────────────────────
        history = st.session_state["cv_chat_history"]

        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

                # Show citations after assistant messages
                if msg["role"] == "assistant" and msg.get("citations"):
                    with st.expander(f"📎 Sources ({len(msg['citations'])} CV excerpts)", expanded=False):
                        for i, cit in enumerate(msg["citations"], 1):
                            name  = cit.get("candidate_name") or cit["candidate_id"]
                            score = cit.get("similarity", 0)
                            cid   = cit["candidate_id"]

                            col_a, col_b = st.columns([5, 1])
                            with col_a:
                                st.markdown(
                                    f"**[{i}] {name}** &nbsp; "
                                    f"<span style='color:grey;font-size:0.85em'>"
                                    f"similarity {score:.0%}</span>",
                                    unsafe_allow_html=True,
                                )
                                st.markdown(
                                    f"> {cit['excerpt'][:300]}{'…' if len(cit['excerpt']) > 300 else ''}",
                                )
                            with col_b:
                                if st.button(
                                    "Shortlist",
                                    key=f"sl_{msg.get('_msg_idx', i)}_{cid}_{i}",
                                    help=f"Shortlist {name}",
                                ):
                                    res = api_post(
                                        f"/candidates/{cid}/shortlist",
                                        json={"jd_id": jd_id},
                                    )
                                    if res:
                                        st.success(f"✅ {name} shortlisted!")

        # ── Input ─────────────────────────────────────────────
        st.caption("⏳ First query after server restart may take 20–40 s while the AI model warms up.")

        question = st.chat_input(
            "e.g. Who has the most Python experience? / Which candidates know Kubernetes?"
        )

        if question:
            # Append user message
            history.append({"role": "user", "content": question})

            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("Searching CVs…"):
                    result = api_post("/candidates/chat", json={
                        "jd_id": jd_id,
                        "question": question,
                        "top_k": 5,
                    })

                if result:
                    answer    = result.get("answer", "No answer returned.")
                    citations = result.get("citations", [])

                    st.markdown(answer)

                    if citations:
                        with st.expander(f"📎 Sources ({len(citations)} CV excerpts)", expanded=True):
                            for i, cit in enumerate(citations, 1):
                                name  = cit.get("candidate_name") or cit["candidate_id"]
                                score = cit.get("similarity", 0)
                                cid   = cit["candidate_id"]

                                col_a, col_b = st.columns([5, 1])
                                with col_a:
                                    st.markdown(
                                        f"**[{i}] {name}** &nbsp; "
                                        f"<span style='color:grey;font-size:0.85em'>"
                                        f"similarity {score:.0%}</span>",
                                        unsafe_allow_html=True,
                                    )
                                    st.markdown(
                                        f"> {cit['excerpt'][:300]}{'…' if len(cit['excerpt']) > 300 else ''}",
                                    )
                                with col_b:
                                    if st.button(
                                        "Shortlist",
                                        key=f"sl_new_{cid}_{i}",
                                        help=f"Shortlist {name}",
                                    ):
                                        res = api_post(
                                            f"/candidates/{cid}/shortlist",
                                            json={"jd_id": jd_id},
                                        )
                                        if res:
                                            st.success(f"✅ {name} shortlisted!")

                    # Persist to history
                    history.append({
                        "role": "assistant",
                        "content": answer,
                        "citations": citations,
                        "_msg_idx": len(history),
                    })
                else:
                    err = "Could not reach the backend."
                    st.error(err)
                    history.append({"role": "assistant", "content": err, "citations": []})

        # Clear chat button
        if history and st.button("🗑️ Clear chat", key="clear_cv_chat"):
            st.session_state["cv_chat_history"] = []
            st.rerun()
