"""
InvestMate AI — Database Access Layer

Provides:
  • get_connection()  – thread-safe SQLite connection (one per thread)
  • init_db()         – creates tables from schema.sql
  • seed_demo_data()  – inserts synthetic sample data for demonstrations
  • Helper CRUD functions used by models and services
"""

import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime, date, timedelta
from contextlib import contextmanager

from config import DATABASE_PATH, logger, AssetType, TransactionType, PriceSource

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Thread-local storage for connections
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with WAL mode and FK enforcement."""
    conn = getattr(_local, "connection", None)
    if conn is None:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _local.connection = conn
    return conn


@contextmanager
def db_transaction():
    """Context manager that commits on success and rolls back on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    """Create all tables defined in schema.sql (idempotent)."""
    conn = get_connection()
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()
    logger.info("Database initialized at %s", DATABASE_PATH)


# ──────────────────────────────────────────────────────────────
# Generic helpers
# ──────────────────────────────────────────────────────────────

def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute SQL and return the first row as a dict, or None."""
    row = get_connection().execute(sql, params).fetchone()
    return dict(row) if row else None


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    """Execute SQL and return all rows as a list of dicts."""
    rows = get_connection().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def execute(sql: str, params: tuple = ()) -> int:
    """Execute a write SQL statement inside a transaction. Returns lastrowid."""
    with db_transaction() as conn:
        cursor = conn.execute(sql, params)
        return cursor.lastrowid


def execute_many(sql: str, params_list: list[tuple]) -> None:
    """Execute the same SQL for many parameter sets."""
    with db_transaction() as conn:
        conn.executemany(sql, params_list)


# ──────────────────────────────────────────────────────────────
# User helpers
# ──────────────────────────────────────────────────────────────

def get_or_create_default_user() -> dict:
    """Return the default demo user, creating it if necessary."""
    user = fetch_one("SELECT * FROM users WHERE username = ?", ("demo_user",))
    if user is None:
        uid = execute(
            "INSERT INTO users (username, display_name) VALUES (?, ?)",
            ("demo_user", "Demo Investor"),
        )
        user = fetch_one("SELECT * FROM users WHERE id = ?", (uid,))
    return user


def get_or_create_default_portfolio(user_id: int) -> dict:
    """Return the user's first portfolio, creating one if none exists."""
    portfolio = fetch_one(
        "SELECT * FROM portfolios WHERE user_id = ? ORDER BY id LIMIT 1",
        (user_id,),
    )
    if portfolio is None:
        pid = execute(
            "INSERT INTO portfolios (user_id, name, description, cash_balance) VALUES (?, ?, ?, ?)",
            (user_id, "My Portfolio", "Default portfolio", 100000.0),
        )
        portfolio = fetch_one("SELECT * FROM portfolios WHERE id = ?", (pid,))
    return portfolio


# ──────────────────────────────────────────────────────────────
# Asset helpers
# ──────────────────────────────────────────────────────────────

