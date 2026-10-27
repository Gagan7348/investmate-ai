"""
InvestMate AI — Intent Router

Maps natural-language user queries to the appropriate tool(s).
Uses keyword matching as the primary mechanism, with optional LLM-based
routing when Groq is available.
"""

from __future__ import annotations

import re
from typing import Optional


# ──────────────────────────────────────────────────────────────
# Intent Definitions
# ──────────────────────────────────────────────────────────────

INTENT_TOOL_MAP: dict[str, list[str]] = {
    "portfolio_value": ["get_portfolio_value"],
    "holdings": ["get_holdings_list"],
    "allocation": ["get_allocation"],
    "sector_allocation": ["get_sector_allocation"],
    "top_performers": ["get_top_performers"],
    "bottom_performers": ["get_bottom_performers"],
    "largest_holdings": ["get_largest_holdings"],
    "returns": ["get_portfolio_value", "get_portfolio_xirr"],
    "xirr": ["get_portfolio_xirr"],
    "risk": ["get_concentration_risk"],
    "risk_report": ["get_risk_report"],
    "sip": ["get_sip_summary"],
    "transactions": ["get_recent_transactions"],
    "data_freshness": ["get_data_freshness_check"],
    "compare_assets": ["get_allocation", "get_holdings_list"],
    "summary": ["get_portfolio_value", "get_allocation", "get_concentration_risk"],
    "performance": ["get_portfolio_value", "get_top_performers", "get_bottom_performers"],
}

# Keyword patterns → intent
KEYWORD_PATTERNS: list[tuple[str, str]] = [
    # Risk (high priority)
    (r"risk|concentrat|danger|expos", "risk"),
    (r"volatil|drawdown|risk\s+report", "risk_report"),

    # XIRR & Returns (high priority)
    (r"xirr|annuali[sz]ed\s+return|money.weighted", "xirr"),

    # SIP (high priority)
    (r"sip|systematic\s+invest", "sip"),
    (r"monthly.*(invest|contribut)", "sip"),

    # Data freshness (high priority)
    (r"(data|price).*(fresh|stale|old|updat)", "data_freshness"),

    # Transactions (high priority)
    (r"transaction|trade|ledger|buy|sell|recent\s+activit", "transactions"),

    # Sector
    (r"sector", "sector_allocation"),

    # Allocation
    (r"(asset\s+)?allocation", "allocation"),
    (r"(distribution|breakdown|split)\s*(of|across|by)", "allocation"),
    (r"how.*divided|how.*distributed", "allocation"),
    (r"compare.*(stock|fund|etf|mutual|asset)", "compare_assets"),

    # Performance & Returns extremes
    (r"(best|top)\s*(perform|holding|stock|fund)", "top_performers"),
    (r"(worst|bottom|poor)\s*(perform|holding|stock|fund)", "bottom_performers"),
    (r"(largest|biggest|highest)\s*(holding|position|value)", "largest_holdings"),
    (r"(most|biggest).*(loss|negative)", "bottom_performers"),
    (r"(most|largest|biggest)\s*(contribut)", "largest_holdings"),
    (r"(gain|loss|profit|return|p\s*&?\s*l|pnl)", "returns"),
    (r"how.*(perform|doing|gone)", "performance"),

    # Portfolio value & overview
    (r"(total|overall).*(value|worth|balance)", "portfolio_value"),
    (r"portfolio\s*(value|worth|summary|overview)", "portfolio_value"),
    (r"how\s+much.*worth", "portfolio_value"),
    (r"what.*total", "portfolio_value"),

    # Holdings
    (r"(list|show|display).*(holding|position|stock|fund)", "holdings"),
    (r"what.*own|what.*hold", "holdings"),
    (r"my\s+(holding|position|investment)", "holdings"),

    # Summary
    (r"(summarize|summary|overview|brief|tell me about)", "summary"),
    (r"explain.*portfolio", "summary"),
]


def detect_intent(query: str) -> tuple[str, list[str]]:
    """
    Detect the user's intent from their query text.

    Returns (intent_name, list_of_tool_names).
    Falls back to 'summary' if no pattern matches.
    """
    query_lower = query.lower().strip()

    for pattern, intent in KEYWORD_PATTERNS:
        if re.search(pattern, query_lower):
            tools = INTENT_TOOL_MAP.get(intent, ["get_portfolio_value"])
            return intent, tools

    # Default fallback
    return "summary", INTENT_TOOL_MAP["summary"]


def get_all_intents() -> list[dict]:
    """Return all known intents with their tool mappings (for testing/docs)."""
    return [
        {"intent": intent, "tools": tools}
        for intent, tools in INTENT_TOOL_MAP.items()
    ]
