from pybit.unified_trading import HTTP
from pprint import pprint  # for better formatted output
import json

session = HTTP(testnet=False)
orderbook = session.get_orderbook(
    category="spot",
    symbol="RUNEUSDT",
    limit=10
)
with open('test_ticker_info.json', 'w') as f:
    json.dump(orderbook, f)

print("\nFirst few bids:")
print("=" * 50)
pprint(orderbook['result']['b'][:10])



print("\nTotal number of bids:")
print(len(orderbook['result']['b']))

