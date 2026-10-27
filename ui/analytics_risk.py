"""
InvestMate AI — Risk & Deep Analytics UI Page

Provides:
  • Multi-dimensional risk monitoring (Concentration, Volatility, Drawdown)
  • Sector and Asset Class distribution charts (Plotly)
  • Systematic Investment Plan (SIP) discipline tracking
  • Asset-level risk metrics
"""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from services.risk_analysis import portfolio_risk_report, concentration_risk
from services.portfolio_analytics import (
    allocation_by_type,
    allocation_by_sector,
    top_performers,
    bottom_performers,
    sip_summary,
    portfolio_xirr,
)
from models.portfolio import get_portfolio_summary, list_holdings
from config import get_currency_symbol


def render_analytics_risk(portfolio_id: int) -> None:
    """Render the detailed Risk & Analytics page."""
    sym = get_currency_symbol()
    summary = get_portfolio_summary(portfolio_id)

    if not summary or summary.get("holdings_count", 0) == 0:
        st.info("No holdings found. Please add investments in the Holdings tab first.")
        return

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(79, 70, 229, 0.25) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 16px; padding: 1.4rem 1.8rem; margin-bottom: 1.5rem;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">
            <h2 style="margin: 0; font-size: 1.7rem; font-weight: 800; color: #818cf8;">
                🛡️ Portfolio Risk & Multi-Asset Intelligence
            </h2>
            <p style="margin: 0.25rem 0 0 0; color: #94a3b8; font-size: 0.9rem;">
                Historical volatility, peak-to-trough drawdowns, single-asset/sector concentration limits, and SIP discipline.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["⚠️ Risk Diagnostics", "📊 Asset & Sector Allocation", "🗓️ SIP Analytics"])

    # ── Tab 1: Risk Diagnostics ─────────────────────────────────────
    with tab1:
        st.markdown("#### 🚨 Risk Alerts & Concentration Watch")
        risk_report = portfolio_risk_report(portfolio_id)
        alerts = risk_report.get("concentration_alerts", [])

        if alerts:
            for alert in alerts:
                sev = alert.get("severity", "MEDIUM")
                if sev == "HIGH":
                    st.error(f"🔴 **HIGH RISK:** {alert['message']}")
                else:
                    st.warning(f"🟡 **WARNING:** {alert['message']}")
        else:
            st.success("🟢 **No concentration risks found:** No holding exceeds 25% and no sector exceeds 40%.")

        st.divider()

        # Asset-level risk breakdown table
        st.markdown("#### 🔍 Asset-Level Risk & Volatility Diagnostics")
        asset_risks = risk_report.get("asset_risk_details", []) or risk_report.get("asset_risks", [])
        if asset_risks:
            risk_rows = []
            for ar in asset_risks:
                vol_info = ar.get("volatility") or {}
                dd_info = ar.get("max_drawdown") or {}
                vol_pct = vol_info.get("annualized_vol_pct")
                vol_str = f"{vol_pct:.1f}%" if vol_pct is not None else "N/A"
                dd_pct = dd_info.get("max_drawdown_pct")
                dd_str = f"{dd_pct:.1f}%" if dd_pct is not None else "N/A"
                name_str = ar.get("asset_name") or ar.get("name") or ar.get("ticker", "—")
                risk_rows.append({
                    "Ticker": ar.get("ticker", "—"),
                    "Name": name_str,
                    "Type": ar.get("asset_type", "—"),
                    "Weight": f"{ar.get('weight_pct', ar.get('portfolio_weight_pct', 0)):.1f}%",
                    "Annualized Volatility": vol_str,
                    "Max Drawdown": dd_str,
                })
            st.dataframe(pd.DataFrame(risk_rows), width='stretch')

        st.caption(
            "ℹ️ **Note on Volatility & Drawdown:** Metrics require historical price records. "
            "For assets with limited history, default models or N/A are indicated."
        )

    # ── Tab 2: Asset & Sector Allocation ────────────────────────────
    with tab2:
        col_alloc1, col_alloc2 = st.columns(2)

        # Asset Class Donut
        with col_alloc1:
            st.markdown("##### 🥧 Asset Class Allocation")
            type_res = allocation_by_type(portfolio_id)
            type_alloc = type_res.get("allocation_pct", {})
            if type_alloc:
                df_type = pd.DataFrame([
                    {"Asset Type": k, "Weight": v} for k, v in type_alloc.items()
                ])
                fig_type = px.pie(
                    df_type,
                    names="Asset Type",
                    values="Weight",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Prism,
                )
                fig_type.update_traces(textposition='inside', textinfo='percent+label')
                fig_type.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
                st.plotly_chart(fig_type, width='stretch')

        # Sector Distribution
        with col_alloc2:
            st.markdown("##### 🏢 Sector Exposure Breakdown")
            sector_res = allocation_by_sector(portfolio_id)
            sector_alloc = sector_res.get("allocation_pct", {})
            if sector_alloc:
                df_sector = pd.DataFrame([
                    {"Sector": k, "Weight (%)": v} for k, v in sector_alloc.items()
                ]).sort_values(by="Weight (%)", ascending=True)

                fig_sector = px.bar(
                    df_sector,
                    x="Weight (%)",
                    y="Sector",
                    orientation='h',
                    color="Weight (%)",
                    color_continuous_scale="Viridis",
                )
                fig_sector.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
                st.plotly_chart(fig_sector, width='stretch')

        st.divider()

        # Top vs Bottom Performers
        st.markdown("#### 🏆 Performance Extremes (P&L %)")
        perf_col1, perf_col2 = st.columns(2)

        with perf_col1:
            st.markdown("##### 🟢 Top Performers")
            tops = top_performers(portfolio_id, n=3)
            for t in tops:
                label_name = t.get("asset_name") or t.get("name") or t.get("ticker", "Asset")
                st.metric(
                    label=f"{label_name} ({t['ticker']})",
                    value=f"{sym}{t['market_value']:,.2f}",
                    delta=f"{t['pnl_pct']:+.2f}%",
                )

        with perf_col2:
            st.markdown("##### 🔴 Bottom Performers")
            bottoms = bottom_performers(portfolio_id, n=3)
            for b in bottoms:
                label_name = b.get("asset_name") or b.get("name") or b.get("ticker", "Asset")
                st.metric(
                    label=f"{label_name} ({b['ticker']})",
                    value=f"{sym}{b['market_value']:,.2f}",
                    delta=f"{b['pnl_pct']:+.2f}%",
                )

    # ── Tab 3: SIP Analytics ────────────────────────────────────────
    with tab3:
        st.markdown("#### 🗓️ Systematic Investment Plan (SIP) Discipline")
        sip_data = sip_summary(portfolio_id)

        c1, c2 = st.columns(2)
        c1.metric("Total Cumulative SIP Inflows", f"{sym}{sip_data.get('total_sip_invested', 0):,.2f}")
        c2.metric("Total Executed SIP Installments", f"{sip_data.get('sip_count', 0)}")

        monthly = sip_data.get("monthly_breakdown", {})
        if monthly:
            st.markdown("##### Monthly SIP Contribution Timeline")
            df_sip = pd.DataFrame([
                {"Month": k, "Amount": v} for k, v in sorted(monthly.items())
            ])
            fig_sip = px.bar(
                df_sip,
                x="Month",
                y="Amount",
                title=f"SIP Inflows per Month ({sym})",
                color_discrete_sequence=["#1f77b4"],
            )
            fig_sip.update_layout(margin=dict(t=30, b=10, l=10, r=10))
            st.plotly_chart(fig_sip, width='stretch')
        else:
            st.info("No SIP transactions recorded yet. Record buy transactions with type 'SIP' to track discipline.")

    # Educational Disclaimer Footer
    st.markdown("---")
    st.caption(
        "⚠️ **Disclaimer:** All risk models and analytics provided are strictly for educational decision-support. "
        "They do not constitute financial advice or investment recommendations."
    )
