import json
from triangle_no_pandas import BybitTriangleArbitrage

class ExtendedBybitTriangleArbitrage(BybitTriangleArbitrage):
    def analyze_usdt_pairs(self):
        """Get detailed orderbook information for all USDT pairs"""
        try:
            # First get all tickers to find USDT pairs
            response = self.session.get_tickers(category="spot")
            if response.get('retCode') != 0:
                print(f"API Error: {response.get('retMsg')}")
                return None

            tickers = response.get('result', {}).get('list', [])
            with open('test2_response.json', 'w') as f:
                json.dump(response, f)

            # Filter for USDT pairs
            usdt_pairs = [ticker['symbol'] for ticker in tickers if ticker['symbol'].endswith('USDT')]
            print(f"\nFound {len(usdt_pairs)} USDT pairs")

            orderbook_data = []
            for symbol in usdt_pairs:
                try:
                    # Get orderbook for each pair
                    orderbook = self.session.get_orderbook(
                        category="spot",
                        symbol=symbol,
                        limit=10  # Get top 10 levels
                    )

                    if orderbook.get('retCode') == 0 and 'result' in orderbook:
                        result = orderbook['result']

                        # Calculate total volume and weighted average prices
                        ask_volume = sum(float(ask[1]) for ask in result['a'][:10])
                        bid_volume = sum(float(bid[1]) for bid in result['b'][:10])

                        # Get best bid/ask
                        best_bid = float(result['b'][0][0]) if result['b'] else 0
                        best_ask = float(result['a'][0][0]) if result['a'] else 0
                        spread = ((best_ask - best_bid) / best_bid * 100) if best_bid > 0 else 0

                        pair_data = {
                            'symbol': symbol,
                            'timestamp': result['ts'],
                            'best_bid': best_bid,
                            'best_ask': best_ask,
                            'spread_percent': spread,
                            'bid_volume_10': bid_volume,
                            'ask_volume_10': ask_volume,
                            'top_10_asks': result['a'][:10],
                            'top_10_bids': result['b'][:10]
                        }

                        orderbook_data.append(pair_data)

                        # Print summary
                        print(f"\n{symbol}:")
                        print(f"Best Bid: {best_bid:.8f} | Best Ask: {best_ask:.8f}")
                        print(f"Spread: {spread:.4f}%")
                        print(f"10-level Bid Volume: {bid_volume:.2f}")
                        print(f"10-level Ask Volume: {ask_volume:.2f}")
                        print("-" * 50)

                except Exception as e:
                    print(f"Error processing {symbol}: {e}")
                    continue

            # Save detailed data to file
            with open('usdt_pairs_orderbooks.json', 'w') as f:
                json.dump(orderbook_data, f, indent=2)

            print(f"\nSaved detailed orderbook data for {len(orderbook_data)} pairs")
            return orderbook_data

        except Exception as e:
            print(f"Error analyzing USDT pairs: {e}")
            return None


if __name__ == "__main__":
    api_key = "your_api_key"
    api_secret = "your_api_secret"
    
    bot = ExtendedBybitTriangleArbitrage(api_key, api_secret, testnet=False)
    orderbooks = bot.analyze_usdt_pairs()