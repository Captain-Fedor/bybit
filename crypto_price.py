from pybit.unified_trading import WebSocket
import time
from datetime import datetime

def handle_websocket_message(message):
    try:
        # Check if message is properly formatted
        if isinstance(message, dict) and 'data' in message:
            data = message['data']
            if isinstance(data, list) and len(data) > 0:
                price = float(data[0]['lastPrice'])
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] BTC/USDT: ${price:,.2f}", end='\r')
    except Exception as e:
        print(f"\nError processing message: {str(e)}")

def main():
    print("Connecting to Bybit WebSocket...")
    
    ws = WebSocket(
        testnet=False,
        channel_type="linear"  # Changed from "spot" to "linear"
    )

    # Subscribe to BTCUSDT ticker
    ws.ticker_stream(
        symbol="BTCUSDT",
        callback=handle_websocket_message
    )

    print("Starting BTC price stream (Press Ctrl+C to stop)...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nClosing WebSocket connection...")
        ws.exit()

if __name__ == "__main__":
    main()