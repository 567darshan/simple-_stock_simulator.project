# trading.py
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict

DATA_PATH = Path('data')
PORTFOLIO_FILE = DATA_PATH / 'portfolio.json'

class Portfolio:
    def __init__(self, cash=10000.0):
        self.cash = float(cash)
        self.holdings: Dict[str, int] = defaultdict(int)
        self.trade_history = []

    @classmethod
    def load(cls):
        DATA_PATH.mkdir(exist_ok=True)
        if not PORTFOLIO_FILE.exists():
            p = cls()
            p.save()
            return p
        with PORTFOLIO_FILE.open('r') as f:
            data = json.load(f)
        p = cls(cash=data.get('cash', 10000.0))
        holdings = data.get('holdings', {})
        for sym, qty in holdings.items():
            p.holdings[sym.upper()] = int(qty)
        p.trade_history = data.get('trade_history', [])
        return p

    def save(self):
        DATA_PATH.mkdir(exist_ok=True)
        data = {
            'cash': self.cash,
            'holdings': dict(self.holdings),
            'trade_history': self.trade_history,
        }
        with PORTFOLIO_FILE.open('w') as f:
            json.dump(data, f, indent=2)

    def buy(self, symbol, price, qty, date):
        qty = int(qty)
        cost = price * qty
        if cost > self.cash + 1e-9:
            raise ValueError('Not enough cash')
        self.cash -= cost
        self.holdings[symbol] += qty
        self.trade_history.append({
            'date': str(date), 'type': 'BUY', 'symbol': symbol, 'qty': qty, 'price': price
        })
        self.save()

    def sell(self, symbol, price, qty, date):
        qty = int(qty)
        if self.holdings.get(symbol, 0) < qty:
            raise ValueError('Not enough shares to sell')
        revenue = price * qty
        self.cash += revenue
        self.holdings[symbol] -= qty
        self.trade_history.append({
            'date': str(date), 'type': 'SELL', 'symbol': symbol, 'qty': qty, 'price': price
        })
        self.save()

    def net_worth(self, market):
        value = self.cash
        for sym, qty in self.holdings.items():
            if qty <= 0:
                continue
            value += market.stocks[sym].price * qty
        return value

    def summary(self, market):
        lines = []
        lines.append(f"Cash: {self.cash:.2f}")
        lines.append(f"Net worth: {self.net_worth(market):.2f}")
        lines.append('Holdings:')
        for sym, qty in self.holdings.items():
            if qty <= 0:
                continue
            price = market.stocks[sym].price
            lines.append(f"  {sym}: {qty} shares @ {price:.2f} -> {qty*price:.2f}")
        return "\n".join(lines)

