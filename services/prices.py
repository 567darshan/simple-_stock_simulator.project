# services/prices.py
import math
import random
import datetime
from collections import deque
from typing import Deque, Dict, Tuple, Optional


class Stock:
    """
    Simple stock model using Geometric Brownian Motion (GBM)
    to simulate daily prices.
    """

    def __init__(self, symbol: str, price: float, mu: float = 0.0005, sigma: float = 0.02):
        self.symbol: str = symbol.upper()
        self.price: float = float(price)
        self.mu: float = float(mu)
        self.sigma: float = float(sigma)
        # Each entry: (date, price)
        self.history: Deque[Tuple[datetime.date, float]] = deque(maxlen=10000)

    def record(self, date: datetime.date) -> None:
        """Record current price with the given date."""
        self.history.append((date, self.price))

    def simulate_day(self) -> float:
        """
        Simulate one trading day of price movement using GBM.
        Returns the new price.
        """
        dt = 1.0  # one day
        eps = random.gauss(0, 1)
        drift = (self.mu - 0.5 * self.sigma * self.sigma) * dt
        diffusion = self.sigma * math.sqrt(dt) * eps
        self.price *= math.exp(drift + diffusion)
        return self.price


class Market:
    """
    Represents a simple market containing multiple stocks.
    """

    def __init__(self, start_date: Optional[datetime.date] = None):
        self.stocks: Dict[str, Stock] = {}
        # Use today's date if none provided
        self.date: datetime.date = start_date or datetime.date.today()

    def add_stock(self, stock: Stock) -> None:
        """Add a stock to the market and record its initial price."""
        key = stock.symbol.upper()
        self.stocks[key] = stock
        stock.record(self.date)

    def list_prices(self) -> Dict[str, float]:
        """Return current prices of all stocks sorted by symbol."""
        return {symbol: self.stocks[symbol].price for symbol in sorted(self.stocks)}

    def simulate_days(self, days: int = 1) -> None:
        """
        Simulate the market forward by the given number of days.
        """
        days = int(days)
        if days <= 0:
            return

        for _ in range(days):
            self.date += datetime.timedelta(days=1)
            for stock in self.stocks.values():
                stock.simulate_day()
                stock.record(self.date)


def make_default_market(start_date: Optional[datetime.date] = None) -> Market:
    """
    Create a Market with a default set of stocks.
    """
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
