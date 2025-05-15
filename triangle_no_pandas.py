from pybit.unified_trading import HTTP
import pandas as pd
import time
import json


class BybitTriangleArbitrage:
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

    def get_tickers(self):
        """Get all tickers from Bybit excluding adventure tokens"""
        try:
            tickers = self.session.get_tickers(category="spot")
            # Filter out adventure tokens (symbols starting with 'A')
            filtered_tickers = [
                ticker for ticker in tickers['result']['list']
                if not ticker['symbol'].startswith('A')
            ]
            _filtered_tickers = [
                pair['symbol'] for pair in filtered_tickers
            ]
            with open('tickers.json', 'w') as f:
                # json.dump({'result': {'list': _filtered_tickers}}, f)
                json.dump(_filtered_tickers, f)
            return _filtered_tickers
        except Exception as e:
            print(f"Error fetching tickers: {e}")
            return None

    def get_orderbook(self, symbol):
        """Get orderbook for a given symbol"""
        try:
            orderbook = self.session.get_orderbook(
                category="spot",
                symbol=symbol,
                limit=1000
            )
            return orderbook
        except Exception as e:
            print(f"Error checking orderbook for {symbol}: {e}")
            return False

    def check_orderbook_depth(self, symbol):
        """Check if there's enough liquidity in the orderbook"""
        orderbook = self.get_orderbook(symbol=symbol)

            # Correct access to orderbook data structure
        if orderbook['result']['a'] and orderbook['result']['b']:
            bids = orderbook['result']['b']  # Bids are under 'b'
            asks = orderbook['result']['a']  # Asks are under 'a' [price,quantity]

                # Calculate cumulative volumes
            bid_liquidity = sum(int((float(bid[0]) * float(bid[1]))) for bid in bids[:self.depth])
            ask_liquidity = sum(int((float(ask[0]) * float(ask[1]))) for ask in asks[:self.depth])
                # print(f"Liquidity for {symbol}: {bid_liquidity} / {ask_liquidity}")

                # Sum top 10 asks
            return bid_liquidity >= self.trade_amount and ask_liquidity >= self.trade_amount
        else:
            print(f"Unexpected orderbook structure for {symbol}: {orderbook}")
            return False

    def calculate_crypto_amount(self, orderbook, trade_amount):
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

    def calculate_arbitrage(self, triangle):
        """Calculate potential arbitrage profit"""
        # Initial amount of base currency

        # Forward trade route
        amount1 = self.trade_amount / triangle['price1']  # USDT -> Token1
        amount2 = amount1 * triangle['price2']  # Token1 -> Token2
        amount3 = amount2 * triangle['price3']  # Token2 -> USDT

        # Calculate profit/loss percentage
        profit_percent = ((amount3 - self.trade_amount) / self.trade_amount) * 100

        return profit_percent

    def scan_opportunities(self, min_profit=0.2, max_profit=3):
        """Scan for triangular arbitrage opportunities"""
        triangles = self.find_triangular_pairs()
        opportunities = []

        for triangle in triangles:
            profit = self.calculate_arbitrage(triangle)
            if profit > min_profit and profit < max_profit:  # Only show opportunities above minimum profit threshold
                opportunities.append({
                    'pairs': [triangle['pair1'], triangle['pair2'], triangle['pair3']],
                    'profit_percent': profit
                })

        return opportunities


# Example usage
if __name__ == "__main__":
    arbitrage_bot = BybitTriangleArbitrage(api_key='qwert', api_secret='1234', testnet=True)


    l=arbitrage_bot.find_triangular_pairs()
    pairs = arbitrage_bot.get_tickers()
    print(len(pairs))
    print(pairs)
    print(len(l))
    print(l)




    # # Initialize with your API keys (use testnet first!)
    # api_key = "6gfeT8jTRhfF4Hf3cV"
    # api_secret = "uIliSYcaPnykJXFqGkbIZx89Nsp7lUOl1m0Y"
    #
    # arbitrage_bot = BybitTriangleArbitrage(api_key, api_secret, testnet=True)
    #
    # while True:
    #     print("Scanning for arbitrage opportunities...")
    #     opportunities = arbitrage_bot.scan_opportunities()
    #
    #     for opp in opportunities:
    #         print(f"Found opportunity: {opp['pairs']}")
    #         print(f"Potential profit: {opp['profit_percent']:.2f}%")
    #
    #     time.sleep(1)  # Wait 1 second before next scan