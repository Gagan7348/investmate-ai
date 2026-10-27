"""
InvestMate AI — Portfolio Reports UI Page

Provides:
  • Executive portfolio summary view
  • Downloadable PDF report (ReportLab)
  • Downloadable CSV exports (Holdings & Transactions)
  • Methodology & transparent calculation notes
  • Disclaimers & educational disclosures
"""

from __future__ import annotations

import streamlit as st
import json
from datetime import datetime

from services.report_service import (
    generate_report_data,
    generate_pdf_report,
    generate_holdings_csv,
    generate_transactions_csv,
)
from database.db import fetch_all
from config import get_currency_symbol


def render_reports(portfolio_id: int) -> None:
    """Render the Reports and Audit Export page."""
    sym = get_currency_symbol()

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(168, 85, 247, 0.2) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 16px; padding: 1.4rem 1.8rem; margin-bottom: 1.5rem;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">
            <h2 style="margin: 0; font-size: 1.7rem; font-weight: 800; color: #c084fc;">
                📑 Portfolio Reports & Auditable Exports
            </h2>
            <p style="margin: 0.25rem 0 0 0; color: #94a3b8; font-size: 0.9rem;">
                Downloadable PDF dossiers, verifiable CSV ledgers, mathematical formulas, and academic methodology.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["📄 Executive Summary & Downloads", "📘 Methodology & Formulas", "🗄️ Past Reports Archive"])

    # ── Tab 1: Executive Summary & Downloads ────────────────────────
    with tab1:
        report_data = generate_report_data(portfolio_id)
        summary = report_data.get("portfolio", {})

        if not summary or summary.get("holdings_count", 0) == 0:
            st.info("No holdings in this portfolio yet. Add holdings to generate reports.")
            return

        st.markdown("#### 📊 Portfolio Overview")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Total Market Value", f"{sym}{summary['portfolio_value']:,.2f}")
        m_col2.metric("Total Invested Capital", f"{sym}{summary['total_invested']:,.2f}")
        m_col3.metric("Unrealized P&L", f"{sym}{summary['total_unrealized_pnl']:,.2f}", f"{summary['total_return_pct']:+.2f}%")
        m_col4.metric("Annualized XIRR", report_data.get("portfolio_xirr", "N/A"))

        st.divider()

        st.markdown("#### 📥 Instant Report Downloads")
        d_col1, d_col2, d_col3 = st.columns(3)

        # PDF Report
        with d_col1:
            st.markdown("##### 📄 PDF Portfolio Dossier")
            pdf_bytes = generate_pdf_report(portfolio_id)
            if pdf_bytes:
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"investmate_report_p{portfolio_id}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.caption("PDF generation requires `reportlab`. Install it to download PDF reports.")

        # Holdings CSV
        with d_col2:
            st.markdown("##### 📊 Holdings Data (CSV)")
            holdings_csv = generate_holdings_csv(portfolio_id)
            st.download_button(
                label="⬇️ Download Holdings CSV",
                data=holdings_csv,
                file_name=f"investmate_holdings_p{portfolio_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        # Transactions CSV
        with d_col3:
            st.markdown("##### 📒 Transactions Ledger (CSV)")
            txns_csv = generate_transactions_csv(portfolio_id)
            st.download_button(
                label="⬇️ Download Ledger CSV",
                data=txns_csv,
                file_name=f"investmate_transactions_p{portfolio_id}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.divider()

        # Risk Alerts & Concentration Summary
        st.markdown("#### ⚠️ Concentration & Risk Snapshot")
        risk_alerts = report_data.get("risk_alerts", [])
        if risk_alerts:
            for alert in risk_alerts:
                sev = alert.get("severity", "MEDIUM")
                if sev == "HIGH":
                    st.error(f"**High Concentration Risk:** {alert['message']}")
                else:
                    st.warning(f"**Concentration Warning:** {alert['message']}")
        else:
            st.success("✅ Diversification healthy: No single asset or sector exceeds the configured risk thresholds.")

    # ── Tab 2: Methodology & Calculation Rules ──────────────────────
    with tab2:
        st.markdown("#### 🔬 Analytical Transparency & Methodology")
        st.markdown("""
        InvestMate AI adheres to rigorous standards of financial arithmetic. All calculations are executed by deterministic Python libraries (`pandas`, `numpy`, `scipy`) without LLM approximations.

        ##### 1. Cost Basis: Weighted Average Cost (WAC)
        When additional shares/units are acquired at differing price points, the cost basis updates as follows:
        $$\\text{New Avg Price} = \\frac{(\\text{Old Quantity} \\times \\text{Old Avg Price}) + (\\text{New Quantity} \\times \\text{Purchase Price})}{\\text{Old Quantity} + \\text{New Quantity}}$$

        ##### 2. Realized & Unrealized P&L
        - **Unrealized P&L** = $\\text{Current Quantity} \\times (\\text{Latest Price} - \\text{Weighted Avg Price})$
        - **Realized P&L** = $\\text{Sell Quantity} \\times (\\text{Sell Price} - \\text{Weighted Avg Price}) - \\text{Brokerage/Fees}$

        ##### 3. Money-Weighted Return: XIRR
        InvestMate AI calculates the Exact Internal Rate of Return (XIRR) by solving the root $r$ of the net present value equation for irregular cash flows:
        $$\\sum_{i=1}^{N} \\frac{C_i}{(1 + r)^{\\frac{d_i - d_0}{365}}} = 0$$
        where $C_i$ are net contributions/withdrawals and the terminal portfolio value, and $d_i$ are respective transaction dates.

        ##### 4. Concentration Risk Thresholds
        - **Single Asset Exposure:** Threshold flagged at **25%** (Medium Risk) and **40%** (High Risk).
        - **Single Sector Exposure:** Threshold flagged at **40%** of total portfolio market value.
        """)

    # ── Tab 3: Past Reports Archive ─────────────────────────────────
    with tab3:
        st.markdown("#### 🗄️ Past Reports Archive")
        rows = fetch_all(
            "SELECT id, report_type, report_date, created_at FROM reports WHERE portfolio_id = ? ORDER BY id DESC LIMIT 10",
            (portfolio_id,),
        )
        if not rows:
            st.info("No previously archived reports found for this portfolio.")
        else:
            st.dataframe(rows, width='stretch')

    # Educational Disclaimer Footer
    st.markdown("---")
    st.caption(
        "⚠️ **Disclaimer:** This report is generated strictly for academic, research, and educational review. "
        "Tax implications, STCG/LTCG rules, and inflation adjustments are not modeled."
    )
