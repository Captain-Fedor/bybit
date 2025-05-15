import json
import os
from datetime import datetime
import websocket
import threading
import ssl
import time
from collections import defaultdict
from typing import Dict, List, Any

class BybitGetOrderBook:
    def __init__(self, symbols, depth=50):

        self.symbols = symbols
        self.depth = depth
        self.orderbooks = {
            symbol: {
                'bids': {},  # price -> quantity
                'asks': {}   # price -> quantity
            } for symbol in symbols
        }
        self.current_data = {}
        self.ws = None
        self.ws_thread = None
        self.json_file = "orderbook_data.json"
        self.running = True

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

    def update_orderbook(self, symbol, bids, asks):
        # Update bids
        for bid in bids:
            price, quantity = float(bid[0]), float(bid[1])
            if quantity > 0:
                self.orderbooks[symbol]['bids'][price] = quantity
            else:
                self.orderbooks[symbol]['bids'].pop(price, None)

        # Update asks
        for ask in asks:
            price, quantity = float(ask[0]), float(ask[1])
            if quantity > 0:
                self.orderbooks[symbol]['asks'][price] = quantity
            else:
                self.orderbooks[symbol]['asks'].pop(price, None)

        # Sort and limit the orderbook
        sorted_bids = sorted(self.orderbooks[symbol]['bids'].items(), reverse=True)[:self.depth]
        sorted_asks = sorted(self.orderbooks[symbol]['asks'].items())[:self.depth]

        # Convert back to the format we want to save
        formatted_bids = [[str(price), str(qty)] for price, qty in sorted_bids]
        formatted_asks = [[str(price), str(qty)] for price, qty in sorted_asks]

        return formatted_bids, formatted_asks

    def save_to_json(self, symbol, bids, asks):
        # Update the data for this symbol
        self.current_data[symbol] = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
            "bids": bids,
            "asks": asks
        }
        
        try:
            # Save all symbols' data
            with open(self.json_file, 'w') as f:
                json.dump(self.current_data, f, indent=2)
            
            file_size = os.path.getsize(self.json_file)
            print(f"Data saved for {symbol}. File size: {file_size/1024:.2f} KB")
                
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
                    
                    # Update internal orderbook and get sorted results
                    formatted_bids, formatted_asks = self.update_orderbook(symbol, bids, asks)
                    
                    # Save the current state
                    self.save_to_json(symbol, formatted_bids, formatted_asks)
                
        except Exception as e:
            print(f"Error handling message: {str(e)}")
            print(f"Message that caused error: {message}")
            import traceback
            print(f"Full error: {traceback.format_exc()}")

    def start(self) -> Dict[str, Any]:
        """
        Start the bot and return the final recorded data.
        
        Returns:
            Dict[str, Any]: The last recorded orderbook data for all symbols
        """
        print("Starting bot...")
        self.connect_websocket()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            print("\nShutting down...")
            if self.ws:
                self.ws.close()
            if self.ws_thread:
                self.ws_thread.join()
            print("Bot stopped successfully")
            
            # Return the final recorded data
            return self.current_data

    def stop(self):
        """Stop the bot gracefully"""
        self.running = False

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

def main():
    symbols = ["ETHUSDT", "BTCUSDT", "SOLUSDT"]
    bot = BybitGetOrderBook(symbols=symbols)
    print(f"Bot initialized with symbols: {symbols}")
    
    try:
        # Run the bot and get the final data
        final_data = bot.start()
        return final_data
    except KeyboardInterrupt:
        bot.stop()
        return bot.current_data

if __name__ == "__main__":
    recorded_data = main()
    print("\nFinal recorded data:")
    print(json.dumps(recorded_data, indent=2))