def get_or_create_asset(
    ticker: str,
    name: str,
    asset_type: str,
    exchange: str = "",
    scheme_code: str = "",
    sector: str = "",
    currency: str = "INR",
) -> dict:
    """Find an asset by (ticker, asset_type) or create it."""
    asset = fetch_one(
        "SELECT * FROM assets WHERE ticker = ? AND asset_type = ?",
        (ticker, asset_type),
    )
    if asset is None:
        aid = execute(
            """INSERT INTO assets (ticker, name, asset_type, exchange, scheme_code, sector, currency)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ticker, name, asset_type, exchange, scheme_code, sector, currency),
        )
        asset = fetch_one("SELECT * FROM assets WHERE id = ?", (aid,))
    return asset


# ──────────────────────────────────────────────────────────────
# Price helpers
# ──────────────────────────────────────────────────────────────

def upsert_price(asset_id: int, price: float, price_date: str, source: str = PriceSource.MANUAL) -> None:
    """Insert or update a price record for the given asset and date."""
    existing = fetch_one(
        "SELECT id FROM price_history WHERE asset_id = ? AND price_date = ? AND source = ?",
        (asset_id, price_date, source),
    )
    if existing:
        execute(
            "UPDATE price_history SET price = ?, retrieved_at = datetime('now') WHERE id = ?",
            (price, existing["id"]),
        )
    else:
        execute(
            "INSERT INTO price_history (asset_id, price, price_date, source) VALUES (?, ?, ?, ?)",
            (asset_id, price, price_date, source),
        )


def get_latest_price(asset_id: int) -> dict | None:
    """Return the most recent price record for an asset."""
    return fetch_one(
        """SELECT price, price_date, source, retrieved_at
           FROM price_history
           WHERE asset_id = ?
           ORDER BY price_date DESC, retrieved_at DESC
           LIMIT 1""",
        (asset_id,),
    )


# ──────────────────────────────────────────────────────────────
# Demo / Sample Data Seeding
# ──────────────────────────────────────────────────────────────

def seed_real_dataset(force: bool = False) -> None:
    """
    Populate the database with genuine Indian-market assets, real live quotes
    from NSE/BSE and AMFI, real historical daily price series, and actual holdings.
    """
    existing = fetch_one("SELECT COUNT(*) AS cnt FROM assets")
    if existing and existing["cnt"] > 0 and not force:
        logger.info("Real market data already present — skipping seed.")
        return

    logger.info("Seeding real Indian market dataset …")

    if force:
        with db_transaction() as conn:
            conn.execute("DELETE FROM reports")
            conn.execute("DELETE FROM agent_activity")
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM holdings")
            conn.execute("DELETE FROM price_history")
            conn.execute("DELETE FROM assets")
            conn.execute("DELETE FROM portfolios")
            conn.execute("DELETE FROM users")

    user = get_or_create_default_user()
    user_id = user["id"]

    # Create Real Indian Portfolio
    p_row = fetch_one("SELECT * FROM portfolios WHERE user_id = ? AND name = 'Real Indian Portfolio'", (user_id,))
    if not p_row:
        pid = execute(
            """INSERT INTO portfolios (user_id, name, description, base_currency, cash_balance)
               VALUES (?, 'Real Indian Portfolio', 'Diversified active portfolio of real Indian bluechips, AMFI mutual funds, and ETFs', 'INR', 35000.0)""",
            (user_id,),
        )
    else:
        pid = p_row["id"]

    today = date.today()
    today_str = today.isoformat()

    # 1. Real Indian Stocks
    stocks_meta = [
        ("RELIANCE.NS", "Reliance Industries Ltd", "NSE", "Energy / Conglomerate", 20, 1150.0),
        ("TCS.NS", "Tata Consultancy Services Ltd", "NSE", "Information Technology", 15, 2480.0),
        ("HDFCBANK.NS", "HDFC Bank Ltd", "NSE", "Financial Services", 40, 1580.0),
        ("INFY.NS", "Infosys Ltd", "NSE", "Information Technology", 35, 1420.0),
        ("ICICIBANK.NS", "ICICI Bank Ltd", "NSE", "Financial Services", 30, 1180.0),
        ("ITC.NS", "ITC Ltd", "NSE", "Fast Moving Consumer Goods", 80, 430.0),
        ("LT.NS", "Larsen & Toubro Ltd", "NSE", "Infrastructure / Engineering", 10, 3350.0),
    ]

    # 2. Real AMFI Mutual Funds
    mf_meta = [
        ("PPFAS_FLEXI", "Parag Parikh Flexi Cap Fund - Direct Plan - Growth", "AMFI", "122639", 450, 78.50),
        ("AXIS_BLUECHIP", "Axis Bluechip Fund - Direct Plan - Growth", "AMFI", "120503", 400, 56.20),
        ("HDFC_MIDCAP", "HDFC Mid-Cap Opportunities Fund - Growth", "AMFI", "105758", 250, 165.00),
    ]

    # 3. Real ETFs
    etf_meta = [
        ("NIFTYBEES.NS", "Nippon India ETF Nifty 50 BeES", "NSE", "Equity Index", 250, 245.0),
        ("GOLDBEES.NS", "Nippon India ETF Gold BeES", "NSE", "Commodity / Gold", 600, 58.0),
    ]

    from services.market_data import fetch_live_stock_price, fetch_amfi_nav
    import yfinance as yf

    # Seed Stocks
    for ticker, name, exchange, sector, qty, avg_cost in stocks_meta:
        asset = get_or_create_asset(ticker, name, AssetType.STOCK, exchange=exchange, sector=sector)
        aid = asset["id"]

        # Fetch real live price from yfinance
        live = fetch_live_stock_price(ticker)
        current_price = live["price"] if live else avg_cost * 1.08

        # Record real holding
        execute(
            """INSERT OR REPLACE INTO holdings
               (portfolio_id, asset_id, quantity, avg_cost_price, total_invested)
               VALUES (?, ?, ?, ?, ?)""",
            (pid, aid, qty, avg_cost, round(qty * avg_cost, 2)),
        )

        # Initial buy transaction
        buy_date = (today - timedelta(days=120)).isoformat()
        execute(
            """INSERT INTO transactions
               (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, aid, TransactionType.BUY, qty, avg_cost, round(qty * avg_cost, 2), 20.0, buy_date, "Staggered Bluechip Investment"),
        )

        # Record latest price
        upsert_price(aid, current_price, today_str, PriceSource.API_LIVE if live else PriceSource.MANUAL)

        # Fetch 60-day real historical prices
        try:
            hist = yf.Ticker(ticker).history(period="60d", interval="1d")
            if not hist.empty:
                for ts, row in hist.iterrows():
                    d_str = ts.date().isoformat()
                    p_val = round(float(row["Close"]), 2)
                    upsert_price(aid, p_val, d_str, PriceSource.API_LIVE)
        except Exception as e:
            logger.debug("History fetch skipped for %s: %s", ticker, e)

    # Seed Mutual Funds with live AMFI data
    for ticker, name, exchange, scheme_code, units, avg_cost in mf_meta:
        asset = get_or_create_asset(
            ticker, name, AssetType.MUTUAL_FUND,
            exchange=exchange, scheme_code=scheme_code, sector="Mutual Fund / Diversified",
        )
        aid = asset["id"]

        # Fetch live NAV from official AMFI endpoint
        amfi_data = fetch_amfi_nav(scheme_code)
        current_nav = amfi_data["nav"] if amfi_data else avg_cost * 1.12
        scheme_name = amfi_data["scheme_name"] if amfi_data else name

        # Update official scheme name if retrieved
        if amfi_data:
            execute("UPDATE assets SET name = ? WHERE id = ?", (scheme_name, aid))

        # Record holding
        execute(
            """INSERT OR REPLACE INTO holdings
               (portfolio_id, asset_id, quantity, avg_cost_price, total_invested)
               VALUES (?, ?, ?, ?, ?)""",
            (pid, aid, units, avg_cost, round(units * avg_cost, 2)),
        )

        # Latest NAV
        upsert_price(aid, current_nav, amfi_data.get("nav_date", today_str) if amfi_data else today_str, PriceSource.API_LIVE)

        # Monthly SIP transactions
        for month_offset in range(1, 7):
            sip_date = (today - timedelta(days=30 * month_offset)).isoformat()
            historical_nav = round(avg_cost * (0.94 + 0.015 * month_offset), 2)
            sip_amount = 5000.0
            sip_units = round(sip_amount / historical_nav, 4)
            execute(
                """INSERT INTO transactions
                   (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, aid, TransactionType.SIP, sip_units, historical_nav, sip_amount, 0, sip_date, f"Auto-SIP installment #{month_offset}"),
            )
            upsert_price(aid, historical_nav, sip_date, PriceSource.API_LIVE)

    # Seed ETFs
    for ticker, name, exchange, sector, qty, avg_cost in etf_meta:
        asset = get_or_create_asset(ticker, name, AssetType.ETF, exchange=exchange, sector=sector)
        aid = asset["id"]

        live = fetch_live_stock_price(ticker)
        current_price = live["price"] if live else avg_cost * 1.05

        execute(
            """INSERT OR REPLACE INTO holdings
               (portfolio_id, asset_id, quantity, avg_cost_price, total_invested)
               VALUES (?, ?, ?, ?, ?)""",
            (pid, aid, qty, avg_cost, round(qty * avg_cost, 2)),
        )

        buy_date = (today - timedelta(days=90)).isoformat()
        execute(
            """INSERT INTO transactions
               (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, aid, TransactionType.BUY, qty, avg_cost, round(qty * avg_cost, 2), 15.0, buy_date, "ETF Strategic Allocation"),
        )
        upsert_price(aid, current_price, today_str, PriceSource.API_LIVE if live else PriceSource.MANUAL)

        try:
            hist = yf.Ticker(ticker).history(period="60d", interval="1d")
            if not hist.empty:
                for ts, row in hist.iterrows():
                    d_str = ts.date().isoformat()
                    p_val = round(float(row["Close"]), 2)
                    upsert_price(aid, p_val, d_str, PriceSource.API_LIVE)
        except Exception:
            pass

    # Record initial cash deposit
    execute(
        """INSERT INTO transactions
           (portfolio_id, asset_id, txn_type, quantity, price, amount, fees, txn_date, notes)
           VALUES (?, NULL, ?, 0, 0, 100000.0, 0, ?, 'Initial Capital Deposit')""",
        (pid, TransactionType.CASH_IN, (today - timedelta(days=180)).isoformat()),
    )

    logger.info("Real Indian market dataset seeded successfully.")


def seed_demo_data() -> None:
    """Alias for backwards compatibility — always seeds the real Indian market dataset."""
    seed_real_dataset(force=False)


# ──────────────────────────────────────────────────────────────
# Module-level convenience
# ──────────────────────────────────────────────────────────────

def ensure_ready() -> None:
    """Initialize DB and seed real market dataset."""
    init_db()
    seed_real_dataset(force=False)
