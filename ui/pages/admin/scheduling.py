import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from ui.components.auth_guard import require_role
from ui.api_client import api_get, api_post


def render(user: dict):
    require_role("admin")
    st.title("Interview Scheduling (Microsoft Graph)")

    st.info(
        "Requires Microsoft Graph configuration (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET) in .env"
    )

    tab1, tab2 = st.tabs(["Schedule Interview", "View Scheduled Interviews"])

    with tab1:
        st.subheader("Find Available Slots & Book")

        jds = api_get("/jd/list") or []
        panel_members = api_get("/users/panel-members") or []

        jd_options = {f"[{j['id']}] {j['title']}": j["id"] for j in jds}
        jd_label_pre = st.selectbox(
            "Job Description",
            list(jd_options.keys()) or ["—"],
            key="sched_jd_pre",
        )
        jd_id_pre = jd_options.get(jd_label_pre)

        # Load ranked candidates for selected JD outside the form so the
        # selectbox options update when the JD changes.
        ranked_for_jd = []
        if jd_id_pre:
            ranked_for_jd = api_get("/candidates/ranked", params={"jd_id": jd_id_pre, "limit": 200}) or []

        cand_pick = {
            f"{c['full_name']}  (score: {c.get('total_score', 0):.0f})": c["candidate_id"]
            for c in ranked_for_jd
        }

        with st.form("schedule_form"):
            if cand_pick:
                cand_label = st.selectbox("Candidate", list(cand_pick.keys()))
                candidate_id = cand_pick[cand_label]
                st.caption(f"Candidate ID: `{candidate_id}`")
            else:
                st.info("No ranked candidates for this JD yet. Run AI Matching on the Ranking page first.")
                candidate_id = st.text_input("Or enter Candidate ID manually")

            jd_options = {f"[{j['id']}] {j['title']}": j["id"] for j in jds}
            jd_label = st.selectbox("Job Description", list(jd_options.keys()) or ["—"])
            jd_id = jd_options.get(jd_label)

            panel_options = {f"{p['full_name']} ({p.get('ms_email') or p['email']})": p.get("ms_email") or p["email"]
                             for p in panel_members}
            selected_panel = st.multiselect("Panel Members (email)", list(panel_options.keys()))
            panel_emails = [panel_options[p] for p in selected_panel]

            date_from = st.date_input("Search From", value=datetime.today())
            date_to = st.date_input("Search To", value=datetime.today() + timedelta(days=7))
            duration = st.selectbox("Duration (minutes)", [30, 45, 60, 90], index=2)
            timezone = st.selectbox("Timezone", ["UTC", "Asia/Kolkata", "America/New_York", "Europe/London"])
            create_teams = st.checkbox("Create Teams Meeting Link", value=True)

            find_slots = st.form_submit_button("Find Available Slots", type="primary")

        if find_slots:
            if not candidate_id or not panel_emails:
                st.warning("Please provide Candidate ID and select at least one panel member.")
            else:
                with st.spinner("Checking availability via MS Graph..."):
                    slots_result = api_post("/schedule/find-slots", json={
                        "candidate_id": candidate_id,
                        "jd_id": jd_id,
                        "panel_user_emails": panel_emails,
                        "date_from": f"{date_from}T09:00:00",
                        "date_to": f"{date_to}T18:00:00",
                        "duration_minutes": duration,
                        "timezone": timezone,
                    })

                if slots_result:
                    slots = slots_result.get("available_slots", [])
                    if not slots:
                        st.warning("No available slots found in the selected range.")
                    else:
                        st.success(f"Found {len(slots)} available slots:")
                        st.session_state["available_slots"] = slots
                        st.session_state["schedule_data"] = {
                            "candidate_id": candidate_id,
                            "jd_id": jd_id,
                            "panel_emails": panel_emails,
                            "duration": duration,
                            "timezone": timezone,
                            "create_teams": create_teams,
                        }

        # Show slots and book
        if "available_slots" in st.session_state:
            slots = st.session_state["available_slots"]
            slot_options = {
                f"{s['start']} → {s['end']} (confidence: {s.get('confidence', 0):.0%})": i
                for i, s in enumerate(slots)
            }
            selected_slot_label = st.selectbox("Select a Time Slot", list(slot_options.keys()))
            selected_idx = slot_options[selected_slot_label]
            selected_slot = slots[selected_idx]

            if st.button("Book This Interview", type="primary"):
                sched_data = st.session_state.get("schedule_data", {})
                with st.spinner("Creating calendar event..."):
                    book_result = api_post("/schedule/create-event", json={
                        "candidate_id": sched_data["candidate_id"],
                        "jd_id": sched_data["jd_id"],
                        "panel_user_emails": sched_data["panel_emails"],
                        "start": selected_slot["start"],
                        "end": selected_slot["end"],
                        "timezone": sched_data["timezone"],
                        "create_teams_meeting": sched_data["create_teams"],
                    })

                if book_result:
                    st.success("Interview scheduled successfully!")
                    if book_result.get("teams_join_url"):
                        st.info(f"Teams Meeting Link: {book_result['teams_join_url']}")
                    st.json(book_result)
                    del st.session_state["available_slots"]

    with tab2:
        st.subheader("All Scheduled Interviews")
        schedules = api_get("/schedule/list") or []
        if not schedules:
            st.info("No interviews scheduled yet.")
        else:
            df = pd.DataFrame([{
                "Schedule ID": s.get("schedule_id", "")[:8] + "...",
                "Candidate": s.get("candidate_id", "")[:8] + "...",
                "Start": s.get("scheduled_start"),
                "End": s.get("scheduled_end"),
                "Status": s.get("status"),
                "Teams Link": "✅" if s.get("teams_join_url") else "❌",
            } for s in schedules])
            st.dataframe(df, use_container_width=True)

            # Cancel
            sched_ids = {s.get("schedule_id", "")[:8]: s["schedule_id"] for s in schedules}
            if sched_ids:
                cancel_label = st.selectbox("Select to Cancel", list(sched_ids.keys()))
                cancel_reason = st.text_input("Cancellation Reason")
                if st.button("Cancel Interview"):
                    result = api_post(f"/schedule/{sched_ids[cancel_label]}/cancel",
                                      json={"reason": cancel_reason})
                    if result:
                        st.success("Interview cancelled.")
                        st.rerun()
