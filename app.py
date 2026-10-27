"""
InvestMate AI — Intelligent Voice-Enabled Multi-Asset Portfolio Management Agent

Main Streamlit Application Entry Point.
"""

from __future__ import annotations

import streamlit as st

# Must be the very first Streamlit command
st.set_page_config(
    page_title="InvestMate AI — Intelligent Portfolio Intelligence",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import (
    GROQ_AVAILABLE,
    ELEVENLABS_AVAILABLE,
    VOICE_ENABLED,
    LLM_MODEL,
    BASE_CURRENCY,
    get_currency_symbol,
)
from database.db import init_db, seed_real_dataset, fetch_all, fetch_one
from models.portfolio import list_portfolios, create_portfolio, delete_portfolio
from ui.dashboard import render_dashboard
from ui.assistant import render_assistant
from ui.holdings import render_holdings
from ui.transactions import render_transactions
from ui.analytics_risk import render_analytics_risk
from ui.watchlist import render_watchlist
from ui.reports import render_reports


# ──────────────────────────────────────────────────────────────
# Luxury High-Tech Fintech Design System (CSS)
# ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* Main Background with subtle radial light blooms */
    .stApp {
        background: radial-gradient(circle at 10% 10%, rgba(37, 99, 235, 0.08) 0%, transparent 35%),
                    radial-gradient(circle at 90% 90%, rgba(16, 185, 129, 0.06) 0%, transparent 35%),
                    #0A0E17;
        color: #f1f5f9;
    }

    /* Metric Cards Styling */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.85) 0%, rgba(15, 23, 42, 0.7) 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.09) !important;
        border-radius: 16px !important;
        padding: 1.25rem 1.4rem !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        position: relative;
        overflow: hidden;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px) !important;
        border-color: rgba(59, 130, 246, 0.5) !important;
        box-shadow: 0 16px 32px -4px rgba(37, 99, 235, 0.25) !important;
    }
    div[data-testid="stMetric"]::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #3b82f6, #10b981, #6366f1);
    }
    div[data-testid="stMetric"] label {
        font-weight: 700 !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        font-size: 0.72rem !important;
        color: #94a3b8 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-weight: 800 !important;
        color: #f8fafc !important;
        font-size: 1.85rem !important;
        letter-spacing: -0.02em !important;
    }

    /* Primary Buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.2rem !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3) !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(37, 99, 235, 0.5) !important;
        border-color: rgba(255, 255, 255, 0.3) !important;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(15, 23, 42, 0.6);
        padding: 6px;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        padding: 8px 18px !important;
        font-weight: 600 !important;
        color: #94a3b8 !important;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.3) 0%, rgba(16, 185, 129, 0.2) 100%) !important;
        color: #60a5fa !important;
        border: 1px solid rgba(59, 130, 246, 0.4) !important;
    }

    /* Sidebar Luxury Theme */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d121f 0%, #080c15 100%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.07) !important;
    }

    .brand-title {
        font-size: 1.55rem;
        font-weight: 800;
        background: linear-gradient(90deg, #60a5fa 0%, #34d399 50%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.02em;
        margin-bottom: 0.15rem;
    }
    .brand-subtitle {
        font-size: 0.75rem;
        color: #94a3b8;
        font-weight: 500;
        margin-bottom: 1.4rem;
        line-height: 1.3;
    }

    /* Status Badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.28rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 0.45rem;
        width: 100%;
        box-sizing: border-box;
    }
    .badge-online {
        background-color: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .badge-live {
        background-color: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.35);
    }
    .badge-fallback {
        background-color: rgba(245, 158, 11, 0.12);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }

    /* Dataframe tables */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
    }

    /* Streamlit Header (Seamless Dark Glassmorphism) */
    header[data-testid="stHeader"], [data-testid="stHeader"] {
        background: rgba(10, 14, 23, 0.75) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
        color: #f1f5f9 !important;
    }
    header[data-testid="stHeader"] * {
        color: #f1f5f9 !important;
    }

    /* Streamlit Bottom Dock (Chat Input Container) */
    [data-testid="stBottom"], div[data-testid="stBottom"] > div {
        background: rgba(10, 14, 23, 0.85) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.06) !important;
    }

    /* Chat Input Styling */
    div[data-testid="stChatInput"] {
        background-color: #111827 !important;
        border: 1px solid rgba(59, 130, 246, 0.4) !important;
        border-radius: 16px !important;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4) !important;
    }
    div[data-testid="stChatInput"] textarea {
        background-color: transparent !important;
        color: #f8fafc !important;
        font-family: inherit !important;
    }
    div[data-testid="stChatInput"] textarea::placeholder {
        color: #94a3b8 !important;
    }
    div[data-testid="stChatInput"] button {
        background: #2563eb !important;
        color: white !important;
        border-radius: 10px !important;
    }

    /* Audio Input Recording Station Styling */
    div[data-testid="stAudioInput"] {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.25) 0%, rgba(15, 23, 42, 0.7) 100%) !important;
        border: 1px solid rgba(59, 130, 246, 0.35) !important;
        border-radius: 16px !important;
        padding: 0.85rem 1.2rem !important;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3) !important;
    }
    div[data-testid="stAudioInput"] button {
        border-radius: 9999px !important;
        transition: all 0.2s ease !important;
    }

    /* Alert / Warning / Success Banners Styling */
    div[data-testid="stAlert"] {
        background-color: rgba(15, 23, 42, 0.7) !important;
        border-radius: 12px !important;
        border-width: 1px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def ensure_database_initialized() -> None:
    """Initialize DB and seed real Indian market dataset."""
    try:
        init_db()
        users = fetch_all("SELECT id FROM users")
        if not users:
            seed_real_dataset(force=False)
    except Exception as e:
        st.error(f"Database initialization error: {e}")


def main() -> None:
    ensure_database_initialized()

    # ── Sidebar ────────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="brand-title">💎 InvestMate AI</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="brand-subtitle">Voice-Enabled Multi-Asset Wealth Intelligence Agent</div>',
            unsafe_allow_html=True,
        )

        # Active Data Feed Pill
        st.markdown(
            '<div class="status-badge badge-live">📡 Market Feeds: Real NSE & Live AMFI</div>',
            unsafe_allow_html=True,
        )

        # Portfolio Selector
        portfolios = fetch_all("SELECT id, name FROM portfolios ORDER BY id")
        if not portfolios:
            seed_real_dataset(force=True)
            portfolios = fetch_all("SELECT id, name FROM portfolios ORDER BY id")

        port_map = {f"💼 {p['name']} (ID: {p['id']})": p["id"] for p in portfolios}
        port_options = list(port_map.keys())

        # Sync with session state
        default_idx = 0
        if "active_portfolio_id" in st.session_state:
            for idx, pid in enumerate(port_map.values()):
                if pid == st.session_state["active_portfolio_id"]:
                    default_idx = idx
                    break

        selected_label = st.selectbox("Active Portfolio", port_options, index=default_idx)
        active_portfolio_id = port_map[selected_label]
        st.session_state["active_portfolio_id"] = active_portfolio_id

        st.divider()

        # Navigation Menu
        nav_options = [
            "📈 Dashboard",
            "🤖 AI & Voice Assistant",
            "💼 Holdings Management",
            "📒 Transaction Ledger",
            "🛡️ Risk & Analytics",
            "🌐 Market & Prices",
            "📑 Reports & Audit Export",
        ]
        page = st.radio("Navigation", nav_options, index=0)

        st.divider()

        # Engine & Service Status
        st.markdown("##### ⚡ Intelligence Engines")
        if GROQ_AVAILABLE:
            st.markdown(
                f'<div class="status-badge badge-online">🟢 Groq: Qwen 27B & Whisper STT</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-badge badge-fallback">🟡 Groq: Rule-based Fallback</div>',
                unsafe_allow_html=True,
            )

        if ELEVENLABS_AVAILABLE and VOICE_ENABLED:
            st.markdown(
                '<div class="status-badge badge-online">🟢 ElevenLabs Voice: Active</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-badge badge-fallback">⚪ Voice: Disabled</div>',
                unsafe_allow_html=True,
            )

        st.caption(f"Base Currency: **{BASE_CURRENCY} ({get_currency_symbol()})**")

        st.divider()

        # Re-seed demo data & portfolio management
        with st.expander("⚙️ Dataset Settings", expanded=False):
            if st.button("🔄 Reload Real Market Dataset"):
                with st.spinner("Fetching live NSE & AMFI records..."):
                    seed_real_dataset(force=True)
                st.success("Real Indian dataset reloaded successfully!")
                st.rerun()

            st.markdown("---")
            st.markdown("**Create Portfolio**")
            new_port_name = st.text_input("Portfolio Name", placeholder="e.g. Retirement Bluechips", key="create_port_name_input")
            if st.button("➕ Create Portfolio", key="create_port_btn"):
                clean_name = new_port_name.strip()
                if not clean_name:
                    st.warning("Please enter a valid portfolio name.")
                else:
                    try:
                        users = fetch_all("SELECT id FROM users LIMIT 1")
                        uid = users[0]["id"] if users else 1
                        new_p = create_portfolio(uid, clean_name)
                        st.session_state["active_portfolio_id"] = new_p["id"]
                        st.success(f"Portfolio '{clean_name}' created successfully!")
                        st.rerun()
                    except ValueError as ve:
                        st.warning(f"⚠️ {ve}")
                    except Exception as e:
                        st.error(f"Failed to create portfolio: {e}")

            # Option to delete empty/custom portfolios (keeping at least 1 portfolio)
            if len(portfolios) > 1:
                st.markdown("---")
                st.markdown("**Manage Portfolios**")
                deletable = {f"{p['name']} (ID: {p['id']})": p["id"] for p in portfolios}
                del_choice = st.selectbox("Select Portfolio to Delete", list(deletable.keys()), key="del_port_select")
                if st.button("🗑️ Delete Selected Portfolio", key="del_port_btn"):
                    del_id = deletable[del_choice]
                    delete_portfolio(del_id)
                    remaining = [p["id"] for p in portfolios if p["id"] != del_id]
                    if remaining:
                        st.session_state["active_portfolio_id"] = remaining[0]
                    st.success("Portfolio deleted successfully.")
                    st.rerun()

        st.caption("InvestMate AI — Real Multi-Asset Intelligence")

    # ── Page Routing ───────────────────────────────────────────
    if page == "📈 Dashboard":
        render_dashboard(active_portfolio_id)
    elif page == "🤖 AI & Voice Assistant":
        render_assistant(active_portfolio_id)
    elif page == "💼 Holdings Management":
        render_holdings(active_portfolio_id)
    elif page == "📒 Transaction Ledger":
        render_transactions(active_portfolio_id)
    elif page == "🛡️ Risk & Analytics":
        render_analytics_risk(active_portfolio_id)
    elif page == "🌐 Market & Prices":
        render_watchlist()
    elif page == "📑 Reports & Audit Export":
        render_reports(active_portfolio_id)


if __name__ == "__main__":
    main()
