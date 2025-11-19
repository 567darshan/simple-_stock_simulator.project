# services/prices.py
import math
import random
import datetime
from collections import deque

class Stock:
    def __init__(self, symbol, price, mu=0.0005, sigma=0.02):
        self.symbol = symbol.upper()
        self.price = float(price)
        self.mu = float(mu)
        self.sigma = float(sigma)
        self.history = deque(maxlen=10000)  # (date, price)

    def record(self, date):
        self.history.append((date, self.price))

    def simulate_day(self):
        dt = 1.0
        eps = random.gauss(0, 1)
        drift = (self.mu - 0.5 * self.sigma * self.sigma) * dt
        diffusion = self.sigma * math.sqrt(dt) * eps
        self.price *= math.exp(drift + diffusion)
        return self.price

class Market:
    def __init__(self, start_date=None):
        self.stocks = {}
        self.date = start_date or datetime.date.today()

    def add_stock(self, stock: Stock):
        self.stocks[stock.symbol] = stock
        stock.record(self.date)

    def list_prices(self):
        return {s: self.stocks[s].price for s in sorted(self.stocks)}

    def simulate_days(self, days=1):
        days = int(days)
        for _ in range(days):
            self.date += datetime.timedelta(days=1)
            for stock in self.stocks.values():
                stock.simulate_day()
                stock.record(self.date)

def make_default_market(start_date=None):
    market = Market(start_date=start_date)
    default_stocks = [
        ("ABC", 100.0, 0.0006, 0.02),
        ("XYZ", 50.0, 0.0003, 0.03),
        ("FOO", 200.0, 0.0008, 0.015),
        ("BAR", 10.0, 0.0001, 0.05),
    ]
    for sym, price, mu, sigma in default_stocks:
        market.add_stock(Stock(sym, price, mu, sigma))
    return market
