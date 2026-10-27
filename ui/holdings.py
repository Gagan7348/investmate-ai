"""
InvestMate AI — Holdings Management UI

CRUD interface for managing portfolio holdings:
  • Add new holdings (stocks, mutual funds, ETFs)
  • Edit quantities and prices
  • Remove holdings
  • CSV import
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date

from models.portfolio import list_holdings, get_portfolio
from models.transaction import record_buy, record_sell
from database.db import get_or_create_asset, upsert_price, fetch_all
from services.market_data import (
    import_prices_from_csv, set_manual_price,
    detect_and_parse_csv, import_nse_historical_prices, import_holdings_from_csv,
)
from config import AssetType, PriceSource, get_currency_symbol


def render_holdings(portfolio_id: int) -> None:
    """Render the holdings management page."""
    sym = get_currency_symbol()

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 16px; padding: 1.4rem 1.8rem; margin-bottom: 1.5rem;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">
            <h2 style="margin: 0; font-size: 1.7rem; font-weight: 800; color: #34d399;">
                💼 Multi-Asset Holdings Management
            </h2>
            <p style="margin: 0.25rem 0 0 0; color: #94a3b8; font-size: 0.9rem;">
                Manage NSE equities, AMFI mutual funds, and ETFs with automatic weighted-average cost tracking.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["📊 Current Holdings", "➕ Add Holding", "📤 CSV Import"])

    # ── Current Holdings Tab ───────────────────────────────
    with tab1:
        holdings = list_holdings(portfolio_id)
        if not holdings:
            st.info("No holdings yet. Use the **Add Holding** tab to get started.")
            return

        for h in holdings:
            with st.expander(
                f"**{h['asset_name']}** ({h['ticker']}) — {sym}{h['market_value']:,.2f}",
                expanded=False,
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Type:** {h['asset_type']}")
                    st.write(f"**Quantity:** {h['quantity']:.4f}")
                    st.write(f"**Avg Cost:** {sym}{h['avg_cost_price']:,.2f}")
                with col2:
                    st.write(f"**Current Price:** {sym}{h['current_price']:,.2f}")
                    st.write(f"**Market Value:** {sym}{h['market_value']:,.2f}")
                    arrow = "↑" if h["pnl_pct"] >= 0 else "↓"
                    color = "green" if h["pnl_pct"] >= 0 else "red"
                    st.markdown(
                        f"**P&L:** :{color}[{sym}{h['unrealized_pnl']:,.2f} ({h['pnl_pct']:+.2f}%) {arrow}]"
                    )
                with col3:
                    st.write(f"**Price Source:** {h['price_source']}")
                    st.write(f"**Price Date:** {h['price_date']}")
                    if h.get("sector"):
                        st.write(f"**Sector:** {h['sector']}")

                # Manual price update
                st.markdown("---")
                pcol1, pcol2, pcol3 = st.columns([2, 2, 1])
                with pcol1:
                    new_price = st.number_input(
                        "Update Price",
                        min_value=0.01,
                        value=float(h["current_price"]),
                        key=f"price_{h['asset_id']}",
                    )
                with pcol2:
                    price_date = st.date_input(
                        "Price Date",
                        value=date.today(),
                        key=f"pdate_{h['asset_id']}",
                    )
                with pcol3:
                    st.write("")  # spacing
                    st.write("")
                    if st.button("💾 Update", key=f"update_{h['asset_id']}"):
                        set_manual_price(h["asset_id"], new_price, price_date.isoformat())
                        st.success(f"Price updated for {h['ticker']}")
                        st.rerun()

                # Sell button
                sell_col1, sell_col2, sell_col3 = st.columns([2, 2, 1])
                with sell_col1:
                    sell_qty = st.number_input(
                        "Sell Quantity",
                        min_value=0.0001,
                        max_value=float(h["quantity"]),
                        value=min(1.0, float(h["quantity"])),
                        key=f"sell_qty_{h['asset_id']}",
                    )
                with sell_col2:
                    sell_price = st.number_input(
                        "Sell Price",
                        min_value=0.01,
                        value=float(h["current_price"]),
                        key=f"sell_price_{h['asset_id']}",
                    )
                with sell_col3:
                    st.write("")
                    st.write("")
                    if st.button("📤 Sell", key=f"sell_{h['asset_id']}"):
                        try:
                            record_sell(
                                portfolio_id, h["asset_id"],
                                sell_qty, sell_price, date.today().isoformat(),
                            )
                            st.success(f"Sold {sell_qty:.4f} units of {h['ticker']}")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

    # ── Add Holding Tab ────────────────────────────────────
    with tab2:
        st.markdown("#### Add New Holding")

        with st.form("add_holding_form", clear_on_submit=True):
            acol1, acol2 = st.columns(2)
            with acol1:
                ticker = st.text_input("Ticker / Scheme Code *", placeholder="e.g. RELIANCE.NS")
                asset_name = st.text_input("Asset Name *", placeholder="e.g. Reliance Industries")
                asset_type = st.selectbox("Asset Type *", [AssetType.STOCK, AssetType.MUTUAL_FUND, AssetType.ETF])
            with acol2:
                exchange = st.text_input("Exchange", placeholder="e.g. NSE, BSE, AMFI")
                scheme_code = st.text_input("Scheme Code (MF only)", placeholder="e.g. 119364")
                sector = st.text_input("Sector", placeholder="e.g. IT, Banking")

            bcol1, bcol2, bcol3 = st.columns(3)
            with bcol1:
                quantity = st.number_input("Quantity *", min_value=0.0001, value=1.0, format="%.4f")
            with bcol2:
                buy_price = st.number_input("Purchase Price *", min_value=0.01, value=100.0)
            with bcol3:
                buy_date = st.date_input("Purchase Date *", value=date.today())

            is_sip = st.checkbox("This is a SIP contribution")
            notes = st.text_input("Notes (optional)")

            submitted = st.form_submit_button("➕ Add to Portfolio")
            if submitted:
                if not ticker or not asset_name:
                    st.error("Please fill in all required fields (marked with *).")
                else:
                    asset = get_or_create_asset(
                        ticker.strip().upper(), asset_name.strip(), asset_type,
                        exchange=exchange.strip(), scheme_code=scheme_code.strip(),
                        sector=sector.strip(),
                    )
                    record_buy(
                        portfolio_id, asset["id"], quantity, buy_price,
                        buy_date.isoformat(), is_sip=is_sip, notes=notes,
                    )
                    st.success(f"✅ Added {quantity:.4f} units of {asset_name} @ {sym}{buy_price:,.2f}")
                    st.rerun()

    # ── CSV Import Tab ─────────────────────────────────────
    with tab3:
        st.markdown("#### 📤 Intelligent Multi-Format CSV Importer")
        st.caption(
            "Supports **Official NSE Historical Price downloads** (like NIFTY 50 index / stock EOD files), "
            "**Broker Portfolios** (Zerodha, Groww, Angel One), and standard pricing spreadsheets."
        )

        uploaded = st.file_uploader(
            "Upload CSV File (NSE EOD Quotes, Broker Holdings, or Price Feed)",
            type=["csv"],
            key="csv_upload",
        )

        if uploaded is not None:
            if uploaded.size > 15 * 1024 * 1024:
                st.error("File exceeds maximum allowed size (15 MB).")
            else:
                try:
                    csv_text = uploaded.read().decode("utf-8")
                except UnicodeDecodeError:
                    csv_text = uploaded.read().decode("latin-1")

                detected = detect_and_parse_csv(csv_text, filename=uploaded.name)
                dtype = detected.get("type", "UNKNOWN")

                if dtype == "NSE_HISTORICAL":
                    rows = detected.get("rows", [])
                    st.success(
                        f"🎯 **Detected NSE Historical Market Series:** Found **{len(rows):,} daily quotes** "
                        f"(Date Range: `{detected.get('earliest_date')}` to `{detected.get('latest_date')}` | "
                        f"Latest Close: **{sym}{detected.get('latest_price', 0):,.2f}**)."
                    )

                    # Preview table
                    df_preview = pd.DataFrame(rows[:5])
                    st.markdown("**Data Preview (First 5 records):**")
                    st.dataframe(df_preview, width="stretch")

                    st.markdown("##### ⚙️ Import Configuration")
                    c1, c2, c3 = st.columns([1.2, 1.8, 1])
                    with c1:
                        target_ticker = st.text_input(
                            "Asset Ticker Symbol",
                            value=detected.get("suggested_ticker", "NIFTY 50"),
                        )
                    with c2:
                        target_name = st.text_input(
                            "Asset Display Name",
                            value=detected.get("suggested_name", "NIFTY 50 Index / ETF"),
                        )
                    with c3:
                        target_type = st.selectbox(
                            "Asset Category",
                            options=[AssetType.ETF, AssetType.STOCK, AssetType.MUTUAL_FUND],
                            index=0 if detected.get("suggested_type") == AssetType.ETF else 1,
                        )

                    # Option to also add as a holding
                    add_as_holding = st.checkbox(
                        "➕ Also add as an active holding to this portfolio?",
                        value=True,
                    )
                    hold_qty = 10.0
                    hold_price = float(detected.get("latest_price", 100.0))
                    if add_as_holding:
                        hc1, hc2 = st.columns(2)
                        with hc1:
                            hold_qty = st.number_input(
                                "Holding Quantity (Units)", min_value=0.001, value=10.0, step=1.0
                            )
                        with hc2:
                            hold_price = st.number_input(
                                "Cost Basis / Purchase Price",
                                min_value=0.01,
                                value=float(detected.get("latest_price", 100.0)),
                            )

                    if st.button("📥 Import Historical Data & Update Portfolio", type="primary"):
                        with st.spinner("Importing historical prices and updating assets..."):
                            res = import_nse_historical_prices(
                                csv_text=csv_text,
                                ticker=target_ticker,
                                name=target_name,
                                asset_type=target_type,
                            )
                            if add_as_holding:
                                asset = get_or_create_asset(
                                    target_ticker, target_name, target_type, exchange="NSE"
                                )
                                record_buy(
                                    portfolio_id=portfolio_id,
                                    asset_id=asset["id"],
                                    quantity=hold_qty,
                                    price=hold_price,
                                    txn_date=detected.get("latest_date", date.today().isoformat()),
                                    notes=f"CSV Import from {uploaded.name}",
                                )
                        st.success(
                            f"✅ Successfully imported **{res['imported']:,} historical price records** for `{target_ticker}`! "
                            + (f"Added **{hold_qty} units** to your active portfolio." if add_as_holding else "")
                        )
                        st.rerun()

                elif dtype == "HOLDINGS":
                    rows = detected.get("rows", [])
                    st.success(
                        f"🎯 **Detected Portfolio Holdings / Tradebook:** Found **{len(rows)} positions** ready to import."
                    )
                    st.dataframe(pd.DataFrame(rows[:10]), width="stretch")

                    if st.button("➕ Import All Holdings into Portfolio", type="primary"):
                        with st.spinner("Recording holdings and purchase transactions..."):
                            res = import_holdings_from_csv(csv_text, portfolio_id=portfolio_id)
                        st.success(
                            f"✅ Successfully imported **{res['imported']} holdings** totaling **{sym}{res.get('total_value', 0):,.2f}**!"
                        )
                        st.rerun()

                else:
                    # Generic / Standard
                    st.info("Uploaded generic format. Review preview below:")
                    st.text_area("CSV Content Preview", csv_text[:1500], height=180, disabled=True)
                    if st.button("📥 Import Prices", type="primary"):
                        res = import_prices_from_csv(csv_text)
                        st.success(f"Imported {res['imported']} prices.")
                        if res.get("errors"):
                            st.warning("\n".join(res["errors"][:5]))
                        st.rerun()

        # Download templates
        st.divider()
        st.markdown("##### 📥 Sample Downloadable CSV Templates")
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            sample_holdings_csv = (
                "ticker,name,asset_type,quantity,price,date\n"
                "RELIANCE.NS,Reliance Industries Ltd,STOCK,15,2450.00,2026-01-15\n"
                "NIFTYBEES.NS,Nippon India ETF Nifty 50,ETF,100,250.00,2026-02-10\n"
                "PPFAS_FLEXI,Parag Parikh Flexi Cap Fund,MUTUAL_FUND,500,85.50,2026-03-01\n"
            )
            st.download_button(
                "📄 Download Sample Holdings CSV Template",
                data=sample_holdings_csv,
                file_name="investmate_sample_holdings.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with t_col2:
            sample_nse_csv = (
                "Date,Open,High,Low,Close,Shares Traded,Turnover\n"
                "21-SEP-2026,23330.2,23466.8,23314.8,23414.3,213639227,17770.46\n"
                "18-SEP-2026,23334.7,23389.15,23286.6,23346.4,375346024,31510.28\n"
            )
            st.download_button(
                "📈 Download Sample NSE EOD Prices Template",
                data=sample_nse_csv,
                file_name="sample_nifty_eod.csv",
                mime="text/csv",
                use_container_width=True,
            )
