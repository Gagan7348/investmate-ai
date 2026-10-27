"""
InvestMate AI — Portfolio Model

High-level operations on portfolios and holdings that sit above the raw
database helpers.  Every public function returns plain dicts/lists so they
can be serialised to JSON and passed to the agent or the UI without ORM
coupling.
"""

from __future__ import annotations

import json
from datetime import datetime
from database.db import (
    fetch_one, fetch_all, execute, db_transaction,
    get_or_create_asset, get_latest_price,
)
from config import AssetType, logger


# ──────────────────────────────────────────────────────────────
# Portfolio CRUD
# ──────────────────────────────────────────────────────────────

def list_portfolios(user_id: int) -> list[dict]:
    return fetch_all(
        "SELECT * FROM portfolios WHERE user_id = ? ORDER BY id", (user_id,)
    )


def get_portfolio(portfolio_id: int) -> dict | None:
    return fetch_one("SELECT * FROM portfolios WHERE id = ?", (portfolio_id,))


def create_portfolio(user_id: int, name: str, description: str = "",
                     cash_balance: float = 0.0) -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Portfolio name cannot be empty.")

    existing = fetch_one(
        "SELECT id, name FROM portfolios WHERE user_id = ? AND LOWER(name) = LOWER(?)",
        (user_id, clean_name),
    )
    if existing:
        raise ValueError(f"A portfolio named '{clean_name}' already exists.")

    pid = execute(
        """INSERT INTO portfolios (user_id, name, description, cash_balance)
           VALUES (?, ?, ?, ?)""",
        (user_id, clean_name, description, cash_balance),
    )
    return fetch_one("SELECT * FROM portfolios WHERE id = ?", (pid,))


def delete_portfolio(portfolio_id: int) -> bool:
    """Delete a portfolio and associated holdings, transactions, and reports."""
    execute("DELETE FROM transactions WHERE portfolio_id = ?", (portfolio_id,))
    execute("DELETE FROM holdings WHERE portfolio_id = ?", (portfolio_id,))
    execute("DELETE FROM watchlist WHERE portfolio_id = ?", (portfolio_id,))
    execute("DELETE FROM reports WHERE portfolio_id = ?", (portfolio_id,))
    execute("DELETE FROM agent_activity WHERE portfolio_id = ?", (portfolio_id,))
    execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    return True


def update_cash_balance(portfolio_id: int, amount: float) -> None:
    execute(
        "UPDATE portfolios SET cash_balance = ?, updated_at = datetime('now') WHERE id = ?",
        (amount, portfolio_id),
    )


# ──────────────────────────────────────────────────────────────
# Holdings CRUD
# ──────────────────────────────────────────────────────────────

def list_holdings(portfolio_id: int) -> list[dict]:
    """Return all holdings for a portfolio, enriched with asset details and latest price."""
    rows = fetch_all(
        """SELECT h.*, a.ticker, a.name AS asset_name, a.asset_type,
                  a.exchange, a.scheme_code, a.sector, a.currency
           FROM holdings h
           JOIN assets a ON a.id = h.asset_id
           WHERE h.portfolio_id = ?
           ORDER BY a.asset_type, a.ticker""",
        (portfolio_id,),
    )
    enriched = []
    for row in rows:
        price_info = get_latest_price(row["asset_id"])
        current_price = price_info["price"] if price_info else 0.0
        price_date = price_info["price_date"] if price_info else "N/A"
        price_source = price_info["source"] if price_info else "UNKNOWN"
        quantity = row["quantity"]
        avg_cost = row["avg_cost_price"]
        market_value = quantity * current_price
        unrealized_pnl = market_value - (quantity * avg_cost)
        pnl_pct = ((current_price / avg_cost) - 1) * 100 if avg_cost > 0 else 0.0

        enriched.append({
            **row,
            "current_price": current_price,
            "price_date": price_date,
            "price_source": price_source,
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })
    return enriched


def get_holding(portfolio_id: int, asset_id: int) -> dict | None:
    return fetch_one(
        "SELECT * FROM holdings WHERE portfolio_id = ? AND asset_id = ?",
        (portfolio_id, asset_id),
    )


def upsert_holding(portfolio_id: int, asset_id: int, quantity: float,
                   avg_cost_price: float, total_invested: float,
                   realized_pnl: float = 0.0) -> None:
    """Insert or update a holding record."""
    existing = get_holding(portfolio_id, asset_id)
    if existing:
        execute(
            """UPDATE holdings
               SET quantity = ?, avg_cost_price = ?, total_invested = ?,
                   realized_pnl = ?, updated_at = datetime('now')
               WHERE portfolio_id = ? AND asset_id = ?""",
            (quantity, avg_cost_price, total_invested, realized_pnl,
             portfolio_id, asset_id),
        )
    else:
        execute(
            """INSERT INTO holdings
               (portfolio_id, asset_id, quantity, avg_cost_price, total_invested, realized_pnl)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (portfolio_id, asset_id, quantity, avg_cost_price, total_invested, realized_pnl),
        )


def remove_holding(portfolio_id: int, asset_id: int) -> None:
    execute(
        "DELETE FROM holdings WHERE portfolio_id = ? AND asset_id = ?",
        (portfolio_id, asset_id),
    )


# ──────────────────────────────────────────────────────────────
# Portfolio Summary (aggregated view)
# ──────────────────────────────────────────────────────────────

def get_portfolio_summary(portfolio_id: int) -> dict:
    """
    Compute portfolio-level aggregates.

    Returns a dict with:
      total_market_value, total_invested, cash_balance,
      total_unrealized_pnl, total_realized_pnl,
      total_return_pct, allocation (by asset type), holdings list
    """
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return {}

    holdings = list_holdings(portfolio_id)
    cash = portfolio["cash_balance"]

    total_market_value = sum(h["market_value"] for h in holdings)
    total_invested = sum(h["total_invested"] for h in holdings)
    total_unrealized = sum(h["unrealized_pnl"] for h in holdings)
    total_realized = sum(h["realized_pnl"] for h in holdings)

    portfolio_value = total_market_value + cash
    total_return_pct = (
        ((total_market_value - total_invested) / total_invested * 100)
        if total_invested > 0 else 0.0
    )

    # Allocation by asset type
    allocation: dict[str, float] = {}
    for h in holdings:
        atype = h["asset_type"]
        allocation[atype] = allocation.get(atype, 0) + h["market_value"]
    if cash > 0:
        allocation["CASH"] = cash

    # Convert to percentages
    alloc_pct: dict[str, float] = {}
    if portfolio_value > 0:
        for k, v in allocation.items():
            alloc_pct[k] = round(v / portfolio_value * 100, 2)

    return {
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio["name"],
        "base_currency": portfolio["base_currency"],
        "cash_balance": round(cash, 2),
        "total_market_value": round(total_market_value, 2),
        "portfolio_value": round(portfolio_value, 2),
        "total_invested": round(total_invested, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "total_realized_pnl": round(total_realized, 2),
        "total_return_pct": round(total_return_pct, 2),
        "allocation": allocation,
        "allocation_pct": alloc_pct,
        "holdings_count": len(holdings),
        "holdings": holdings,
    }
