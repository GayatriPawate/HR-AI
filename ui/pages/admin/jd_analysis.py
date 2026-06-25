import io
import streamlit as st
import json
from ui.components.auth_guard import require_role
from ui.api_client import api_post, api_get


# ── File → plain text extractors ─────────────────────────────

def _text_from_txt(file_bytes: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace")


def _text_from_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        raise ValueError(f"Could not read DOCX: {e}")


def _text_from_excel(file_bytes: bytes) -> str:
    try:
        import pandas as pd
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
        parts = []
        for sheet in xl.sheet_names:
            df = xl.parse(sheet).fillna("")
            parts.append(f"--- Sheet: {sheet} ---")
            parts.append(df.to_string(index=False))
        return "\n".join(parts)
    except Exception as e:
        raise ValueError(f"Could not read Excel: {e}")


def _extract_text(uploaded_file) -> str:
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    raw = uploaded_file.read()
    if ext == "txt":
        return _text_from_txt(raw)
    if ext in ("docx", "doc"):
        return _text_from_docx(raw)
    if ext in ("xlsx", "xls", "csv"):
        if ext == "csv":
            return _text_from_txt(raw)
        return _text_from_excel(raw)
    raise ValueError(f"Unsupported file type: .{ext}")


# ── Result display helper ─────────────────────────────────────

def _show_result(result: dict):
    st.success(f"JD created and analyzed! ID: {result.get('id')}")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Mandatory Skills")
        for s in result.get("mandatory_skills", []):
            st.markdown(f"- ✅ **{s}**")
        st.subheader("Secondary Skills")
        for s in result.get("secondary_skills", []):
            st.markdown(f"- 🔵 {s}")
        st.subheader("Nice to Have")
        for s in result.get("nice_to_have", []):
            st.markdown(f"- ⚪ {s}")
    with col2:
        st.subheader("JD Details")
        st.markdown(f"**Domain:** {result.get('domain') or '—'}")
        st.markdown(f"**Min Experience:** {result.get('min_experience_yrs') or '—'} yrs")
        st.markdown(f"**Status:** {result.get('status') or '—'}")
        soft = result.get("soft_skills") or []
        if soft:
            st.markdown("**Soft Skills:** " + ", ".join(soft))
        st.subheader("Evaluation Rubric")
        rubric = result.get("rubric")
        if rubric:
            if isinstance(rubric, list):
                for cat in rubric:
                    with st.expander(cat.get("category", "Category")):
                        st.write(cat.get("scoring_guide", ""))
            else:
                st.json(rubric)


# ── Main render ───────────────────────────────────────────────

def render(user: dict):
    require_role("admin")
    st.title("Job Description Analysis")

    tab_paste, tab_file, tab_view = st.tabs([
        "✏️ Paste JD Text",
        "📂 Upload File (TXT / DOCX / Excel)",
        "📋 View Existing JDs",
    ])

    # ── Tab 1: paste text (original behaviour) ────────────────
    with tab_paste:
        with st.form("jd_paste_form"):
            title = st.text_input("Job Title", placeholder="e.g. Senior Python Developer")
            raw_text = st.text_area(
                "Paste Job Description",
                height=300,
                placeholder="Paste the full job description here...",
            )
            submitted = st.form_submit_button("Analyze JD", type="primary")

        if submitted:
            if not title or not raw_text:
                st.warning("Please provide both job title and description.")
            else:
                with st.spinner("Analyzing JD with AI..."):
                    result = api_post("/jd/create", json={"title": title, "raw_text": raw_text})
                if result:
                    _show_result(result)

    # ── Tab 2: upload file ────────────────────────────────────
    with tab_file:
        st.caption("Supported formats: **TXT**, **DOCX / DOC**, **XLSX / XLS**, **CSV**")

        uploaded = st.file_uploader(
            "Upload JD file",
            type=["txt", "docx", "doc", "xlsx", "xls", "csv"],
            key="jd_file_upload",
        )

        extracted_text = ""
        if uploaded:
            try:
                extracted_text = _extract_text(uploaded)
                with st.expander("📄 Extracted text preview", expanded=False):
                    st.text(extracted_text[:3000] + ("…" if len(extracted_text) > 3000 else ""))
            except ValueError as e:
                st.error(str(e))
                extracted_text = ""

        with st.form("jd_file_form"):
            file_title = st.text_input(
                "Job Title",
                placeholder="e.g. Senior Python Developer",
                key="jd_file_title",
            )
            # Let HR edit the extracted text before submitting
            editable_text = st.text_area(
                "Extracted JD text (edit if needed)",
                value=extracted_text,
                height=280,
                key="jd_file_text",
            )
            file_submitted = st.form_submit_button("Analyze JD", type="primary")

        if file_submitted:
            if not file_title:
                st.warning("Please enter a job title.")
            elif not editable_text.strip():
                st.warning("No text to analyze. Upload a file or paste text above.")
            else:
                with st.spinner("Analyzing JD with AI..."):
                    result = api_post("/jd/create", json={"title": file_title, "raw_text": editable_text})
                if result:
                    _show_result(result)

    # ── Tab 3: view existing JDs ──────────────────────────────
    with tab_view:
        jds = api_get("/jd/list") or []
        if not jds:
            st.info("No JDs created yet.")
        else:
            for jd in jds:
                with st.expander(f"[ID: {jd['id']}] {jd['title']} — {jd.get('status', '').upper()}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Mandatory Skills:**", ", ".join(jd.get("mandatory_skills") or []))
                        st.write("**Secondary Skills:**", ", ".join(jd.get("secondary_skills") or []))
                        st.write("**Domain:**", jd.get("domain", "—"))
                    with col2:
                        st.write("**Min Experience:**", f"{jd.get('min_experience_yrs', '—')} years")
                        st.write("**Created:**", jd.get("created_at", "—"))
