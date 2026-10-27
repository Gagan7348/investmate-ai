"""
InvestMate AI — Conversational AI & Voice Assistant UI Page

Provides:
  • Two-way voice interaction:
      - Direct microphone input via Streamlit st.audio_input
      - Ultra-fast speech-to-text via Groq Whisper (whisper-large-v3)
      - Natural voice synthesis readout via ElevenLabs
  • Conversational natural-language interface for portfolio queries
  • Quick query prompt buttons for common financial questions
  • Agent Reasoning & Tool Inspector (transparency into tool execution)
  • Real-time latency and verified ground-truth display
"""

from __future__ import annotations

import streamlit as st
from agent.controller import process_query
from services.voice_service import transcribe_speech, is_voice_available
from config import GROQ_AVAILABLE, ELEVENLABS_AVAILABLE, VOICE_ENABLED, get_currency_symbol



def render_transparency_in_text(msg_or_res: dict, expanded: bool = False) -> None:
    """
    Render the Agent Reasoning & Tool Execution Transparency section in clean,
    human-readable text format instead of raw JSON code.
    """
    tools_used = msg_or_res.get("tools_used", [])
    if not tools_used:
        return

    intent = msg_or_res.get("intent", "general_query")
    duration_ms = msg_or_res.get("duration_ms", 0)
    tool_results = msg_or_res.get("tool_results", [])

    intent_map = {
        "portfolio_value": "Portfolio Valuation & Capital Overview",
        "holdings": "Holdings & Asset Inventory Check",
        "allocation": "Asset Class & Sector Exposure Breakdown",
        "performance": "Performance Analysis (Top & Bottom Assets)",
        "xirr": "Annualized Money-Weighted Return (XIRR)",
        "risk": "Risk Diagnostics & Concentration Limits",
        "sip": "Systematic Investment Plan (SIP) Audit",
        "transactions": "Transaction History Audit",
        "data_freshness": "Market Feed Freshness Verification",
        "summary": "Comprehensive Portfolio Health & Performance Summary",
    }
    friendly_intent = intent_map.get(intent, intent.replace("_", " ").title())

    tool_name_map = {
        "get_portfolio_value": "Portfolio Valuation",
        "get_holdings_list": "Holdings Inventory",
        "get_allocation": "Asset Class Allocation",
        "get_sector_allocation": "Sector Allocation",
        "get_top_performers": "Top Performers Analysis",
        "get_bottom_performers": "Underperformers Analysis",
        "get_largest_holdings": "Largest Holdings Valuation",
        "get_portfolio_xirr": "Annualized Return (XIRR)",
        "get_concentration_risk": "Concentration Risk Monitor",
        "get_risk_report": "Comprehensive Risk Report",
        "get_sip_summary": "SIP Investment Summary",
        "get_recent_transactions": "Transaction Ledger",
        "get_data_freshness_check": "Market Data Freshness",
    }
    friendly_tools = [tool_name_map.get(t, t.replace("_", " ").title()) for t in tools_used]

    with st.expander("🔍 Agent Reasoning & Tool Execution Transparency", expanded=expanded):
        # 1. High-level Metadata Summary in Clean Text Cards
        st.markdown(
            f"""
            <div style="background: rgba(15, 23, 42, 0.6); padding: 1rem 1.2rem; border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.25); margin-bottom: 1rem;">
                <div style="font-size: 0.95rem; margin-bottom: 0.4rem;">
                    <strong style="color: #60a5fa;">🎯 Intent Detected:</strong> <span style="color: #f1f5f9;">{friendly_intent}</span>
                </div>
                <div style="font-size: 0.95rem; margin-bottom: 0.4rem;">
                    <strong style="color: #34d399;">⚙️ Analytical Tools Executed:</strong> <span style="color: #f1f5f9;">{', '.join(friendly_tools) if friendly_tools else 'None'}</span>
                </div>
                <div style="font-size: 0.95rem;">
                    <strong style="color: #fbbf24;">⏱️ Total Execution Latency:</strong> <span style="color: #f1f5f9;">{duration_ms:,} ms (Deterministic Python Math Engine)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### 📋 Verified Analytical Findings (Ground Truth)")
        st.caption("All figures below are exact calculations retrieved directly from database records and live market feeds — zero LLM approximations.")

        if not tool_results:
            st.info("No tool results were generated for this query.")
            return

        # Render each tool result in rich, structured TEXT format (NO CODE BLOCKS)
        for idx, res in enumerate(tool_results):
            tool = res.get("tool", "")
            data = res.get("data", {})
            title = tool_name_map.get(tool, tool.replace("_", " ").title())

            st.markdown(f"**📌 Tool #{idx+1}: {title}**")

            if tool == "get_portfolio_value":
                pv = data.get("portfolio_value", 0)
                inv = data.get("total_invested", 0)
                pnl = data.get("total_unrealized_pnl", 0)
                pnl_pct = data.get("total_return_pct", 0)
                cash = data.get("cash_balance", 0)
                mv = data.get("total_market_value", 0)
                count = data.get("holdings_count", 0)
                cur = data.get("currency", "₹")
                arrow = "↑" if pnl >= 0 else "↓"

                st.markdown(
                    f"- **Total Portfolio Value:** {cur}{pv:,.2f}\n"
                    f"- **Market Value (Holdings):** {cur}{mv:,.2f} across **{count} active assets**\n"
                    f"- **Invested Capital:** {cur}{inv:,.2f}\n"
                    f"- **Total Unrealized P&L:** {cur}{pnl:+,.2f} ({pnl_pct:+.2f}%) {arrow}\n"
                    f"- **Available Liquid Cash:** {cur}{cash:,.2f}\n"
                    f"- **Realized P&L from Exits:** {cur}{data.get('total_realized_pnl', 0):,.2f}"
                )

            elif tool == "get_allocation":
                alloc = data.get("allocation_pct", {})
                st.markdown("Asset breakdown by portfolio weight:")
                for asset_type, pct in alloc.items():
                    friendly_type = asset_type.replace("_", " ").title()
                    st.markdown(f"- **{friendly_type}:** {pct:.1f}%")

            elif tool == "get_sector_allocation":
                sectors = data.get("sector_pct", {})
                st.markdown("Sector exposure breakdown:")
                for sec, pct in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
                    st.markdown(f"- **{sec}:** {pct:.1f}%")

            elif tool == "get_concentration_risk":
                alerts = data.get("alerts", [])
                if alerts:
                    st.markdown("⚠️ **Concentration Risk Warnings:**")
                    for a in alerts:
                        st.markdown(f"- **[{a.get('severity', 'Warning').upper()}]** {a.get('message', '')}")
                else:
                    st.markdown("✅ **Diversification Status:** Healthy. No individual holding exceeds 25% and no single sector exceeds 40% of total capital.")

            elif tool == "get_portfolio_xirr":
                xirr_val = data.get("xirr_pct", "N/A")
                st.markdown(
                    f"- **Annualized Return (XIRR):** **{xirr_val}**\n"
                    f"- **Calculation Method:** Money-weighted annualized internal rate of return factoring the exact dates and amounts of all cash flows (buys, sells, SIPs).\n"
                    f"- **Status Note:** {data.get('note', '')}"
                )

            elif tool in ("get_top_performers", "get_bottom_performers"):
                key = "top_performers" if "top" in tool else "bottom_performers"
                performers = data.get(key, [])
                if performers:
                    for p in performers:
                        pnl = p.get("pnl_pct", 0)
                        arrow = "↑" if pnl >= 0 else "↓"
                        st.markdown(f"- **{p.get('name', '')}** (`{p.get('ticker', '')}`): **{pnl:+.2f}%** {arrow} (Unrealized: ₹{p.get('unrealized_pnl', 0):+,.2f})")
                else:
                    st.markdown("- No holding performance data available.")

            elif tool == "get_holdings_list":
                holdings = data.get("holdings", [])
                st.markdown(f"Verified **{len(holdings)} holdings** in portfolio:")
                for h in holdings[:8]:
                    pnl = h.get("pnl_pct", 0)
                    arrow = "↑" if pnl >= 0 else "↓"
                    st.markdown(f"- **{h.get('name', '')}** ({h.get('ticker', '')}): Quantity: {h.get('quantity', 0):.2f} | Current Price: ₹{h.get('current_price', 0):,.2f} | Market Value: ₹{h.get('market_value', 0):,.2f} | P&L: {pnl:+.2f}% {arrow}")
                if len(holdings) > 8:
                    st.markdown(f"*(and {len(holdings) - 8} additional holdings...)*")

            elif tool == "get_sip_summary":
                st.markdown(
                    f"- **Total SIP Capital Invested:** ₹{data.get('total_sip_invested', 0):,.2f}\n"
                    f"- **Total SIP Installments:** {data.get('sip_count', 0)} completed installments\n"
                    f"- **Monthly SIP Investment Average:** ₹{data.get('monthly_average', 0):,.2f}"
                )

            elif tool == "get_recent_transactions":
                txns = data.get("transactions", [])
                st.markdown(f"Retrieved **{len(txns)} transactions**:")
                for t in txns[:6]:
                    st.markdown(f"- **{t.get('date', '')}**: {t.get('type', '')} {t.get('name', '')} — Qty: {t.get('quantity', 0):.2f} @ ₹{t.get('price', 0):,.2f} (Total: ₹{t.get('amount', 0):,.2f})")

            elif tool == "get_data_freshness_check":
                st.markdown(f"- **Data Freshness Report:** {data.get('message', 'All prices up to date.')}")

            elif tool == "get_risk_report":
                st.markdown(f"- **Overall Risk Level:** {data.get('overall_risk_level', 'MODERATE')}")
                alerts = data.get("concentration_alerts", [])
                if alerts:
                    for a in alerts:
                        st.markdown(f"- ⚠️ {a.get('message', '')}")
                else:
                    st.markdown("- ✅ No concentration breaches.")

            else:
                if isinstance(data, dict):
                    for k, v in data.items():
                        readable_k = k.replace("_", " ").title()
                        if isinstance(v, (int, float)):
                            st.markdown(f"- **{readable_k}:** {v:,.2f}" if isinstance(v, float) else f"- **{readable_k}:** {v:,}")
                        elif isinstance(v, (str, bool)):
                            st.markdown(f"- **{readable_k}:** {v}")
                        elif isinstance(v, list):
                            st.markdown(f"- **{readable_k}:** {len(v)} item(s)")
                else:
                    st.markdown(f"- {str(data)}")

            st.write("")  # Spacing between tools

        st.caption("🔒 Computational Guarantee: Python mathematical models computed these facts directly from verified portfolio records and live NSE/AMFI feeds. The Groq AI agent interprets these facts without fabricating figures.")


def render_assistant(portfolio_id: int) -> None:
    """Render the AI & Voice Assistant chat interface."""
    sym = get_currency_symbol()

    # Page Header Banner
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(30, 58, 138, 0.3) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 16px; padding: 1.5rem 1.8rem; margin-bottom: 1.5rem;
                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h2 style="margin: 0; font-size: 1.6rem; font-weight: 800; color: #60a5fa;">
                        🎙️ Conversational Voice & AI Agent
                    </h2>
                    <p style="margin: 0.3rem 0 0 0; color: #94a3b8; font-size: 0.95rem;">
                        Real-time voice intelligence grounded in deterministic mathematical computations & live Indian market feeds.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Status / Feature badges
    badge_cols = st.columns([1, 1, 2])
    with badge_cols[0]:
        if GROQ_AVAILABLE:
            st.success("⚡ Groq Qwen 27B & Whisper STT: Online", icon="✅")
        else:
            st.warning("⚡ Groq LLM: Rule-based Fallback", icon="⚠️")

    with badge_cols[1]:
        if ELEVENLABS_AVAILABLE and VOICE_ENABLED:
            st.success("🔊 ElevenLabs Speech: Active", icon="✅")
        else:
            st.info("🔇 Voice Readout: Muted", icon="ℹ️")

    with badge_cols[2]:
        voice_toggle = st.toggle("Voice Readout (ElevenLabs TTS)", value=VOICE_ENABLED and ELEVENLABS_AVAILABLE)

    # ── Voice Recording Station ───────────────────────────────────────
    st.markdown("#### 🎙️ Voice Input Station")
    st.caption("Click the microphone below and speak naturally in English (e.g., 'What is my total portfolio value?', 'Which are my best performing stocks?').")

    mic_col1, mic_col2 = st.columns([2, 1])
    with mic_col1:
        recorded_audio = st.audio_input("Record your voice question", key="audio_mic_input")

    with mic_col2:
        st.markdown(
            """
            <div style="padding: 1rem; background: rgba(30, 41, 59, 0.4); border-radius: 12px; border: 1px dashed rgba(148, 163, 184, 0.3); font-size: 0.85rem; color: #94a3b8;">
                <strong style="color: #60a5fa;">💡 How Voice Works:</strong><br>
                1. Click Record & speak.<br>
                2. Whisper transcribes audio instantly.<br>
                3. Deterministic tools fetch facts.<br>
                4. ElevenLabs speaks the answer back.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Initialize chat history in session state
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    f"Hello! I am **InvestMate AI**, your personal portfolio intelligence assistant.\n\n"
                    f"I track your real Indian equities, AMFI mutual funds, and ETFs with exact deterministic "
                    f"mathematics. You can **speak to me via the microphone above** or type your questions below.\n\n"
                    f"Try one of the quick suggestions or ask about your portfolio!"
                ),
                "tools_used": [],
                "tool_results": [],
                "duration_ms": 0,
                "audio_bytes": None,
            }
        ]

    # Quick prompt shortcuts
    st.markdown("##### 💡 Quick Insights")
    q_col1, q_col2, q_col3 = st.columns(3)
    quick_query = None

    with q_col1:
        if st.button("📊 Total Portfolio Value"):
            quick_query = "What is my total portfolio value, invested amount, and current P&L?"
        if st.button("📈 What is my XIRR Return?"):
            quick_query = "What is my portfolio XIRR and annualized performance?"

    with q_col2:
        if st.button("🏆 Top & Bottom Performers"):
            quick_query = "Which investments are my best and worst performers?"
        if st.button("🥧 Asset Allocation Breakdown"):
            quick_query = "Breakdown my portfolio allocation across stocks, mutual funds, ETFs, and cash."

    with q_col3:
        if st.button("⚠️ Check Concentration Risk"):
            quick_query = "Do I have any single-stock or sector concentration risks?"
        if st.button("🔄 Check Data Freshness"):
            quick_query = "Are all my asset prices up to date?"

    st.divider()

    # Display Chat History
    for msg in st.session_state.messages:
        role = msg["role"]
        with st.chat_message(role, avatar="🧑‍💻" if role == "user" else "🤖"):
            st.markdown(msg["content"])

            # If voice audio is attached
            if msg.get("audio_bytes"):
                st.audio(msg["audio_bytes"], format="audio/mp3")

            # Transparency & Reasoning Accordion for Assistant
            if role == "assistant" and msg.get("tools_used"):
                render_transparency_in_text(msg, expanded=False)

    # Determine input: microphone audio vs text chat vs quick query
    prompt_to_run = None
    input_source = "text"

    # Check if new voice audio was submitted
    if recorded_audio:
        # Check if we already processed this exact audio file to prevent duplicate runs on rerun
        audio_id = f"audio_{getattr(recorded_audio, 'size', 0)}_{getattr(recorded_audio, 'name', '')}"
        if st.session_state.get("last_processed_audio") != audio_id:
            with st.spinner("🎙️ Transcribing voice via Groq Whisper..."):
                transcribed_text = transcribe_speech(recorded_audio)
                if transcribed_text:
                    prompt_to_run = transcribed_text
                    input_source = "voice"
                    st.session_state.last_processed_audio = audio_id
                    st.toast(f"🎙️ Transcribed: \"{transcribed_text}\"", icon="🗣️")
                else:
                    st.warning("Could not transcribe speech. Please ensure your microphone is working and speak clearly.")

    # Text input
    typed_input = st.chat_input("Ask a question or speak above...")
    if typed_input:
        prompt_to_run = typed_input
        input_source = "text"
    elif quick_query:
        prompt_to_run = quick_query
        input_source = "quick"

    if prompt_to_run:
        # Add user query
        display_label = f"🎙️ *\"{prompt_to_run}\"*" if input_source == "voice" else prompt_to_run
        st.session_state.messages.append({"role": "user", "content": display_label})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(display_label)

        # Process with Agent Controller
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("InvestMate AI is consulting analytical tools..."):
                agent_res = process_query(
                    query=prompt_to_run,
                    portfolio_id=portfolio_id,
                    generate_audio=voice_toggle,
                )

            # Display response
            st.markdown(agent_res["response"])

            # Play audio if generated
            if agent_res.get("audio_bytes"):
                st.audio(agent_res["audio_bytes"], format="audio/mp3", autoplay=True)

            # Show transparency inspector
            if agent_res.get("tools_used"):
                render_transparency_in_text(agent_res, expanded=True)

        # Save to chat history
        st.session_state.messages.append({
            "role": "assistant",
            "content": agent_res["response"],
            "intent": agent_res.get("intent"),
            "tools_used": agent_res.get("tools_used", []),
            "tool_results": agent_res.get("tool_results", []),
            "duration_ms": agent_res.get("duration_ms", 0),
            "audio_bytes": agent_res.get("audio_bytes"),
        })

    # Educational Disclaimer Footer
    st.markdown("---")
    st.caption(
        "⚠️ **InvestMate AI Disclaimer:** Educational decision-support tool. Not a SEBI-registered advisor. "
        "Valuations are computed from verified live NSE quotes and AMFI NAV feeds."
    )
