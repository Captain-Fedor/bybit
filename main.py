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
    with open('triangles.json', 'w') as f:
        json.dump(triangles, f)
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
    TRADING_AMOUNT_USDT = 1000
    MIN_PROFIT = 1 # in precents
    MAX_PROFIT = 50 # in precents


    trading_pairs = unique_triangle_pairs
    client = MultiSocketClient(
        symbols=trading_pairs,
        default_amount=TRADING_AMOUNT_USDT
    )
    triangle_monitor = BybitTriangleCalculation(trade_amount=TRADING_AMOUNT_USDT, min_profit=MIN_PROFIT, max_profit=MAX_PROFIT)

    try:
        client.start()
        print("Starting WebSocket connections...")
        print(f"Monitoring liquidity for {len(trading_pairs)} pairs...")
        print(f"Liquidity check amount: ${TRADING_AMOUNT_USDT:,} USDT equivalent for each pair")
        print(f"Update interval: {SLEEP_TIME} seconds")

        while True:
            # Get current orderbooks
            client.print_orderbooks()
            current_orderbooks = client.get_orderbooks()
            
            # Save complete orderbook data to file
            orderbooks_data = {
                'timestamp': datetime.now().isoformat(), 
                'orderbooks': current_orderbooks
            }
            
            try:
                with open('orderbooks.json', 'w') as f:
                    json.dump(orderbooks_data, f, indent=2)
            except Exception as e:
                print(f"Error saving orderbooks: {e}")
            
            # Run arbitrage calculation with current orderbooks
            print("\nRunning arbitrage calculation...")
            triangle_monitor.calculate_arbitrage(current_orderbooks)
            
            # Clear screen and wait before next update
            time.sleep(SLEEP_TIME)
            print("\033[2J\033[H")  # Clear screen

    except KeyboardInterrupt:
        print("\nShutting down...")
        client.stop()
