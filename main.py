import json
import websocket
from typing import Dict, List
import ssl
import threading
import time
from datetime import datetime
from pprint import pprint
import os
from collections import deque
import threading

from pybit.unified_trading import HTTP

from triangle_no_pandas import BybitTradingPairList, BybitTriangleCalculation
from test_triple_socket import SymbolWebSocket, MultiSocketClient

if __name__ == "__main__":

    """get all posssible pairs from Bybit
        form all possible triangles
        filter unique pairs from triangles for analisys"""

    scanner = BybitTradingPairList(api_key='qwert', api_secret='1234', testnet=False)
    triangles = scanner.find_triangular_pairs()
    # pairs = scanner.get_tickers() # all pairs from bybit for debug only
    unique_triangle_pairs = scanner.filter_unique_triangles(triangles)
    with open('unique_triangle_pairs.json', 'w') as f:
        json.dump(unique_triangle_pairs, f)

    # print(len(pairs))
    # print(pairs)
    print(f'find_triangular_pairs: {len(triangles)}')
    print(triangles)
    print(f'number of unique pairs {len(unique_triangle_pairs)}')
    print(unique_triangle_pairs)

    """ form orderbooks for unique triangle pairs
    claculate profit for each unique triangle pair with filter to avoid spillage (need to create)
    timestamp for each unique triangle pair with profit
    save to file
    """

    websocket.enableTrace(False)

    # WebSocket parameters
    SLEEP_TIME = 1  # seconds between orderbook updates
    TRADING_AMOUNT_USDT = 10


    trading_pairs = unique_triangle_pairs
    client = MultiSocketClient(
        symbols=trading_pairs,
        default_amount=TRADING_AMOUNT_USDT
    )
    triangle_monitor = BybitTriangleCalculation(trade_amount=TRADING_AMOUNT_USDT)

    try:
        client.start()
        print("Starting WebSocket connections...")
        print(f"Monitoring liquidity for {len(trading_pairs)} pairs...")
        print(f"Liquidity check amount: ${TRADING_AMOUNT_USDT:,} USDT equivalent for each pair")
        print(f"Update interval: {SLEEP_TIME} seconds")

        while True:
            client.print_orderbooks()
            orderbooks = {'timestamp': datetime.now().isoformat(), 'orderbooks': client.get_orderbooks()
            }
            with open('orderbooks.json', 'w') as f:
                json.dump(orderbooks, f, indent=2)

            time.sleep(SLEEP_TIME)  # Use the defined sleep parameter
            print("\033[2J\033[H")  # Clear screen

    except KeyboardInterrupt:
        print("\nShutting down...")
        client.stop()
