"""
api.py - Improved lightweight Flask API for the stock simulator with robust portfolio/history handling.

Drop-in replacement for your previous api_server.py; main changes:
 - /api/portfolio and /api/history now accept Portfolio.load() returning either an object (with attributes)
   or a plain dict (e.g. read directly from portfolio.json).
 - small defensive checks to avoid attribute errors and to always return the JSON shape the frontend expects.
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pathlib import Path
from services.prices import make_default_market, Stock
from trading import Portfolio
import datetime
import os
import shutil
import json
import logging
from logging.handlers import RotatingFileHandler

# -----------------------
# Paths and Flask app
# -----------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

app = Flask(__name__, static_folder=str(STATIC_DIR))
CORS(app)

# -----------------------
# Logging Setup
# -----------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "server.log"

logger = logging.getLogger("stock_api")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    filename=str(LOG_FILE),
    maxBytes=5_000_000,  # rotate after 5MB
    backupCount=3
)
formatter = logging.Formatter("%(asctime)s  %(levelname)s  %(message)s")
handler.setFormatter(formatter)

# Avoid adding multiple handlers on reloads
if not logger.handlers:
    logger.addHandler(handler)


@app.before_request
def log_request():
    try:
        body = request.get_data(as_text=True)
    except Exception:
        body = ""
    logger.info(f"REQ {request.remote_addr} {request.method} {request.path} body={body}")

# -----------------------
# Utility helpers
# -----------------------
def resp_ok(message="ok", data=None, status=200):
    return jsonify({"success": True, "message": message, "data": data or {}}), status

def resp_err(message="error", status=400, data=None):
    return jsonify({"success": False, "message": message, "data": data or {}}), status

def read_json_request(require_json=False):
    try:
        j = request.get_json(silent=True)
    except Exception:
        j = None
    if require_json and j is None:
        return None, resp_err("Request body must be valid JSON", 400)
    return j or {}, None

def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------
# Global market instance
# -----------------------
market = make_default_market()

# -----------------------
# Serve frontend
# -----------------------
@app.route("/", methods=["GET"])
def root():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return send_from_directory(str(STATIC_DIR), "index.html")
    return resp_ok("Stock Simulator API running. Visit /api/prices", {"routes": ["/api/prices", "/api/portfolio"]})

@app.route("/static/<path:filename>", methods=["GET"])
def static_files(filename):
    file_path = STATIC_DIR / filename
    if file_path.exists():
        return send_from_directory(str(STATIC_DIR), filename)
    return resp_err("Not found", 404)

# -----------------------
# API endpoints (improved)
# -----------------------
@app.route("/api/prices", methods=["GET"])
def api_prices():
    try:
        stocks = market.list_prices()
        return resp_ok("prices returned", {"date": str(market.date), "prices": stocks})
    except Exception as e:
        logger.exception("Failed to list prices")
        return resp_err(f"Failed to list prices: {e}", 500)

@app.route("/api/next", methods=["POST"])
def api_next():
    j, err = read_json_request(require_json=False)
    if err:
        return err
    days = j.get("days", request.args.get("days", 1))
    try:
        days = int(days)
    except Exception:
        return resp_err("days must be an integer", 400)
    if days < 1:
        return resp_err("days must be >= 1", 400)
    if days > 3650:
        return resp_err("days too large (max 3650)", 400)
    try:
        market.simulate_days(days)
        logger.info(f"SIMULATE days={days} new_date={market.date}")
        return resp_ok(f"Advanced {days} day(s)", {"date": str(market.date)})
    except Exception as e:
        logger.exception("Simulation failed")
        return resp_err(f"Simulation failed: {e}", 500)

@app.route("/api/addstock", methods=["POST"])
def api_addstock():
    j, err = read_json_request(require_json=True)
    if err:
        return err
    symbol = (j.get("symbol") or "").strip().upper()
    if not symbol:
        return resp_err("symbol is required", 400)
    if symbol in market.stocks:
        return resp_err("stock already exists", 400)
    try:
        price = float(j.get("price"))
    except Exception:
        return resp_err("price must be a number", 400)
    try:
        mu = float(j.get("mu", 0.0005))
        sigma = float(j.get("sigma", 0.02))
    except Exception:
        return resp_err("mu and sigma must be numbers", 400)
    try:
        stock = Stock(symbol, price, mu, sigma)
        market.add_stock(stock)
        logger.info(f"ADDSTOCK {symbol} price={price} mu={mu} sigma={sigma}")
        return resp_ok("stock added", {"symbol": symbol, "price": price, "mu": mu, "sigma": sigma}, 201)
    except Exception as e:
        logger.exception("Failed to add stock")
        return resp_err(f"Failed to add stock: {e}", 500)

@app.route("/api/buy", methods=["POST"])
def api_buy():
    j, err = read_json_request(require_json=True)
    if err:
        return err
    symbol = (j.get("symbol") or "").upper()
    qty = j.get("qty")
    try:
        qty = int(qty)
    except Exception:
        return resp_err("qty must be an integer", 400)
    if qty <= 0:
        return resp_err("qty must be > 0", 400)
    if symbol not in market.stocks:
        return resp_err("unknown symbol", 400)
    portfolio = Portfolio.load()
    price = market.stocks[symbol].price
    try:
        portfolio.buy(symbol, price, qty, market.date)
        logger.info(f"BUY {symbol} qty={qty} price={price:.2f} cash_after={portfolio.cash:.2f}")
        return resp_ok("bought", {"symbol": symbol, "qty": qty, "price": price, "cash": portfolio.cash, "net_worth": portfolio.net_worth(market)})
    except Exception as e:
        logger.exception("Buy failed")
        return resp_err(str(e), 400)

@app.route("/api/sell", methods=["POST"])
def api_sell():
    j, err = read_json_request(require_json=True)
    if err:
        return err
    symbol = (j.get("symbol") or "").upper()
    qty = j.get("qty")
    try:
        qty = int(qty)
    except Exception:
        return resp_err("qty must be an integer", 400)
    if qty <= 0:
        return resp_err("qty must be > 0", 400)
    if symbol not in market.stocks:
        return resp_err("unknown symbol", 400)
    portfolio = Portfolio.load()
    price = market.stocks[symbol].price
    try:
        portfolio.sell(symbol, price, qty, market.date)
        logger.info(f"SELL {symbol} qty={qty} price={price:.2f} cash_after={portfolio.cash:.2f}")
        return resp_ok("sold", {"symbol": symbol, "qty": qty, "price": price, "cash": portfolio.cash, "net_worth": portfolio.net_worth(market)})
    except Exception as e:
        logger.exception("Sell failed")
        return resp_err(str(e), 400)

@app.route("/api/portfolio", methods=["GET"])
def api_portfolio():
    """
    Robust portfolio endpoint:
    - Accepts Portfolio.load() returning either object-with-attributes or plain dict.
    - Normalizes holdings into a list of {symbol, qty, price, value}.
    - Attempts to call portfolio.net_worth(market) if available; otherwise approximates.
    """
    try:
        portfolio = Portfolio.load()

        # Normalize cash and holdings map whether portfolio is dict or object
        if isinstance(portfolio, dict):
            cash = portfolio.get("cash", 0.0)
            holdings_map = portfolio.get("holdings", {}) or {}
        else:
            cash = getattr(portfolio, "cash", 0.0)
            holdings_map = getattr(portfolio, "holdings", {}) or {}

        holdings = []
        for sym, qty in holdings_map.items():
            try:
                qty_num = int(qty)
            except Exception:
                # skip invalid entries
                continue
            stock = market.stocks.get(sym)
            price = stock.price if stock is not None else None
            value = (price * qty_num) if (price is not None) else None
            holdings.append({"symbol": sym, "qty": qty_num, "price": price, "value": value})

        # Compute net_worth: prefer portfolio.net_worth(market) when available
        net_worth = None
        if isinstance(portfolio, dict):
            net_worth = portfolio.get("net_worth")
        else:
            try:
                net_worth = portfolio.net_worth(market)
            except Exception:
                net_worth = None

        # If still None, approximate: cash + sum(price * qty)
        if net_worth is None:
            approx = float(cash or 0.0)
            for h in holdings:
                if h["value"] is not None:
                    approx += float(h["value"])
            net_worth = approx

        return resp_ok("portfolio", {"cash": cash, "net_worth": net_worth, "holdings": holdings})
    except Exception as e:
        logger.exception("Failed to load portfolio")
        return resp_err(f"Failed to load portfolio: {e}", 500)

@app.route("/api/history", methods=["GET"])
def api_history():
    """
    Robust history endpoint:
    - Accepts Portfolio.load() returning either object-with-attributes or plain dict.
    - Returns trades as a list under {"trades": [...]}
    """
    try:
        portfolio = Portfolio.load()
        if isinstance(portfolio, dict):
            trades = portfolio.get("trade_history") or portfolio.get("trades") or []
        else:
            trades = getattr(portfolio, "trade_history", None) or getattr(portfolio, "trades", []) or []
        if trades is None:
            trades = []
        return resp_ok("history", {"trades": trades})
    except Exception as e:
        logger.exception("Failed to load history")
        return resp_err(f"Failed to load history: {e}", 500)

@app.route("/api/price_history/<string:symbol>", methods=["GET"])
def api_price_history(symbol):
    symbol = symbol.upper()
    if symbol not in market.stocks:
        return resp_err("unknown symbol", 404)
    stock = market.stocks[symbol]
    history = [{"date": str(d), "price": float(p)} for d, p in stock.history]
    return resp_ok("price history", {"symbol": symbol, "history": history})

# -----------------------
# Reset endpoint (dev only)
# -----------------------
@app.route("/api/reset", methods=["POST"])
def api_reset():
    try:
        ensure_data_dir()
        backup_name = None
        if PORTFOLIO_FILE.exists():
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = DATA_DIR / f"portfolio_backup_{ts}.json"
            shutil.copy2(PORTFOLIO_FILE, backup_name)
        default_port = Portfolio()
        default_port.save()
        global market
        market = make_default_market()
        logger.info(f"RESET performed; backup={backup_name}")
        return resp_ok("reset complete", {"backup": str(backup_name) if backup_name else None})
    except Exception as e:
        logger.exception("Reset failed")
        return resp_err(f"Reset failed: {e}", 500)

# -----------------------
# Generic error handlers
# -----------------------
@app.errorhandler(404)
def handle_404(e):
    return resp_err("Not found", 404)

@app.errorhandler(500)
def handle_500(e):
    return resp_err("Server error", 500)

# -----------------------
# Run server
# -----------------------
if __name__ == "__main__":
    print("Starting improved API server on http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=True)
