from pybit.unified_trading import HTTP
import pandas as pd
import time
import json
import requests
import certifi
from typing import List
from test_triple_socket import SymbolWebSocket, MultiSocketClient


class BybitTradingPairList():
    def __init__(self, api_key, api_secret, testnet=False, trade_amount=1000):
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        self.min_volume = 1  # Minimum 24h volume
        self.min_turnover = 1  # Minimum 24h turnover in USDT
        self.trade_amount = trade_amount
        self.depth = 50

    # def get_tickers(self):
    #     """Get all tickers from Bybit excluding adventure tokens"""
    #     try:
    #         tickers = self.session.get_tickers(category="spot")
    #         # Filter out adventure tokens (symbols starting with 'A')
    #         filtered_tickers = [
    #             ticker for ticker in tickers['result']['list']
    #             if not ticker['symbol'].startswith('A')
    #         ]
    #         _filtered_tickers = [
    #             pair['symbol'] for pair in filtered_tickers
    #         ]
    #         with open('tickers.json', 'w') as f:
    #             # json.dump({'result': {'list': _filtered_tickers}}, f)
    #             json.dump(_filtered_tickers, f)
    #         return _filtered_tickers
    #     except Exception as e:
    #         print(f"Error fetching tickers: {e}")
    #         return None

    def get_tickers(self) -> List[str]:  # from pair_socket_downloadable
        url = "https://api.bybit.com/v5/market/instruments-info"
        params = {"category": "spot"}

        try:
            response = requests.get(url, params=params, verify=certifi.where())
            response.raise_for_status()
            data = response.json()

            if data["retCode"] == 0 and "list" in data["result"]:
                return [item["symbol"] for item in data["result"]["list"]]

        except Exception as e:
            print(f"Error fetching pairs: {e}")

        return []

    def find_triangular_pairs(self, base_currency="USDT"):
        """Find all possible triangular pairs with the given base currency"""
        pair_tickers = self.get_tickers()
        if not pair_tickers:
            return []

        # Create DataFrame of all trading pairs
        triangular_pairs = []
        # Find all possible triangular combinations
        for pair1 in pair_tickers:
            symbol1 = pair1
            if not symbol1.endswith(base_currency):
                continue

            token1 = symbol1.replace(base_currency, '')

            # Find second pair
            for pair2 in pair_tickers:
                if pair2.startswith(token1):
                    token2 = pair2.replace(token1, '')

                    # Find third pair to complete the triangle
                    for pair3 in pair_tickers:
                        if pair3 == f"{token2}{base_currency}":
                            # Check orderbook depth for all pairs
                            # Example trade amount in USDT
                            triangular_pairs.append({
                                'pair1': symbol1,
                                'pair2': pair2,
                                'pair3': pair3
                            })

        return triangular_pairs

    def filter_unique_triangles(self, triangular_pairs):
        """
        Filter out duplicate triangular pairs regardless of their order.
        
        Args:
            triangular_pairs (list): List of dictionaries containing triangular pairs
            
        Returns:
            list: Filtered list containing only unique triangular pairs
        """
        triangle_pairs_all = []
        for triangle in triangular_pairs:
            triangle_pairs_all.append(triangle['pair1'])
            triangle_pairs_all.append(triangle['pair2'])
            triangle_pairs_all.append(triangle['pair3'])
            triangle_pairs_all = list(set(triangle_pairs_all))
        return list(set(triangle_pairs_all))


