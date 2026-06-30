"""
frontend/app.py — Main entry point for the UFDR dashboard (Streamlit).
"""

import time
import streamlit as st
from api_client import api_get, api_post, set_selected_case_id, get_selected_case_id

st.set_page_config(
    page_title="UFDR Forensic Intelligence",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 UFDR Forensic Intelligence Platform")
st.caption(
    "AI-based UFDR Analysis Tool — built against SIH Problem ID 25198 "
    "(Ministry of Home Affairs / National Investigation Agency)"
)

st.warning(
    "⚠️ **For authorized investigative use only.** This tool assists "
    "qualified examiners — it does not replace them. All findings must "
    "be independently verified before use in any proceeding. Built and "
    "tested on synthetic data only.",
    icon="⚠️",
)

current_case_id = get_selected_case_id()
if current_case_id:
    st.success(
        f"✅ Active case: **{st.session_state.get('case_name', current_case_id)}** "
        f"(`{current_case_id}`) — use the sidebar to explore Search, Ask AI, "
        f"Link Analysis, and Risk Ranking for this case."
    )

st.divider()

tab_upload, tab_existing = st.tabs(["📤 Upload New Case", "📁 Select Existing Case"])

# ── Tab 1: Upload a new case ────────────────────────────────────────
with tab_upload:
    st.subheader("Upload a UFDR File")
    st.caption("Accepted formats: JSON, ZIP, CSV")

    uploaded_file = st.file_uploader(
        "Choose a UFDR export file", type=["json", "zip", "csv"]
    )
    case_description = st.text_input(
        "Case description (optional)",
        placeholder="e.g. Mumbai cybercrime case — seized device, June 2026",
    )

    if uploaded_file is not None and st.button("🚀 Upload and Process", type="primary"):
        with st.spinner("Uploading file..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            data = {"case_description": case_description}
            result = api_post("/upload/case", files=files, data=data)

        if result and result.get("success"):
            case_id = result["case_id"]
            st.info(f"📋 Upload accepted. Case ID: `{case_id}`. Processing in background...")

            progress_placeholder = st.empty()
            status = "processing"
            max_attempts = 30
            for attempt in range(max_attempts):
                status_result = api_get(f"/upload/case/{case_id}/status")
                if not status_result:
                    break
                status = status_result.get("status", "processing")
                progress_placeholder.write(f"Status: **{status}**  (checked {attempt + 1}x)")
                if status in ("ready", "error"):
                    break
                time.sleep(1)

            if status == "ready":
                st.success(f"✅ Case ready! {status_result.get('case_name')}")
                set_selected_case_id(case_id, status_result.get("case_name", case_id))
                st.balloons()
            elif status == "error":
                st.error(
                    "❌ Processing failed. Check the backend terminal logs "
                    "for the full traceback."
                )
            else:
                st.warning(
                    f"⏳ Still processing after {max_attempts}s. Check the "
                    "**Select Existing Case** tab in a moment — large "
                    "files may take longer than this page waits."
                )

# ── Tab 2: Select an existing case ──────────────────────────────────
with tab_existing:
    st.subheader("Select a Previously Uploaded Case")

    if st.button("🔄 Refresh case list"):
        st.rerun()

    cases_result = api_get("/upload/cases")

    if cases_result and cases_result.get("cases"):
        for case in cases_result["cases"]:
            counts = case.get("record_counts", {})
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                st.write(f"**{case['case_name']}**")
                st.caption(f"`{case['case_id']}` — {case.get('file_name', '')}")

            with col2:
                status_emoji = {"ready": "✅", "processing": "⏳", "error": "❌"}.get(
                    case["status"], "❓"
                )
                st.write(
                    f"{status_emoji} {case['status']} — "
                    f"{counts.get('chats', 0)} chats, "
                    f"{counts.get('calls', 0)} calls, "
                    f"{counts.get('contacts', 0)} contacts"
                )

            with col3:
                disabled = case["status"] != "ready"
                if st.button("Select", key=f"select_{case['case_id']}", disabled=disabled):
                    set_selected_case_id(case["case_id"], case["case_name"])
                    st.success(f"Selected: {case['case_name']}")
                    st.rerun()

            st.divider()
    elif cases_result:
        st.info("No cases uploaded yet. Use the **Upload New Case** tab to get started.")

st.divider()
st.caption(
    "📊 Once a case is selected, use the sidebar to navigate to "
    "**Search**, **Ask AI**, **Link Analysis**, and **Risk Ranking**."
)