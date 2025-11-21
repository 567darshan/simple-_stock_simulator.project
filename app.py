"""
Unified API server for the stock simulator.
- Uses port 5001 by default
- CORS enabled
- JSON shape matches frontend expectations:
  - success: { message, ...data_fields }
  - error:   { error, ...optional_fields }

This file is identical to your uploaded app.py except:
- Replaced the broken /buy handler with a safe, canonical /api/buy handler
  that loads the portfolio, validates input, persists state, and returns
  the full JSON the frontend expects (trades, prices, portfolio_summary).
- Updated /api/sell to persist the portfolio and return the same canonical
  fields for parity.
- Kept all other code and routes unchanged.
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pathlib import Path
from services.prices import make_default_market, Stock
from trading import Portfolio
import datetime
import shutil
import logging
from logging.handlers import RotatingFileHandler

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"

app = Flask(__name__, static_folder=str(STATIC_DIR))
CORS(app)

# -----------------------
# Logging setup
# -----------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "server.log"

logger = logging.getLogger("stock_app")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    filename=str(LOG_FILE),
    maxBytes=3_000_000,
    backupCount=3
)
formatter = logging.Formatter("%(asctime)s  %(levelname)s  %(message)s")
handler.setFormatter(formatter)

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
# Global market instance
# -----------------------
# Move market here so helpers that reference `market` are safe at runtime.
market = make_default_market()


# -----------------------
# Helper functions
# -----------------------
def resp_ok(message="ok", data=None, status=200):
    """
    Success response:

    {
      "success": true,
      "message": "text",
      ...data fields merged here...
    }
    """
    payload = {"success": True, "message": message}
    if isinstance(data, dict):
        payload.update(data)
    return jsonify(payload), status


def resp_err(message="error", status=400, data=None):
    """
    Error response:

    {
      "success": false,
      "error": "message",
      ...optional extra fields...
    }
    """
    payload = {"success": False, "error": message}
    if isinstance(data, dict):
        payload.update(data)
    return jsonify(payload), status


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


def _prices_dict():
    """Return simple { symbol: price } mapping from market.stocks."""
    try:
        return {sym: float(stock.price) for sym, stock in getattr(market, "stocks", {}).items()}
    except Exception:
        return {}


def _portfolio_summary_dict(portfolio):
    """
    Build a JSON-serializable portfolio summary dict:
    { cash, net_worth, holdings: [ {symbol, qty, price, value}, ... ] }
    """
    cash = getattr(portfolio, "cash", 0.0)
    # build holdings list similar to api_portfolio
    holdings_map = getattr(portfolio, "holdings", {}) or {}
    holdings = []
    for sym, qty in holdings_map.items():
        try:
            qty_num = int(qty)
        except Exception:
            continue
        stock = getattr(market, "stocks", {}).get(sym.upper())
        price = float(stock.price) if stock is not None else None
        value = (price * qty_num) if (price is not None) else None
        holdings.append({"symbol": sym, "qty": qty_num, "price": price, "value": value})

    try:
        net_worth = portfolio.net_worth(market)
    except Exception:
        # fallback: approximate from cash + holdings with known prices
        approx = float(cash or 0.0)
        for h in holdings:
            if h["value"] is not None:
                approx += float(h["value"])
        net_worth = approx

    return {"cash": cash, "net_worth": net_worth, "holdings": holdings}


# -----------------------
# Serve frontend
# -----------------------
@app.route("/", methods=["GET"])
def root():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return send_from_directory(str(STATIC_DIR), "index.html")
    return resp_ok(
        "Stock Simulator API running. Visit /api/prices",
        {"routes": ["/api/prices", "/api/portfolio"]}
    )


@app.route("/static/<path:filename>", methods=["GET"])
def static_files(filename):
    file_path = STATIC_DIR / filename
    if file_path.exists():
        return send_from_directory(str(STATIC_DIR), filename)
    return resp_err("Not found", 404)


# -----------------------
# API endpoints
# -----------------------
@app.route("/api/prices", methods=["GET"])
def api_prices():
    try:
        stocks = market.list_prices()
        return resp_ok(
            "prices returned",
            {"date": str(market.date), "prices": stocks}
        )
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
        return resp_ok(
            f"Advanced {days} day(s)",
            {"date": str(market.date)}
        )
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
        return resp_ok(
            "stock added",
            {"symbol": symbol, "price": price, "mu": mu, "sigma": sigma},
            201,
        )
    except Exception as e:
        logger.exception("Failed to add stock")
        return resp_err(f"Failed to add stock: {e}", 500)


# -----------------------
# Replaced broken /buy with canonical /api/buy
# -----------------------
@app.route("/api/buy", methods=["POST"])
def api_buy():
    """
    Expects JSON: { "symbol": "ABC", "qty": 1 }
    Returns canonical JSON: success,message,symbol,qty,price,cash,net_worth,trades,prices,portfolio_summary
    """
    j, err = read_json_request(require_json=True)
    if err:
        return err

    symbol = (j.get("symbol") or "").strip().upper()
    qty = j.get("qty", None)

    if not symbol:
        return resp_err("symbol is required", 400)

    try:
        qty = int(float(qty))  # accept numeric-ish values but convert to int
    except Exception:
        return resp_err("qty must be an integer", 400)
    if qty <= 0:
        return resp_err("qty must be > 0", 400)

    if symbol not in market.stocks:
        return resp_err("unknown symbol", 400)

    try:
        # Load portfolio (Portfolio.load handles default case)
        portfolio = Portfolio.load()

        # Use current market price as executed price
        price = float(market.stocks[symbol].price)

        # portfolio.buy mutates and saves internally; it raises on failure.
        portfolio.buy(symbol, price, qty, market.date)

        # After calling buy(), the portfolio is persisted by trading.Portfolio.save()
        # Prepare canonical response
        trades = getattr(portfolio, "trade_history", []) or []
        prices = _prices_dict()
        portfolio_summary = _portfolio_summary_dict(portfolio)

        response = {
            "symbol": symbol,
            "qty": qty,
            "price": price,
            "cash": getattr(portfolio, "cash", None),
            "net_worth": portfolio_summary.get("net_worth"),
            "trades": trades,
            "prices": prices,
            "portfolio_summary": portfolio_summary,
        }
        return resp_ok("bought", response, 200)

    except Exception as e:
        logger.exception("Buy failed")
        # return JSON-safe error payload
        return resp_err(f"Buy failed: {e}", 500, {"trades": [], "prices": {}})


# -----------------------
# Update /api/sell to persist and return canonical fields
# -----------------------
@app.route("/api/sell", methods=["POST"])
def api_sell():
    """
    Expects JSON: { "symbol": "ABC", "qty": 1 }
    Returns canonical JSON similar to /api/buy.
    """
    j, err = read_json_request(require_json=True)
    if err:
        return err

    symbol = (j.get("symbol") or "").strip().upper()
    qty = j.get("qty", None)

    if not symbol:
        return resp_err("symbol is required", 400)

    try:
        qty = int(float(qty))
    except Exception:
        return resp_err("qty must be an integer", 400)
    if qty <= 0:
        return resp_err("qty must be > 0", 400)

    if symbol not in market.stocks:
        return resp_err("unknown symbol", 400)

    try:
        portfolio = Portfolio.load()
        price = float(market.stocks[symbol].price)

        # portfolio.sell mutates + saves internally; will raise on insufficient shares
        portfolio.sell(symbol, price, qty, market.date)

        trades = getattr(portfolio, "trade_history", []) or []
        prices = _prices_dict()
        portfolio_summary = _portfolio_summary_dict(portfolio)

        response = {
            "symbol": symbol,
            "qty": qty,
            "price": price,
            "cash": getattr(portfolio, "cash", None),
            "net_worth": portfolio_summary.get("net_worth"),
            "trades": trades,
            "prices": prices,
            "portfolio_summary": portfolio_summary,
        }
        return resp_ok("sold", response, 200)

    except Exception as e:
        logger.exception("Sell failed")
        return resp_err(f"Sell failed: {e}", 400, {"trades": [], "prices": {}})


@app.route("/api/portfolio", methods=["GET"])
def api_portfolio():
    """
    - Works whether Portfolio.load() returns a dict or an object.
    - Returns: { message, cash, net_worth, holdings: [...] }
    """
    try:
        portfolio = Portfolio.load()

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
                continue

            stock = market.stocks.get(sym)
            price = stock.price if stock is not None else None
            value = (price * qty_num) if (price is not None) else None

            holdings.append(
                {"symbol": sym, "qty": qty_num, "price": price, "value": value}
            )

        net_worth = None
        if isinstance(portfolio, dict):
            net_worth = portfolio.get("net_worth")
        else:
            try:
                net_worth = portfolio.net_worth(market)
            except Exception:
                net_worth = None

        if net_worth is None:
            approx = float(cash or 0.0)
            for h in holdings:
                if h["value"] is not None:
                    approx += float(h["value"])
            net_worth = approx

        return resp_ok(
            "portfolio",
            {"cash": cash, "net_worth": net_worth, "holdings": holdings},
        )
    except Exception as e:
        logger.exception("Failed to load portfolio")
        return resp_err(f"Failed to load portfolio: {e}", 500)


@app.route("/api/history", methods=["GET"])
def api_history():
    """
    Returns: { message, trades: [...] }
    """
    try:
        portfolio = Portfolio.load()
        if isinstance(portfolio, dict):
            trades = portfolio.get("trade_history") or portfolio.get("trades") or []
        else:
            trades = (
                getattr(portfolio, "trade_history", None)
                or getattr(portfolio, "trades", [])
                or []
            )
        if trades is None:
            trades = []

        return resp_ok("history", {"trades": trades})
    except Exception as e:
        logger.exception("Failed to load history")
        return resp_err(f"Failed to load history: {e}", 500)


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """
    Returns summary statistics based on trade_history:
      - total_buys
      - total_sells
      - net_invested
      - total_profit (vs starting cash 10,000)
      - num_trades
    Matches frontend loadStats() expectations.
    """
    try:
        portfolio = Portfolio.load()
        trades = getattr(portfolio, "trade_history", []) or []

        total_buys = 0.0
        total_sells = 0.0

        for t in trades:
            try:
                t_type = str(t.get("type", "")).upper()
                qty = int(t.get("qty", 0))
                price = float(t.get("price", 0.0))
            except Exception:
                continue

            if qty <= 0 or price < 0:
                continue

            amount = price * qty
            if t_type == "BUY":
                total_buys += amount
            elif t_type == "SELL":
                total_sells += amount

        net_invested = total_buys - total_sells
        total_profit = portfolio.net_worth(market) - 10000.0
        num_trades = len(trades)

        return resp_ok(
            "stats",
            {
                "total_buys": total_buys,
                "total_sells": total_sells,
                "net_invested": net_invested,
                "total_profit": total_profit,
                "num_trades": num_trades,
            },
        )
    except Exception as e:
        logger.exception("Failed to compute stats")
        return resp_err(f"Failed to compute stats: {e}", 500)


@app.route("/api/price_history/<string:symbol>", methods=["GET"])
def api_price_history(symbol):
    """
    Returns: { message, symbol, dates: [...], prices: [...] }
    Which matches JS: data.dates, data.prices
    """
    symbol = symbol.upper()
    if symbol not in market.stocks:
        return resp_err("unknown symbol", 404)

    stock = market.stocks[symbol]
    history_list = list(stock.history)

    dates = [str(d) for d, _ in history_list]
    prices = [float(p) for _, p in history_list]

    return resp_ok(
        "price history",
        {"symbol": symbol, "dates": dates, "prices": prices},
    )


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
        return resp_ok(
            "reset complete",
            {"backup": str(backup_name) if backup_name else None},
        )
    except Exception as e:
        logger.exception("Reset failed")
        return resp_err(f"Reset failed: {e}", 500)


@app.route("/api/login", methods=["POST"])
def api_login():
    """
    Lightweight login endpoint.
    Accepts JSON or form: { "user": "<username>" }
    Returns: { success: true, message: "...", user: "..." }
    NOTE: this is intentionally stateless (no sessions). Frontend should
    include ?user=<name> on API calls or set header as needed.
    """
    try:
        j, err = read_json_request(require_json=False)
        if err:
            return err
        # accept from JSON, form data, or query param
        user = (j.get("user") if isinstance(j, dict) else None) \
               or request.form.get("user") \
               or request.args.get("user") \
               or "guest"
        user = str(user).strip()
        if not user:
            return resp_err("user is required", 400)

        # respond with a canonical success payload frontend expects
        return resp_ok("login successful", {"user": user})
    except Exception as e:
        logger.exception("Login failed")
        return resp_err(f"Login failed: {e}", 500)

@app.route("/api/prices_live", methods=["GET"])
def api_prices_live():
    """
    Live prices endpoint - simplified safe mode.
    Always return simulated prices and a flag 'live_enabled': False so the frontend
    can continue rendering the ticker without error and knows live mode is disabled.
    """
    try:
        simulated_prices = market.list_prices()
        data = {
            "live_enabled": False,              # explicitly tell the UI live mode is disabled
            "message": "Live data disabled; running in simulation mode.",
            "date": str(market.date),
            "prices": simulated_prices
        }
        # Return HTTP 200 so the frontend does not treat this as a service failure.
        return resp_ok("live disabled", data, 200)
    except Exception as e:
        logger.exception("prices_live failed")
        return resp_err(f"prices_live failed: {e}", 500)


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
    print("Starting app on http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=True)
