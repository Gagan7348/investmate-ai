"""
Unit tests for InvestMate AI portfolio operations and weighted average cost calculations.
"""

import pytest
import sqlite3
from database.db import init_db, seed_demo_data, fetch_all, fetch_one
from models.portfolio import list_portfolios, get_portfolio, list_holdings, get_portfolio_summary
from models.transaction import record_buy, record_sell, record_cash_in, record_cash_out


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initialize database and demo data before tests."""
    init_db()
    seed_demo_data()


def test_list_portfolios():
    users = fetch_all("SELECT id FROM users LIMIT 1")
    assert len(users) > 0
    portfolios = list_portfolios(users[0]["id"])
    assert len(portfolios) >= 1
    assert "name" in portfolios[0]


def test_portfolio_summary():
    portfolios = fetch_all("SELECT id FROM portfolios LIMIT 1")
    assert len(portfolios) > 0
    pid = portfolios[0]["id"]

    summary = get_portfolio_summary(pid)
    assert summary is not None
    assert summary["portfolio_value"] >= 0
    assert summary["total_invested"] >= 0
    assert summary["holdings_count"] >= 0
    assert "holdings" in summary


def test_cash_flow_transactions():
    portfolios = fetch_all("SELECT id FROM portfolios LIMIT 1")
    pid = portfolios[0]["id"]
    p_before = get_portfolio(pid)
    initial_cash = p_before["cash_balance"]

    # Deposit cash
    record_cash_in(pid, 50000.0, "2024-01-01", notes="Test Deposit")
    p_after_in = get_portfolio(pid)
    assert p_after_in["cash_balance"] == pytest.approx(initial_cash + 50000.0, rel=1e-3)

    # Withdraw cash
    record_cash_out(pid, 20000.0, "2024-01-02", notes="Test Withdrawal")
    p_after_out = get_portfolio(pid)
    assert p_after_out["cash_balance"] == pytest.approx(initial_cash + 30000.0, rel=1e-3)
