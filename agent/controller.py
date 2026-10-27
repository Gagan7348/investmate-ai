"""
InvestMate AI — Agent Controller

Orchestrates the full agent pipeline:
  1. Receive user query
  2. Detect intent via intent router
  3. Select and execute tools
  4. Validate results
  5. Generate natural-language response via Groq LLM
  6. Fall back to rule-based response when LLM is unavailable
  7. Optionally generate voice output
  8. Log activity

The controller enforces:
  • Maximum tool calls per request (prevents loops)
  • Tool allowlist validation
  • Separation of computation from explanation
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Optional

from config import (
    GROQ_API_KEY, GROQ_AVAILABLE, LLM_MODEL, MAX_TOOL_CALLS,
    logger, get_currency_symbol,
)
from agent.intent_router import detect_intent
from agent.tools import execute_tool, TOOL_MAP
from agent.tool_registry import is_valid_tool, get_tool_schemas
from agent.prompts import SYSTEM_PROMPT, TOOL_RESULT_PROMPT, FALLBACK_PROMPT
from services.voice_service import text_to_speech, is_voice_available
from database.db import execute as db_execute


def _call_groq(messages: list[dict], model: str | None = None) -> str | None:
    """Call Groq API and return the assistant message text, or None on failure."""
    if not GROQ_AVAILABLE:
        return None

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=model or LLM_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content
    except ImportError:
        logger.error("groq package not installed.")
        return None
    except Exception as e:
        logger.error("Groq API error: %s", e)
        return None


def _rule_based_response(intent: str, tool_results: list[dict]) -> str:
    """
    Generate a structured text response without the LLM.
    Used as fallback when Groq is unavailable.
    """
    sym = get_currency_symbol()
    lines = [f"**📊 InvestMate AI — Analysis Results**\n"]

    for result in tool_results:
        tool_name = result.get("tool", "unknown")
        data = result.get("data", {})

        if tool_name == "get_portfolio_value":
            lines.append("### Portfolio Value")
            lines.append(f"- **Total Value:** {sym}{data.get('portfolio_value', 0):,.2f}")
            lines.append(f"- **Invested Capital:** {sym}{data.get('total_invested', 0):,.2f}")
            lines.append(f"- **Cash Balance:** {sym}{data.get('cash_balance', 0):,.2f}")
            up = data.get('total_unrealized_pnl', 0)
            arrow = "↑" if up >= 0 else "↓"
            lines.append(f"- **Unrealized P&L:** {sym}{up:,.2f} {arrow}")
            lines.append(f"- **Realized P&L:** {sym}{data.get('total_realized_pnl', 0):,.2f}")
            lines.append(f"- **Return:** {data.get('total_return_pct', 0):.2f}%")
            lines.append(f"- **Holdings:** {data.get('holdings_count', 0)}")
            lines.append("")

        elif tool_name == "get_holdings_list":
            lines.append("### Holdings")
            for h in data.get("holdings", []):
                arrow = "↑" if h["pnl_pct"] >= 0 else "↓"
                lines.append(
                    f"- **{h['name']}** ({h['ticker']}): "
                    f"{sym}{h['market_value']:,.2f} | "
                    f"P&L: {h['pnl_pct']:+.2f}% {arrow} | "
                    f"Price: {sym}{h['current_price']:,.2f} ({h['price_source']})"
                )
            lines.append("")

        elif tool_name == "get_allocation":
            lines.append("### Asset Allocation")
            alloc = data.get("allocation_pct", {})
            for asset_type, pct in alloc.items():
                lines.append(f"- **{asset_type}:** {pct:.1f}%")
            lines.append("")

        elif tool_name in ("get_top_performers", "get_bottom_performers"):
            key = "top_performers" if "top" in tool_name else "bottom_performers"
            label = "Top Performers" if "top" in tool_name else "Bottom Performers"
            lines.append(f"### {label}")
            for p in data.get(key, []):
                arrow = "↑" if p["pnl_pct"] >= 0 else "↓"
                lines.append(f"- **{p['name']}**: {p['pnl_pct']:+.2f}% {arrow}")
            lines.append("")

        elif tool_name == "get_portfolio_xirr":
            lines.append("### Portfolio XIRR")
            lines.append(f"- **Annualized Return (XIRR):** {data.get('xirr_pct', 'N/A')}")
            lines.append(f"- *{data.get('note', '')}*")
            lines.append("")

        elif tool_name == "get_concentration_risk":
            lines.append("### Concentration Risk")
            if data.get("alerts"):
                for a in data["alerts"]:
                    lines.append(f"- ⚠️ {a['message']}")
            else:
                lines.append("- ✅ No concentration risks detected.")
            lines.append("")

        elif tool_name == "get_sip_summary":
            lines.append("### SIP Summary")
            lines.append(f"- **Total SIP Invested:** {sym}{data.get('total_sip_invested', 0):,.2f}")
            lines.append(f"- **SIP Transactions:** {data.get('sip_count', 0)}")
            monthly = data.get("monthly_breakdown", {})
            if monthly:
                lines.append("- **Monthly Breakdown:**")
                for month, amt in sorted(monthly.items()):
                    lines.append(f"  - {month}: {sym}{amt:,.2f}")
            lines.append("")

        elif tool_name == "get_recent_transactions":
            lines.append("### Recent Transactions")
            for t in data.get("transactions", [])[:10]:
                lines.append(
                    f"- {t['date']} | {t['type']} | {t['name']} | "
                    f"Qty: {t['quantity']:.2f} @ {sym}{t['price']:,.2f}"
                )
            lines.append("")

        elif tool_name == "get_risk_report":
            lines.append("### Risk Report")
            alerts = data.get("concentration_alerts", [])
            if alerts:
                for a in alerts:
                    lines.append(f"- ⚠️ [{a['severity']}] {a['message']}")
            else:
                lines.append("- ✅ No concentration risks at current thresholds.")
            lines.append(f"\n*{data.get('disclaimer', '')}*")
            lines.append("")

        elif tool_name == "get_data_freshness_check":
            lines.append("### Data Freshness")
            lines.append(f"- {data.get('message', '')}")
            lines.append("")

        else:
            friendly_title = tool_name.replace("_", " ").title()
            lines.append(f"### {friendly_title}")
            if isinstance(data, dict):
                for k, v in data.items():
                    k_str = k.replace("_", " ").title()
                    lines.append(f"- **{k_str}:** {v}")
            else:
                lines.append(f"- {data}")
            lines.append("")

    lines.append("---")
    lines.append("*⚠️ All data is for educational purposes. Prices may be simulated or delayed.*")

    return "\n".join(lines)


def process_query(
    query: str,
    portfolio_id: int,
    generate_audio: bool = False,
) -> dict:
    """
    Main agent entry point.

    Args:
        query: User's natural-language question
        portfolio_id: Active portfolio ID
        generate_audio: Whether to generate TTS audio

    Returns:
        {
            "response": str,        # natural-language answer
            "intent": str,
            "tools_used": list,
            "tool_results": list,
            "audio_bytes": bytes | None,
            "duration_ms": int,
            "error": str | None,
        }
    """
    start_time = time.time()
    error = None

    # Step 1: Detect intent
    intent, tool_names = detect_intent(query)
    logger.info("Intent: %s → Tools: %s", intent, tool_names)

    # Step 2: Execute tools (with limit)
    tool_results = []
    tools_called = []
    for tool_name in tool_names[:MAX_TOOL_CALLS]:
        if not is_valid_tool(tool_name):
            logger.warning("Skipping invalid tool: %s", tool_name)
            continue
        result = execute_tool(tool_name, portfolio_id)
        tool_results.append(result)
        tools_called.append(tool_name)

    # Step 3: Generate response
    if GROQ_AVAILABLE:
        # Use LLM for natural-language explanation
        tool_data_str = json.dumps(tool_results, indent=2, default=str)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
            {"role": "assistant", "content": TOOL_RESULT_PROMPT.format(tool_results=tool_data_str)},
            {"role": "user", "content": "Based on the tool results above, please answer my question clearly and accurately."},
        ]
        response_text = _call_groq(messages)
        if not response_text:
            response_text = _rule_based_response(intent, tool_results)
            error = "LLM call failed — using rule-based response."
    else:
        response_text = _rule_based_response(intent, tool_results)

    # Step 4: Optional voice
    audio_bytes = None
    if generate_audio and is_voice_available():
        # Clean text for crisp, natural TTS pronunciation
        plain_text = (
            response_text.replace("**", "")
            .replace("###", "")
            .replace("##", "")
            .replace("---", "")
            .replace("₹", "Rupees ")
            .replace("↑", "up ")
            .replace("↓", "down ")
        )
        # Limit to ~600 chars for concise spoken summary
        audio_text = plain_text[:600]
        audio_bytes = text_to_speech(audio_text)

    duration_ms = int((time.time() - start_time) * 1000)

    # Step 5: Log activity
    try:
        db_execute(
            """INSERT INTO agent_activity
               (portfolio_id, user_query, detected_intent, tools_called,
                tool_results, final_response, duration_ms, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                portfolio_id, query, intent,
                json.dumps(tools_called),
                json.dumps(tool_results, default=str)[:10000],
                response_text[:5000],
                duration_ms,
                error or "",
            ),
        )
    except Exception as e:
        logger.warning("Failed to log agent activity: %s", e)

    return {
        "response": response_text,
        "intent": intent,
        "tools_used": tools_called,
        "tool_results": tool_results,
        "audio_bytes": audio_bytes,
        "duration_ms": duration_ms,
        "error": error,
    }
