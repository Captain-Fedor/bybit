import json
import websocket
from typing import Dict, List
import ssl
import threading
import time
from datetime import datetime
from pprint import pprint
import os
from collections import deque
import threading


class SymbolWebSocket:
    def __init__(self, symbols: List[str], socket_id: int, orderbooks: Dict, update_queue: deque):
        self.ws_url = "wss://stream.bybit.com/v5/public/spot"
        self.symbols = symbols
        self.socket_id = socket_id
        self.orderbooks = orderbooks
        self.update_queue = update_queue
        self.ws = None
        self.running = False
        self.lock = threading.Lock()

    def _get_subscribe_message(self) -> Dict:
        return {
            "op": "subscribe",
            "args": [f"orderbook.50.{symbol}" for symbol in self.symbols]
        }

    def _update_orderbook(self, symbol: str, bids: List, asks: List):
        with self.lock:
            if symbol not in self.orderbooks:
                self.orderbooks[symbol] = {
                    'bids': [],
                    'asks': [],
                    'socket_id': self.socket_id,
                    'timestamp': datetime.now().isoformat()
                }

            # Convert existing bids/asks to dictionary for efficient updates
            current_bids = {float(price): float(qty) for price, qty in self.orderbooks[symbol]['bids']}
            current_asks = {float(price): float(qty) for price, qty in self.orderbooks[symbol]['asks']}

            # Update bids
            for price, qty in bids:
                price, qty = float(price), float(qty)
                if qty > 0:
                    current_bids[price] = qty
                else:
                    current_bids.pop(price, None)

            # Update asks
            for price, qty in asks:
                price, qty = float(price), float(qty)
                if qty > 0:
                    current_asks[price] = qty
                else:
                    current_asks.pop(price, None)

            # Convert back to sorted lists
            self.orderbooks[symbol]['bids'] = [
                [price, qty]
                for price, qty in sorted(current_bids.items(), reverse=True)
            ]
            self.orderbooks[symbol]['asks'] = [
                [price, qty]
                for price, qty in sorted(current_asks.items())
            ]

            # Update timestamp
            self.orderbooks[symbol]['timestamp'] = datetime.now().isoformat()

            # Signal update
            self.update_queue.append(symbol)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'topic' in data and 'orderbook' in data['topic']:
                book_data = data.get('data', {})
                symbol = book_data.get('s', '')
                bids = book_data.get('b', [])
                asks = book_data.get('a', [])

                if data.get('type') == 'snapshot':
                    with self.lock:
                        self.orderbooks[symbol] = {
                            'bids': [[float(price), float(qty)] for price, qty in bids if float(qty) > 0],
                            'asks': [[float(price), float(qty)] for price, qty in asks if float(qty) > 0],
                            'socket_id': self.socket_id,
                            'timestamp': datetime.now().isoformat()
                        }
                    self.update_queue.append(symbol)
                elif data.get('type') == 'delta':
                    self._update_orderbook(symbol, bids, asks)

        except Exception as e:
            print(f"Error in Socket {self.socket_id}: {e}")

    def _on_error(self, ws, error):
        print(f"WebSocket error in Socket {self.socket_id} at {datetime.now().isoformat()}: {error}")
        print(f"Affected symbols: {self.symbols}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket closed for Socket {self.socket_id} at {datetime.now().isoformat()}")
        print(f"Close status code: {close_status_code}")
        print(f"Close message: {close_msg}")
        print(f"Affected symbols: {self.symbols}")
        if self.running:
            print(f"Attempting to reconnect Socket {self.socket_id}...")
            time.sleep(5)
            self._ws_thread()

    def _on_open(self, ws):
        print(
            f"{datetime.now().strftime('%H:%M:%S.%f')} WebSocket {self.socket_id} connected with {len(self.symbols)} pairs")
        ws.send(json.dumps(self._get_subscribe_message()))

    def _ws_thread(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_message,
            on_open=self._on_open,
            on_error=self._on_error,
            on_close=self._on_close
        )

        self.ws.run_forever(
            sslopt={"cert_reqs": ssl.CERT_NONE},
            ping_interval=20,
            ping_timeout=10
        )

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._ws_thread)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()


