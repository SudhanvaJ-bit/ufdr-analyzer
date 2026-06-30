"""
frontend/api_client.py — Shared HTTP client + session-state helpers for
every page in the Streamlit dashboard.
"""

import requests
import streamlit as st

API_BASE_URL = "http://localhost:8000"


def api_get(path: str, params: dict = None) -> dict | None:
    """GET request to the backend with shared error handling."""
    try:
        response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "⚠️ Can't reach the backend API. Is it running? "
            "Start it with: `uvicorn backend.main:app --reload --port 8000`"
        )
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", "")
        except Exception:
            pass
        st.error(f"⚠️ API error ({e.response.status_code}): {detail or str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Request failed: {e}")
    return None


def api_post(path: str, json_body: dict = None, files: dict = None, data: dict = None) -> dict | None:
    """POST request to the backend with the same shared error handling as api_get."""
    try:
        response = requests.post(
            f"{API_BASE_URL}{path}", json=json_body, files=files, data=data, timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "⚠️ Can't reach the backend API. Is it running? "
            "Start it with: `uvicorn backend.main:app --reload --port 8000`"
        )
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", "")
        except Exception:
            pass
        st.error(f"⚠️ API error ({e.response.status_code}): {detail or str(e)}")
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Request failed: {e}")
    return None


def get_selected_case_id() -> str | None:
    """The case_id the officer is currently working with, or None if
    they haven't selected one yet on the Upload/Cases page."""
    return st.session_state.get("case_id")


def set_selected_case_id(case_id: str, case_name: str = ""):
    st.session_state["case_id"] = case_id
    st.session_state["case_name"] = case_name


def require_case_selected() -> str | None:
    """
    Call at the top of any page that needs an active case. Shows a
    friendly warning and returns None if nothing is selected yet.
    """
    case_id = get_selected_case_id()
    if not case_id:
        st.warning(
            "⚠️ No case selected yet. Go to the **Upload & Cases** page "
            "first and select or upload a case."
        )
        return None
    return case_id


def risk_color(score: float) -> str:
    """Consistent color coding for risk scores across every page."""
    if score >= 3.0:
        return "🔴"
    elif score >= 1.0:
        return "🟠"
    return "🟢"