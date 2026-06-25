"""
Admin page: book an interview slot on behalf of a candidate.
DEMO MODE — slot state managed via st.session_state; candidate list fetched from live API.
"""
import streamlit as st
import uuid
from datetime import datetime

from ui.components.auth_guard import require_role
from ui.api_client import api_get


def _init():
    """Ensure shared demo state exists (created by panel_availability page if visited first)."""
    if "demo_slots" not in st.session_state:
        from ui.pages.admin.panel_availability import _init as _pa_init
        _pa_init()
    if "demo_bookings" not in st.session_state:
        st.session_state["demo_bookings"] = []


def render(user: dict):
    require_role("admin")
    _init()

    st.title("Book Interview Slot for Candidate")
    st.caption("Slot locking is simulated via session state")

    # ── Step 1: JD & Candidate ────────────────────────────────
    st.subheader("Step 1 — Select JD & Candidate")

    jds = api_get("/jd/list") or []
    if not jds:
        st.warning("No Job Descriptions found. Please create a JD first.")
        return

    jd_options = {f"[{j['id']}] {j['title']}": j["id"] for j in jds}

    col1, col2 = st.columns(2)

    with col1:
        jd_label = st.selectbox("Job Description", list(jd_options.keys()))
        jd_id = jd_options[jd_label]

    with col2:
        ranked = api_get("/candidates/ranked", params={"jd_id": jd_id, "limit": 200}) or []
        if not ranked:
            st.info("No ranked candidates for this JD. Run AI Matching on the Ranking page first.")
            return
        cand_options = {
            f"{c['full_name']}  (score: {c.get('total_score', 0):.0f})": {
                "candidate_id": c["candidate_id"],
                "full_name": c["full_name"],
                "jd_id": jd_id,
                "total_score": c.get("total_score", 0),
            }
            for c in ranked
        }
        cand_label = st.selectbox("Candidate", list(cand_options.keys()))
        selected_candidate = cand_options[cand_label]
        st.caption(f"Candidate ID: `{selected_candidate['candidate_id']}`")

    # ── Step 2: Available slots ───────────────────────────────
    st.subheader("Step 2 — Choose an Available Slot")

    available = [
        s for s in st.session_state["demo_slots"]
        if s["status"] == "available"
        and (s.get("jd_id") is None or s.get("jd_id") == jd_id)
    ]
    available.sort(key=lambda s: s["slot_start"])

    if not available:
        st.warning(
            "No available slots for this JD. "
            "Go to **Panel Availability → Add Slots** to create some."
        )
        return

    slot_labels = {
        f"{datetime.fromisoformat(s['slot_start']).strftime('%d %b %Y  %H:%M')} – "
        f"{datetime.fromisoformat(s['slot_end']).strftime('%H:%M')}"
        f"   |   {s['panel_name']}": s
        for s in available
    }

    selected_label = st.radio(
        "Pick a slot",
        list(slot_labels.keys()),
        help="Each slot can only be booked once.",
    )
    selected_slot = slot_labels[selected_label]

    notes = st.text_input("Notes (optional)", placeholder="e.g. Candidate confirmed via email")

    # ── Step 3: Confirmation preview ─────────────────────────
    st.subheader("Step 3 — Confirm Booking")

    slot_start = datetime.fromisoformat(selected_slot["slot_start"])
    slot_end   = datetime.fromisoformat(selected_slot["slot_end"])

    st.info(
        f"**Candidate:** {selected_candidate['full_name']}  \n"
        f"**Slot:** {slot_start.strftime('%d %b %Y  %H:%M')} – {slot_end.strftime('%H:%M')}  \n"
        f"**Panel Member:** {selected_slot['panel_name']}  \n"
        f"**JD:** {jd_label}"
    )

    if st.button("Confirm Booking", type="primary", use_container_width=True):
        # Atomic check-and-lock (session state equivalent of UPDATE WHERE status='available')
        slot_obj = next(
            (s for s in st.session_state["demo_slots"] if s["id"] == selected_slot["id"]),
            None,
        )
        if slot_obj is None or slot_obj["status"] != "available":
            st.error("This slot was just taken by another booking — please choose a different slot.")
            st.rerun()
            return

        # Lock the slot
        slot_obj["status"] = "booked"

        # Record booking
        booking = {
            "booking_id":    f"bk-{uuid.uuid4().hex[:6]}",
            "slot_id":       selected_slot["id"],
            "slot_start":    selected_slot["slot_start"],
            "slot_end":      selected_slot["slot_end"],
            "panel_user_id": selected_slot["panel_user_id"],
            "panel_name":    selected_slot["panel_name"],
            "candidate_id":  selected_candidate["candidate_id"],
            "candidate_name": selected_candidate["full_name"],
            "jd_id":         jd_id,
            "booked_at":     datetime.utcnow().isoformat(),
            "notes":         notes or None,
        }
        st.session_state["demo_bookings"].append(booking)

        st.success(
            f"Slot booked!  \n"
            f"**{selected_candidate['full_name']}** — "
            f"{slot_start.strftime('%d %b %Y  %H:%M')} – {slot_end.strftime('%H:%M')}  \n"
            f"Panel: {selected_slot['panel_name']}"
        )
        st.balloons()

        # Show confirmation card
        st.markdown("---")
        st.markdown("### Booking Confirmation")
        c1, c2, c3 = st.columns(3)
        c1.metric("Candidate", selected_candidate["full_name"])
        c2.metric("Date & Time", slot_start.strftime("%d %b  %H:%M"))
        c3.metric("Panel Member", selected_slot["panel_name"])
