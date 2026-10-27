"""
InvestMate AI — Agent Tools

Each tool is a deterministic Python function with:
  • A clear name and description
  • Explicit input parameters
  • Structured output (dict)

The LLM never performs calculations — it only interprets tool results.
"""

from __future__ import annotations

import json
from typing import Any

from models.portfolio import list_holdings, get_portfolio_summary
from models.transaction import list_transactions, get_sip_transactions
from services.portfolio_analytics import (
    portfolio_valuation, holding_valuation, allocation_by_type,
    allocation_by_sector, top_performers, bottom_performers,
    largest_holdings, portfolio_xirr, holding_xirr, sip_summary,
    simple_return,
)
from services.risk_analysis import (
    concentration_risk, historical_volatility, maximum_drawdown,
    portfolio_risk_report,
)
from services.market_data import get_data_freshness
from config import logger, get_currency_symbol


# ──────────────────────────────────────────────────────────────
# Tool Definitions (for LLM function-calling and registry)
# ──────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_portfolio_value",
        "description": "Get the total portfolio value including market value, invested capital, cash balance, and overall P&L.",
        "parameters": {"portfolio_id": "int"},
    },
    {
        "name": "get_holdings_list",
        "description": "List all holdings with current prices, quantities, market values, and P&L for each asset.",
        "parameters": {"portfolio_id": "int"},
    },
    {
        "name": "get_allocation",
        "description": "Get portfolio allocation breakdown by asset type (stocks, mutual funds, ETFs, cash).",
        "parameters": {"portfolio_id": "int"},
    },
    {
        "name": "get_sector_allocation",
        "description": "Get portfolio allocation breakdown by sector.",
        "parameters": {"portfolio_id": "int"},
    },
    {
        "name": "get_top_performers",
        "description": "Get the top N holdings by return percentage.",
        "parameters": {"portfolio_id": "int", "n": "int (default 5)"},
    },
    {
        "name": "get_bottom_performers",
        "description": "Get the bottom N holdings by return percentage (worst performers).",
        "parameters": {"portfolio_id": "int", "n": "int (default 5)"},
    },
    {
        "name": "get_largest_holdings",
        "description": "Get the N largest holdings by market value.",
        "parameters": {"portfolio_id": "int", "n": "int (default 5)"},
    },
    {
        "name": "get_portfolio_xirr",
        "description": "Calculate the portfolio's annualized money-weighted return (XIRR) from all transactions.",
        "parameters": {"portfolio_id": "int"},
    },
    {
        "name": "get_concentration_risk",
        "description": "Identify concentration risks — holdings or sectors with unusually high portfolio weight.",
        "parameters": {"portfolio_id": "int"},
    },
    {
        "name": "get_risk_report",
        "description": "Generate a comprehensive risk report with concentration alerts, volatility, and drawdown for all holdings.",
        "parameters": {"portfolio_id": "int"},
    },
    {
        "name": "get_sip_summary",
        "description": "Summarize SIP (Systematic Investment Plan) contributions by month and asset.",
        "parameters": {"portfolio_id": "int"},
    },
    {
        "name": "get_recent_transactions",
        "description": "Get the most recent transactions (buys, sells, SIPs, dividends).",
        "parameters": {"portfolio_id": "int", "limit": "int (default 20)"},
    },
    {
        "name": "get_data_freshness_check",
        "description": "Check how fresh the price data is for all holdings and flag stale data.",
        "parameters": {"portfolio_id": "int"},
    },
]


# ──────────────────────────────────────────────────────────────
# Tool Implementations
# ──────────────────────────────────────────────────────────────

def _safe_execute(func, **kwargs) -> dict:
    """Wrap tool execution with error handling."""
    try:
        return {"success": True, "data": func(**kwargs)}
    except Exception as e:
        logger.error("Tool execution error: %s", e)
        return {"success": False, "error": str(e)}


def get_portfolio_value(portfolio_id: int) -> dict:
    summary = get_portfolio_summary(portfolio_id)
    sym = get_currency_symbol()
    return {
        "portfolio_name": summary.get("portfolio_name", ""),
        "portfolio_value": summary.get("portfolio_value", 0),
        "total_market_value": summary.get("total_market_value", 0),
        "total_invested": summary.get("total_invested", 0),
        "cash_balance": summary.get("cash_balance", 0),
        "total_unrealized_pnl": summary.get("total_unrealized_pnl", 0),
        "total_realized_pnl": summary.get("total_realized_pnl", 0),
        "total_return_pct": summary.get("total_return_pct", 0),
        "holdings_count": summary.get("holdings_count", 0),
        "currency": sym,
    }


def get_holdings_list(portfolio_id: int) -> dict:
    holdings = list_holdings(portfolio_id)
    simplified = []
    for h in holdings:
        simplified.append({
            "ticker": h["ticker"],
            "name": h["asset_name"],
            "type": h["asset_type"],
            "quantity": h["quantity"],
            "avg_cost": h["avg_cost_price"],
            "current_price": h["current_price"],
            "market_value": h["market_value"],
            "unrealized_pnl": h["unrealized_pnl"],
            "pnl_pct": h["pnl_pct"],
            "price_source": h["price_source"],
            "price_date": h["price_date"],
        })
    return {"holdings": simplified, "count": len(simplified)}


