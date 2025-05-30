import asyncio
import json
import websockets
import time
import hmac
import hashlib
from dotenv import load_dotenv
import os
from pybit.unified_trading import HTTP
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()

class BybitWalletManager:
    def __init__(self, testnet=True):
        # Load API credentials from environment variables
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found in .env file")
            
        self.testnet = testnet
        
        # Initialize REST client
        self.client = HTTP(
            testnet=self.testnet,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
        # WebSocket URL for testnet/mainnet
        self.ws_url = "wss://stream-testnet.bybit.com/v5/public/spot" if testnet else "wss://stream.bybit.com/v5/public/spot"

    async def connect_websocket(self):
        auth_params = self._get_auth_params()
        ws_url = f"{self.ws_url}?{auth_params}"
        
        # Add SSL context to handle certificate verification
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        async with websockets.connect(ws_url, ssl=ssl_context) as websocket:
            # Subscribe to trade updates
            subscribe_message = {
                "op": "subscribe",
                "args": ["trade.BTCUSDT"]
            }
            await websocket.send(json.dumps(subscribe_message))
            
            while True:
                try:
                    message = await websocket.recv()
                    await self.handle_message(json.loads(message))
                except Exception as e:
                    print(f"WebSocket error: {e}")
                    break

    def _get_auth_params(self) -> str:
        """Generate authentication parameters for WebSocket connection"""
        timestamp = int(time.time() * 1000)
        param_str = f"api_key={self.api_key}&timestamp={timestamp}"
        signature = hmac.new(
            bytes(self.api_secret, "utf-8"),
            bytes(param_str, "utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"{param_str}&sign={signature}"

    async def handle_message(self, message: Dict[str, Any]):
        """Handle incoming WebSocket messages"""
        print(f"Received message: {message}")

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        Place a market order
        :param symbol: Trading pair (e.g., 'BTCUSDT')
        :param side: 'Buy' or 'Sell'
        :param quantity: Amount to trade
        """
        try:
            response = self.client.place_order(
                category="spot",
                symbol=symbol,
                side=side.upper(),
                orderType="MARKET",
                qty=str(quantity),
                isLeverage=0,
                orderFilter="ORDER"
            )
            print(f"Order placed: {response}")
            return response
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def buy_market(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Place market buy order"""
        return self.place_market_order(symbol, "Buy", quantity)

    def sell_market(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Place market sell order"""
        return self.place_market_order(symbol, "Sell", quantity)

    def get_wallet_balance(self) -> Dict[str, Any]:
        """Get wallet balance"""
        try:
            balance = self.client.get_wallet_balance(accountType="UNIFIED")  # Changed from SPOT to UNIFIED
            print(f"Wallet balance: {balance}")
            return balance
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            return None

    async def start(self):
        """Start the WebSocket connection"""
        while True:
            try:
                await self.connect_websocket()
            except Exception as e:
                print(f"Connection error: {e}")
                await asyncio.sleep(5)  # Wait before reconnecting

async def main():
    try:
        wallet_manager = BybitWalletManager(testnet=True)
        
        # Get wallet balance
        wallet_manager.get_wallet_balance()
        
        # Example usage
        # Place a market buy order for 0.001 BTC
        wallet_manager.buy_market("BTCUSDT", 0.001)
        
        # Place a market sell order for 0.001 BTC
        wallet_manager.sell_market("BTCUSDT", 0.001)
        
        # Start WebSocket connection
        await wallet_manager.start()
        
    except ValueError as e:
        print(f"Error: {e}")
        print("Please make sure your .env file exists and contains BYBIT_API_KEY and BYBIT_API_SECRET")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())