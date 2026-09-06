"""DTCK Dashboard (Streamlit) — Phase-0 scaffold.

Landing page only; dashboard modules (market overview, screener, ranking,
stock detail, backtest, system health) arrive with their phases (§29).
"""

from __future__ import annotations

import os

import streamlit as st

st.set_page_config(page_title="DTCK — AI Investment Platform", layout="wide")

api_host = os.getenv("API_HOST", "http://localhost:8000")

st.title("DTCK — AI Investment Research & Decision Intelligence Platform")
st.caption("Vietnam Stock Market · HOSE / HNX / UPCOM · VN30 first")

st.markdown(
    """
    > **AI does not replace investment judgment. AI increases the speed,
    > consistency, depth and traceability of investment research.**

    Pipeline: `DATA → QUANT → BACKTEST → ML → RAG → AI AGENT → EVIDENCE → RISK CONTROL → HUMAN`
    """
)

st.divider()

col_status, col_phase = st.columns(2)

with col_status:
    st.subheader("System Health")
    with st.spinner("Checking API..."):
        try:
            import httpx

            r = httpx.get(f"{api_host}/healthz", timeout=5)
            st.json(r.json())
        except Exception as exc:  # noqa: BLE001 - scaffold, surface any failure
            st.error(f"API not reachable at {api_host}: {exc}")

with col_phase:
    st.subheader("Roadmap (§57)")
    roadmap = [
        "Specification (done)",
        "Database design (docs done; migrations pending)",
        "Repository structure (done)",
        "Data sources & ingestion  ← next",
        "Quant Engine",
        "Backtesting",
        "RAG",
        "AI Agent",
        "ML Prediction",
        "Portfolio Intelligence",
        "Production",
    ]
    for step in roadmap:
        marker = "✅" if "(done)" in step or "← next" in step else "⬜"
        st.markdown(f"{marker} {step.replace(' ← next', ' **(next)**')}")
