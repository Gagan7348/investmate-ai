# InvestMate AI — Intelligent Voice-Enabled Multi-Asset Portfolio Management Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/framework-Streamlit-red.svg)](https://streamlit.io/)
[![Groq LLM](https://img.shields.io/badge/LLM-Groq%20Llama%203.3-orange.svg)](https://groq.com/)
[![ElevenLabs](https://img.shields.io/badge/voice-ElevenLabs-black.svg)](https://elevenlabs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

InvestMate AI is a production-inspired academic project combining **portfolio tracking**, **deterministic financial analytics**, **AI-powered natural-language explanations**, **voice interaction**, **risk monitoring**, and **personalized portfolio reporting** into a unified web application.

---

## 🌟 Key Features

1. **Multi-Asset Portfolio Support (India):**
   - **Listed Equities:** NSE / BSE stocks (e.g. `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS`, `INFY.NS`).
   - **Indian Mutual Funds:** Live NAV lookup via AMFI's official public feed using 6-digit scheme codes (e.g. `120503`).
   - **Exchange-Traded Funds (ETFs):** Nifty 50 Bees, Gold BeES, etc.
   - **Cash & Liquidity Tracking:** Real-time cash balance management with deposits, withdrawals, and dividend accrual.

2. **Deterministic Financial Analytics (Zero Hallucination):**
   - **Weighted Average Cost Basis (WAC):** Automatically recalculated on each purchase.
   - **Realized & Unrealized P&L:** Track gains and losses accurately.
   - **Exact Money-Weighted Returns (XIRR):** Solves exact internal rate of return for irregular cash flows using Brent's method (`scipy.optimize.brentq`).
   - **Asset & Sector Allocation:** Plotly interactive donut and horizontal bar charts.

3. **Intelligent Conversational Agent & Voice:**
   - **Grounded AI Engine:** Powered by Groq's high-speed LLaMA 3.3 70B model.
   - **Tool Allowlist & Registry:** LLM never computes math — it queries deterministic analytical tools (`get_portfolio_value`, `get_portfolio_xirr`, `get_concentration_risk`, etc.).
   - **Full Transparency Inspector:** View detected intent, executed tools, execution latency, and raw data returned.
   - **Voice Readout:** High-fidelity text-to-speech powered by ElevenLabs with local audio caching.
   - **Rule-Based Fallback:** If Groq or internet access is unavailable, the agent falls back to a deterministic rule-based template response.

4. **Risk & Volatility Monitoring:**
   - **Single-Asset Concentration Risk:** Flags any investment exceeding 25% (Medium) or 40% (High) of total portfolio value.
   - **Sector Concentration Risk:** Flags any sector representing > 40% exposure.
   - **Historical Volatility & Drawdown:** Annualized standard deviation and peak-to-trough drawdown diagnostics.
   - **SIP Discipline Tracker:** Monthly systematic accumulation visualizer.

5. **Auditable Reporting & Exports:**
   - **Executive PDF Portfolio Dossier:** Formatted PDF generation via ReportLab.
   - **Holdings CSV:** Complete export with current prices, cost basis, and P&L.
   - **Transactions CSV:** Full ledger of historical cash flows.
   - **Methodology Documentation:** Explicit formulas and academic limitations displayed transparently in-app.

---

## 🏛️ Architecture & Project Structure

```text
Investmate/
├── agent/
│   ├── controller.py         # Full agent pipeline orchestration (intent -> tools -> LLM -> voice)
│   ├── intent_router.py      # Natural language query to tool mapping
│   ├── prompts.py            # Guardrail system prompts (prevents financial hallucination)
│   ├── tool_registry.py      # Approved tool allowlist & parameter validation
│   └── tools.py              # Deterministic tool implementations
├── database/
│   ├── db.py                 # Thread-safe SQLite connection pool & CRUD helpers
│   └── schema.sql            # Idempotent SQLite schema (Users, Portfolios, Assets, Prices, Txns)
├── models/
│   ├── portfolio.py          # Portfolio and holdings aggregation logic
│   └── transaction.py        # BUY/SELL/SIP weighted-average cost & cash tracking
├── services/
│   ├── market_data.py        # AMFI live NAV feed, manual quotes, CSV import
│   ├── portfolio_analytics.py# Valuation, simple returns, XIRR, SIP analytics
│   ├── report_service.py     # PDF & CSV generation matching dashboard numbers
│   ├── risk_analysis.py      # Concentration thresholds, volatility, drawdown
│   └── voice_service.py      # ElevenLabs TTS integration with local caching
├── ui/
│   ├── analytics_risk.py     # Risk diagnostics, sector treemap, SIP analytics
│   ├── assistant.py          # Conversational chat, quick prompt pills, voice player, inspector
│   ├── dashboard.py          # Executive KPIs, Plotly allocation donuts, holdings preview
│   ├── holdings.py           # Add holding, sell position, CSV import, inline price editor
│   ├── reports.py            # Download PDF dossier, CSVs, and inspect formulas
│   ├── transactions.py       # Full transaction ledger & cash management
│   └── watchlist.py          # Live AMFI NAV search, price directory & refresh
├── tests/
│   ├── test_agent.py         # Tests for intent routing and tool validation
│   ├── test_analytics.py     # Tests for XIRR, returns, and risk thresholds
│   └── test_portfolio.py     # Tests for portfolio summary and cash flows
├── app.py                    # Main Streamlit application entry point
├── config.py                 # Central configuration and environment loader
├── requirements.txt          # Python dependencies
└── .env                      # API keys and local configuration
```

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- Windows, macOS, or Linux

### 2. Environment Setup
```powershell
# Clone or navigate to the project directory
cd Investmate

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\Activate.ps1
# On macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Keys
Copy `.env.example` to `.env` (or update `.env` directly):
```env
# Groq LLM API Key (Free tier available at console.groq.com)
GROQ_API_KEY=your_groq_api_key_here

# ElevenLabs Voice API Key (Optional)
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# LLM Model
LLM_MODEL=llama-3.3-70b-versatile

# Base Currency
BASE_CURRENCY=INR
```
> **Note:** If no API keys are provided, the system automatically runs in **Offline/Demo Mode** with synthetic data and rule-based conversational responses.

### 4. Run the Application
```powershell
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### 5. Run the Test Suite
```powershell
pytest
```

---

## 🔒 Disclaimers & Regulatory Notes

InvestMate AI is an **educational decision-support project**. It does not execute autonomous trades, does not guarantee financial returns, and is not a SEBI-registered investment advisor. Market data may be delayed, simulated, or entered manually. Always consult a certified financial planner for real-world investments.
