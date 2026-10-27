"""
Unit tests for InvestMate AI analytics, returns (XIRR), and risk thresholds.
"""

import pytest
from database.db import init_db, seed_demo_data, fetch_all
from services.portfolio_analytics import (
    portfolio_valuation,
    allocation_by_type,
    allocation_by_sector,
    top_performers,
    portfolio_xirr,
    simple_return,
)
from services.risk_analysis import concentration_risk, portfolio_risk_report


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    seed_demo_data()


def test_simple_return():
    ret = simple_return(100.0, 120.0)
    assert ret == pytest.approx(20.0, rel=1e-3)

    ret_loss = simple_return(100.0, 80.0)
    assert ret_loss == pytest.approx(-20.0, rel=1e-3)


def test_allocation_by_type():
    portfolios = fetch_all("SELECT id FROM portfolios LIMIT 1")
    pid = portfolios[0]["id"]

    alloc = allocation_by_type(pid)
    assert isinstance(alloc, dict)
    pcts = alloc.get("allocation_pct", {})
    if pcts:
        total_pct = sum(pcts.values())
        assert total_pct == pytest.approx(100.0, abs=1.0)


def test_concentration_risk_alerts():
    portfolios = fetch_all("SELECT id FROM portfolios LIMIT 1")
    pid = portfolios[0]["id"]

    alerts = concentration_risk(pid)
    assert isinstance(alerts, list)
    for alert in alerts:
        assert "type" in alert
        assert "severity" in alert
        assert "message" in alert
