from pybit.unified_trading import HTTP
import pandas as pd
import time
import json
import requests
import certifi
from typing import List


class BybitTradingPairList:
    def __init__(self, api_key, api_secret, testnet=False):
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        self.min_volume = 1  # Minimum 24h volume
        self.min_turnover = 1  # Minimum 24h turnover in USDT
        self.trade_amount = 1000
        self.depth = 100

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
    def __init__(self, trade_amount=1000):
        """
        Initialize the calculation class
        
        Args:
            trade_amount (float): Initial amount for trading calculations (in USDT)
        """
        self.trade_amount = trade_amount

    def calculate_arbitrage(self, triangle):
        """
        Calculate potential arbitrage profit
        
        Args:
            triangle (dict): Dictionary containing trading pairs and their prices
                           Expected format: {
                               'price1': float,
                               'price2': float,
                               'price3': float
                           }
        
        Returns:
            float: Profit percentage
        """
        # Forward trade route
        amount1 = self.trade_amount / triangle['price1']  # USDT -> Token1
        amount2 = amount1 * triangle['price2']  # Token1 -> Token2
        amount3 = amount2 * triangle['price3']  # Token2 -> USDT

        # Calculate profit/loss percentage
        profit_percent = ((amount3 - self.trade_amount) / self.trade_amount) * 100

        return profit_percent

    def scan_opportunities(self, triangles, min_profit=0.2, max_profit=3):
        """
        Scan for triangular arbitrage opportunities within profit range
        
        Args:
            triangles (list): List of triangle dictionaries with price information
            min_profit (float): Minimum profit percentage to consider (default: 0.2)
            max_profit (float): Maximum profit percentage to consider (default: 3)
        
        Returns:
            list: List of dictionaries containing profitable opportunities
        """
        opportunities = []

        for triangle in triangles:
            profit = self.calculate_arbitrage(triangle)
            if min_profit < profit < max_profit:
                opportunities.append({
                    'pairs': [triangle['pair1'], triangle['pair2'], triangle['pair3']],
                    'profit_percent': profit
                })

        return opportunities


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
