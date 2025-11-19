# app.py
from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

from services.prices import make_default_market
from trading import Portfolio

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent

# Single global market instance
market = make_default_market()


def get_portfolio():
    return Portfolio.load()


# ---------- FRONTEND ----------

@app.get("/")
def index():
    return send_from_directory(BASE_DIR / "static", "index.html")


# ---------- API ROUTES ----------

@app.get("/api/prices")
def api_prices():
    prices = market.list_prices()
    return jsonify({
        "date": str(market.date),
        "prices": prices,
    })


@app.post("/api/next")
def api_next():
    data = request.get_json(silent=True) or {}
    days = int(data.get("days", 1))
    market.simulate_days(days)
    return jsonify({
        "message": f"Advanced {days} day(s).",
        "date": str(market.date),
    })


@app.get("/api/portfolio")
def api_portfolio():
    portfolio = get_portfolio()

    holdings = []
    for sym, qty in portfolio.holdings.items():
        if qty <= 0:
            continue
        price = market.stocks[sym].price
        holdings.append({
            "symbol": sym,
            "qty": qty,
            "price": price,
            "value": qty * price,
        })

    return jsonify({
        "cash": portfolio.cash,
        "net_worth": portfolio.net_worth(market),
        "holdings": holdings,
    })


@app.post("/api/buy")
def api_buy():
    data = request.get_json(force=True)
    symbol = data.get("symbol", "").upper()
    qty = int(data.get("qty", 0))

    if symbol not in market.stocks:
        return jsonify({"error": "Unknown symbol"}), 400
    if qty <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    portfolio = get_portfolio()
    price = market.stocks[symbol].price

    try:
        portfolio.buy(symbol, price, qty, market.date)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": f"Bought {qty} of {symbol} @ {price:.2f}",
        "cash": portfolio.cash,
        "net_worth": portfolio.net_worth(market),
    })


@app.post("/api/sell")
def api_sell():
    data = request.get_json(force=True)
    symbol = data.get("symbol", "").upper()
    qty = int(data.get("qty", 0))

    if symbol not in market.stocks:
        return jsonify({"error": "Unknown symbol"}), 400
    if qty <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    portfolio = get_portfolio()
    price = market.stocks[symbol].price

    try:
        portfolio.sell(symbol, price, qty, market.date)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": f"Sold {qty} of {symbol} @ {price:.2f}",
        "cash": portfolio.cash,
        "net_worth": portfolio.net_worth(market),
    })


@app.get("/api/history")
def api_history():
    portfolio = get_portfolio()
    return jsonify({"trades": portfolio.trade_history})


@app.post("/api/reset")
def api_reset():
    """Reset portfolio to default state (10000 cash, no holdings)."""
    p = Portfolio()
    p.save()
    return jsonify({
        "message": "Portfolio reset to default state.",
        "cash": p.cash,
        "net_worth": p.net_worth(market),
    })


@app.get("/api/price_history/<symbol>")
def api_price_history(symbol):
    """Return date/price arrays for a given stock symbol."""
    sym = symbol.upper()
    if sym not in market.stocks:
        return jsonify({"error": "Unknown symbol"}), 400

    stock = market.stocks[sym]
    dates = [str(d) for d, _ in stock.history]
    prices = [p for _, p in stock.history]

    return jsonify({
        "symbol": sym,
        "dates": dates,
        "prices": prices,
    })


@app.get("/api/stats")
def api_stats():
    """Overall summary stats: invested, profit, trade count."""
    portfolio = get_portfolio()
    trades = portfolio.trade_history

    total_buys = 0.0
    total_sells = 0.0
    num_trades = len(trades)

    for t in trades:
        qty = int(t.get("qty", 0))
        price = float(t.get("price", 0.0))
        amount = qty * price
        if t.get("type") == "BUY":
            total_buys += amount
        elif t.get("type") == "SELL":
            total_sells += amount

    starting_cash = 10000.0
    net_worth = portfolio.net_worth(market)
    total_profit = net_worth - starting_cash

    return jsonify({
        "total_buys": total_buys,
        "total_sells": total_sells,
        "net_invested": total_buys - total_sells,
        "net_worth": net_worth,
        "total_profit": total_profit,
        "num_trades": num_trades,
    })


if __name__ == "__main__":
    app.run(debug=True)
