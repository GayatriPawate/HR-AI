import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="HR Hiring Platform",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session defaults ───────────────────────────────────────────
for key in ["jwt", "role", "user_id", "name"]:
    if key not in st.session_state:
        st.session_state[key] = None


def get_user():
    if not st.session_state.get("jwt"):
        return None
    return {
        "user_id": st.session_state["user_id"],
        "role":    st.session_state["role"],
        "name":    st.session_state["name"],
        "sub":     st.session_state["user_id"],
    }


def logout():
    for key in ["jwt", "role", "user_id", "name",
                "panel_candidate_id", "panel_jd_id",
                "view_candidate_id", "view_jd_id",
                "generated_questions", "available_slots"]:
        st.session_state[key] = None
    st.rerun()


def _azure_configured() -> bool:
    """Check if MS Graph / Azure credentials are set in environment."""
    return all([
        os.environ.get("AZURE_TENANT_ID", "").strip(),
        os.environ.get("AZURE_CLIENT_ID", "").strip(),
        os.environ.get("AZURE_CLIENT_SECRET", "").strip(),
        os.environ.get("GRAPH_ORGANIZER_EMAIL", "").strip(),
    ])


def _azure_locked_page(title: str, icon: str):
    """Render a greyed-out placeholder for pages that need Azure credentials."""
    st.markdown(
        f"""
        <div style="
            background:#f5f5f5;
            border:1px solid #ddd;
            border-radius:12px;
            padding:40px;
            text-align:center;
            color:#999;
            margin-top:40px;
        ">
            <div style="font-size:3rem;">{icon} 🔒</div>
            <h2 style="color:#bbb; margin:12px 0 8px 0;">{title}</h2>
            <p style="font-size:1rem; color:#aaa;">
                This feature requires <b>Microsoft Azure</b> credentials.<br>
                Add the following to your <code>.env</code> file and restart the app:
            </p>
            <pre style="
                display:inline-block;
                text-align:left;
                background:#eee;
                padding:14px 20px;
                border-radius:8px;
                font-size:0.85rem;
                color:#666;
                margin-top:10px;
            ">AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
GRAPH_ORGANIZER_EMAIL=hr@yourcompany.com</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Not authenticated ──────────────────────────────────────────
user = get_user()
if not user:
    from ui.pages.login import render as render_login
    render_login()
    st.stop()

azure_ok = _azure_configured()

# Pages that need Azure — shown with 🔒 suffix when not configured
_AZURE_PAGES = {
    "🗓️ Schedule Interview",
    "🕐 Panel Availability",
    "📆 Book Interview Slot",
    "📧 Email Interview Invite",
}

def _nav_label(label: str) -> str:
    """Append 🔒 to labels that need Azure when not configured."""
    if not azure_ok and label in _AZURE_PAGES:
        return label + "  🔒"
    return label


# ── Sidebar Navigation ─────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/48/000000/conference-call.png", width=48)
    st.title("HR Platform")
    st.write(f"👤 **{user['name']}**")
    role_badge = "🔑 ADMIN" if user["role"] == "admin" else "👥 PANEL"
    st.caption(role_badge)
    st.divider()

    if user["role"] == "admin":
        admin_pages = [
            "📊 Dashboard",
            "📁 Upload Resumes",
            "📋 JD Analysis",
            "🏆 Candidate Ranking",
            "👤 Candidate Detail",
            "🗓️ Schedule Interview",
            "🕐 Panel Availability",
            "📆 Book Interview Slot",
            "📅 Interview Tracking",
            "📧 Email Interview Invite",
            "📈 Analytics",
            "👥 User Management",
            "🤖 Manager Agent",
        ]
        page_label = st.radio(
            "Navigate",
            [_nav_label(p) for p in admin_pages],
            label_visibility="collapsed",
        )
        # Strip the 🔒 suffix to get the real page name
        page = page_label.replace("  🔒", "")

        if not azure_ok:
            st.caption("🔒 Azure pages require credentials in .env")

    else:
        page_label = st.radio("Navigate", [
            "📋 Assigned Candidates",
            "👤 Candidate Profile",
            "❓ Question Generator",
            "📝 Submit Feedback",
        ], label_visibility="collapsed")
        page = page_label

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        logout()

# ── Page Routing ───────────────────────────────────────────────
if user["role"] == "admin":
    if page == "📊 Dashboard":
        from ui.pages.admin.dashboard import render
        render(user)

    elif page == "📁 Upload Resumes":
        from ui.pages.admin.upload_cv import render
        render(user)

    elif page == "📋 JD Analysis":
        from ui.pages.admin.jd_analysis import render
        render(user)

    elif page == "🏆 Candidate Ranking":
        from ui.pages.admin.ranking import render
        render(user)

    elif page == "👤 Candidate Detail":
        from ui.pages.admin.candidate_detail import render
        render(user)

    elif page == "🗓️ Schedule Interview":
        if not azure_ok:
            _azure_locked_page("Schedule Interview", "🗓️")
        else:
            from ui.pages.admin.scheduling import render
            render(user)

    elif page == "🕐 Panel Availability":
        if not azure_ok:
            _azure_locked_page("Panel Availability", "🕐")
        else:
            from ui.pages.admin.panel_availability import render
            render(user)

    elif page == "📆 Book Interview Slot":
        if not azure_ok:
            _azure_locked_page("Book Interview Slot", "📆")
        else:
            from ui.pages.admin.slot_booking import render
            render(user)

    elif page == "📅 Interview Tracking":
        from ui.pages.admin.interview_tracking import render
        render(user)

    elif page == "📧 Email Interview Invite":
        if not azure_ok:
            _azure_locked_page("Email Interview Invite", "📧")
        else:
            from ui.pages.admin.email_invite import render
            render(user)

    elif page == "📈 Analytics":
        from ui.pages.admin.analytics import render
        render(user)

    elif page == "👥 User Management":
        from ui.pages.admin.user_management import render
        render(user)

    elif page == "🤖 Manager Agent":
        from ui.pages.admin.manager_agent import render
        render(user)

elif user["role"] == "panel":
    if page == "📋 Assigned Candidates":
        from ui.pages.panel.assigned_candidates import render
        render(user)

    elif page == "👤 Candidate Profile":
        from ui.pages.panel.cv_viewer import render
        render(user)

    elif page == "❓ Question Generator":
        from ui.pages.panel.question_generator import render
        render(user)

    elif page == "📝 Submit Feedback":
        from ui.pages.panel.feedback_submission import render
        render(user)
