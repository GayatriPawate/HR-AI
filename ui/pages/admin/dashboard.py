import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from ui.components.auth_guard import require_role
from ui.api_client import api_get


def render(user: dict):
    require_role("admin")
    st.title("HR Dashboard")
    st.caption(f"Logged in as: **{user['name']}** (Admin)")

    # JD Filter
    jds = api_get("/jd/list") or []
    jd_options = {f"[{j['id']}] {j['title']}": j["id"] for j in jds}
    jd_options = {"All JDs": None, **jd_options}
    selected_jd_label = st.selectbox("Filter by Job Description", list(jd_options.keys()))
    jd_id = jd_options[selected_jd_label]

    # Fetch metrics
    params = {}
    if jd_id:
        params["jd_id"] = jd_id
    metrics = api_get("/dashboard/metrics", params=params)

    if not metrics:
        st.info("No data available. Upload resumes and create a JD to get started.")
        return

    # ── KPI Cards ──────────────────────────────────────────────
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Candidates", metrics.get("total_candidates", 0))
    col2.metric("Shortlisted", metrics.get("shortlisted", 0))
    col3.metric("Interview Pending", metrics.get("interview_pending", 0))
    col4.metric("Scheduled", metrics.get("interview_scheduled", 0))
    col5.metric("Selected", metrics.get("selected", 0))
    col6.metric("Rejected", metrics.get("rejected", 0))

    st.divider()

    col_left, col_right = st.columns(2)

    # ── Stage Funnel ───────────────────────────────────────────
    with col_left:
        st.subheader("Hiring Funnel")
        funnel_data = metrics.get("funnel", [])
        if funnel_data:
            stages = [f["stage"] for f in funnel_data]
            counts = [f["count"] for f in funnel_data]
            fig = go.Figure(go.Funnel(y=stages, x=counts, textposition="inside", textinfo="value+percent initial"))
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # ── Tier Distribution ──────────────────────────────────────
    with col_right:
        st.subheader("Candidate Tier Distribution")
        tier_data = metrics.get("tier_distribution", [])
        if tier_data:
            tiers = [t["tier"] for t in tier_data]
            counts = [t["count"] for t in tier_data]
            colors = {
                "Highly Suitable": "#2ecc71",
                "Suitable": "#3498db",
                "Manual Review": "#f39c12",
                "Not Suitable": "#e74c3c",
            }
            fig2 = px.pie(
                values=counts, names=tiers,
                color=tiers,
                color_discrete_map=colors,
            )
            fig2.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig2, use_container_width=True)

    # ── Upcoming Scheduled Interviews ──────────────────────────
    st.subheader("Upcoming Interviews")
    upcoming = metrics.get("upcoming_schedules", [])
    if upcoming:
        import pandas as pd
        df = pd.DataFrame(upcoming)
        df = df[["candidate_id", "scheduled_start", "scheduled_end", "status", "teams_join_url"]]
        df.columns = ["Candidate ID", "Start", "End", "Status", "Teams Link"]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No upcoming interviews scheduled.")

    # ── Average Scores by JD ───────────────────────────────────
    avg_scores = metrics.get("avg_scores_by_jd", [])
    if avg_scores:
        st.subheader("Average Match Score by JD")
        import pandas as pd
        df_scores = pd.DataFrame(avg_scores)
        df_scores.columns = ["JD ID", "Avg Score"]
        fig3 = px.bar(df_scores, x="JD ID", y="Avg Score", color="Avg Score",
                      color_continuous_scale="Blues", range_y=[0, 100])
        st.plotly_chart(fig3, use_container_width=True)
