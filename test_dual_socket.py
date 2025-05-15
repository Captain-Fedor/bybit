import json
import websocket
from typing import Dict, List
import ssl
import threading
import time

class DualSocketClient:
    def __init__(self, symbols: List[str]):
        self.ws_url = "wss://stream.bybit.com/v5/public/spot"
        self.symbols = symbols
        self.orderbooks = {symbol: {} for symbol in symbols}
        self.running = False

    def _get_subscribe_message(self, symbols: List[str]) -> Dict:
        return {
            "op": "subscribe",
            "args": [f"orderbook.50.{symbol}" for symbol in symbols]
        }

    def _update_orderbook(self, symbol: str, bids: List, asks: List):
        if symbol not in self.orderbooks:
            self.orderbooks[symbol] = {'bids': {}, 'asks': {}}
        
        # Update bids
        for price, qty in bids:
            price, qty = float(price), float(qty)
            if qty > 0:
                self.orderbooks[symbol]['bids'][price] = qty
            else:
                self.orderbooks[symbol]['bids'].pop(price, None)

        # Update asks
        for price, qty in asks:
            price, qty = float(price), float(qty)
            if qty > 0:
                self.orderbooks[symbol]['asks'][price] = qty
            else:
                self.orderbooks[symbol]['asks'].pop(price, None)

    def _process_orderbook(self, data: Dict):
        book_data = data.get('data', {})
        symbol = book_data.get('s', '')
        bids = book_data.get('b', [])
        asks = book_data.get('a', [])
        
        if data.get('type') == 'snapshot':
            self.orderbooks[symbol] = {
                'bids': {float(price): float(qty) for price, qty in bids if float(qty) > 0},
                'asks': {float(price): float(qty) for price, qty in asks if float(qty) > 0},
                'u': book_data.get('u', 0),
                'seq': book_data.get('seq', 0)
            }
        elif data.get('type') == 'delta':
            self._update_orderbook(symbol, bids, asks)
            self.orderbooks[symbol].update({
                'u': book_data.get('u', 0),
                'seq': book_data.get('seq', 0)
            })

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'topic' in data and 'orderbook' in data['topic']:
                self._process_orderbook(data)
        except Exception as e:
            print(f"Error: {e}")

    def _ws_thread(self):
        def on_open(ws):
            ws.send(json.dumps(self._get_subscribe_message(self.symbols)))
            print("WebSocket connected")

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_message,
            on_open=on_open
        )

        self.ws.run_forever(
            sslopt={"cert_reqs": ssl.CERT_NONE},
            ping_interval=20,
            ping_timeout=10
        )

    def start(self):
        self.running = True
        self.ws_thread = threading.Thread(target=self._ws_thread)
        self.ws_thread.daemon = True
        self.ws_thread.start()

    def stop(self):
        self.running = False
        if hasattr(self, 'ws'):
            self.ws.close()

    def get_orderbook(self, symbol: str) -> Dict:
        return self.orderbooks.get(symbol, {})

    def print_orderbooks(self):
        """Print current state of orderbooks with improved formatting"""
        for symbol in self.symbols:
            ob = self.get_orderbook(symbol)
            if ob and (ob.get('bids') or ob.get('asks')):
                print(f"\n{'='*50}")
                print(f"{symbol} Orderbook".center(50))
                print(f"{'='*50}")
                
                bids = sorted(ob.get('bids', {}).items(), reverse=True)[:5]
                asks = sorted(ob.get('asks', {}).items())[:5]
                
                # Header
                print(f"\n{'Price':^15} | {'Quantity':^15} | {'Total($)':^15}")
                print('-' * 49)
                
                # Print asks in reverse order (highest to lowest)
                for price, qty in reversed(asks):
                    total = price * qty
                    print(f"{price:15.8f} | {qty:15.3f} | {total:15.2f}")
                
                # Spread calculation if both bids and asks exist
                if bids and asks:
                    spread = asks[0][0] - bids[0][0]
                    spread_pct = (spread / asks[0][0]) * 100
                    print(f"\nSpread: {spread:.8f} ({spread_pct:.2f}%)")
                
                # Print bids
                print('-' * 49)
                for price, qty in bids:
                    total = price * qty
                    print(f"{price:15.8f} | {qty:15.3f} | {total:15.2f}")
                
                print(f"\nBid Levels: {len(ob.get('bids', {}))}")
                print(f"Ask Levels: {len(ob.get('asks', {}))}")
                print(f"Update ID: {ob.get('u', 0)}")

if __name__ == "__main__":
    # Enable debug level for websocket
    websocket.enableTrace(True)
    
    symbols = ["BTCUSDT", "ETHUSDT", "DOGEUSDT"]
    client = DualSocketClient(symbols)
    
    try:
        client.start()
        print("Starting WebSocket connection...")
        
        while True:
            client.print_orderbooks()
            time.sleep(1)  # Reduced to 1 second
            print("\033[2J\033[H")  # Clear screen
            
    except KeyboardInterrupt:
        print("\nShutting down...")
        client.stop()