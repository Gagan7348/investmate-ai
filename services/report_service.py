"""
InvestMate AI — Report Generation Service

Generates downloadable portfolio reports:
  • CSV exports (holdings, transactions)
  • PDF reports via ReportLab (optional)
  • Summary data matching dashboard figures
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from models.portfolio import list_holdings, get_portfolio_summary, get_portfolio
from models.transaction import list_transactions
from services.portfolio_analytics import (
    portfolio_xirr, allocation_by_type, allocation_by_sector, sip_summary,
)
from services.risk_analysis import concentration_risk
from database.db import execute
from config import get_currency_symbol, logger


def generate_holdings_csv(portfolio_id: int) -> str:
    """Generate CSV text for all holdings."""
    holdings = list_holdings(portfolio_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Ticker", "Asset Name", "Type", "Sector", "Quantity",
        "Avg Cost", "Current Price", "Market Value",
        "Unrealized P&L", "P&L %", "Price Date", "Price Source",
    ])
    for h in holdings:
        writer.writerow([
            h["ticker"], h["asset_name"], h["asset_type"], h.get("sector", ""),
            h["quantity"], h["avg_cost_price"], h["current_price"],
            h["market_value"], h["unrealized_pnl"], h["pnl_pct"],
            h["price_date"], h["price_source"],
        ])
    return output.getvalue()


def generate_transactions_csv(portfolio_id: int) -> str:
    """Generate CSV text for all transactions."""
    txns = list_transactions(portfolio_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date", "Type", "Ticker", "Asset Name", "Quantity",
        "Price", "Amount", "Fees", "Notes",
    ])
    for t in txns:
        writer.writerow([
            t["txn_date"], t["txn_type"], t.get("ticker", "CASH"),
            t.get("asset_name", "Cash"), t["quantity"], t["price"],
            t["amount"], t["fees"], t.get("notes", ""),
        ])
    return output.getvalue()


def generate_report_data(portfolio_id: int) -> dict:
    """
    Compile all report data into a single dict.
    This is the source of truth — the PDF and dashboard must match.
    """
    summary = get_portfolio_summary(portfolio_id)
    alloc = allocation_by_type(portfolio_id)
    sector_alloc = allocation_by_sector(portfolio_id)
    risk_alerts = concentration_risk(portfolio_id)
    sip = sip_summary(portfolio_id)
    xirr_val = portfolio_xirr(portfolio_id)

    report = {
        "report_date": date.today().isoformat(),
        "generated_at": datetime.now().isoformat(),
        "portfolio": summary,
        "allocation_by_type": alloc,
        "allocation_by_sector": sector_alloc,
        "risk_alerts": risk_alerts,
        "sip_summary": sip,
        "portfolio_xirr": f"{xirr_val * 100:.2f}%" if xirr_val is not None else "N/A",
        "methodology": {
            "cost_basis": "Weighted Average Cost",
            "return_metric": "XIRR (annualized, money-weighted)",
            "volatility": "Annualized std-dev of log returns (252 trading days)",
            "drawdown": "Peak-to-trough from available price history",
        },
        "limitations": [
            "Prices may be delayed or simulated — check source labels.",
            "Tax implications are not calculated.",
            "Returns do not account for inflation.",
            "Risk indicators use limited historical data.",
        ],
        "currency_symbol": get_currency_symbol(),
    }

    # Store report in database
    try:
        execute(
            """INSERT INTO reports (portfolio_id, report_type, report_date, data_json)
               VALUES (?, 'SUMMARY', ?, ?)""",
            (portfolio_id, report["report_date"], json.dumps(report, default=str)),
        )
    except Exception as e:
        logger.warning("Could not store report: %s", e)

    return report


def generate_pdf_report(portfolio_id: int) -> bytes | None:
    """
    Generate a formatted PDF report using ReportLab.
    Returns PDF bytes, or None if ReportLab is unavailable.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch, cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    except ImportError:
        logger.warning("ReportLab not installed — PDF export unavailable.")
        return None

    report_data = generate_report_data(portfolio_id)
    summary = report_data["portfolio"]
    sym = report_data["currency_symbol"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle("Title", parent=styles["Title"],
                                  fontSize=20, spaceAfter=12)
    heading_style = ParagraphStyle("Heading2", parent=styles["Heading2"],
                                    fontSize=14, spaceAfter=8, spaceBefore=16)
    normal_style = styles["Normal"]

    elements = []

    # Title
    elements.append(Paragraph("InvestMate AI — Portfolio Report", title_style))
    elements.append(Paragraph(
        f"Report Date: {report_data['report_date']} | "
        f"Portfolio: {summary.get('portfolio_name', 'N/A')}",
        normal_style,
    ))
    elements.append(Spacer(1, 0.3 * inch))

    # Summary table
    elements.append(Paragraph("Portfolio Summary", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Total Portfolio Value", f"{sym}{summary.get('portfolio_value', 0):,.2f}"],
        ["Invested Capital", f"{sym}{summary.get('total_invested', 0):,.2f}"],
        ["Cash Balance", f"{sym}{summary.get('cash_balance', 0):,.2f}"],
        ["Unrealized P&L", f"{sym}{summary.get('total_unrealized_pnl', 0):,.2f}"],
        ["Realized P&L", f"{sym}{summary.get('total_realized_pnl', 0):,.2f}"],
        ["Return %", f"{summary.get('total_return_pct', 0):.2f}%"],
        ["XIRR", report_data.get('portfolio_xirr', 'N/A')],
    ]
    t = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3 * inch))

    # Holdings table
    elements.append(Paragraph("Holdings", heading_style))
    holdings = summary.get("holdings", [])
    h_data = [["Ticker", "Type", "Qty", "Cost", "Price", "Value", "P&L %"]]
    for h in holdings:
        h_data.append([
            h["ticker"], h["asset_type"],
            f"{h['quantity']:.2f}", f"{sym}{h['avg_cost_price']:.2f}",
            f"{sym}{h['current_price']:.2f}", f"{sym}{h['market_value']:,.2f}",
            f"{h['pnl_pct']:+.2f}%",
        ])
    ht = Table(h_data, colWidths=[1.2 * inch, 0.9 * inch, 0.7 * inch,
                                    0.9 * inch, 0.9 * inch, 1 * inch, 0.8 * inch])
    ht.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    elements.append(ht)
    elements.append(Spacer(1, 0.3 * inch))

    # Limitations
    elements.append(Paragraph("Methodology & Limitations", heading_style))
    for lim in report_data.get("limitations", []):
        elements.append(Paragraph(f"• {lim}", normal_style))

    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        "This report is generated for educational purposes only and does not "
        "constitute investment advice.",
        ParagraphStyle("Disclaimer", parent=normal_style, fontSize=8,
                       textColor=colors.grey),
    ))

    doc.build(elements)
    return buffer.getvalue()
