from pybit.unified_trading import WebSocket
import asyncio
import json
import os
from dotenv import load_dotenv


async def handle_message(message):
    """Handle incoming WebSocket messages"""
    print(f"Received message: {json.dumps(message, indent=2)}")


async def connect_bybit_websocket():
    load_dotenv()
    try:
        # Your testnet API credentials
        api_key = os.getenv("TEST_API_KEY")
        api_secret = os.getenv("TEST_API_SECRET")

        # Initialize WebSocket client with testnet
        ws = WebSocket(
            testnet=True,
            api_key=api_key,
            api_secret=api_secret,
            channel_type="linear"
        )

        # Subscribe to BTC-USDT orderbook
        ws.orderbook_stream(
            symbol="BTCUSDT",
            depth=1,
            callback=handle_message
        )

        # Subscribe to BTC-USDT trades
        ws.trade_stream(
            symbol="BTCUSDT",
            callback=handle_message
        )

        print("WebSocket connected! Listening for messages...")

        # Keep the connection alive
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"Error in WebSocket connection: {e}")
    finally:
        # Cleanup
        if 'ws' in locals():
            ws.exit()


async def main():
    print("Starting Bybit WebSocket connection...")
    await connect_bybit_websocket()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")