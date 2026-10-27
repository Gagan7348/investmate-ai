"""
InvestMate AI — Portfolio Analytics Service

All financial calculations live here — deterministic Python, never LLM-generated.

Calculations:
  • Market value, unrealized/realized P&L
  • Holding-period return (simple)
  • XIRR for dated cash-flow sequences
  • Allocation percentages
  • Top/bottom performers
  • Monthly SIP summary
"""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

import numpy as np
from scipy.optimize import brentq

from models.portfolio import list_holdings, get_portfolio_summary, get_portfolio
from models.transaction import list_transactions, list_transactions_for_asset, get_sip_transactions
from config import logger


# ──────────────────────────────────────────────────────────────
# Valuation
# ──────────────────────────────────────────────────────────────

def portfolio_valuation(portfolio_id: int) -> dict:
    """Full portfolio valuation — wrapper around model summary."""
    return get_portfolio_summary(portfolio_id)


def holding_valuation(portfolio_id: int, asset_id: int) -> dict | None:
    """Valuation for a single holding."""
    holdings = list_holdings(portfolio_id)
    for h in holdings:
        if h["asset_id"] == asset_id:
            return h
    return None


# ──────────────────────────────────────────────────────────────
# Returns
# ──────────────────────────────────────────────────────────────

def simple_return(cost: float, current: float) -> float:
    """Simple holding-period return percentage."""
    if cost <= 0:
        return 0.0
    return round(((current - cost) / cost) * 100, 2)


def xirr(cash_flows: list[tuple[date, float]], guess: float = 0.1) -> float | None:
    """
    Calculate XIRR (extended internal rate of return) for a series of
    dated cash flows.

    cash_flows: list of (date, amount) where outflows are negative and
                inflows are positive.

    Returns annualized rate as a decimal (e.g. 0.12 = 12%), or None if
    it cannot be solved.
    """
    if len(cash_flows) < 2:
        return None

    # Sort by date
    cash_flows = sorted(cash_flows, key=lambda x: x[0])
    d0 = cash_flows[0][0]

    def npv(rate):
        return sum(
            amount / ((1 + rate) ** ((d - d0).days / 365.25))
            for d, amount in cash_flows
        )

    try:
        return round(brentq(npv, -0.99, 10.0, maxiter=200), 6)
    except (ValueError, RuntimeError):
        logger.warning("XIRR did not converge for %d cash flows", len(cash_flows))
        return None


def portfolio_xirr(portfolio_id: int) -> float | None:
    """
    Compute portfolio-level XIRR from all transactions plus current value.

    Convention:
      • Buys / SIPs / CASH_IN  → negative (money going out of pocket)
      • Sells / CASH_OUT        → positive (money coming back)
      • Current value today      → positive (terminal value)
    """
    txns = list_transactions(portfolio_id, limit=10000)
    if not txns:
        return None

    flows: list[tuple[date, float]] = []
    for t in txns:
        d = datetime.fromisoformat(t["txn_date"]).date() if isinstance(t["txn_date"], str) else t["txn_date"]
        if t["txn_type"] in ("BUY", "SIP", "CASH_IN"):
            flows.append((d, -t["amount"]))
        elif t["txn_type"] in ("SELL", "CASH_OUT", "DIVIDEND"):
            flows.append((d, t["amount"]))

    # Terminal value = current market value + cash
    summary = get_portfolio_summary(portfolio_id)
    if summary:
        flows.append((date.today(), summary["portfolio_value"]))

    return xirr(flows)


def holding_xirr(portfolio_id: int, asset_id: int) -> float | None:
    """Compute XIRR for a single holding."""
    txns = list_transactions_for_asset(portfolio_id, asset_id)
    if not txns:
        return None

    flows: list[tuple[date, float]] = []
    for t in txns:
        d = datetime.fromisoformat(t["txn_date"]).date()
        if t["txn_type"] in ("BUY", "SIP"):
            flows.append((d, -t["amount"]))
        elif t["txn_type"] in ("SELL", "DIVIDEND"):
            flows.append((d, t["amount"]))

    # Current value
    from models.portfolio import list_holdings as _lh
    holdings = _lh(portfolio_id)
    for h in holdings:
        if h["asset_id"] == asset_id:
            flows.append((date.today(), h["market_value"]))
            break

    return xirr(flows)


# ──────────────────────────────────────────────────────────────
# Allocation Analysis
# ──────────────────────────────────────────────────────────────

def allocation_by_type(portfolio_id: int) -> dict:
    """Return allocation breakdown by asset type (amounts and percentages)."""
    summary = get_portfolio_summary(portfolio_id)
    return {
        "allocation": summary.get("allocation", {}),
        "allocation_pct": summary.get("allocation_pct", {}),
        "portfolio_value": summary.get("portfolio_value", 0),
    }


def allocation_by_sector(portfolio_id: int) -> dict:
    """Return allocation breakdown by sector."""
    holdings = list_holdings(portfolio_id)
    sector_map: dict[str, float] = {}
    total = 0.0
    for h in holdings:
        sector = h.get("sector", "Unknown") or "Unknown"
        sector_map[sector] = sector_map.get(sector, 0) + h["market_value"]
        total += h["market_value"]

    pct_map = {}
    if total > 0:
        pct_map = {k: round(v / total * 100, 2) for k, v in sector_map.items()}

    return {"allocation": sector_map, "allocation_pct": pct_map, "total": total}


# ──────────────────────────────────────────────────────────────
# Performance Ranking
# ──────────────────────────────────────────────────────────────

def top_performers(portfolio_id: int, n: int = 5, limit: int | None = None) -> list[dict]:
    """Top N holdings by unrealized P&L percentage."""
    count = limit if limit is not None else n
    holdings = list_holdings(portfolio_id)
    sorted_h = sorted(holdings, key=lambda h: h["pnl_pct"], reverse=True)
    return sorted_h[:count]


def bottom_performers(portfolio_id: int, n: int = 5, limit: int | None = None) -> list[dict]:
    """Bottom N holdings by unrealized P&L percentage."""
    count = limit if limit is not None else n
    holdings = list_holdings(portfolio_id)
    sorted_h = sorted(holdings, key=lambda h: h["pnl_pct"])
    return sorted_h[:count]


def largest_holdings(portfolio_id: int, n: int = 5, limit: int | None = None) -> list[dict]:
    """Top N holdings by market value."""
    count = limit if limit is not None else n
    holdings = list_holdings(portfolio_id)
    sorted_h = sorted(holdings, key=lambda h: h["market_value"], reverse=True)
    return sorted_h[:count]


# ──────────────────────────────────────────────────────────────
# SIP Analysis
# ──────────────────────────────────────────────────────────────

def sip_summary(portfolio_id: int) -> dict:
    """Summarize SIP contributions by month and asset."""
    sips = get_sip_transactions(portfolio_id)
    monthly: dict[str, float] = {}
    by_asset: dict[str, float] = {}
    total = 0.0

    for s in sips:
        month_key = s["txn_date"][:7]  # YYYY-MM
        monthly[month_key] = monthly.get(month_key, 0) + s["amount"]
        aname = s.get("asset_name", s.get("ticker", "Unknown"))
        by_asset[aname] = by_asset.get(aname, 0) + s["amount"]
        total += s["amount"]

    return {
        "total_sip_invested": round(total, 2),
        "monthly_breakdown": monthly,
        "by_asset": by_asset,
        "sip_count": len(sips),
    }
