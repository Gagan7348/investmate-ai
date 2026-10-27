"""
InvestMate AI — Configuration Module

Centralizes all application settings. Values are read from environment
variables (loaded via python-dotenv) with sensible defaults so the app
can run in demo mode without any .env file.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from the project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

def _get_setting(key: str, default: str = "") -> str:
    """Retrieve setting from environment variable, falling back to Streamlit secrets."""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = _get_setting("GROQ_API_KEY", "")
ELEVENLABS_API_KEY: str = _get_setting("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID: str = _get_setting("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")

# ---------------------------------------------------------------------------
# LLM Settings
# ---------------------------------------------------------------------------
LLM_MODEL: str = _get_setting("LLM_MODEL", "qwen/qwen3.8-27b")

# ---------------------------------------------------------------------------
# Application Settings
# ---------------------------------------------------------------------------
BASE_CURRENCY: str = _get_setting("BASE_CURRENCY", "INR")
DEMO_MODE: bool = _get_setting("DEMO_MODE", "false").lower() in ("true", "1", "yes")
DATABASE_PATH: str = _get_setting("DATABASE_PATH", str(PROJECT_ROOT / "investmate.db"))
MAX_TOOL_CALLS: int = int(_get_setting("MAX_TOOL_CALLS", "5"))
VOICE_ENABLED: bool = _get_setting("VOICE_ENABLED", "true").lower() in ("true", "1", "yes")
LOG_LEVEL: str = _get_setting("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Derived / Convenience Flags
# ---------------------------------------------------------------------------
GROQ_AVAILABLE: bool = bool(GROQ_API_KEY and GROQ_API_KEY != "gsk_your_groq_api_key_here")
ELEVENLABS_AVAILABLE: bool = bool(
    ELEVENLABS_API_KEY and ELEVENLABS_API_KEY != "your_elevenlabs_api_key_here"
)

# ---------------------------------------------------------------------------
# Currency Symbols
# ---------------------------------------------------------------------------
CURRENCY_SYMBOLS: dict[str, str] = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

def get_currency_symbol() -> str:
    """Return the symbol for the configured base currency."""
    return CURRENCY_SYMBOLS.get(BASE_CURRENCY, BASE_CURRENCY)

# ---------------------------------------------------------------------------
# Asset Type Constants
# ---------------------------------------------------------------------------
class AssetType:
    STOCK = "STOCK"
    MUTUAL_FUND = "MUTUAL_FUND"
    ETF = "ETF"
    CASH = "CASH"

    ALL = [STOCK, MUTUAL_FUND, ETF, CASH]

# ---------------------------------------------------------------------------
# Transaction Type Constants
# ---------------------------------------------------------------------------
class TransactionType:
    BUY = "BUY"
    SELL = "SELL"
    SIP = "SIP"           # Systematic Investment Plan (treated as a BUY with SIP tag)
    DIVIDEND = "DIVIDEND"
    CASH_IN = "CASH_IN"
    CASH_OUT = "CASH_OUT"

# ---------------------------------------------------------------------------
# Price Source Constants
# ---------------------------------------------------------------------------
class PriceSource:
    MANUAL = "MANUAL"
    CSV_IMPORT = "CSV_IMPORT"
    API_LIVE = "API_LIVE"
    API_DELAYED = "API_DELAYED"
    API_HISTORICAL = "API_HISTORICAL"
    SIMULATED = "SIMULATED"

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger("investmate")
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    return logger

logger = setup_logging()