def get_allocation(portfolio_id: int) -> dict:
    return allocation_by_type(portfolio_id)


def get_sector_allocation(portfolio_id: int) -> dict:
    return allocation_by_sector(portfolio_id)


def get_top_performers(portfolio_id: int, n: int = 5) -> dict:
    performers = top_performers(portfolio_id, n)
    return {
        "top_performers": [
            {"ticker": p["ticker"], "name": p["asset_name"],
             "pnl_pct": p["pnl_pct"], "unrealized_pnl": p["unrealized_pnl"],
             "market_value": p["market_value"]}
            for p in performers
        ]
    }


def get_bottom_performers(portfolio_id: int, n: int = 5) -> dict:
    performers = bottom_performers(portfolio_id, n)
    return {
        "bottom_performers": [
            {"ticker": p["ticker"], "name": p["asset_name"],
             "pnl_pct": p["pnl_pct"], "unrealized_pnl": p["unrealized_pnl"],
             "market_value": p["market_value"]}
            for p in performers
        ]
    }


def get_largest_holdings(portfolio_id: int, n: int = 5) -> dict:
    holdings = largest_holdings(portfolio_id, n)
    return {
        "largest_holdings": [
            {"ticker": h["ticker"], "name": h["asset_name"],
             "market_value": h["market_value"], "pnl_pct": h["pnl_pct"]}
            for h in holdings
        ]
    }


def get_portfolio_xirr(portfolio_id: int) -> dict:
    rate = portfolio_xirr(portfolio_id)
    return {
        "xirr": rate,
        "xirr_pct": f"{rate * 100:.2f}%" if rate is not None else "N/A",
        "method": "XIRR — annualized money-weighted return from all dated transactions",
        "note": "This accounts for the timing and size of each cash flow.",
    }


def get_concentration_risk(portfolio_id: int) -> dict:
    alerts = concentration_risk(portfolio_id)
    return {
        "alerts": alerts,
        "alert_count": len(alerts),
        "message": (
            f"Found {len(alerts)} concentration risk alert(s)."
            if alerts
            else "No concentration risks detected at current thresholds."
        ),
    }


def get_risk_report(portfolio_id: int) -> dict:
    return portfolio_risk_report(portfolio_id)


def get_sip_summary(portfolio_id: int) -> dict:
    return sip_summary(portfolio_id)


def get_recent_transactions(portfolio_id: int, limit: int = 20) -> dict:
    txns = list_transactions(portfolio_id, limit=limit)
    simplified = []
    for t in txns:
        simplified.append({
            "date": t["txn_date"],
            "type": t["txn_type"],
            "ticker": t.get("ticker", "CASH"),
            "name": t.get("asset_name", "Cash"),
            "quantity": t["quantity"],
            "price": t["price"],
            "amount": t["amount"],
            "fees": t["fees"],
        })
    return {"transactions": simplified, "count": len(simplified)}


def get_data_freshness_check(portfolio_id: int) -> dict:
    holdings = list_holdings(portfolio_id)
    freshness = []
    stale_count = 0
    for h in holdings:
        info = get_data_freshness(h["asset_id"])
        info["ticker"] = h["ticker"]
        freshness.append(info)
        if info.get("stale"):
            stale_count += 1

    return {
        "freshness": freshness,
        "stale_count": stale_count,
        "total_holdings": len(holdings),
        "message": (
            f"⚠️ {stale_count} holding(s) have stale price data."
            if stale_count
            else "All price data is current."
        ),
    }


# ──────────────────────────────────────────────────────────────
# Tool Dispatcher
# ──────────────────────────────────────────────────────────────

TOOL_MAP: dict[str, callable] = {
    "get_portfolio_value": get_portfolio_value,
    "get_holdings_list": get_holdings_list,
    "get_allocation": get_allocation,
    "get_sector_allocation": get_sector_allocation,
    "get_top_performers": get_top_performers,
    "get_bottom_performers": get_bottom_performers,
    "get_largest_holdings": get_largest_holdings,
    "get_portfolio_xirr": get_portfolio_xirr,
    "get_concentration_risk": get_concentration_risk,
    "get_risk_report": get_risk_report,
    "get_sip_summary": get_sip_summary,
    "get_recent_transactions": get_recent_transactions,
    "get_data_freshness_check": get_data_freshness_check,
}


def execute_tool(tool_name: str, portfolio_id: int, **kwargs) -> dict:
    """
    Execute a tool by name with validated arguments.

    Returns: {"success": bool, "data": ..., "error": ...}
    """
    if tool_name not in TOOL_MAP:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    func = TOOL_MAP[tool_name]
    try:
        result = func(portfolio_id=portfolio_id, **kwargs)
        return {"success": True, "tool": tool_name, "data": result}
    except Exception as e:
        logger.error("Tool %s failed: %s", tool_name, e)
        return {"success": False, "tool": tool_name, "error": str(e)}
