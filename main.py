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
from walllet_connect import WalletManager, TriangleWalletExecutor

def calculate_profit_percentage(entry_price: float, current_price: float) -> float:
    """
    Calculate profit percentage based on entry and current price
    """
    return ((current_price - entry_price) / entry_price) * 100

class ProfitManager:
    def __init__(self):
        # More realistic profit targets
        self.take_profit_percent = 0.5  # 0.5% profit target
        self.stop_loss_percent = -0.3   # 0.3% loss limit
        self.trailing_stop_percent = 0.2 # 0.2% trailing stop
        
        self.entry_price = None
        self.highest_price = None
        self.trailing_stop_price = None

    def set_entry(self, price: float):
        self.entry_price = price
        self.highest_price = price
        self.trailing_stop_price = price * (1 - self.trailing_stop_percent/100)

    def should_take_profit(self, current_price: float) -> bool:
        if not self.entry_price:
            return False
            
        profit_percent = calculate_profit_percentage(self.entry_price, current_price)
        return profit_percent >= self.take_profit_percent

    def should_stop_loss(self, current_price: float) -> bool:
        if not self.entry_price:
            return False
            
        profit_percent = calculate_profit_percentage(self.entry_price, current_price)
        return profit_percent <= self.stop_loss_percent

    def update_trailing_stop(self, current_price: float):
        if current_price > self.highest_price:
            self.highest_price = current_price
            self.trailing_stop_price = current_price * (1 - self.trailing_stop_percent/100)

    def hit_trailing_stop(self, current_price: float) -> bool:
        return current_price <= self.trailing_stop_price

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    # Load environment variables from .env file
    load_dotenv()

    # Get configuration from environment variables with type conversion and defaults
    SLEEP_TIME = float(os.getenv('SLEEP_TIME', 1))  # seconds between orderbook updates
    TRADING_AMOUNT_USDT = float(os.getenv('TRADING_AMOUNT_USDT', 1000))
    MIN_PROFIT = float(os.getenv('MIN_PROFIT', 0.5))  # in percents
    MAX_PROFIT = float(os.getenv('MAX_PROFIT', 1000))  # in percents

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