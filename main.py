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
                    # defensive: history may be empty in rare cases
                    try:
                        first_price = st.history[0][1] if len(st.history) > 0 else st.price
                        print(f"  {sym} start price ~ {first_price:.2f} current {st.price:.2f} mu={st.mu} sigma={st.sigma}")
                    except Exception:
                        print(f"  {sym} current {st.price:.2f} mu={st.mu} sigma={st.sigma}")

            elif action == 'addstock':
                # Usage: addstock SYMBOL PRICE [mu] [sigma]
                if len(parts) < 3:
                    print('Usage: addstock SYMBOL PRICE [mu] [sigma]')
                    continue
                sym = parts[1].upper()
                try:
                    price = float(parts[2])
                except ValueError:
                    print('PRICE must be a number, e.g. 12.5')
                    continue
                mu = float(parts[3]) if len(parts) > 3 else 0.0005
                sigma = float(parts[4]) if len(parts) > 4 else 0.02
                # create and add the stock to the market
                from services.prices import Stock
                stock = Stock(sym, price, mu, sigma)
                market.add_stock(stock)
                print(f'Added stock {sym} @ {price:.2f} mu={mu} sigma={sigma}')

            elif action == 'next':
                # safer parsing
                try:
                    n = int(parts[1]) if len(parts) > 1 else 1
                    if n < 1:
                        print('Number of days must be >= 1')
                        continue
                except Exception:
                    print("Usage: next N  (N must be a positive integer)")
                    continue
                market.simulate_days(n)
                print(f"Advanced {n} day(s). New date: {market.date}")

            elif action == 'buy':
                if len(parts) < 3:
                    print('Usage: buy SYMBOL QTY')
                    continue
                sym = parts[1].upper()
                try:
                    qty = int(parts[2])
                    if qty <= 0:
                        print('Quantity must be a positive integer')
                        continue
                except ValueError:
                    print('Usage: buy SYMBOL QTY  (QTY must be an integer)')
                    continue
                if sym not in market.stocks:
                    print('Unknown symbol')
                    continue
                price = market.stocks[sym].price
                try:
                    portfolio.buy(sym, price, qty, market.date)
                    print(f"Bought {qty} of {sym} @ {price:.2f} -> cash {portfolio.cash:.2f}")
                except Exception as e:
                    # show friendly error from Portfolio (e.g. insufficient cash)
                    print(f"Buy failed: {e}")

            elif action == 'sell':
                if len(parts) < 3:
                    print('Usage: sell SYMBOL QTY')
                    continue
                sym = parts[1].upper()
                try:
                    qty = int(parts[2])
                    if qty <= 0:
                        print('Quantity must be a positive integer')
                        continue
                except ValueError:
                    print('Usage: sell SYMBOL QTY  (QTY must be an integer)')
                    continue
                if sym not in market.stocks:
                    print('Unknown symbol')
                    continue
                price = market.stocks[sym].price
                try:
                    portfolio.sell(sym, price, qty, market.date)
                    print(f"Sold {qty} of {sym} @ {price:.2f} -> cash {portfolio.cash:.2f}")
                except Exception as e:
                    print(f"Sell failed: {e}")

            elif action == 'portfolio':
                print(portfolio.summary(market))

            elif action == 'history':
                if not portfolio.trade_history:
                    print('No trades yet.')
                else:
                    for t in portfolio.trade_history:
                        # defensive formatting
                        try:
                            print(f"{t.get('date','')} {t.get('type','')} {t.get('symbol','')} {t.get('qty','')} @ {float(t.get('price',0)):.2f}")
                        except Exception:
                            print(t)

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
                # Convert dates to strings for plotting (safe with matplotlib)
                dates = [str(d) for d, _ in stock.history]
                prices = [p for _, p in stock.history]
                if not dates or not prices:
                    print('No price history available to plot.')
                    continue
                try:
                    plt.figure()
                    plt.plot(dates, prices)
                    plt.title(f"Price history: {sym}")
                    plt.xlabel('Date')
                    plt.ylabel('Price')
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    plt.show()
                except Exception as e:
                    print(f"Plot failed: {e}")

            else:
                print("Unknown command. Type 'help' to see available commands.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    main()
