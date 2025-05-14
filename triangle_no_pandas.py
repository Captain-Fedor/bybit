from pybit.unified_trading import HTTP
import pandas as pd
import time
import json


class BybitTriangleArbitrage:
    def __init__(self, api_key, api_secret, testnet=True):
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        self.min_volume = 1000  # Minimum 24h volume
        self.min_turnover = 1000  # Minimum 24h turnover in USDT
        self.trade_amount = 1000
        self.depth = 1

    def get_tickers(self):
        """Get all tickers from Bybit excluding adventure tokens"""
        try:
            tickers = self.session.get_tickers(category="spot")
            # Filter out adventure tokens (symbols starting with 'A')
            filtered_tickers = [
                ticker for ticker in tickers['result']['list']
                if not ticker['symbol'].startswith('A')
            ]
            with open('tickers.json', 'w') as f:
                json.dump({'result': {'list': filtered_tickers}}, f)
            return filtered_tickers
        except Exception as e:
            print(f"Error fetching tickers: {e}")
            return None

    def check_orderbook_depth(self, symbol):
        """Check if there's enough liquidity in the orderbook"""
        try:
            orderbook = self.session.get_orderbook(
                category="spot",
                symbol=symbol,
                limit=1000

            )

            # Correct access to orderbook data structure
            if 'result' in orderbook and 'b' in orderbook['result'] and 'a' in orderbook['result']:
                bids = orderbook['result']['b']  # Bids are under 'b'
                asks = orderbook['result']['a']  # Asks are under 'a' [price,quantity]
                print(bids)
                print(asks)
                print(f"Orderbook depth for {symbol}: {len(bids)} bids, {len(asks)} asks")

                # Calculate cumulative volumes
                bid_liquidity = sum(int((float(bid[0]) * float(bid[1]))) for bid in bids[:self.depth])
                ask_liquidity = sum(int((float(ask[0]) * float(ask[1]))) for ask in asks[:self.depth])
                print(f"Liquidity for {symbol}: {bid_liquidity} / {ask_liquidity}")

                # Sum top 10 asks
                return bid_liquidity >= self.trade_amount and ask_liquidity >= self.trade_amount
            else:
                print(f"Unexpected orderbook structure for {symbol}: {orderbook}")
                return False

        except Exception as e:
            print(f"Error checking orderbook for {symbol}: {e}")
            return False

    def find_triangular_pairs(self, base_currency="USDT"):
        """Find all possible triangular pairs with the given base currency"""
        tickers = self.get_tickers()
        if not tickers:
            return []

        # Create DataFrame of all trading pairs
        pairs_data = []
        for ticker in tickers:
            symbol = ticker['symbol']
            price = float(ticker['lastPrice'])
            volume = float(ticker['volume24h'])
            if volume >= self.min_volume:  # Only include pairs with sufficient volume
                pairs_data.append({
                    'symbol': symbol,
                    'price': price,
                    'volume': volume
                })

        triangular_pairs = []
        # Find all possible triangular combinations
        for pair1 in pairs_data:
            symbol1 = pair1['symbol']
            if not symbol1.endswith(base_currency):
                continue

            token1 = symbol1.replace(base_currency, '')

            # Find second pair
            for pair2 in pairs_data:
                if pair2['symbol'].startswith(token1):
                    token2 = pair2['symbol'].replace(token1, '')

                    # Find third pair to complete the triangle
                    for pair3 in pairs_data:
                        if pair3['symbol'] == f"{token2}{base_currency}":
                            # Check orderbook depth for all pairs
                            # Example trade amount in USDT
                            if (self.check_orderbook_depth(symbol1) and
                                    self.check_orderbook_depth(pair2['symbol']) and
                                    self.check_orderbook_depth(pair3['symbol'])):
                                triangular_pairs.append({
                                    'pair1': symbol1,
                                    'pair2': pair2['symbol'],
                                    'pair3': pair3['symbol'],
                                    'price1': pair1['price'],
                                    'price2': pair2['price'],
                                    'price3': pair3['price'],
                                    'volume1': pair1['volume'],
                                    'volume2': pair2['volume'],
                                    'volume3': pair3['volume']
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
    # Initialize with your API keys (use testnet first!)
    api_key = "6gfeT8jTRhfF4Hf3cV"
    api_secret = "uIliSYcaPnykJXFqGkbIZx89Nsp7lUOl1m0Y"

    arbitrage_bot = BybitTriangleArbitrage(api_key, api_secret, testnet=True)

    while True:
        print("Scanning for arbitrage opportunities...")
        opportunities = arbitrage_bot.scan_opportunities()

        for opp in opportunities:
            print(f"Found opportunity: {opp['pairs']}")
            print(f"Potential profit: {opp['profit_percent']:.2f}%")

        time.sleep(1)  # Wait 1 second before next scan