"""
InvestMate AI — Risk Analysis Service

Transparent, educational risk indicators:
  • Concentration risk (single-asset and sector)
  • Historical volatility (annualized std-dev of daily returns)
  • Maximum drawdown
  • Benchmark comparison (when data available)

Every flag includes threshold, evidence, and a disclaimer that historical
metrics are not predictions.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Optional

import numpy as np

from models.portfolio import list_holdings, get_portfolio_summary
from database.db import fetch_all
from config import logger


# ──────────────────────────────────────────────────────────────
# Thresholds (configurable)
# ──────────────────────────────────────────────────────────────
CONCENTRATION_WARN_PCT = 25.0   # single-asset % of portfolio
SECTOR_CONCENTRATION_WARN_PCT = 40.0   # single-sector % of portfolio
MIN_PRICE_HISTORY_DAYS = 30  # minimum data points for vol/drawdown


def concentration_risk(portfolio_id: int) -> list[dict]:
    """
    Flag holdings or sectors whose weight exceeds the configured thresholds.
    Returns a list of alert dicts.
    """
    summary = get_portfolio_summary(portfolio_id)
    if not summary or summary["portfolio_value"] <= 0:
        return []

    alerts: list[dict] = []
    total = summary["portfolio_value"]

    # Per-holding concentration
    for h in summary["holdings"]:
        weight = h["market_value"] / total * 100
        if weight >= CONCENTRATION_WARN_PCT:
            alerts.append({
                "type": "HOLDING_CONCENTRATION",
                "severity": "HIGH" if weight >= 40 else "MEDIUM",
                "asset": h["ticker"],
                "asset_name": h["asset_name"],
                "weight_pct": round(weight, 2),
                "threshold_pct": CONCENTRATION_WARN_PCT,
                "message": (
                    f"{h['asset_name']} ({h['ticker']}) represents {weight:.1f}% of your "
                    f"portfolio, exceeding the {CONCENTRATION_WARN_PCT}% concentration threshold. "
                    f"Consider whether this level of exposure aligns with your risk tolerance."
                ),
                "disclaimer": "This is an educational observation, not investment advice.",
            })

    # Sector concentration
    sector_values: dict[str, float] = {}
    for h in summary["holdings"]:
        sector = h.get("sector", "Unknown") or "Unknown"
        sector_values[sector] = sector_values.get(sector, 0) + h["market_value"]

    for sector, value in sector_values.items():
        weight = value / total * 100
        if weight >= SECTOR_CONCENTRATION_WARN_PCT:
            alerts.append({
                "type": "SECTOR_CONCENTRATION",
                "severity": "HIGH" if weight >= 60 else "MEDIUM",
                "sector": sector,
                "weight_pct": round(weight, 2),
                "threshold_pct": SECTOR_CONCENTRATION_WARN_PCT,
                "message": (
                    f"The '{sector}' sector represents {weight:.1f}% of your portfolio, "
                    f"exceeding the {SECTOR_CONCENTRATION_WARN_PCT}% sector threshold."
                ),
                "disclaimer": "Sector classification is approximate.",
            })

    return alerts


def historical_volatility(asset_id: int) -> dict:
    """
    Compute annualized historical volatility from daily price history.

    Returns:
      daily_vol, annualized_vol, data_points, sufficient_data, disclaimer
    """
    prices = fetch_all(
        """SELECT price, price_date FROM price_history
           WHERE asset_id = ?
           ORDER BY price_date ASC""",
        (asset_id,),
    )

    if len(prices) < 2:
        return {
            "daily_vol": None,
            "annualized_vol": None,
            "data_points": len(prices),
            "sufficient_data": False,
            "message": "Insufficient price history for volatility calculation.",
        }

    values = [p["price"] for p in prices]
    returns = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            returns.append(math.log(values[i] / values[i - 1]))

    if not returns:
        return {
            "daily_vol": None,
            "annualized_vol": None,
            "data_points": len(prices),
            "sufficient_data": False,
            "message": "Could not compute returns from price history.",
        }

    daily_vol = float(np.std(returns, ddof=1))
    annualized_vol = daily_vol * math.sqrt(252)
    sufficient = len(returns) >= MIN_PRICE_HISTORY_DAYS

    return {
        "daily_vol": round(daily_vol, 6),
        "annualized_vol": round(annualized_vol, 4),
        "annualized_vol_pct": round(annualized_vol * 100, 2),
        "data_points": len(returns),
        "sufficient_data": sufficient,
        "message": (
            f"Annualized volatility: {annualized_vol * 100:.2f}% "
            f"(based on {len(returns)} data points)."
            if sufficient
            else f"Only {len(returns)} data points available — volatility estimate may be unreliable."
        ),
        "disclaimer": (
            "Historical volatility measures past price fluctuations and does not "
            "predict future risk or returns."
        ),
    }


def maximum_drawdown(asset_id: int) -> dict:
    """
    Compute maximum drawdown from price history.

    Max drawdown = largest peak-to-trough decline as a percentage.
    """
    prices = fetch_all(
        """SELECT price, price_date FROM price_history
           WHERE asset_id = ?
           ORDER BY price_date ASC""",
        (asset_id,),
    )

    if len(prices) < 2:
        return {
            "max_drawdown_pct": None,
            "data_points": len(prices),
            "sufficient_data": False,
            "message": "Insufficient price history for drawdown calculation.",
        }

    values = [p["price"] for p in prices]
    peak = values[0]
    max_dd = 0.0
    peak_date = prices[0]["price_date"]
    trough_date = peak_date

    for i, v in enumerate(values):
        if v > peak:
            peak = v
            peak_date = prices[i]["price_date"]
        dd = (peak - v) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            trough_date = prices[i]["price_date"]

    return {
        "max_drawdown_pct": round(max_dd * 100, 2),
        "peak_date": peak_date,
        "trough_date": trough_date,
        "data_points": len(values),
        "sufficient_data": len(values) >= MIN_PRICE_HISTORY_DAYS,
        "message": f"Maximum drawdown: {max_dd * 100:.2f}%.",
        "disclaimer": "Past drawdowns do not guarantee future risk levels.",
    }


def portfolio_risk_report(portfolio_id: int) -> dict:
    """
    Comprehensive risk report combining concentration, volatility,
    and drawdown indicators.
    """
    conc_alerts = concentration_risk(portfolio_id)
    holdings = list_holdings(portfolio_id)

    asset_risk = []
    for h in holdings:
        vol = historical_volatility(h["asset_id"])
        dd = maximum_drawdown(h["asset_id"])
        asset_risk.append({
            "ticker": h["ticker"],
            "asset_name": h["asset_name"],
            "asset_type": h["asset_type"],
            "weight_pct": round(
                h["market_value"] / max(sum(hh["market_value"] for hh in holdings), 1) * 100, 2
            ),
            "volatility": vol,
            "max_drawdown": dd,
        })

    return {
        "concentration_alerts": conc_alerts,
        "asset_risk_details": asset_risk,
        "total_alerts": len(conc_alerts),
        "disclaimer": (
            "All risk indicators are historical and educational. "
            "They do not constitute a complete risk assessment or investment advice."
        ),
    }
