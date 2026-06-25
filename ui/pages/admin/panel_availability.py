"""
Admin page: manage panel member availability slots.
DEMO MODE — all data lives in st.session_state, no API calls needed.
"""
import streamlit as st
from datetime import datetime, timedelta, date, time
from ui.components.auth_guard import require_role


# ── Static demo data ──────────────────────────────────────────
DEMO_PANEL = [
    {"id": "panel-001", "full_name": "Arjun Sharma",   "email": "arjun@company.com"},
    {"id": "panel-002", "full_name": "Priya Nair",     "email": "priya@company.com"},
    {"id": "panel-003", "full_name": "Ravi Mehta",     "email": "ravi@company.com"},
]
DEMO_JDS = [
    {"id": 1, "title": "Senior Backend Engineer"},
    {"id": 2, "title": "ML Engineer"},
    {"id": 3, "title": "DevOps Lead"},
]


def _init():
    if "demo_slots" not in st.session_state:
        # Pre-seed a few slots so the demo page isn't empty
        base = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        st.session_state["demo_slots"] = [
            {"id": "slot-001", "panel_user_id": "panel-001", "panel_name": "Arjun Sharma",
             "jd_id": 1, "slot_start": (base + timedelta(hours=10)).isoformat(),
             "slot_end":   (base + timedelta(hours=11)).isoformat(), "status": "available"},
            {"id": "slot-002", "panel_user_id": "panel-001", "panel_name": "Arjun Sharma",
             "jd_id": 1, "slot_start": (base + timedelta(hours=14)).isoformat(),
             "slot_end":   (base + timedelta(hours=15)).isoformat(), "status": "available"},
            {"id": "slot-003", "panel_user_id": "panel-002", "panel_name": "Priya Nair",
             "jd_id": 1, "slot_start": (base + timedelta(days=1, hours=11)).isoformat(),
             "slot_end":   (base + timedelta(days=1, hours=12)).isoformat(), "status": "available"},
            {"id": "slot-004", "panel_user_id": "panel-003", "panel_name": "Ravi Mehta",
             "jd_id": 2, "slot_start": (base + timedelta(hours=9)).isoformat(),
             "slot_end":   (base + timedelta(hours=10)).isoformat(), "status": "booked"},
        ]
    if "demo_bookings" not in st.session_state:
        base = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        st.session_state["demo_bookings"] = [
            {"booking_id": "bk-001", "slot_id": "slot-004",
             "slot_start": (base + timedelta(hours=9)).isoformat(),
             "slot_end":   (base + timedelta(hours=10)).isoformat(),
             "panel_user_id": "panel-003", "panel_name": "Ravi Mehta",
             "candidate_id": "cand-001", "candidate_name": "Aarav Patel",
             "jd_id": 2, "booked_at": datetime.utcnow().isoformat(), "notes": "Candidate confirmed via email"},
        ]


