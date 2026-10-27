"""
InvestMate AI — Market Data & Price Watch UI Page

Provides:
  • Real-time / delayed price lookup for Indian assets
  • AMFI Indian Mutual Fund live NAV search
  • Asset price updater (Manual, AMFI, CSV)
  • Price freshness monitor with data source transparency
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date

from database.db import fetch_all
from services.market_data import (
    fetch_amfi_nav,
    set_manual_price,
    refresh_all_asset_prices,
    get_all_assets_freshness,
)
from config import get_currency_symbol, PriceSource


def render_watchlist() -> None:
    """Render the Market Data & Price Freshness page."""
    sym = get_currency_symbol()

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(14, 165, 233, 0.2) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 16px; padding: 1.4rem 1.8rem; margin-bottom: 1.5rem;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">
            <h2 style="margin: 0; font-size: 1.7rem; font-weight: 800; color: #38bdf8;">
                🌐 Market Pricing & Live Feeds
            </h2>
            <p style="margin: 0.25rem 0 0 0; color: #94a3b8; font-size: 0.9rem;">
                Official AMFI mutual fund scheme query endpoint, live NSE price feeds, and data freshness metrics.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["📋 Tracked Assets & Freshness", "🔍 AMFI Mutual Fund NAV Lookup", "✏️ Update Asset Price"])

    # ── Tab 1: Tracked Assets & Freshness ───────────────────────────
    with tab1:
        st.markdown("#### 📊 Asset Price Directory")
        assets = fetch_all(
            """SELECT a.id, a.ticker, a.name, a.asset_type, a.exchange, a.scheme_code, a.sector,
                      p.price, p.price_date, p.source, p.retrieved_at
               FROM assets a
               LEFT JOIN (
                   SELECT asset_id, price, price_date, source, retrieved_at,
                          ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY price_date DESC, id DESC) as rn
                   FROM price_history
               ) p ON a.id = p.asset_id AND p.rn = 1
               ORDER BY a.asset_type, a.ticker"""
        )

        if not assets:
            st.info("No assets registered in the database yet. Add holdings to register assets.")
            return

        table_data = []
        for a in assets:
            price_val = f"{sym}{a['price']:,.2f}" if a["price"] else "N/A"
            source_badge = a["source"] or "None"
            table_data.append({
                "Ticker": a["ticker"],
                "Name": a["name"],
                "Type": a["asset_type"],
                "Exchange": a["exchange"] or "—",
                "Sector": a["sector"] or "—",
                "Latest Price": price_val,
                "Price Date": a["price_date"] or "—",
                "Source": source_badge,
            })

        st.dataframe(pd.DataFrame(table_data), width="stretch")

        st.divider()

        # Data Freshness Check
        st.markdown("#### 🔄 Price Freshness Status")
        freshness = get_all_assets_freshness()
        f_col1, f_col2, f_col3 = st.columns(3)
        f_col1.metric("Total Assets", freshness.get("total_assets", 0))
        f_col2.metric("Assets with Prices", freshness.get("priced_assets", 0))
        f_col3.metric("Stale Prices (>3 days)", freshness.get("stale_count", 0))

        if freshness.get("stale_assets"):
            st.warning(f"⚠️ Stale assets detected: {', '.join(freshness['stale_assets'])}")

        if st.button("🔄 Refresh All Prices (Live Feeds)"):
            with st.spinner("Refreshing price feeds..."):
                res = refresh_all_asset_prices()
                st.success(f"Refresh completed: {res.get('updated', 0)} prices updated. ({res.get('failed', 0)} failed)")
                st.rerun()

    # ── Tab 2: AMFI Mutual Fund NAV Lookup ──────────────────────────
    with tab2:
        st.markdown("#### 🇮🇳 Live AMFI Mutual Fund NAV Search")
        st.caption("Query the official Association of Mutual Funds in India (AMFI) NAV database using the 6-digit scheme code.")

        sc_col1, sc_col2 = st.columns([3, 1])
        with sc_col1:
            scheme_code_input = st.text_input("Enter AMFI Scheme Code (e.g. 120503, 118834, 119551)", value="120503")
        with sc_col2:
            st.write("")
            st.write("")
            search_btn = st.button("🔍 Search AMFI", key="amfi_search_btn")

        if search_btn or scheme_code_input:
            with st.spinner("Fetching from AMFI India..."):
                amfi_res = fetch_amfi_nav(scheme_code_input.strip())
                if amfi_res:
                    st.success("✅ Scheme Found in AMFI Records!")
                    st.json(amfi_res)
                    st.metric(
                        label=amfi_res.get("scheme_name", "Mutual Fund NAV"),
                        value=f"{sym}{amfi_res.get('nav', 0):,.4f}",
                        delta=f"Date: {amfi_res.get('nav_date')}",
                    )
                else:
                    st.error(f"Scheme code '{scheme_code_input}' not found in AMFI live feed.")

    # ── Tab 3: Update Asset Price ───────────────────────────────────
    with tab3:
        st.markdown("#### ✏️ Set / Override Asset Price")
        asset_options = {f"{a['ticker']} — {a['name']} ({a['asset_type']})": a["id"] for a in assets}

        if asset_options:
            selected_label = st.selectbox("Select Asset to Price", list(asset_options.keys()))
            selected_asset_id = asset_options[selected_label]

            p_col1, p_col2 = st.columns(2)
            with p_col1:
                new_price = st.number_input("Enter New Price", min_value=0.01, value=100.0, step=0.5)
            with p_col2:
                new_date = st.date_input("Price As Of Date", value=date.today())

            if st.button("💾 Save Updated Price", key="save_price_btn"):
                set_manual_price(selected_asset_id, float(new_price), new_date.isoformat())
                st.success(f"Price updated successfully to {sym}{new_price:,.2f} on {new_date}!")
                st.rerun()

    # Educational Disclaimer Footer
    st.markdown("---")
    st.caption(
        "⚠️ **InvestMate AI Pricing Transparency:** Quotes are obtained from open AMFI text endpoints or local inputs. "
        "Intraday prices are not real-time tick feeds. All valuations are for academic decision-support."
    )
