import json
import os
from datetime import datetime
import websocket
import threading
import ssl
import time

class BybitTriangleArbitrage:
    def __init__(self, symbols=None, depth=50):
        if symbols is None:
            symbols = ["ETHUSDT", "BTCUSDT"]
        self.symbols = symbols
        self.depth = depth
        self.bids = {symbol: {} for symbol in symbols}
        self.asks = {symbol: {} for symbol in symbols}
        self.ws = None
        self.ws_thread = None
        
        self.data_dir = os.path.join(os.getcwd(), 'orderbook_data')
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            print(f"Directory created/verified at: {self.data_dir}")
        except Exception as e:
            print(f"Error creating directory: {e}")
        
        self.json_file = "orderbook_data.json"
        self.all_data = self.load_existing_data()

    def load_existing_data(self):
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Error reading existing file, starting fresh")
                return {}
        return {}

    def connect_websocket(self):
        websocket.enableTrace(True)
        ws_url = "wss://stream.bybit.com/v5/public/spot"
        
        sslopt = {
            "cert_reqs": ssl.CERT_NONE,
            "check_hostname": False
        }
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        self.ws_thread = threading.Thread(target=lambda: self.ws.run_forever(sslopt=sslopt))
        self.ws_thread.daemon = True
        self.ws_thread.start()

    def start(self):
        print("Starting bot...")
        self.connect_websocket()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            if self.ws:
                self.ws.close()
            if self.ws_thread:
                self.ws_thread.join()
            print("Bot stopped successfully")

    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket Connection Closed")

    def on_open(self, ws):
        print("WebSocket Connection Opened")
        for symbol in self.symbols:
            subscribe_message = {
                "op": "subscribe",
                "args": [f"orderbook.50.{symbol}"]
            }
            ws.send(json.dumps(subscribe_message))
            print(f"Subscribed to {symbol} orderbook")

    def update_orderbook(self, symbol, bids, asks):
        # Update bids
        for bid in bids:
            price, size = float(bid[0]), float(bid[1])
            if size == 0:
                self.bids[symbol].pop(price, None)
            else:
                self.bids[symbol][price] = size

        # Update asks
        for ask in asks:
            price, size = float(ask[0]), float(ask[1])
            if size == 0:
                self.asks[symbol].pop(price, None)
            else:
                self.asks[symbol][price] = size

    def get_sorted_orderbook(self, symbol):
        bids = sorted(self.bids[symbol].items(), key=lambda x: x[0], reverse=True)
        asks = sorted(self.asks[symbol].items(), key=lambda x: x[0])
        return bids, asks

    def save_to_json(self, symbol):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        
        if not self.bids[symbol] and not self.asks[symbol]:
            return
        
        current_bids, current_asks = self.get_sorted_orderbook(symbol)
        
        # Format data as [price, size] arrays
        new_data = {
            "symbol": symbol,
            "bids": [[price, size] for price, size in current_bids[:self.depth]],
            "asks": [[price, size] for price, size in current_asks[:self.depth]]
        }
        
        # Add to main data structure
        if symbol not in self.all_data:
            self.all_data[symbol] = {}
        self.all_data[symbol][timestamp] = new_data
        
        try:
            with open(self.json_file, 'w') as f:
                json.dump(self.all_data, f, indent=2)
            
            file_size = os.path.getsize(self.json_file)
            print(f"Data saved. File size: {file_size/1024:.2f} KB")
                
        except Exception as e:
            print(f"Error saving to JSON: {str(e)}")
            import traceback
            print(f"Full error: {traceback.format_exc()}")

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            if 'data' in data:
                symbol = data['data']['s']
                if symbol in self.symbols:
                    asks = data['data'].get('a', [])
                    bids = data['data'].get('b', [])
                    
                    print(f"Processing {symbol} - Bids: {len(bids)}, Asks: {len(asks)}")
                    
                    self.update_orderbook(symbol, bids, asks)
                    self.save_to_json(symbol)
                
        except Exception as e:
            print(f"Error handling message: {str(e)}")
            print(f"Message that caused error: {message}")
            import traceback
            print(f"Full error: {traceback.format_exc()}")

def main():
    symbols = ["ETHUSDT", "BTCUSDT", "SOLUSDT"]
    bot = BybitTriangleArbitrage(symbols=symbols)
    print(f"Bot initialized with symbols: {symbols}")
    bot.start()

if __name__ == "__main__":
    main()