def render(user: dict):
    require_role("admin")
    _init()

    st.title("Panel Availability Slots")
    st.caption("Demo mode — data is stored in session state")

    panel_options = {f"{p['full_name']} ({p['email']})": p["id"] for p in DEMO_PANEL}
    panel_name_map = {p["id"]: p["full_name"] for p in DEMO_PANEL}
    jd_options = {"— All JDs —": None}
    jd_options.update({f"[{j['id']}] {j['title']}": j["id"] for j in DEMO_JDS})

    tab_add, tab_view, tab_bookings = st.tabs([
        "➕ Add Slots",
        "📋 View / Delete Slots",
        "📅 Bookings",
    ])

    # ── Tab 1: Add Slots ──────────────────────────────────────
    with tab_add:
        st.subheader("Post availability slots for a panel member")

        with st.form("add_slots_form", clear_on_submit=True):
            panel_label = st.selectbox("Panel Member", list(panel_options.keys()))
            panel_user_id = panel_options[panel_label]

            jd_label = st.selectbox("Job Description (optional)", list(jd_options.keys()))
            jd_id = jd_options[jd_label]

            num_slots = st.number_input("Number of slots to add", min_value=1, max_value=8, value=3, step=1)
            slot_date = st.date_input("Date", value=date.today() + timedelta(days=1))
            duration_min = st.selectbox("Slot duration (minutes)", [30, 45, 60, 90], index=2)

            slot_times = []
            cols = st.columns(min(int(num_slots), 4))
            for i in range(int(num_slots)):
                col = cols[i % len(cols)]
                default_hour = 9 + i
                t = col.time_input(
                    f"Slot {i+1}",
                    value=time(min(default_hour, 17), 0),
                    key=f"slot_t_{i}",
                )
                slot_times.append(t)

            submitted = st.form_submit_button("Create Slots", type="primary", use_container_width=True)

        if submitted:
            import uuid as _uuid
            created = 0
            for t in slot_times:
                start_dt = datetime.combine(slot_date, t)
                end_dt = start_dt + timedelta(minutes=int(duration_min))
                st.session_state["demo_slots"].append({
                    "id": f"slot-{_uuid.uuid4().hex[:6]}",
                    "panel_user_id": panel_user_id,
                    "panel_name": panel_name_map[panel_user_id],
                    "jd_id": jd_id,
                    "slot_start": start_dt.isoformat(),
                    "slot_end": end_dt.isoformat(),
                    "status": "available",
                })
                created += 1
            st.success(f"Created {created} slot(s) for {panel_label}.")
            st.rerun()

    # ── Tab 2: View / Delete Slots ────────────────────────────
    with tab_view:
        st.subheader("All slots")

        col1, col2, col3 = st.columns(3)
        with col1:
            fp_label = st.selectbox("Panel member", ["— All —"] + list(panel_options.keys()), key="fp")
            fp_id = panel_options.get(fp_label)
        with col2:
            fj_label = st.selectbox("JD", list(jd_options.keys()), key="fj")
            fj_id = jd_options[fj_label]
        with col3:
            fs = st.selectbox("Status", ["— All —", "available", "booked", "cancelled"], key="fs")
            fs_val = None if fs == "— All —" else fs

        slots = [
            s for s in st.session_state["demo_slots"]
            if (fp_id is None or s["panel_user_id"] == fp_id)
            and (fj_id is None or s["jd_id"] == fj_id)
            and (fs_val is None or s["status"] == fs_val)
        ]
        slots.sort(key=lambda s: s["slot_start"])

        if not slots:
            st.info("No slots found for the selected filters.")
        else:
            color = {"available": "🟢", "booked": "🔴", "cancelled": "⚫"}
            for slot in slots:
                start = datetime.fromisoformat(slot["slot_start"]).strftime("%d %b %Y  %H:%M")
                end   = datetime.fromisoformat(slot["slot_end"]).strftime("%H:%M")
                c1, c2 = st.columns([7, 1])
                with c1:
                    st.markdown(
                        f"{color.get(slot['status'], '⚪')} **{slot['panel_name']}** &nbsp;|&nbsp; "
                        f"{start} – {end} &nbsp;|&nbsp; "
                        f"JD: {slot.get('jd_id') or 'Any'} &nbsp;|&nbsp; `{slot['status']}`"
                    )
                with c2:
                    if slot["status"] == "available":
                        if st.button("🗑️", key=f"del_{slot['id']}", help="Delete slot"):
                            st.session_state["demo_slots"] = [
                                s for s in st.session_state["demo_slots"] if s["id"] != slot["id"]
                            ]
                            st.success("Slot deleted.")
                            st.rerun()

    # ── Tab 3: Bookings ───────────────────────────────────────
    with tab_bookings:
        st.subheader("Candidate slot bookings")

        b1, b2 = st.columns(2)
        with b1:
            bp_label = st.selectbox("Panel member", ["— All —"] + list(panel_options.keys()), key="bp")
            bp_id = panel_options.get(bp_label)
        with b2:
            bj_label = st.selectbox("JD", list(jd_options.keys()), key="bj")
            bj_id = jd_options[bj_label]

        bookings = [
            bk for bk in st.session_state["demo_bookings"]
            if (bp_id is None or bk.get("panel_user_id") == bp_id)
            and (bj_id is None or bk.get("jd_id") == bj_id)
        ]

        if not bookings:
            st.info("No bookings yet.")
        else:
            for bk in bookings:
                start = datetime.fromisoformat(bk["slot_start"]).strftime("%d %b %Y  %H:%M")
                end   = datetime.fromisoformat(bk["slot_end"]).strftime("%H:%M")
                c1, c2 = st.columns([7, 1])
                with c1:
                    st.markdown(
                        f"📌 **{bk['candidate_name']}** &nbsp;|&nbsp; "
                        f"{start} – {end} &nbsp;|&nbsp; "
                        f"Panel: {bk.get('panel_name', '—')} &nbsp;|&nbsp; JD: {bk.get('jd_id') or '—'}"
                        + (f"  \n_{bk['notes']}_" if bk.get("notes") else "")
                    )
                with c2:
                    if st.button("Cancel", key=f"cancel_{bk['booking_id']}", help="Cancel & free slot"):
                        # Free the slot
                        for s in st.session_state["demo_slots"]:
                            if s["id"] == bk["slot_id"]:
                                s["status"] = "available"
                                break
                        st.session_state["demo_bookings"] = [
                            b for b in st.session_state["demo_bookings"]
                            if b["booking_id"] != bk["booking_id"]
                        ]
                        st.success("Booking cancelled — slot is now available again.")
                        st.rerun()
