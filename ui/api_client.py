import requests
import streamlit as st
from config.settings import get_settings

settings = get_settings()
API_BASE = "http://localhost:8000"


def _headers() -> dict:
    token = st.session_state.get("jwt", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        resp = requests.get(f"{API_BASE}{path}", headers=_headers(), params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API Error {resp.status_code}: {resp.json().get('detail', 'Unknown error')}")
        return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None


def api_post(path: str, json: dict | None = None, files=None, data: dict | None = None) -> dict | None:
    try:
        if files:
            resp = requests.post(f"{API_BASE}{path}", headers=_headers(), files=files, data=data, timeout=120)
        else:
            resp = requests.post(f"{API_BASE}{path}", headers=_headers(), json=json, timeout=120)
        if resp.status_code in (200, 201):
            return resp.json()
        st.error(f"API Error {resp.status_code}: {resp.json().get('detail', 'Unknown error')}")
        return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None


def api_patch(path: str, json: dict) -> dict | None:
    try:
        resp = requests.patch(f"{API_BASE}{path}", headers=_headers(), json=json, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API Error {resp.status_code}: {resp.json().get('detail', 'Unknown error')}")
        return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None


# ── Availability & Slot Booking ───────────────────────────────

def create_availability_slots(panel_user_id: str, slots: list, jd_id: int | None = None) -> dict | None:
    return api_post("/availability/slots", json={
        "panel_user_id": panel_user_id,
        "jd_id": jd_id,
        "slots": slots,
    })


def list_availability_slots(panel_user_id: str | None = None, jd_id: int | None = None, status: str | None = None) -> list | None:
    params = {}
    if panel_user_id:
        params["panel_user_id"] = panel_user_id
    if jd_id:
        params["jd_id"] = jd_id
    if status:
        params["status"] = status
    return api_get("/availability/slots", params=params)


def delete_availability_slot(slot_id: str) -> dict | None:
    try:
        import requests as _req
        resp = _req.delete(f"{API_BASE}/availability/slots/{slot_id}", headers=_headers(), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        import streamlit as _st
        _st.error(f"API Error {resp.status_code}: {resp.json().get('detail', 'Unknown')}")
        return None
    except Exception as e:
        import streamlit as _st
        _st.error(f"Connection error: {e}")
        return None


def book_slot(slot_id: str, candidate_id: str, jd_id: int, interview_id: str | None = None, notes: str | None = None) -> dict | None:
    return api_post("/availability/book", json={
        "slot_id": slot_id,
        "candidate_id": candidate_id,
        "jd_id": jd_id,
        "interview_id": interview_id,
        "notes": notes,
    })


def list_bookings(panel_user_id: str | None = None, jd_id: int | None = None, candidate_id: str | None = None) -> list | None:
    params = {}
    if panel_user_id:
        params["panel_user_id"] = panel_user_id
    if jd_id:
        params["jd_id"] = jd_id
    if candidate_id:
        params["candidate_id"] = candidate_id
    return api_get("/availability/bookings", params=params)


def cancel_booking(booking_id: str) -> dict | None:
    try:
        import requests as _req
        resp = _req.delete(f"{API_BASE}/availability/bookings/{booking_id}", headers=_headers(), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        import streamlit as _st
        _st.error(f"API Error {resp.status_code}: {resp.json().get('detail', 'Unknown')}")
        return None
    except Exception as e:
        import streamlit as _st
        _st.error(f"Connection error: {e}")
        return None


def login(email: str, password: str) -> dict | None:
    try:
        resp = requests.post(f"{API_BASE}/auth/login", json={"email": email, "password": password}, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Cannot reach the backend server. Make sure start.bat is running.")
    except requests.exceptions.Timeout:
        raise TimeoutError("Server is still starting up (loading AI model). Please wait 30 s and try again.")
