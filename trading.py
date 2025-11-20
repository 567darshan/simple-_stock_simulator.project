# trading.py
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, Optional, List
import datetime

DATA_PATH = Path("data")
PORTFOLIO_FILE = DATA_PATH / "portfolio.json"


class Portfolio:
    """
    Simple portfolio class.
    - cash: float
    - holdings: dict symbol -> qty (ints)
    - trade_history: list of trade dicts:
        {
          "date": "YYYY-MM-DD",
          "type": "BUY" | "SELL",
          "symbol": "ABC",
          "qty": int,
          "price": float
        }
    """

    def __init__(self, cash: float = 10000.0):
        self.cash: float = float(cash)
        self.holdings: Dict[str, int] = defaultdict(int)
        self.trade_history: List[Dict[str, Any]] = []

    # --- persistence ---
    @classmethod
    def load(cls) -> "Portfolio":
        """
        Load portfolio from data/portfolio.json.
        If file does not exist, create a default one with 10,000 cash.
        """
        DATA_PATH.mkdir(parents=True, exist_ok=True)

        if not PORTFOLIO_FILE.exists():
            p = cls()
            p.save()
            return p

        with PORTFOLIO_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        p = cls(cash=data.get("cash", 10000.0))

        holdings = data.get("holdings", {}) or {}
        # normalize keys to uppercase and ensure ints
        for sym, qty in holdings.items():
            try:
                p.holdings[sym.upper()] = int(qty)
            except Exception:
                # skip invalid quantities
                continue

        # accept either "trade_history" or "trades" for compatibility
        p.trade_history = data.get("trade_history", []) or data.get("trades", []) or []
        return p

    def save(self) -> None:
        """Persist the portfolio to data/portfolio.json."""
        DATA_PATH.mkdir(parents=True, exist_ok=True)
        data = {
            "cash": self.cash,
            "holdings": dict(self.holdings),
            "trade_history": self.trade_history,
        }
        with PORTFOLIO_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # --- trading ops ---
    def buy(
        self,
        symbol: str,
        price: float,
        qty: int,
        date: Optional[Any] = None,
    ) -> None:
        """
        Buy qty shares of symbol at price.
        Raises ValueError on invalid input or insufficient cash.
        """
        if symbol is None:
            raise ValueError("Symbol required")

        symbol = symbol.upper()

        try:
            qty = int(qty)
        except Exception:
            raise ValueError("Quantity must be an integer")

        if qty <= 0:
            raise ValueError("Quantity must be > 0")

        price = float(price)
        cost = price * qty

        if cost > self.cash + 1e-9:
            raise ValueError("Not enough cash")

        self.cash -= cost
        self.holdings[symbol] = int(self.holdings.get(symbol, 0)) + qty

        self.trade_history.append(
            {
                "date": self._format_date(date),
                "type": "BUY",
                "symbol": symbol,
                "qty": qty,
                "price": price,
            }
        )
        self.save()

    def sell(
        self,
        symbol: str,
        price: float,
        qty: int,
        date: Optional[Any] = None,
    ) -> None:
        """
        Sell qty shares of symbol at price.
        Raises ValueError on invalid input or insufficient shares.
        """
        if symbol is None:
            raise ValueError("Symbol required")

        symbol = symbol.upper()

        try:
            qty = int(qty)
        except Exception:
            raise ValueError("Quantity must be an integer")

        if qty <= 0:
            raise ValueError("Quantity must be > 0")

        owned = int(self.holdings.get(symbol, 0))
        if qty > owned:
            raise ValueError("Not enough shares to sell")

        price = float(price)
        revenue = price * qty
        self.cash += revenue

        new_qty = owned - qty
        if new_qty <= 0:
            # remove symbol entirely if zero or negative
            if symbol in self.holdings:
                del self.holdings[symbol]
        else:
            self.holdings[symbol] = new_qty

        self.trade_history.append(
            {
                "date": self._format_date(date),
                "type": "SELL",
                "symbol": symbol,
                "qty": qty,
                "price": price,
            }
        )
        self.save()

    def _format_date(self, date_val: Optional[Any]) -> str:
        """Return YYYY-MM-DD string for date_val or today's date if None."""
        if date_val is None:
            return datetime.date.today().isoformat()
        if isinstance(date_val, datetime.datetime):
            return date_val.date().isoformat()
        if isinstance(date_val, datetime.date):
            return date_val.isoformat()
        # fallback if some other type is passed
        return str(date_val)

    # --- helpers ---
    def net_worth(self, market) -> float:
        """
        Compute net worth given a market.
        Skip symbols missing from the market instead of raising.
        """
        value = float(self.cash or 0.0)
        for sym, qty in self.holdings.items():
            if qty <= 0:
                continue
            # ensure lookup uses uppercase keys
            stock = getattr(market, "stocks", {}).get(sym.upper())
            if stock is None:
                # skip unknown/removed symbol
                continue
            value += float(stock.price) * int(qty)
        return value

    def summary(self, market) -> str:
        """Return a human-readable summary for CLI usage."""
        lines = []
        lines.append(f"Cash: {self.cash:.2f}")
        lines.append(f"Net worth: {self.net_worth(market):.2f}")
        lines.append("Holdings:")
        for sym, qty in self.holdings.items():
            if qty <= 0:
                continue
            stock = getattr(market, "stocks", {}).get(sym.upper())
            if stock is None:
                lines.append(f"  {sym}: {qty} shares @ UNKNOWN (market missing)")
                continue
            price = float(stock.price)
            lines.append(f"  {sym}: {qty} shares @ {price:.2f} -> {qty * price:.2f}")
        return "\n".join(lines)
