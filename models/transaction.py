"""
InvestMate AI — Transaction Model

Records every portfolio cash-flow event (BUY, SELL, SIP, DIVIDEND,
CASH_IN, CASH_OUT) and updates the corresponding holding's position.

Uses weighted-average cost basis for buys and realized P&L for sells.
"""

from __future__ import annotations

from datetime import datetime
from database.db import (
    fetch_one, fetch_all, execute, db_transaction, get_connection,
    get_or_create_asset, upsert_price,
)
from models.portfolio import (
    get_holding, upsert_holding, update_cash_balance, get_portfolio,
)
from config import TransactionType, PriceSource, logger


# ──────────────────────────────────────────────────────────────
# Transaction Queries
# ──────────────────────────────────────────────────────────────

def list_transactions(portfolio_id: int, limit: int = 200) -> list[dict]:
    """Return all transactions for a portfolio, most recent first."""
    return fetch_all(
        """SELECT t.*, a.ticker, a.name AS asset_name, a.asset_type
           FROM transactions t
           LEFT JOIN assets a ON a.id = t.asset_id
           WHERE t.portfolio_id = ?
           ORDER BY t.txn_date DESC, t.id DESC
           LIMIT ?""",
        (portfolio_id, limit),
    )


def list_transactions_for_asset(portfolio_id: int, asset_id: int) -> list[dict]:
    return fetch_all(
        """SELECT * FROM transactions
           WHERE portfolio_id = ? AND asset_id = ?
           ORDER BY txn_date ASC""",
        (portfolio_id, asset_id),
    )


def get_sip_transactions(portfolio_id: int) -> list[dict]:
    """Return all SIP transactions ordered by date."""
    return fetch_all(
        """SELECT t.*, a.ticker, a.name AS asset_name
           FROM transactions t
           JOIN assets a ON a.id = t.asset_id
           WHERE t.portfolio_id = ? AND t.txn_type = 'SIP'
           ORDER BY t.txn_date ASC""",
        (portfolio_id,),
    )


# ──────────────────────────────────────────────────────────────
# Record a BUY / SIP
# ──────────────────────────────────────────────────────────────

def record_buy(
    portfolio_id: int,
    asset_id: int,
    quantity: float,
    price: float,
    txn_date: str,
    fees: float = 0.0,
    is_sip: bool = False,
    notes: str = "",
) -> int:
    """
    Record a purchase transaction and update the holding.

    Uses weighted-average cost basis:
        new_avg = (old_qty * old_avg + new_qty * new_price) / (old_qty + new_qty)
    """
    amount = round(quantity * price, 2)
    txn_type = TransactionType.SIP if is_sip else TransactionType.BUY

    txn_id = execute(
        """INSERT INTO transactions
           (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes),
    )

    # Update holding
    holding = get_holding(portfolio_id, asset_id)
    if holding:
        old_qty = holding["quantity"]
        old_avg = holding["avg_cost_price"]
        new_qty = old_qty + quantity
        new_avg = ((old_qty * old_avg) + (quantity * price)) / new_qty if new_qty > 0 else price
        new_invested = holding["total_invested"] + amount
        upsert_holding(portfolio_id, asset_id, new_qty, round(new_avg, 4),
                       round(new_invested, 2), holding["realized_pnl"])
    else:
        upsert_holding(portfolio_id, asset_id, quantity, price, amount)

    # Record the price
    upsert_price(asset_id, price, txn_date, PriceSource.MANUAL)

    # Deduct cash
    portfolio = get_portfolio(portfolio_id)
    if portfolio:
        new_cash = max(portfolio["cash_balance"] - amount - fees, 0)
        update_cash_balance(portfolio_id, round(new_cash, 2))

    logger.info("Recorded %s: %.4f units @ ₹%.2f on %s (txn #%d)",
                txn_type, quantity, price, txn_date, txn_id)
    return txn_id


# ──────────────────────────────────────────────────────────────
# Record a SELL
# ──────────────────────────────────────────────────────────────

def record_sell(
    portfolio_id: int,
    asset_id: int,
    quantity: float,
    price: float,
    txn_date: str,
    fees: float = 0.0,
    notes: str = "",
) -> int:
    """
    Record a sell transaction.

    Realized P&L = (sell_price − avg_cost) × quantity − fees
    Uses weighted-average cost basis.
    """
    holding = get_holding(portfolio_id, asset_id)
    if not holding:
        raise ValueError("Cannot sell: no holding exists for this asset.")
    if holding["quantity"] < quantity:
        raise ValueError(
            f"Cannot sell {quantity} units — only {holding['quantity']} held."
        )

    amount = round(quantity * price, 2)
    avg_cost = holding["avg_cost_price"]
    realized = round((price - avg_cost) * quantity - fees, 2)

    txn_id = execute(
        """INSERT INTO transactions
           (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (portfolio_id, asset_id, TransactionType.SELL, quantity, price, amount,
         fees, txn_date, notes),
    )

    new_qty = holding["quantity"] - quantity
    # total_invested reduces proportionally
    proportion_sold = quantity / holding["quantity"] if holding["quantity"] > 0 else 1
    new_invested = holding["total_invested"] * (1 - proportion_sold)
    new_realized = holding["realized_pnl"] + realized

    upsert_holding(portfolio_id, asset_id, round(new_qty, 4),
                   avg_cost, round(new_invested, 2), round(new_realized, 2))

    # Add cash
    portfolio = get_portfolio(portfolio_id)
    if portfolio:
        new_cash = portfolio["cash_balance"] + amount - fees
        update_cash_balance(portfolio_id, round(new_cash, 2))

    # Record price
    upsert_price(asset_id, price, txn_date, PriceSource.MANUAL)

    logger.info("Recorded SELL: %.4f units @ ₹%.2f on %s → realized P&L ₹%.2f (txn #%d)",
                quantity, price, txn_date, realized, txn_id)
    return txn_id


# ──────────────────────────────────────────────────────────────
# Cash-flow transactions
# ──────────────────────────────────────────────────────────────

def record_cash_in(portfolio_id: int, amount: float, txn_date: str, notes: str = "") -> int:
    txn_id = execute(
        """INSERT INTO transactions
           (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes)
           VALUES (?, NULL, 'CASH_IN', 0, 0, ?, 0, ?, ?)""",
        (portfolio_id, amount, txn_date, notes),
    )
    portfolio = get_portfolio(portfolio_id)
    if portfolio:
        update_cash_balance(portfolio_id, round(portfolio["cash_balance"] + amount, 2))
    return txn_id


def record_cash_out(portfolio_id: int, amount: float, txn_date: str, notes: str = "") -> int:
    txn_id = execute(
        """INSERT INTO transactions
           (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes)
           VALUES (?, NULL, 'CASH_OUT', 0, 0, ?, 0, ?, ?)""",
        (portfolio_id, amount, txn_date, notes),
    )
    portfolio = get_portfolio(portfolio_id)
    if portfolio:
        new_cash = max(portfolio["cash_balance"] - amount, 0)
        update_cash_balance(portfolio_id, round(new_cash, 2))
    return txn_id
