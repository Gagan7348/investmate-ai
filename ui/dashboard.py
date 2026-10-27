"""
InvestMate AI — Dashboard UI Page

Professional financial dashboard with:
  • KPI cards (portfolio value, P&L, returns)
  • Interactive allocation charts (Plotly)
  • Holdings table with P&L coloring
  • Data freshness warnings
"""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from models.portfolio import get_portfolio_summary, list_holdings
from services.portfolio_analytics import (
    portfolio_xirr, allocation_by_type, allocation_by_sector,
)
from services.risk_analysis import concentration_risk
from services.market_data import refresh_all_prices
from config import get_currency_symbol


def render_dashboard(portfolio_id: int) -> None:
    """Render the main dashboard page."""
    sym = get_currency_symbol()
    summary = get_portfolio_summary(portfolio_id)

    if not summary or summary["holdings_count"] == 0:
        st.info("📭 No holdings found. Go to **Holdings** to add your first investment.")
        return

    # ── Executive Hero Banner ──────────────────────────────
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(30, 58, 138, 0.25) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 16px; padding: 1.4rem 1.8rem; margin-bottom: 1.5rem;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <span style="display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 0.75rem; font-weight: 700; border: 1px solid rgba(16, 185, 129, 0.3); margin-bottom: 0.4rem;">
                        🟢 LIVE NSE & AMFI DATASET
                    </span>
                    <h2 style="margin: 0; font-size: 1.8rem; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em;">
                        Portfolio Overview & Financial Analytics
                    </h2>
                    <p style="margin: 0.25rem 0 0 0; color: #94a3b8; font-size: 0.9rem;">
                        Real bluechips, mutual fund schemes, and index ETFs verified deterministically without LLM approximations.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── KPI Cards ──────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Portfolio Value",
            value=f"{sym}{summary['portfolio_value']:,.2f}",
        )
    with col2:
        st.metric(
            label="Invested Capital",
            value=f"{sym}{summary['total_invested']:,.2f}",
        )
    with col3:
        unrealized = summary["total_unrealized_pnl"]
        st.metric(
            label="Unrealized P&L",
            value=f"{sym}{unrealized:,.2f}",
            delta=f"{summary['total_return_pct']:+.2f}%",
        )
    with col4:
        st.metric(
            label="Realized P&L",
            value=f"{sym}{summary['total_realized_pnl']:,.2f}",
        )

    # Second row of metrics
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric(label="Available Cash Balance", value=f"{sym}{summary['cash_balance']:,.2f}")
    with col6:
        st.metric(label="Active Asset Holdings", value=str(summary["holdings_count"]))
    with col7:
        xirr_val = portfolio_xirr(portfolio_id)
        xirr_display = f"{xirr_val * 100:.2f}%" if xirr_val is not None else "N/A"
        st.metric(label="Annualized Return (XIRR)", value=xirr_display)
    with col8:
        alerts = concentration_risk(portfolio_id)
        alert_count = len(alerts)
        st.metric(
            label="Concentration Alerts",
            value=str(alert_count),
            delta="⚠️ Check Alerts" if alert_count > 0 else "✅ Well Diversified",
            delta_color="inverse" if alert_count > 0 else "off",
        )

    st.divider()

    # ── Charts ─────────────────────────────────────────────
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("#### 🥧 Asset Class Allocation")
        alloc = summary["allocation"]
        if alloc:
            labels_map = {
                "STOCK": "Equities (NSE)", "MUTUAL_FUND": "Mutual Funds (AMFI)",
                "ETF": "ETFs", "CASH": "Liquid Cash",
            }
            palette = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"]
            fig = go.Figure(data=[go.Pie(
                labels=[labels_map.get(k, k) for k in alloc.keys()],
                values=list(alloc.values()),
                hole=0.55,
                marker=dict(colors=palette, line=dict(color='#0b0f19', width=2)),
                textinfo="label+percent",
                textposition="outside",
            )])
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, font=dict(color="#cbd5e1")),
                margin=dict(t=20, b=40, l=20, r=20),
                height=350,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Plus Jakarta Sans, sans-serif", color="#e2e8f0"),
            )
            st.plotly_chart(fig, width='stretch')

    with chart_col2:
        st.markdown("#### 🏢 Sector Exposure Breakdown")
        sector_data = allocation_by_sector(portfolio_id)
        sector_alloc = sector_data.get("allocation", {})
        if sector_alloc:
            sec_palette = ["#6366f1", "#ec4899", "#14b8a6", "#f97316", "#06b6d4", "#a855f7", "#84cc16"]
            fig2 = go.Figure(data=[go.Pie(
                labels=list(sector_alloc.keys()),
                values=list(sector_alloc.values()),
                hole=0.55,
                marker=dict(colors=sec_palette, line=dict(color='#0b0f19', width=2)),
                textinfo="label+percent",
                textposition="outside",
            )])
            fig2.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, font=dict(color="#cbd5e1")),
                margin=dict(t=20, b=40, l=20, r=20),
                height=350,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Plus Jakarta Sans, sans-serif", color="#e2e8f0"),
            )
            st.plotly_chart(fig2, width='stretch')

    st.divider()

    # ── Holdings Performance Bar Chart ─────────────────────
    st.markdown("#### Holdings Performance (%)")
    holdings = summary["holdings"]
    if holdings:
        df = pd.DataFrame(holdings)
        df = df.sort_values("pnl_pct", ascending=True)
        colors = ["#FF4B4B" if v < 0 else "#00CC66" for v in df["pnl_pct"]]

        fig3 = go.Figure(data=[go.Bar(
            x=df["pnl_pct"],
            y=df["ticker"],
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.2f}%" for v in df["pnl_pct"]],
            textposition="outside",
        )])
        fig3.update_layout(
            xaxis_title="Return (%)",
            yaxis_title="",
            height=max(300, len(holdings) * 40),
            margin=dict(t=10, b=30, l=120, r=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig3, width='stretch')

    st.divider()

    # ── Holdings Table ─────────────────────────────────────
    st.markdown("#### 📋 Holdings Detail")
    if holdings:
        table_data = []
        for h in holdings:
            arrow = "↑" if h["pnl_pct"] >= 0 else "↓"
            table_data.append({
                "Ticker": h["ticker"],
                "Name": h["asset_name"],
                "Type": h["asset_type"],
                "Qty": f"{h['quantity']:.2f}",
                "Avg Cost": f"{sym}{h['avg_cost_price']:,.2f}",
                "Price": f"{sym}{h['current_price']:,.2f}",
                "Value": f"{sym}{h['market_value']:,.2f}",
                "P&L": f"{sym}{h['unrealized_pnl']:,.2f} {arrow}",
                "Return %": f"{h['pnl_pct']:+.2f}%",
                "Source": h["price_source"],
            })
        st.dataframe(pd.DataFrame(table_data), width='stretch', hide_index=True)

    # ── Risk Alerts ────────────────────────────────────────
    if alerts:
        st.markdown("#### ⚠️ Risk Alerts")
        for alert in alerts:
            severity_icon = "🔴" if alert["severity"] == "HIGH" else "🟡"
            st.warning(f"{severity_icon} {alert['message']}")

    # ── Data Freshness ─────────────────────────────────────
    stale_holdings = [h for h in holdings if h.get("price_source") == "SIMULATED"]
    if stale_holdings:
        st.caption(
            "⚠️ Some prices are **simulated sample data**. "
            "Use the refresh button or enter manual prices for accuracy."
        )

    # ── Refresh Button ─────────────────────────────────────
    st.divider()
    if st.button("🔄 Refresh Market Prices", key="refresh_prices"):
        with st.spinner("Fetching latest prices..."):
            result = refresh_all_prices(portfolio_id)
            if result["updated"]:
                st.success(f"Updated: {', '.join(result['updated'])}")
            if result["failed"]:
                st.warning(f"Could not update: {', '.join(result['failed'])}")
            st.rerun()
