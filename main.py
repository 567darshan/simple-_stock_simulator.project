# main.py
from services.prices import make_default_market
from trading import Portfolio

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

COMMANDS = '''
Available commands:
  prices                 - show current market prices
  list                   - alias for prices
  next N                 - simulate next N days (N defaults to 1)
  buy SYMBOL QTY         - buy QTY shares of SYMBOL at current price
  sell SYMBOL QTY        - sell QTY shares of SYMBOL at current price
  portfolio              - show portfolio summary
  history                - show trade history
  pricehist SYMBOL       - show price history plot for SYMBOL (requires matplotlib)
  config                 - show simulated date and available stocks
  help                   - show this help
  quit / exit            - exit the simulator
'''

def main():
    print('Simple stock market simulator (project layout)')
    market = make_default_market()
    portfolio = Portfolio.load()

    print("Type 'help' to see commands.\n")

    while True:
        try:
            cmd = input(f"[{market.date}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print('\nExiting simulator.')
            break
        if not cmd:
            continue
        parts = cmd.split()
        action = parts[0].lower()

        try:
            if action in ('quit', 'exit'):
                print('Goodbye!')
                break
            elif action in ('help', 'h', '?'):
                print(COMMANDS)
            elif action in ('prices', 'list'):
                prices = market.list_prices()
                for s, p in prices.items():
                    print(f"{s}: {p:.2f}")
            elif action == 'config':
                print(f"Simulated date: {market.date}")
                print('Stocks:')
                for sym, st in market.stocks.items():
                    print(f"  {sym} start price ~ {st.history[0][1]:.2f} current {st.price:.2f} mu={st.mu} sigma={st.sigma}")
            elif action == 'next':
                n = 1
                if len(parts) > 1:
                    n = int(parts[1])
                market.simulate_days(n)
                print(f"Advanced {n} day(s). New date: {market.date}")
            elif action == 'buy':
                if len(parts) < 3:
                    print('Usage: buy SYMBOL QTY')
                    continue
                sym = parts[1].upper()
                qty = int(parts[2])
                if sym not in market.stocks:
                    print('Unknown symbol')
                    continue
                price = market.stocks[sym].price
                portfolio.buy(sym, price, qty, market.date)
                print(f"Bought {qty} of {sym} @ {price:.2f} -> cash {portfolio.cash:.2f}")
            elif action == 'sell':
                if len(parts) < 3:
                    print('Usage: sell SYMBOL QTY')
                    continue
                sym = parts[1].upper()
                qty = int(parts[2])
                if sym not in market.stocks:
                    print('Unknown symbol')
                    continue
                price = market.stocks[sym].price
                portfolio.sell(sym, price, qty, market.date)
                print(f"Sold {qty} of {sym} @ {price:.2f} -> cash {portfolio.cash:.2f}")
            elif action == 'portfolio':
                print(portfolio.summary(market))
            elif action == 'history':
                if not portfolio.trade_history:
                    print('No trades yet.')
                else:
                    for t in portfolio.trade_history:
                        print(f"{t['date']} {t['type']} {t['symbol']} {t['qty']} @ {t['price']:.2f}")
            elif action == 'pricehist':
                if len(parts) < 2:
                    print('Usage: pricehist SYMBOL')
                    continue
                sym = parts[1].upper()
                if sym not in market.stocks:
                    print('Unknown symbol')
                    continue
                if plt is None:
                    print('matplotlib not available. Install matplotlib to use plotting: pip install matplotlib')
                    continue
                stock = market.stocks[sym]
                dates = [d for d, p in stock.history]
                prices = [p for d, p in stock.history]
                plt.figure()
                plt.plot(dates, prices)
                plt.title(f"Price history: {sym}")
                plt.xlabel('Date')
                plt.ylabel('Price')
                plt.tight_layout()
                plt.show()
            else:
                print("Unknown command. Type 'help' to see available commands.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    main()