class MultiSocketClient:
    def __init__(self, symbols: List[str], trading_amounts: Dict[str, float] = None, default_amount: float = 10000,
                 max_pairs_per_socket: int = 150):
        self.all_symbols = symbols
        self.max_pairs_per_socket = max_pairs_per_socket
        self.orderbooks = {}
        self.sockets = []
        self.update_queue = deque(maxlen=1000)  # Store updates
        self.socket_symbols = self._distribute_symbols()
        self.trading_amounts = trading_amounts or {}
        self.default_amount = default_amount
        self.lock = threading.Lock()

        # Start JSON writer thread
        self.json_writer_running = True
        self.json_writer_thread = threading.Thread(target=self._json_writer_task)
        self.json_writer_thread.daemon = True
        self.json_writer_thread.start()

    def _check_liquidity(self, symbol: str, book: Dict) -> bool:
        """Check if orderbook has sufficient liquidity for the trading amount"""
        amount = self.trading_amounts.get(symbol, self.default_amount)

        if not book.get('bids') or not book.get('asks'):
            return False

        # Get average price for conversion
        best_bid = book['bids'][0][0] if book['bids'] else 0
        best_ask = book['asks'][0][0] if book['asks'] else float('inf')
        avg_price = (best_bid + best_ask) / 2 if best_bid and best_ask != float('inf') else best_bid

        # Convert USDT amount to base currency quantity
        base_quantity = amount / avg_price if avg_price > 0 else 0

        # Calculate cumulative liquidity
        bid_liquidity = sum(qty for _, qty in book['bids'])
        ask_liquidity = sum(qty for _, qty in book['asks'])

        # Return True if both sides have sufficient liquidity
        return bid_liquidity >= base_quantity and ask_liquidity >= base_quantity

    def _json_writer_task(self):
        """Continuously write updates to JSON file"""
        # Create the directory if it doesn't exist
        os.makedirs('test_triple_socket', exist_ok=True)
        
        while self.json_writer_running:
            if len(self.update_queue) > 0:
                with self.lock:
                    # Filter orderbooks with sufficient liquidity
                    valid_orderbooks = {}
                    for symbol, book in self.orderbooks.items():

                            # Calculate totals in USDT
                            total_bids_value_usdt = sum(price * qty for price, qty in book.get('bids', []))
                            total_asks_value_usdt = sum(price * qty for price, qty in book.get('asks', []))

                            # Calculate totals in base currency (sum of quantities)
                            total_bids_volume = sum(qty for _, qty in book.get('bids', []))
                            total_asks_volume = sum(qty for _, qty in book.get('asks', []))

                            # Get base currency from symbol (remove USDT/USDC suffix)
                            base_currency = symbol.replace('USDT', '').replace('USDC', '')

                            # Add the book data along with the totals
                            valid_orderbooks[symbol] = {
                                **book,  # Include all existing book data
                                'total_bids_value_usdt': round(total_bids_value_usdt, 2),
                                'total_asks_value_usdt': round(total_asks_value_usdt, 2),
                                f'total_bids_volume_{base_currency}': round(total_bids_volume, 8),
                                f'total_asks_volume_{base_currency}': round(total_asks_volume, 8)
                            }

                # Get total number of pairs from load_trading_pairs
                expected_pairs = set(load_trading_pairs())  # All trading pairs
                actual_pairs = len(valid_orderbooks)
                monitored_pairs = set(valid_orderbooks.keys())  # Pairs being monitored
                unmonitored_pairs = list(expected_pairs - monitored_pairs)  # Pairs not being monitored

                result = {
                    'timestamp': datetime.now().isoformat(),
                    'trading_amount_usdt': self.default_amount,
                    'total_pairs': actual_pairs,
                    'pairs not monitored by test_triple_socket': unmonitored_pairs,
                    'number of pairs uploaded initially': len(load_trading_pairs()),
                    'socket_distribution': {
                        f'socket_{i + 1}': len(symbols)
                        for i, symbols in enumerate(self.socket_symbols)
                    },
                    'orderbooks': valid_orderbooks
                }

                try:
                    with open('test_triple_socket/result.json', 'w') as f:
                        json.dump(result, f, indent=2)
                except Exception as e:
                    print(f"Error saving to JSON: {e}")

                # Clear processed updates
                self.update_queue.clear()

            time.sleep(0.1)  # Small delay to prevent CPU overuse

    def _distribute_symbols(self) -> List[List[str]]:
        """Distribute symbols evenly across 3 sockets"""
        socket_symbols = []
        total_symbols = len(self.all_symbols)

        if total_symbols > self.max_pairs_per_socket * 3:
            print(f"Warning: Total pairs ({total_symbols}) exceeds maximum capacity ({self.max_pairs_per_socket * 3})")
            self.all_symbols = self.all_symbols[:self.max_pairs_per_socket * 3]
            total_symbols = len(self.all_symbols)

        base_size = total_symbols // 3
        remainder = total_symbols % 3

        start = 0
        for i in range(3):
            size = base_size + (1 if i < remainder else 0)
            end = start + size
            socket_symbols.append(self.all_symbols[start:end])
            start = end

        return socket_symbols

    def start(self):
        for socket_id, symbols in enumerate(self.socket_symbols):
            if symbols:
                socket = SymbolWebSocket(symbols, socket_id + 1, self.orderbooks, self.update_queue)
                self.sockets.append(socket)
                socket.start()

    def stop(self):
        self.json_writer_running = False
        for socket in self.sockets:
            socket.stop()

    def get_orderbooks(self) -> Dict:
        with self.lock:
            return self.orderbooks.copy()

    def print_orderbooks(self):
        orderbooks = self.get_orderbooks()
        print("\nActive Pairs:", len(orderbooks))
        print("Socket Distribution:")
        for i, symbols in enumerate(self.socket_symbols):
            print(f"Socket {i + 1}: {len(symbols)} pairs")

        print("\nOrderbooks for each socket (first 10 pairs):")
        # Group orderbooks by socket_id
        socket_books = {1: [], 2: [], 3: []}
        for symbol, book in orderbooks.items():
            socket_id = book.get('socket_id')
            if socket_id:
                socket_books[socket_id].append((symbol, book))

        # Print first 10 orderbooks from each socket
        for socket_id in [1, 2, 3]:
            books = socket_books[socket_id]
            print(f"\nSocket {socket_id} orderbooks:")
            for symbol, book in books[:10]:  # Only show first 10 pairs
                print(f"\n{symbol}:")
                if 'bids' in book and 'asks' in book:
                    print("Top 3 Bids:", book['bids'][:3])
                    print("Top 3 Asks:", book['asks'][:3])
                    print("Last Update:", book.get('timestamp', 'N/A'))


def load_trading_pairs() -> List[str]:
    return [

    "ENJUSDT",
    "ETCUSDT",
    "ETHBTC",
    "ETHUSDT",
    "BTCUSDC",
    "XRPBTC"

    

  ]




if __name__ == "__main__":
    websocket.enableTrace(False)

    # WebSocket parameters
    SLEEP_TIME = 1  # seconds between orderbook updates
    TRADING_AMOUNT_USDT = 10  # $100k USDT base trading amount

    trading_pairs = load_trading_pairs()
    client = MultiSocketClient(
        symbols=trading_pairs,
        default_amount=TRADING_AMOUNT_USDT
    )

    try:
        client.start()
        print("Starting WebSocket connections...")
        print(f"Monitoring liquidity for {len(trading_pairs)} pairs...")
        print(f"Liquidity check amount: ${TRADING_AMOUNT_USDT:,} USDT equivalent for each pair")
        print(f"Update interval: {SLEEP_TIME} seconds")

        while True:
            client.print_orderbooks()
            time.sleep(SLEEP_TIME)  # Use the defined sleep parameter
            print("\033[2J\033[H")  # Clear screen

    except KeyboardInterrupt:
        print("\nShutting down...")
        client.stop()