from pybit.unified_trading import HTTP
from pprint import pprint  # for better formatted output
import json

session = HTTP(testnet=False)
orderbook = session.get_orderbook(
    category="spot",
    symbol="WEMIXUSDT",
    limit=100
)
trade_amount = 100 #USDT

with open('test_ticker_info.json', 'w') as f:
    json.dump(orderbook, f)


def calculate_crypto_amount(orderbook, trade_amount):
    asks = orderbook['result']['a']
    sum_amount = 0
    crypto_count = 0

    # Pre-convert strings to floats to avoid repeated conversions
    asks_float = [(float(price), float(amount)) for price, amount in asks]

    for price, amount in asks_float:
        position_total = price * amount
        if sum_amount + position_total <= trade_amount:
            sum_amount += position_total
            crypto_count += amount
        else:
            # Calculate remaining amount needed
            remaining = trade_amount - sum_amount
            partial_amount = remaining / price
            crypto_count += partial_amount
            break

    return crypto_count


print("\nFirst few bids:")
print("=" * 50)
pprint(orderbook['result']['a'][:10])
# calculating amount of crypto to buy for USDT
# sum = 0
# crypto_count = 0
# for pos in orderbook['result']['a']:
#     if sum < trade_amount:
#         sum += float(pos[0])*float(pos[1])
#         crypto_count += float(pos[1])
#     if sum == trade_amount:
#         break
#     if sum > trade_amount:
#         delta_crypto = (sum - trade_amount)/float(pos[0])
#         crypto_count -= delta_crypto
#         break


print("\nTotal number of asks:")
print(len(orderbook['result']['a']))
print("\nTotal number of coins:","%.4f" % calculate_crypto_amount(orderbook, trade_amount))

