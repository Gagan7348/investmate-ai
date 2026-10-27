"""
InvestMate AI — Transactions UI Page

Displays transaction history and allows cash-flow management.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date

from models.transaction import list_transactions, record_cash_in, record_cash_out
from models.portfolio import get_portfolio
from config import get_currency_symbol


def render_transactions(portfolio_id: int) -> None:
    """Render the transactions page."""
    sym = get_currency_symbol()

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 16px; padding: 1.4rem 1.8rem; margin-bottom: 1.5rem;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">
            <h2 style="margin: 0; font-size: 1.7rem; font-weight: 800; color: #fbbf24;">
                📒 Transaction Ledger & Cash Flows
            </h2>
            <p style="margin: 0.25rem 0 0 0; color: #94a3b8; font-size: 0.9rem;">
                Immutable ledger of all BUY, SELL, SIP installments, dividend distributions, and cash deposits.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["📜 All Transactions", "💰 Cash Management"])

    # ── Transaction History ────────────────────────────────
    with tab1:
        txns = list_transactions(portfolio_id)
        if not txns:
            st.info("No transactions recorded yet.")
            return

        table_data = []
        for t in txns:
            type_icons = {
                "BUY": "🟢", "SELL": "🔴", "SIP": "🔵",
                "DIVIDEND": "💰", "CASH_IN": "➕", "CASH_OUT": "➖",
            }
            icon = type_icons.get(t["txn_type"], "•")
            table_data.append({
                "": icon,
                "Date": t["txn_date"],
                "Type": t["txn_type"],
                "Asset": t.get("asset_name", "Cash") or "Cash",
                "Ticker": t.get("ticker", "—") or "—",
                "Quantity": f"{t['quantity']:.4f}" if t["quantity"] else "—",
                "Price": f"{sym}{t['price']:,.2f}" if t["price"] else "—",
                "Amount": f"{sym}{t['amount']:,.2f}",
                "Fees": f"{sym}{t['fees']:,.2f}" if t["fees"] else "—",
                "Notes": t.get("notes", ""),
            })

        df = pd.DataFrame(table_data)

        # Filters
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            type_filter = st.multiselect(
                "Filter by Type",
                options=["BUY", "SELL", "SIP", "DIVIDEND", "CASH_IN", "CASH_OUT"],
                default=[],
                key="txn_type_filter",
            )
        with filter_col2:
            search = st.text_input("Search by asset name", key="txn_search")

        if type_filter:
            df = df[df["Type"].isin(type_filter)]
        if search:
            df = df[df["Asset"].str.contains(search, case=False, na=False)]

        st.dataframe(df, width='stretch', hide_index=True)
        st.caption(f"Showing {len(df)} transaction(s)")

    # ── Cash Management ────────────────────────────────────
    with tab2:
        portfolio = get_portfolio(portfolio_id)
        if portfolio:
            st.metric("Current Cash Balance", f"{sym}{portfolio['cash_balance']:,.2f}")

        st.markdown("---")

        ccol1, ccol2 = st.columns(2)

        with ccol1:
            st.markdown("#### ➕ Add Cash")
            with st.form("cash_in_form"):
                cash_in_amount = st.number_input("Amount", min_value=0.01, value=10000.0, key="cash_in_amt")
                cash_in_date = st.date_input("Date", value=date.today(), key="cash_in_date")
                cash_in_notes = st.text_input("Notes", key="cash_in_notes", placeholder="e.g. Salary credit")
                if st.form_submit_button("➕ Add Cash"):
                    record_cash_in(portfolio_id, cash_in_amount, cash_in_date.isoformat(), cash_in_notes)
                    st.success(f"Added {sym}{cash_in_amount:,.2f} to cash balance")
                    st.rerun()

        with ccol2:
            st.markdown("#### ➖ Withdraw Cash")
            with st.form("cash_out_form"):
                cash_out_amount = st.number_input("Amount", min_value=0.01, value=5000.0, key="cash_out_amt")
                cash_out_date = st.date_input("Date", value=date.today(), key="cash_out_date")
                cash_out_notes = st.text_input("Notes", key="cash_out_notes", placeholder="e.g. Withdrawal")
                if st.form_submit_button("➖ Withdraw Cash"):
                    record_cash_out(portfolio_id, cash_out_amount, cash_out_date.isoformat(), cash_out_notes)
                    st.success(f"Withdrew {sym}{cash_out_amount:,.2f} from cash balance")
                    st.rerun()
