import streamlit as st
import plotly.express as px
import pandas as pd
from ui.components.auth_guard import require_role
from ui.api_client import api_get


def render(user: dict):
    require_role("admin")
    st.title("Analytics & Reports")

    jds = api_get("/jd/list") or []
    jd_options = {"All JDs": None}
    jd_options.update({f"[{j['id']}] {j['title']}": j["id"] for j in jds})
    selected_label = st.selectbox("Filter by JD", list(jd_options.keys()))
    jd_id = jd_options[selected_label]

    params = {}
    if jd_id:
        params["jd_id"] = jd_id
    metrics = api_get("/dashboard/metrics", params=params)

    if not metrics:
        st.info("No data available yet.")
        return

    # ── Funnel Chart ───────────────────────────────────────────
    st.subheader("Hiring Pipeline Funnel")
    funnel = metrics.get("funnel", [])
    if funnel:
        df_f = pd.DataFrame(funnel)
        df_f.columns = ["Stage", "Count"]
        fig = px.funnel(df_f, x="Count", y="Stage")
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    # ── Tier Breakdown ─────────────────────────────────────────
    with col1:
        st.subheader("Tier Distribution")
        tiers = metrics.get("tier_distribution", [])
        if tiers:
            df_t = pd.DataFrame(tiers)
            df_t.columns = ["Tier", "Count"]
            fig2 = px.pie(df_t, values="Count", names="Tier",
                          color="Tier",
                          color_discrete_map={
                              "Highly Suitable": "#2ecc71",
                              "Suitable": "#3498db",
                              "Manual Review": "#f39c12",
                              "Not Suitable": "#e74c3c",
                          })
            st.plotly_chart(fig2, use_container_width=True)

    # ── Status Breakdown ───────────────────────────────────────
    with col2:
        st.subheader("Candidate Status Breakdown")
        status_data = metrics.get("status_breakdown", {})
        if status_data:
            df_s = pd.DataFrame(
                [{"Status": k, "Count": v} for k, v in status_data.items() if v > 0]
            )
            fig3 = px.bar(df_s, x="Status", y="Count", color="Count",
                          color_continuous_scale="Blues")
            fig3.update_layout(xaxis_tickangle=-30)
            st.plotly_chart(fig3, use_container_width=True)

    # ── Average Scores ─────────────────────────────────────────
    avg_scores = metrics.get("avg_scores_by_jd", [])
    if avg_scores:
        st.subheader("Average Match Score by JD")
        df_avg = pd.DataFrame(avg_scores)
        df_avg.columns = ["JD ID", "Avg Score"]
        fig4 = px.bar(df_avg, x="JD ID", y="Avg Score", range_y=[0, 100],
                      text_auto=True)
        st.plotly_chart(fig4, use_container_width=True)

    # ── Summary Metrics ────────────────────────────────────────
    st.subheader("Summary")
    total = metrics.get("total_candidates", 0)
    shortlisted = metrics.get("shortlisted", 0)
    rejected = metrics.get("rejected", 0)
    selected = metrics.get("selected", 0)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Shortlist Rate", f"{(shortlisted/total*100 if total else 0):.1f}%")
    col_b.metric("Rejection Rate", f"{(rejected/total*100 if total else 0):.1f}%")
    col_c.metric("Selection Rate", f"{(selected/total*100 if total else 0):.1f}%")