class BybitTriangleCalculation:
    def __init__(self, trade_amount=10, min_profit=1, max_profit=10):
        """
        Initialize the calculation class
        
        Args:
            trade_amount (float): Initial amount for trading calculations (in USDT)
        """
        self.trade_amount = trade_amount
        self.orderbooks = {}
        self.triangles = []
        self.min_profit = min_profit
        self.max_profit = max_profit
        
        # Safely load triangles.json
        try:
            with open('triangles.json', 'r') as file:
                self.triangles = json.load(file)
            print(f"Successfully loaded {len(self.triangles)} triangles for arbitrage calculation")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load triangles.json: {e}")

    def calculate_value(self, pair, trade_amount, status): # status 'asks', 'bids'
        """
        Calculate how many tokens can be bought/sold at current market prices
        
        Args:
            pair (str): Trading pair symbol (e.g., 'BTCUSDT')
            trade_amount (float): Amount to trade
            status (str): 'asks' for buying, 'bids' for selling
            
        Returns:
            float: Total quantity that can be traded
        """
        # Safety checks
        if pair not in self.orderbooks:
            print(f"Pair {pair} not found in orderbooks")
            return 0
            
        if status not in self.orderbooks[pair]:
            print(f"Status {status} not found for pair {pair}")
            return 0
            
        orderbook_data = self.orderbooks[pair][status]
        if not orderbook_data:
            print(f"Empty {status} for pair {pair}")
            return 0
            
        # Process the orderbook
        total_quantity = 0
        remaining_sum = trade_amount
        
        try:
            for price_qty in orderbook_data:
                # Convert string values to float
                price = float(price_qty[0])
                qty = float(price_qty[1])
                
                if remaining_sum >= price * qty:
                    # Can buy/sell all quantity at this price
                    total_quantity += qty
                    remaining_sum -= price * qty
                else:
                    # Can only buy/sell partial quantity
                    possible_quantity = remaining_sum / price
                    total_quantity += possible_quantity
                    break
        except Exception as e:
            print(f"Error processing {status} for {pair}: {e}")
            return 0

        return total_quantity


    def calculate_arbitrage(self, external_orderbooks=None):
        """
        Calculate arbitrage opportunities using orderbook data
        
        Args:
            external_orderbooks (dict, optional): Latest orderbooks from the WebSocket client
        
        Returns:
            dict: Dictionary of arbitrage results
        """
        results = {}
        
        # Update orderbooks if provided externally
        if external_orderbooks:
            self.orderbooks = external_orderbooks
            
        # Ensure we have orderbooks and triangles data
        if not self.orderbooks:
            print("No orderbooks available for arbitrage calculation")
            return results
            
        if not self.triangles:
            print("No triangles available for arbitrage calculation")
            return results
            
        # Track processing stats
        triangles_processed = 0
        triangles_skipped = 0
        
        # Process each triangle
        for triangle in self.triangles:
            triangles_processed += 1
            try:
                # Check if all required pairs exist in the triangle
                if not all(key in triangle for key in ['pair1', 'pair2', 'pair3']):
                    triangles_skipped += 1
                    continue
                
                # Check if all required pairs exist in orderbooks
                pair1 = triangle['pair1']
                pair2 = triangle['pair2']
                pair3 = triangle['pair3']
                
                if not all(pair in self.orderbooks for pair in [pair1, pair2, pair3]):
                    triangles_skipped += 1
                    continue
                
                # Process the triangle
                token_value1 = self.calculate_value(pair1, self.trade_amount, 'asks')
                if token_value1 <= 0:
                    triangles_skipped += 1
                    continue
                    
                token_value2 = self.calculate_value(pair2, token_value1, 'bids')
                if token_value2 <= 0:
                    triangles_skipped += 1
                    continue
                    
                token_value3 = self.calculate_value(pair3, token_value2, 'asks')
                if token_value3 <= 0:
                    triangles_skipped += 1
                    continue
                    
                # Calculate the arbitrage profit
                final_amount = token_value3
                profit_amount = final_amount - self.trade_amount
                profit_percent = (profit_amount / self.trade_amount) * 100
                
                # Save profitable triangle (even small or negative ones for analysis)

                if self.min_profit <= profit_percent <= self.max_profit:
                    triangle_key = f"{pair1}-{pair2}-{pair3}"
                    results[triangle_key] = {
                        "pairs": [pair1, pair2, pair3],
                        "initial_amount": self.trade_amount,
                        "final_amount": round(final_amount, 6),
                        "profit_amount": round(profit_amount, 6),
                        "profit_percent": round(profit_percent, 4)
                    }
                
            except Exception as e:
                print(f"Error calculating arbitrage for triangle {triangle}: {e}")
                triangles_skipped += 1
                continue
            
        # Print stats
        print(f"Processed {triangles_processed} triangles, skipped {triangles_skipped}")
        print(f"Found {len(results)} potential arbitrage opportunities")
        
        # Save results to file
        timestamp = int(time.time())
        output_data = {
            "timestamp": timestamp,
            "trade_amount": self.trade_amount,
            "triangles_processed": triangles_processed,
            "triangles_skipped": triangles_skipped,
            "results": results
        }
        
        try:
            with open('arbitrage_res_all.json', 'w') as f:
                json.dump(output_data, f, indent=4)
            print("Saved arbitrage results to arbitrage_res_all.json")
        except Exception as e:
            print(f"Error saving arbitrage results: {e}")
            
        return results
        







    # def scan_opportunities(self, min_profit=0.2, max_profit=0.5):
    #     """
    #     Scan for triangular arbitrage opportunities within profit range
    #
    #     Args:
    #         triangles (list): List of triangle dictionaries with price information
    #         min_profit (float): Minimum profit percentage to consider (default: 0.2)
    #         max_profit (float): Maximum profit percentage to consider (default: 3)
    #
    #     Returns:
    #         list: List of dictionaries containing profitable opportunities
    #     """
    #     opportunities = []
    #
    #     for triangle in triangles:
    #         profit = self.calculate_arbitrage(triangle)
    #         if min_profit < profit < max_profit:
    #             opportunities.append({
    #                 'pairs': [triangle['pair1'], triangle['pair2'], triangle['pair3']],
    #                 'profit_percent': profit
    #             })
    #
    #     return opportunities


# Example usage
if __name__ == "__main__":
    arbitrage_bot = BybitTradingPairList(api_key='qwert', api_secret='1234', testnet=False)

    triangles = arbitrage_bot.find_triangular_pairs()
    pairs = arbitrage_bot.get_tickers()
    unique_triangle_pairs = arbitrage_bot.filter_unique_triangles(triangles)
    with open('unique_triangle_pairs.json', 'w') as f:
        json.dump(unique_triangle_pairs, f)

    print(len(pairs))
    print(pairs)
    print(f'find_triangular_pairs: {len(triangles)}')
    print(triangles)
    print(f'number of unique pairs {len(unique_triangle_pairs)}')
    print(unique_triangle_pairs)