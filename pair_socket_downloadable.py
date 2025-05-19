import asyncio
import json
import ssl
import time
from pathlib import Path
from typing import Dict, List
import websockets
import certifi
import requests

class BybitSpotOrderbookChecker:
    def __init__(self):
        self.ws_url = "wss://stream.bybit.com/v5/public/spot"
        self.verified_pairs: Dict[str, Dict] = {}
        self.verification_timeout = 5
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.usdt_prices = {}  # Cache for USDT prices

    def get_usdt_price(self, symbol: str) -> float:
        """Get price in USDT for a given symbol."""
        if symbol.endswith('USDT'):
            return 1.0
            
        usdt_symbol = f"{symbol.split(symbol[-3:])[0]}USDT"
        
        if usdt_symbol in self.verified_pairs:
            # Use the mid price from the orderbook
            orderbook = self.verified_pairs[usdt_symbol]
            if orderbook["bids"] and orderbook["asks"]:
                return (float(orderbook["bids"][0][0]) + float(orderbook["asks"][0][0])) / 2
                
        # If we don't have the price yet, fetch it from the API
        url = "https://api.bybit.com/v5/market/tickers"
        params = {"category": "spot", "symbol": usdt_symbol}
        try:
            response = requests.get(url, params=params, verify=certifi.where())
            response.raise_for_status()
            data = response.json()
            if data.get("result") and data["result"].get("list"):
                price = float(data["result"]["list"][0]["lastPrice"])
                self.usdt_prices[symbol] = price
                return price
        except Exception as e:
            print(f"Error fetching USDT price for {symbol}: {e}")
        return None

    def calculate_usdt_value(self, symbol: str, orders: List[List[str]]) -> float:
        """Calculate total value in USDT for a list of orders."""
        if symbol.endswith('USDT'):
            return sum(float(price) * float(size) for price, size in orders)
            
        usdt_price = self.get_usdt_price(symbol)
        if usdt_price is None:
            return 0.0
            
        if symbol.endswith('USDT'):
            return sum(float(price) * float(size) for price, size in orders)
        else:
            # For non-USDT pairs, convert to USDT
            return sum(float(price) * float(size) * usdt_price for price, size in orders)

    def get_all_spot_pairs(self) -> List[str]:
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

    async def verify_pairs_batch(self, pairs: List[str], batch_size: int = 10):
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]
            tasks = [self.verify_orderbook(pair) for pair in batch]
            await asyncio.gather(*tasks)
            print(f"Processed {min(i + batch_size, len(pairs))}/{len(pairs)} pairs")

    async def verify_orderbook(self, symbol: str) -> bool:
        try:
            async with websockets.connect(
                self.ws_url,
                ssl=self.ssl_context
            ) as ws:
                subscribe_msg = {
                    "op": "subscribe",
                    "args": [f"orderbook.50.{symbol}"]
                }
                await ws.send(json.dumps(subscribe_msg))
                
                start_time = time.time()
                while time.time() - start_time < self.verification_timeout:
                    response = await ws.recv()
                    data = json.loads(response)
                    
                    if data.get("op") == "subscribe" and data.get("success"):
                        continue
                    
                    if "data" in data and "b" in data["data"] and "a" in data["data"]:
                        # Get all bids and asks
                        all_bids = data["data"]["b"]
                        all_asks = data["data"]["a"]
                        
                        if len(all_bids) > 0 or len(all_asks) > 0:
                            # Calculate total value for entire orderbook
                            total_bids_value = sum(float(price) * float(size) for price, size in all_bids)
                            total_asks_value = sum(float(price) * float(size) for price, size in all_asks)
                            
                            # Convert to USDT if needed
                            if not symbol.endswith('USDT'):
                                usdt_price = self.get_usdt_price(symbol)
                                if usdt_price:
                                    total_bids_value *= usdt_price
                                    total_asks_value *= usdt_price

                            # Sort bids (highest first) and asks (lowest first)
                            bids_display = sorted(all_bids, key=lambda x: float(x[0]), reverse=True)[:3]
                            asks_display = sorted(all_asks, key=lambda x: float(x[0]))[:3]
                            
                            orderbook_data = {
                                "timestamp": data.get("ts", int(time.time() * 1000)),
                                "bids": bids_display,  # Top 3 bids for display
                                "asks": asks_display,  # Top 3 asks for display
                                "bid_depth": len(all_bids),
                                "ask_depth": len(all_asks),
                                "total_bids_value": round(total_bids_value, 2),
                                "total_asks_value": round(total_asks_value, 2),
                                "total_orderbook_value": round(total_bids_value + total_asks_value, 2),
                                "quote_currency": "USDT" if symbol.endswith('USDT') else symbol[-3:]
                            }
                            
                            self.verified_pairs[symbol] = orderbook_data
                            
                            # Print the pair and its orderbook information
                            print(f"\n{symbol}:")
                            print(f"Orderbook depths - Bids: {len(all_bids)}, Asks: {len(all_asks)}")
                            print(f"Total orderbook value: {orderbook_data['total_orderbook_value']} USDT")
                            print(f"  Total bids value: {orderbook_data['total_bids_value']} USDT")
                            print(f"  Total asks value: {orderbook_data['total_asks_value']} USDT")
                            print("\nTop 3 Bids:")
                            for price, size in bids_display:
                                value = float(price) * float(size)
                                print(f"  {price} - {size} (Value: {round(value, 2)} {orderbook_data['quote_currency']})")
                            print("Top 3 Asks:")
                            for price, size in asks_display:
                                value = float(price) * float(size)
                                print(f"  {price} - {size} (Value: {round(value, 2)} {orderbook_data['quote_currency']})")
                            print("-" * 40)
                            
                            return True
                
                return False
        except Exception as e:
            print(f"Error verifying {symbol}: {e}")
            return False

    def run_verification(self, debug_limit=None):
        print("Fetching all spot trading pairs...")
        pairs = self.get_all_spot_pairs()
        
        if debug_limit:
            pairs = pairs[:debug_limit]
            print(f"Debug mode: limiting to first {debug_limit} pairs")
        
        print(f"Found {len(pairs)} pairs to verify\n")
        
        print("Starting orderbook verification...")
        asyncio.run(self.verify_pairs_batch(pairs))
        
        # Create pair_socket directory if it doesn't exist
        pair_socket_dir = Path("pair_socket")
        pair_socket_dir.mkdir(exist_ok=True)
        
        # Save full orderbook results to pair_socket/all_pairs.json
        result = {
            "timestamp": int(time.time()),
            "verified_pairs": self.verified_pairs
        }
        
        with open(pair_socket_dir / 'all_pairs.json', 'w') as f:
            json.dump(result, f, indent=2)
            
        # Save just the pair names to pairs_names_only.json
        pairs_names = {
            "timestamp": int(time.time()),
            "total_pairs": len(self.verified_pairs),
            "pairs": sorted(list(self.verified_pairs.keys()))
        }
        
        with open(pair_socket_dir / 'pairs_names_only.json', 'w') as f:
            json.dump(pairs_names, f, indent=2)
        
        print(f"\nSaved {len(self.verified_pairs)} pairs to all_pairs.json")
        print(f"Saved pair names to pairs_names_only.json")
        
        return self.verified_pairs

if __name__ == "__main__":
    checker = BybitSpotOrderbookChecker()
    verified_pairs = checker.run_verification(debug_limit=50)  # Remove debug_limit to check all pairs
    # Or use debug_limit to test with fewer pairs:
    # verified_pairs = checker.run_verification(debug_limit=10)

    # Additional check for specific pair
    specific_pair = "BTCUSDT"  # You can change this to any valid trading pair
    print(f"\nChecking specific pair: {specific_pair}...")
    asyncio.run(checker.verify_orderbook(specific_pair))

    # Create pair_socket directory if it doesn't exist
    pair_socket_dir = Path("pair_socket")
    pair_socket_dir.mkdir(exist_ok=True)

    # Save the single pair data to one_pair.json
    result = {
        "timestamp": int(time.time()),
        "pair": specific_pair,
        "orderbook_data": checker.verified_pairs[specific_pair]
    }

    with open(pair_socket_dir / 'one_pair.json', 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Saved {specific_pair} orderbook data to one_pair.json")
