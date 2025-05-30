import asyncio
import json
import websockets
import time
import hmac
import hashlib
import ssl
from dotenv import load_dotenv
import os
from pybit.unified_trading import HTTP
from typing import Dict, Any

class BybitWalletManager:
    def __init__(self, testnet=True):
        load_dotenv()
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        
        # Initialize client with V5 API
        self.client = HTTP(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=testnet
        )
        # Correct V5 WebSocket URL
        self.ws_url = "wss://stream-testnet.bybit.com/v5/public" if testnet else "wss://stream.bybit.com/v5/public"

    def get_wallet_balance(self) -> Dict[str, Any]:
        """
        Get wallet balance for the Unified Trading Account
        :return: Dictionary containing wallet balance information
        """
        try:
            balance = self.client.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"  # You can modify this or remove to get all coins
            )
            print(f"Wallet balance: {balance}")
            return balance
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            return None

    def buy_market(self, symbol: str, amount: float) -> Dict[str, Any]:
        """
        Place a market buy order
        :param symbol: Trading pair (e.g., 'BTCUSDT')
        :param amount: Amount in USDT to spend
        """
        return self.place_market_order(symbol, "BUY", amount)

    def sell_market(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """
        Place a market sell order
        :param symbol: Trading pair (e.g., 'BTCUSDT')
        :param quantity: Amount of crypto to sell
        """
        return self.place_market_order(symbol, "SELL", quantity)

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        Place a market order
        :param symbol: Trading pair (e.g., 'BTCUSDT')
        :param side: 'Buy' or 'Sell'
        :param quantity: Amount in USDT for buy orders, crypto amount for sell orders
        """
        try:
            response = self.client.place_order(
                category="spot",
                symbol=symbol,
                side=side.upper(),
                orderType="MARKET",
                qty=str(quantity),  # Use qty for both buy and sell
                isLeverage=0,
                orderFilter="Order"
            )
            print(f"Order placed: {response}")
            return response
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def generate_signature(self, expires: str) -> str:
        """Generate authentication signature"""
        signature = hmac.new(
            bytes(self.api_secret, "utf-8"),
            bytes(f"GET/realtime{expires}", "utf-8"),
            digestmod="sha256"
        )
        return signature.hexdigest()

    async def connect_websocket(self):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with websockets.connect(self.ws_url, ssl=ssl_context) as websocket:
                # Auth
                expires = str(int((time.time() + 10) * 1000))
                signature = self.generate_signature(expires)
                
                auth_message = {
                    "req_id": "auth",
                    "op": "auth",
                    "args": [
                        self.api_key,
                        expires,
                        signature
                    ]
                }
                await websocket.send(json.dumps(auth_message))
                auth_resp = await websocket.recv()
                print(f"Auth response: {auth_resp}")

                # Subscribe to topics
                subscribe_message = {
                    "req_id": "spot",
                    "op": "subscribe",
                    "args": [
                        "orderbook.1.BTCUSDT",
                        "publicTrade.BTCUSDT"
                    ]
                }
                await websocket.send(json.dumps(subscribe_message))
                
                while True:
                    try:
                        message = await websocket.recv()
                        await self.handle_message(json.loads(message))
                    except websockets.ConnectionClosed:
                        print("WebSocket connection closed, attempting to reconnect...")
                        break
                    except Exception as e:
                        print(f"WebSocket error: {e}")
                        break
        except Exception as e:
            print(f"Connection error: {e}")

    async def handle_message(self, message):
        """
        Handle incoming WebSocket messages
        """
        print(f"Received message: {message}")

    async def start(self):
        """
        Start the WebSocket connection
        """
        await self.connect_websocket()

# Main execution remains the same
async def main():
    try:
        wallet_manager = BybitWalletManager(testnet=True)
        
        # Get wallet balance
        wallet_manager.get_wallet_balance()
        
        # Example usage
        # Place a market buy order for 20 USDT worth of BTC
        wallet_manager.buy_market("BTCUSDT", 20)  # Buying for 20 USDT
        
        # Place a market sell order for 0.001 BTC
        # Only execute this if you have BTC in your account
        # wallet_manager.sell_market("BTCUSDT", 0.001)  # Selling 0.001 BTC
        
        # Start WebSocket connection
        await wallet_manager.start()
        
    except ValueError as e:
        print(f"Error: {e}")
        print("Please make sure your .env file exists and contains BYBIT_API_KEY and BYBIT_API_SECRET")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())