"""
Unit tests for InvestMate AI agent intent router, tool registry, and execution.
"""

import pytest
from database.db import init_db, seed_demo_data, fetch_all
from agent.intent_router import detect_intent
from agent.tool_registry import is_valid_tool, validate_tool_call, get_tool_names
from agent.tools import execute_tool, TOOL_MAP
from agent.controller import process_query


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    seed_demo_data()


def test_intent_detection():
    intent, tools = detect_intent("What is my total portfolio value?")
    assert intent == "portfolio_value"
    assert "get_portfolio_value" in tools

    intent2, tools2 = detect_intent("Check concentration risk in my holdings")
    assert intent2 == "risk"
    assert "get_concentration_risk" in tools2

    intent3, tools3 = detect_intent("What are my top performers?")
    assert intent3 == "top_performers"
    assert "get_top_performers" in tools3


def test_tool_registry():
    assert is_valid_tool("get_portfolio_value") is True
    assert is_valid_tool("get_holdings_list") is True
    assert is_valid_tool("non_existent_tool_123") is False

    valid, err = validate_tool_call("get_portfolio_value", {"portfolio_id": 1})
    assert valid is True
    assert err == ""

    invalid, err2 = validate_tool_call("fake_tool", {"portfolio_id": 1})
    assert invalid is False


def test_execute_tools():
    portfolios = fetch_all("SELECT id FROM portfolios LIMIT 1")
    pid = portfolios[0]["id"]

    res = execute_tool("get_portfolio_value", pid)
    assert res["tool"] == "get_portfolio_value"
    assert "portfolio_value" in res["data"]
    assert "total_invested" in res["data"]


def test_agent_process_query():
    portfolios = fetch_all("SELECT id FROM portfolios LIMIT 1")
    pid = portfolios[0]["id"]

    output = process_query("What is my portfolio value?", pid, generate_audio=False)
    assert "response" in output
    assert len(output["response"]) > 0
    assert "get_portfolio_value" in output["tools_used"]
    assert output["duration_ms"] >= 0
