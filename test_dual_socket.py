import websocket
import json
import threading
import ssl
import certifi
from typing import List, Dict, Tuple

class TripleSocketManager:
    def __init__(self):
        self.ws1 = None
        self.ws2 = None
        self.ws3 = None
        self.orderbook1 = {}
        self.orderbook2 = {}
        self.orderbook3 = {}
        self.running = True
        self.MAX_PAIRS_PER_CONNECTION = 150

    def start(self):
        """Start the WebSocket connections"""
        pairs = self.get_filtered_tickers()
        ws1_pairs, ws2_pairs, ws3_pairs = self.split_pairs(pairs)
        
        self.ws1 = self._connect_websocket("ws1", ws1_pairs)
        self.ws2 = self._connect_websocket("ws2", ws2_pairs)
        self.ws3 = self._connect_websocket("ws3", ws3_pairs)

    def split_pairs(self, pairs: List[dict]) -> Tuple[List[dict], List[dict], List[dict]]:
        """Split the trading pairs into three groups, respecting the 150 pair per connection limit"""
        total_pairs = len(pairs)
        max_total = self.MAX_PAIRS_PER_CONNECTION * 3
        
        if total_pairs > max_total:
            print(f"Warning: Total pairs ({total_pairs}) exceeds maximum capacity ({max_total})")
            pairs = pairs[:max_total]
        
        third = len(pairs) // 3
        return (
            pairs[:third],
            pairs[third:2*third],
            pairs[2*third:]
        )

    def _connect_websocket(self, ws_name: str, pairs: List[dict]) -> websocket.WebSocketApp:
        """Create a WebSocket connection"""
        endpoint = "wss://stream.bybit.com/v5/public/spot"
        
        ws = websocket.WebSocketApp(
            endpoint,
            on_message=lambda ws, msg: self._on_message(ws, msg, ws_name),
            on_error=lambda ws, error: self._on_error(ws, error, ws_name),
            on_close=lambda ws, close_status_code, close_msg: self._on_close(ws, close_status_code, close_msg, ws_name),
            on_open=lambda ws: self._on_open(ws, ws_name, pairs)
        )
        
        ws_thread = threading.Thread(
            target=lambda: ws.run_forever(
                sslopt={
                    "cert_reqs": ssl.CERT_REQUIRED,
                    "ca_certs": certifi.where()
                }
            )
        )
        ws_thread.daemon = True
        ws_thread.start()
        
        return ws

    def _on_open(self, ws, ws_name: str, pairs: List[dict]):
        """Handle WebSocket connection open"""
        print(f"{ws_name} connection established")
        self._subscribe_to_orderbook(ws, pairs)

    def _subscribe_to_orderbook(self, ws, pairs: List[dict]):
        """Subscribe to orderbook data for specified pairs"""
        try:
            if not pairs:
                print("Warning: No pairs available for subscription")
                return
                
            if len(pairs) > self.MAX_PAIRS_PER_CONNECTION:
                print(f"Warning: Number of pairs ({len(pairs)}) exceeds WebSocket limit ({self.MAX_PAIRS_PER_CONNECTION})")
                pairs = pairs[:self.MAX_PAIRS_PER_CONNECTION]
                
            subscribe_message = {
                "op": "subscribe",
                "args": [f"orderbook.1.{pair['symbol']}" for pair in pairs]
            }
            print(f"Attempting to subscribe with pairs: {pairs}")
            print(f"Sending subscription message: {subscribe_message}")
            ws.send(json.dumps(subscribe_message))
            
        except Exception as e:
            print(f"Error in subscription: {e}")

    def _on_message(self, ws, message, ws_name: str):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            print(f"Received message on {ws_name}: {data}")
            
            # Process orderbook data based on which connection received it
            processed_data = self._process_orderbook(data)
            if processed_data:
                if ws_name == "ws1":
                    self.orderbook1 = processed_data
                elif ws_name == "ws2":
                    self.orderbook2 = processed_data
                else:  # ws3
                    self.orderbook3 = processed_data
            
                # Check for arbitrage opportunities
                self._check_arbitrage_opportunities(ws_name, data)
            
        except Exception as e:
            print(f"Error processing message on {ws_name}: {e}")

    def _on_error(self, ws, error, ws_name: str):
        """Handle WebSocket errors"""
        print(f"Error in {ws_name}: {error}")

    def _on_close(self, ws, close_status_code, close_msg, ws_name: str):
        """Handle WebSocket connection close"""
        print(f"{ws_name} connection closed: {close_status_code} - {close_msg}")
        if self.running:
            print(f"Attempting to reconnect {ws_name}...")
            pairs = self.get_filtered_tickers()
            ws1_pairs, ws2_pairs, ws3_pairs = self.split_pairs(pairs)
            
            if ws_name == "ws1":
                self.ws1 = self._connect_websocket(ws_name, ws1_pairs)
            elif ws_name == "ws2":
                self.ws2 = self._connect_websocket(ws_name, ws2_pairs)
            else:  # ws3
                self.ws3 = self._connect_websocket(ws_name, ws3_pairs)

    def _process_orderbook(self, data: Dict) -> Dict:
        """Process orderbook data"""
        try:
            if 'topic' not in data:  # Skip non-orderbook messages
                return {}
                
            symbol = data['data']['s']
            orderbook = {
                'symbol': symbol,
                'timestamp': data['ts'],
                'bids': {price: qty for price, qty in data['data']['b']},
                'asks': {price: qty for price, qty in data['data']['a']},
                'update_id': data['data']['u'],
                'sequence': data['data']['seq']
            }
            
            print(f"Processed orderbook for {symbol}:")
            print(f"Top bid: {list(orderbook['bids'].items())[0] if orderbook['bids'] else 'No bids'}")
            print(f"Top ask: {list(orderbook['asks'].items())[0] if orderbook['asks'] else 'No asks'}")
            
            return orderbook
            
        except Exception as e:
            print(f"Error processing orderbook: {e}")
            return {}

    def _check_arbitrage_opportunities(self, ws_name: str, data: Dict):
        """Check for arbitrage opportunities across all orderbooks"""
        try:
            if 'topic' not in data or 'data' not in data:
                return
                
            symbol = data['data']['s']
            
            best_bid = float(data['data']['b'][0][0]) if data['data']['b'] else None
            best_ask = float(data['data']['a'][0][0]) if data['data']['a'] else None
            
            if best_bid and best_ask:
                spread = ((best_ask - best_bid) / best_bid) * 100
                print(f"Spread for {symbol}: {spread:.4f}%")
                
                if spread > 0.5:  # 0.5% spread threshold
                    print(f"Potential arbitrage opportunity found for {symbol}")
                    print(f"Bid: {best_bid}, Ask: {best_ask}, Spread: {spread:.4f}%")
                    
        except Exception as e:
            print(f"Error checking arbitrage: {e}")

    def stop(self):
        """Stop all WebSocket connections"""
        self.running = False
        if self.ws1:
            self.ws1.close()
        if self.ws2:
            self.ws2.close()
        if self.ws3:
            self.ws3.close()

    def get_filtered_tickers(self) -> List[dict]:
        """Get filtered list of tickers"""
        # Return some test data for now
        return [
            {'symbol': 'BTCUSDT'},
            {'symbol': 'ETHUSDT'},
            {'symbol': 'BNBUSDT'},
            {'symbol': 'XRPUSDT'},
            {'symbol': 'SOLUSDT'},
            {'symbol': 'DOGEUSDT'}
        ]

if __name__ == "__main__":
    try:
        print("Starting WebSocket connections...")
        manager = TripleSocketManager()
        manager.start()
        
        # Keep the main thread running
        import time
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down WebSocket connections...")
        manager.stop()
        print("Shutdown complete")