import asyncio
import json
import requests
import websockets
import ssl
import certifi
import time
from typing import List, Dict
from pathlib import Path

def load_trading_pairs() -> List[str]:
    pair_socket_dir = Path("pair_socket")
    
    # Load verified pairs from all_pairs.json
    with open(pair_socket_dir / "all_pairs.json", "r") as f:
        verified_pairs = json.load(f)["verified_pairs"]
    
    # Load pairs to avoid from no_adventure.json
    with open(pair_socket_dir / "no_adventure.json", "r") as f:
        no_adventure_pairs = json.load(f)
    
    # Get the set of verified pairs excluding any that are in no_adventure
    trading_pairs = [
        pair for pair in verified_pairs.keys()
        if pair not in no_adventure_pairs
    ]
    
    if not trading_pairs:
        raise ValueError("No valid trading pairs found after filtering")
    
    return trading_pairs

class SymbolWebSocket:
    def __init__(self, symbols: List[str], socket_id: int):
        self.symbols = symbols
        self.socket_id = socket_id
        # ... rest of the implementation ...

    def _get_subscribe_message(self) -> Dict:
        subscription = {
            "op": "subscribe",
            "args": [f"orderbook.50.{symbol}" for symbol in self.symbols]
        }
        print(f"Socket {self.socket_id} subscribing to: {subscription}")  # Debug print
        return subscription

class BybitSpotOrderbookChecker:
    def __init__(self):
        self.ws_url = "wss://stream.bybit.com/v5/public/spot"
        self.verified_pairs: Dict[str, Dict] = {}
        self.verification_timeout = 5
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        
    def get_all_spot_pairs(self) -> List[str]:
        url = "https://api.bybit.com/v5/market/instruments-info"
        params = {"category": "spot"}
        
        try:
            response = requests.get(url, params=params, verify=certifi.where())
            response.raise_for_status()
            data = response.json()
            
            pairs = []
            if data.get("result") and data["result"].get("list"):
                for instrument in data["result"]["list"]:
                    if instrument.get("status") == "Trading":
                        pairs.append(instrument["symbol"])
            return sorted(pairs)
        except Exception as e:
            print(f"Error fetching pairs: {e}")
            return []

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

    async def verify_pairs_batch(self, pairs: List[str], batch_size: int = 5):
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]
            tasks = [self.verify_orderbook(pair) for pair in batch]
            await asyncio.gather(*tasks)

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
        
        # Save results to pair_socket/all_pairs.json
        result = {
            "timestamp": int(time.time()),
            "verified_pairs": self.verified_pairs
        }
        
        with open(pair_socket_dir / 'all_pairs.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        return self.verified_pairs

if __name__ == "__main__":
    try:
        import websockets
        import certifi
    except ImportError:
        print("Installing required libraries...")
        import subprocess
        subprocess.check_call(["pip", "install", "websockets", "certifi"])
        import websockets
        import certifi
    
    checker = BybitSpotOrderbookChecker()
    verified_pairs = checker.run_verification(debug_limit=10)  # Set debug limit to 10 pairs or if nothing
    # it will download all pairs