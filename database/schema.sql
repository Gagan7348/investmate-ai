-- ==========================================================================
-- InvestMate AI — Database Schema  (SQLite)
-- ==========================================================================
-- Conventions:
--   • All monetary amounts are stored as REAL (IEEE-754).  For a production
--     system you would use DECIMAL / fixed-point; for this academic MVP the
--     Python code uses Decimal where precision matters.
--   • Timestamps are ISO-8601 strings in UTC.
--   • Every table has created_at / updated_at columns.
-- ==========================================================================

-- Users
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    display_name    TEXT    NOT NULL DEFAULT '',
    email           TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Portfolios (a user may have more than one)
CREATE TABLE IF NOT EXISTS portfolios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    description     TEXT    DEFAULT '',
    base_currency   TEXT    NOT NULL DEFAULT 'INR',
    cash_balance    REAL    NOT NULL DEFAULT 0.0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

-- Assets (canonical registry — shared across portfolios)
CREATE TABLE IF NOT EXISTS assets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT    NOT NULL,           -- e.g. RELIANCE.NS, INF209K01YQ0
    name            TEXT    NOT NULL DEFAULT '',
    asset_type      TEXT    NOT NULL CHECK(asset_type IN ('STOCK','MUTUAL_FUND','ETF','CASH')),
    exchange        TEXT    DEFAULT '',          -- NSE, BSE, AMFI, etc.
    scheme_code     TEXT    DEFAULT '',          -- AMFI scheme code for MFs
    sector          TEXT    DEFAULT '',
    currency        TEXT    NOT NULL DEFAULT 'INR',
    metadata_json   TEXT    DEFAULT '{}',        -- flexible extra fields
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(ticker, asset_type)
);

-- Holdings (link between portfolio and asset with aggregated position)
CREATE TABLE IF NOT EXISTS holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id        INTEGER NOT NULL REFERENCES assets(id),
    quantity        REAL    NOT NULL DEFAULT 0.0,
    avg_cost_price  REAL    NOT NULL DEFAULT 0.0,  -- weighted-average cost per unit
    total_invested  REAL    NOT NULL DEFAULT 0.0,   -- sum of buy amounts
    realized_pnl    REAL    NOT NULL DEFAULT 0.0,
    notes           TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(portfolio_id, asset_id)
);

-- Transactions (immutable ledger of buys, sells, SIPs, dividends, cash flows)
CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id        INTEGER REFERENCES assets(id),       -- NULL for pure cash txns
    txn_type        TEXT    NOT NULL CHECK(txn_type IN ('BUY','SELL','SIP','DIVIDEND','CASH_IN','CASH_OUT')),
    quantity        REAL    NOT NULL DEFAULT 0.0,
    price           REAL    NOT NULL DEFAULT 0.0,          -- per-unit price at txn time
    amount          REAL    NOT NULL DEFAULT 0.0,          -- total = quantity * price (+ fees)
    fees            REAL    NOT NULL DEFAULT 0.0,
    txn_date        TEXT    NOT NULL,                       -- ISO date of the transaction
    notes           TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Price History
CREATE TABLE IF NOT EXISTS price_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id        INTEGER NOT NULL REFERENCES assets(id),
    price           REAL    NOT NULL,
    price_date      TEXT    NOT NULL,           -- market date
    source          TEXT    NOT NULL DEFAULT 'MANUAL',  -- MANUAL, CSV_IMPORT, API_LIVE, …
    retrieved_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(asset_id, price_date, source)
);

-- Watchlist
CREATE TABLE IF NOT EXISTS watchlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id        INTEGER NOT NULL REFERENCES assets(id),
    target_price    REAL    DEFAULT NULL,
    alert_above     REAL    DEFAULT NULL,
    alert_below     REAL    DEFAULT NULL,
    notes           TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(portfolio_id, asset_id)
);

-- Agent Activity Log
CREATE TABLE IF NOT EXISTS agent_activity (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER REFERENCES portfolios(id),
    user_query      TEXT    NOT NULL,
    detected_intent TEXT    DEFAULT '',
    tools_called    TEXT    DEFAULT '[]',       -- JSON array of tool names
    tool_results    TEXT    DEFAULT '{}',       -- JSON object of tool outputs
    final_response  TEXT    DEFAULT '',
    response_audio  TEXT    DEFAULT '',         -- path or cache key for TTS audio
    duration_ms     INTEGER DEFAULT 0,
    error           TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Generated Reports
CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    report_type     TEXT    NOT NULL DEFAULT 'SUMMARY',
    report_date     TEXT    NOT NULL,
    data_json       TEXT    NOT NULL DEFAULT '{}',
    file_path       TEXT    DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_holdings_portfolio   ON holdings(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_transactions_portfolio ON transactions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date    ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_price_history_asset  ON price_history(asset_id, price_date);
CREATE INDEX IF NOT EXISTS idx_watchlist_portfolio  ON watchlist(portfolio_id);
