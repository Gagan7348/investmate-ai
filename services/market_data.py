"""
InvestMate AI — Market Data Service

Modular interface for fetching asset prices from various sources.

Implemented sources:
  1. Manual entry (always available)
  2. CSV import
  3. AMFI NAV feed for Indian mutual funds (free, public)
  4. yfinance-style API for stocks/ETFs (optional, may have limits)

Every price record includes: source, retrieval timestamp, and market date.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from typing import Optional

import requests

from database.db import (
    fetch_all, fetch_one, get_or_create_asset, upsert_price, get_latest_price,
)
from config import PriceSource, AssetType, logger


# ──────────────────────────────────────────────────────────────
# Manual Price Entry
# ──────────────────────────────────────────────────────────────

def set_manual_price(asset_id: int, price: float, price_date: str) -> None:
    """Record a manually-entered price."""
    if price <= 0:
        raise ValueError("Price must be positive.")
    upsert_price(asset_id, price, price_date, PriceSource.MANUAL)
    logger.info("Manual price set for asset %d: ₹%.2f on %s", asset_id, price, price_date)


# ──────────────────────────────────────────────────────────────
# CSV Import
# ──────────────────────────────────────────────────────────────

def parse_flexible_date(date_str: str) -> str | None:
    """Parse various date formats into standard ISO YYYY-MM-DD."""
    if not date_str:
        return None
    s = str(date_str).strip().strip("\"'")
    formats = (
        "%d-%b-%Y", "%d-%B-%Y", "%d-%b-%y",
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
        "%m/%d/%Y", "%m-%d-%Y", "%b %d, %Y",
        "%d %b %Y", "%Y/%m/%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s).strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def infer_ticker_from_filename(filename: str) -> tuple[str, str, str]:
    """
    Infer ticker symbol, asset name, and asset type from uploaded filename.
    e.g. 'NIFTY 50-21-09-2025-to-21-09-2026.csv' -> ('NIFTY 50', 'NIFTY 50 Index / ETF', 'ETF')
    """
    fn = filename.upper()
    if "NIFTY" in fn and "50" in fn:
        return "NIFTY 50", "NIFTY 50 Index / ETF", AssetType.ETF
    elif "BANKNIFTY" in fn or ("NIFTY" in fn and "BANK" in fn):
        return "BANKNIFTY", "Nifty Bank Index", AssetType.ETF
    elif "SENSEX" in fn:
        return "SENSEX", "BSE Sensex Index", AssetType.ETF
    elif "GOLDBEES" in fn or "GOLD" in fn:
        return "GOLDBEES.NS", "Nippon India ETF Gold BeES", AssetType.ETF
    elif "NIFTYBEES" in fn:
        return "NIFTYBEES.NS", "Nippon India ETF Nifty 50 BeES", AssetType.ETF

    # Try matching ticker-like prefix (e.g. RELIANCE, INFY)
    clean = re.sub(r"[\-_].*", "", filename).strip()
    clean = re.sub(r"\.csv$", "", clean, flags=re.IGNORECASE).strip()
    if clean:
        ticker = clean.upper()
        if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
            ticker = f"{ticker}.NS"
        return ticker, clean.title(), AssetType.STOCK

    return "IMPORTED_ASSET", "Imported Asset", AssetType.STOCK


def detect_and_parse_csv(csv_text: str, filename: str = "") -> dict:
    """
    Intelligently inspect and parse CSV content.
    Supports:
      1. NSE Official Historical Price CSVs (e.g., NIFTY 50, stocks: Date, Open, High, Low, Close...)
      2. Portfolio Holdings / Trades CSVs (e.g., Ticker/Symbol, Quantity, Buy Price, Date)
      3. Generic Pricing CSVs (ticker, price, date, asset_type)
    """
    lines = [l.strip() for l in csv_text.strip().splitlines() if l.strip()]
    if not lines:
        return {"type": "EMPTY", "error": "The uploaded CSV file is empty."}

def _safe_float(val: any, default: float = 0.0) -> float:
    """Safely parse float from string with comma stripping."""
    try:
        s = str(val).replace(",", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return default


def detect_and_parse_csv(csv_text: str, filename: str = "") -> dict:
    """
    Intelligently inspect and parse CSV content.
    Supports:
      1. Portfolio Holdings / Trades CSVs (Ticker/Symbol, Quantity, Buy Price, Date)
      2. NSE Official Historical Price CSVs (e.g. NIFTY 50: Date, Open, High, Low, Close...)
      3. Headerless NSE Price CSVs (21-SEP-2026, 23330.2, ...)
      4. Generic Pricing CSVs (ticker, price, date, asset_type)
    """
    lines = [l.strip() for l in csv_text.strip().splitlines() if l.strip()]
    if not lines:
        return {"type": "EMPTY", "error": "The uploaded CSV file is empty."}

    reader = list(csv.reader(io.StringIO(csv_text)))
    if not reader:
        return {"type": "EMPTY", "error": "Could not parse CSV content."}

    suggested_ticker, suggested_name, suggested_type = infer_ticker_from_filename(filename)

    # Check header
    first_row = [c.strip() for c in reader[0]]
    first_row_lower = [c.lower() for c in first_row]

    # Check for Symbol / Ticker columns first (indicates Holdings or Multi-Asset Pricing)
    sym_col_idx = None
    qty_col_idx = None
    price_col_idx = None
    date_col_idx = None
    type_col_idx = None
    name_col_idx = None

    for i, col in enumerate(first_row_lower):
        if col in ("ticker", "symbol", "instrument", "stock", "asset", "scrip"):
            sym_col_idx = i
        elif col in ("quantity", "qty", "qty.", "shares", "units", "holding", "volume") and "traded" not in col:
            qty_col_idx = i
        elif col in ("price", "buy_price", "purchase_price", "avg_cost", "avg. cost", "cost", "rate", "avg_price", "close", "ltp"):
            price_col_idx = i
        elif col in ("date", "buy_date", "purchase_date", "trade_date"):
            date_col_idx = i
        elif col in ("asset_type", "type", "category"):
            type_col_idx = i
        elif col in ("name", "asset_name", "stock_name", "company"):
            name_col_idx = i

    # Mode 1: Portfolio Holdings / Broker Export CSV
    if sym_col_idx is not None and (qty_col_idx is not None or type_col_idx is not None):
        parsed_holdings = []
        for row in reader[1:]:
            if not row or len(row) <= sym_col_idx:
                continue
            ticker = row[sym_col_idx].strip().upper()
            if not ticker or ticker.lower() in ("symbol", "ticker", "instrument"):
                continue

            qty = _safe_float(row[qty_col_idx], 1.0) if qty_col_idx is not None and len(row) > qty_col_idx else 1.0
            pr = _safe_float(row[price_col_idx], 100.0) if price_col_idx is not None and len(row) > price_col_idx else 100.0

            d = date.today().isoformat()
            if date_col_idx is not None and len(row) > date_col_idx:
                parsed_d = parse_flexible_date(row[date_col_idx])
                if parsed_d:
                    d = parsed_d

            # Inferred asset type
            a_type = AssetType.STOCK
            if type_col_idx is not None and len(row) > type_col_idx:
                t_val = row[type_col_idx].strip().upper()
                if "ETF" in t_val:
                    a_type = AssetType.ETF
                elif "MUTUAL" in t_val or "MF" in t_val:
                    a_type = AssetType.MUTUAL_FUND
            elif "BEES" in ticker or "ETF" in ticker or "NIFTY" in ticker:
                a_type = AssetType.ETF
            elif "FUND" in ticker or "PLAN" in ticker:
                a_type = AssetType.MUTUAL_FUND

            name = row[name_col_idx].strip() if name_col_idx is not None and len(row) > name_col_idx else ticker

            parsed_holdings.append({
                "ticker": ticker,
                "name": name,
                "asset_type": a_type,
                "quantity": qty,
                "price": pr,
                "date": d,
            })

        if parsed_holdings:
            return {
                "type": "HOLDINGS",
                "rows": parsed_holdings,
                "total_rows": len(parsed_holdings),
            }

    # Mode 2: Check if first row is already data (e.g. 21-SEP-2026, 23330.2, ...)
    first_col_date = parse_flexible_date(first_row[0])
    is_headerless_nse = bool(first_col_date and len(first_row) >= 2 and _safe_float(first_row[1]) > 0)

    # Mode 3: Check if header matches NSE EOD quotes (Date, Open, High, Low, Close...)
    has_date_col = any("date" in c for c in first_row_lower)
    has_close_col = any(c in ("close", "closing price", "close price", "adj close", "ltp", "nav") for c in first_row_lower)
    has_ohlc = any(c in ("open", "high", "low") for c in first_row_lower)
    is_nse_header = has_date_col and (has_close_col or has_ohlc) and sym_col_idx is None

    if is_headerless_nse or is_nse_header:
        start_idx = 0 if is_headerless_nse else 1
        date_idx = 0
        close_idx = 4 if len(reader[start_idx]) >= 5 else 1

        if is_nse_header:
            for i, col in enumerate(first_row_lower):
                if "date" in col:
                    date_idx = i
                elif col in ("close", "closing price", "close price", "adj close", "nav", "ltp"):
                    close_idx = i

        parsed_rows = []
        for row in reader[start_idx:]:
            if not row or len(row) <= max(date_idx, close_idx):
                continue
            d = parse_flexible_date(row[date_idx])
            if not d:
                continue
            p = _safe_float(row[close_idx])
            if p <= 0:
                continue
            o = _safe_float(row[1], p) if len(row) > 1 else p
            h = _safe_float(row[2], p) if len(row) > 2 else p
            l = _safe_float(row[3], p) if len(row) > 3 else p

            parsed_rows.append({
                "date": d,
                "price": p,
                "open": o,
                "high": h,
                "low": l,
            })

        if parsed_rows:
            return {
                "type": "NSE_HISTORICAL",
                "suggested_ticker": suggested_ticker,
                "suggested_name": suggested_name,
                "suggested_type": suggested_type,
                "rows": parsed_rows,
                "total_rows": len(parsed_rows),
                "latest_price": parsed_rows[0]["price"],
                "latest_date": parsed_rows[0]["date"],
                "earliest_date": parsed_rows[-1]["date"],
            }

    # Mode 4: Generic Prices Fallback (DictReader)
    return {
        "type": "GENERIC_PRICES",
        "headers": first_row,
        "sample": reader[1:6],
    }


def import_nse_historical_prices(
    csv_text: str,
    ticker: str,
    name: str = "",
    asset_type: str = AssetType.ETF,
    exchange: str = "NSE",
    sector: str = "Index / ETF",
) -> dict:
    """Import historical prices from an NSE / Yahoo historical CSV feed."""
    parsed_info = detect_and_parse_csv(csv_text, filename=ticker)
    rows = parsed_info.get("rows", [])
    if not rows:
        return {"imported": 0, "errors": ["No valid date and price rows could be parsed from the CSV."]}

    final_ticker = ticker.strip().upper()
    final_name = name.strip() or final_ticker
    asset = get_or_create_asset(
        final_ticker, final_name, asset_type, exchange=exchange, sector=sector
    )
    asset_id = asset["id"]

    imported = 0
    errors = []
    prices_to_insert = []
    for r in rows:
        try:
            d = r["date"]
            p = float(r["price"])
            if p > 0:
                upsert_price(asset_id, p, d, PriceSource.CSV_IMPORT)
                imported += 1
        except Exception as e:
            errors.append(f"Row {r}: {e}")

    # Set latest price
    if rows:
        latest = rows[0]
        upsert_price(asset_id, latest["price"], latest["date"], PriceSource.CSV_IMPORT)

    logger.info("Imported %d historical prices for %s (%s)", imported, final_ticker, final_name)
    return {
        "imported": imported,
        "ticker": final_ticker,
        "name": final_name,
        "latest_price": rows[0]["price"] if rows else 0,
        "latest_date": rows[0]["date"] if rows else "",
        "earliest_date": rows[-1]["date"] if rows else "",
        "errors": errors[:5],
    }


def import_holdings_from_csv(csv_text: str, portfolio_id: int) -> dict:
    """Import holdings and purchase transactions into the active portfolio."""
    from models.transaction import record_buy
    parsed_info = detect_and_parse_csv(csv_text)
    rows = parsed_info.get("rows", [])
    if not rows:
        return {"imported": 0, "errors": ["No valid holdings rows detected."]}

    imported = 0
    errors = []
    total_val = 0.0

    for i, r in enumerate(rows, start=1):
        try:
            ticker = r["ticker"]
            name = r.get("name", ticker)
            asset_type = r.get("asset_type", AssetType.STOCK)
            qty = float(r.get("quantity", 1.0))
            price = float(r.get("price", 100.0))
            txn_date = r.get("date", date.today().isoformat())

            asset = get_or_create_asset(ticker, name, asset_type, exchange="NSE")
            record_buy(
                portfolio_id=portfolio_id,
                asset_id=asset["id"],
                quantity=qty,
                price=price,
                txn_date=txn_date,
                notes="CSV Portfolio Import",
            )
            imported += 1
            total_val += (qty * price)
        except Exception as e:
            errors.append(f"Row {i} ({r.get('ticker', 'unknown')}): {e}")

    logger.info("Imported %d holdings (Total: ₹%.2f) to portfolio %d", imported, total_val, portfolio_id)
    return {
        "imported": imported,
        "total_value": total_val,
        "errors": errors[:5],
    }


def import_prices_from_csv(csv_text: str) -> dict:
    """
    Import prices from CSV text with automatic format detection.
    Supports:
      • NSE Historical daily quotes (NIFTY 50, stocks: Date, Open, High, Low, Close)
      • Standard pricing feed: ticker, asset_type, price, date
    """
    detected = detect_and_parse_csv(csv_text)

    # If it is NSE historical data (e.g. NIFTY 50)
    if detected.get("type") == "NSE_HISTORICAL":
        t = detected.get("suggested_ticker", "NIFTY 50")
        n = detected.get("suggested_name", "NIFTY 50 Index / ETF")
        at = detected.get("suggested_type", AssetType.ETF)
        return import_nse_historical_prices(csv_text, ticker=t, name=n, asset_type=at)

    # Fallback to standard DictReader
    reader = csv.DictReader(io.StringIO(csv_text))
    imported = 0
    errors = []

    fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]
    required = {"ticker", "price"}
    if not any("ticker" in f for f in fieldnames) or not any("price" in f for f in fieldnames):
        # If it has rows, attempt to import as NSE historical
        if detected.get("rows"):
            return import_nse_historical_prices(csv_text, ticker="NIFTY 50", name="NIFTY 50 Index / ETF")
        return {
            "imported": 0,
            "errors": [
                "Could not automatically map columns. Please ensure columns include 'Date' & 'Close' (NSE EOD format) "
                "or 'ticker', 'price', and 'date'."
            ],
        }

    for i, row in enumerate(reader, start=2):
        try:
            clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k and v}
            ticker = clean_row.get("ticker", "").upper()
            if not ticker: continue
            asset_type = clean_row.get("asset_type", AssetType.STOCK).upper()
            price = float(clean_row.get("price", 0))
            raw_date = clean_row.get("date", date.today().isoformat())
            price_date = parse_flexible_date(raw_date) or date.today().isoformat()

            if price <= 0:
                continue

            name = clean_row.get("name", ticker)
            exchange = clean_row.get("exchange", "NSE")
            scheme_code = clean_row.get("scheme_code", "")
            sector = clean_row.get("sector", "General")

            asset = get_or_create_asset(
                ticker, name, asset_type, exchange=exchange,
                scheme_code=scheme_code, sector=sector,
            )
            upsert_price(asset["id"], price, price_date, PriceSource.CSV_IMPORT)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    return {"imported": imported, "errors": errors, "total_rows": imported + len(errors)}


# ──────────────────────────────────────────────────────────────
# AMFI NAV Fetch (Indian Mutual Funds)
# ──────────────────────────────────────────────────────────────
AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def fetch_amfi_nav(scheme_code: str) -> dict | None:
    """
    Fetch the latest NAV for an Indian mutual fund from AMFI's public feed.

    The AMFI file is a semicolon-separated text file with columns:
    Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;[Plan;Option;]Net Asset Value;Date
    NAV is always fields[-2], date is always fields[-1].
    """
    try:
        resp = requests.get(AMFI_NAV_URL, timeout=15)
        resp.raise_for_status()

        target_code = str(scheme_code).strip()
        for line in resp.text.splitlines():
            fields = line.split(";")
            if len(fields) >= 5 and fields[0].strip() == target_code:
                nav_str = fields[-2].strip()
                nav_date_str = fields[-1].strip()
                try:
                    nav = float(nav_str)
                except ValueError:
                    continue

                # Parse date (DD-Mon-YYYY format e.g. 23-Oct-2026)
                nav_date = date.today().isoformat()
                if nav_date_str:
                    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
                        try:
                            parsed = datetime.strptime(nav_date_str, fmt)
                            nav_date = parsed.date().isoformat()
                            break
                        except ValueError:
                            pass

                name_parts = [x.strip() for x in fields[3:-2] if x.strip() and x.strip() != "-"]
                scheme_name = " - ".join(name_parts) if name_parts else f"Scheme {scheme_code}"
                return {
                    "scheme_code": target_code,
                    "scheme_name": scheme_name,
                    "nav": nav,
                    "nav_date": nav_date,
                    "source": PriceSource.API_LIVE,
                }

        logger.warning("Scheme code %s not found in AMFI feed", scheme_code)
        return None
    except requests.RequestException as e:
        logger.error("Failed to fetch AMFI data: %s", e)
        return None


def fetch_live_stock_price(ticker: str) -> dict | None:
    """
    Fetch real live / last close quote for an Indian stock or ETF via yfinance.
    Appends .NS if exchange is NSE and not already specified.
    """
    try:
        import yfinance as yf
        sym = ticker.strip()
        if not sym.endswith(".NS") and not sym.endswith(".BO"):
            sym = f"{sym}.NS"

        tkr = yf.Ticker(sym)
        price = None
        # Try fast_info first
        try:
            price = float(tkr.fast_info.get("lastPrice") or tkr.fast_info.get("regularMarketPrice") or 0.0)
        except Exception:
            pass

        # Fallback to history
        if not price or price <= 0:
            hist = tkr.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        if price and price > 0:
            return {
                "ticker": ticker,
                "price": round(price, 2),
                "price_date": date.today().isoformat(),
                "source": PriceSource.API_LIVE,
            }
        return None
    except Exception as e:
        logger.warning("Failed to fetch live quote for %s: %s", ticker, e)
        return None


def update_mutual_fund_nav(asset_id: int, scheme_code: str) -> dict | None:
    """Fetch and store the latest NAV for a mutual fund."""
    result = fetch_amfi_nav(scheme_code)
    if result:
        upsert_price(asset_id, result["nav"], result["nav_date"], PriceSource.API_DELAYED)
        logger.info("Updated NAV for scheme %s: ₹%.4f on %s",
                     scheme_code, result["nav"], result["nav_date"])
    return result


# ──────────────────────────────────────────────────────────────
# Stock / ETF Price Fetch (yfinance-style, optional)
# ──────────────────────────────────────────────────────────────

def fetch_stock_price(ticker: str) -> dict | None:
    """
    Attempt to fetch the latest price for a stock/ETF ticker.
    Uses a simple Yahoo Finance query (no auth required for basic quotes).
    Falls back gracefully if unavailable.
    """
    try:
        # Use Yahoo Finance v8 API (public, no key needed for basic data)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {"interval": "1d", "range": "5d"}
        headers = {"User-Agent": "InvestMateAI/1.0"}

        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.warning("Yahoo Finance returned %d for %s", resp.status_code, ticker)
            return None

        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None

        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice", 0)
        if price <= 0:
            return None

        return {
            "ticker": ticker,
            "price": price,
            "currency": meta.get("currency", "INR"),
            "exchange": meta.get("exchangeName", ""),
            "market_time": datetime.fromtimestamp(
                meta.get("regularMarketTime", 0)
            ).isoformat() if meta.get("regularMarketTime") else "",
            "source": PriceSource.API_DELAYED,
        }
    except Exception as e:
        logger.warning("Could not fetch price for %s: %s", ticker, e)
        return None


def update_stock_price(asset_id: int, ticker: str) -> dict | None:
    """Fetch and store the latest price for a stock/ETF."""
    result = fetch_stock_price(ticker)
    if result:
        price_date = date.today().isoformat()
        upsert_price(asset_id, result["price"], price_date, PriceSource.API_DELAYED)
        logger.info("Updated price for %s: ₹%.2f", ticker, result["price"])
    return result


# ──────────────────────────────────────────────────────────────
# Bulk Price Refresh
# ──────────────────────────────────────────────────────────────

def refresh_all_prices(portfolio_id: int) -> dict:
    """
    Attempt to refresh prices for all assets in a portfolio.
    Returns summary of successes and failures.
    """
    from models.portfolio import list_holdings
    holdings = list_holdings(portfolio_id)

    updated = []
    failed = []

    for h in holdings:
        asset_type = h["asset_type"]
        try:
            if asset_type == AssetType.MUTUAL_FUND and h.get("scheme_code"):
                result = update_mutual_fund_nav(h["asset_id"], h["scheme_code"])
            elif asset_type in (AssetType.STOCK, AssetType.ETF) and h.get("ticker"):
                result = update_stock_price(h["asset_id"], h["ticker"])
            else:
                result = None

            if result:
                updated.append(h["ticker"])
            else:
                failed.append(h["ticker"])
        except Exception as e:
            failed.append(f"{h['ticker']} ({e})")

    return {
        "updated": updated,
        "failed": failed,
        "updated_count": len(updated),
        "failed_count": len(failed),
    }


# ──────────────────────────────────────────────────────────────
# Price History Query
# ──────────────────────────────────────────────────────────────

def get_price_history(asset_id: int, days: int = 365) -> list[dict]:
    """Return price history for an asset, most recent first."""
    return fetch_all(
        """SELECT price, price_date, source, retrieved_at
           FROM price_history
           WHERE asset_id = ?
           ORDER BY price_date DESC
           LIMIT ?""",
        (asset_id, days),
    )


def get_all_assets_freshness() -> dict:
    """Aggregate price freshness across all tracked assets."""
    assets = fetch_all("SELECT id, ticker FROM assets")
    total = len(assets)
    priced = 0
    stale_assets = []

    for a in assets:
        latest = get_latest_price(a["id"])
        if latest:
            priced += 1
            try:
                price_date = datetime.fromisoformat(latest["price_date"]).date()
                days_old = (date.today() - price_date).days
                if days_old > 3:
                    stale_assets.append(a["ticker"])
            except Exception:
                stale_assets.append(a["ticker"])

    return {
        "total_assets": total,
        "priced_assets": priced,
        "stale_count": len(stale_assets),
        "stale_assets": stale_assets,
    }


def refresh_all_asset_prices() -> dict:
    """Refresh prices for ALL assets in the database (no portfolio required)."""
    assets = fetch_all(
        "SELECT id, ticker, asset_type, scheme_code FROM assets"
    )
    updated = []
    failed = []

    for a in assets:
        asset_type = a["asset_type"]
        try:
            if asset_type == AssetType.MUTUAL_FUND and a.get("scheme_code"):
                result = update_mutual_fund_nav(a["id"], a["scheme_code"])
            elif asset_type in (AssetType.STOCK, AssetType.ETF) and a.get("ticker"):
                result = update_stock_price(a["id"], a["ticker"])
            else:
                result = None

            if result:
                updated.append(a["ticker"])
            else:
                failed.append(a["ticker"])
        except Exception as e:
            failed.append(f"{a['ticker']} ({e})")

    return {
        "updated": len(updated),
        "failed": len(failed),
        "updated_tickers": updated,
        "failed_tickers": failed,
    }


def get_data_freshness(asset_id: int) -> dict:
    """Check how fresh the latest price data is for an asset."""
    latest = get_latest_price(asset_id)
    if not latest:
        return {
            "has_price": False,
            "message": "No price data available.",
            "stale": True,
        }

    price_date = datetime.fromisoformat(latest["price_date"]).date()
    days_old = (date.today() - price_date).days

    return {
        "has_price": True,
        "price": latest["price"],
        "price_date": latest["price_date"],
        "source": latest["source"],
        "days_old": days_old,
        "stale": days_old > 3,
        "message": (
            f"Price from {latest['price_date']} ({latest['source']})"
            + (f" — ⚠️ {days_old} days old" if days_old > 3 else "")
        ),
    }
