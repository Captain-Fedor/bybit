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
import backoff

class BybitWalletManager:
    def __init__(self, testnet=True):
        load_dotenv()
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        
        # Initialize client with V5 API
        self.session = HTTP(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=testnet
        )
        
        if testnet:
            self.ws_url = "wss://stream-testnet.bybit.com/v5/private"
        else:
            self.ws_url = "wss://stream.bybit.com/v5/private"
            
        self.ws = None
        self.should_reconnect = True
        self.reconnect_interval = 5
        self.max_retries = 3

    def get_wallet_balance(self) -> Dict[str, Any]:
        """Get wallet balance for the Unified Trading Account"""
        try:
            response = self.session.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            return response
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            return None

    def generate_signature(self, expires: str) -> str:
        """Generate authentication signature"""
        signature = hmac.new(
            bytes(self.api_secret, "utf-8"),
            bytes(f"GET/realtime{expires}", "utf-8"),
            digestmod=hashlib.sha256
        )
        return signature.hexdigest()

    async def connect_websocket(self):
        """Establish WebSocket connection"""
        while self.should_reconnect:
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                async with websockets.connect(
                    self.ws_url,
                    ssl=ssl_context,
                    ping_interval=20,
                    ping_timeout=10
                ) as websocket:
                    self.ws = websocket
                    print("WebSocket connected successfully")
                    
                    # Authentication
                    expires = str(int((time.time() + 10) * 1000))
                    signature = self.generate_signature(expires)
                    
                    auth_message = {
                        "req_id": "auth",
                        "op": "auth",
                        "args": [self.api_key, expires, signature]
                    }
                    
                    await websocket.send(json.dumps(auth_message))
                    auth_resp = await websocket.recv()
                    print(f"Auth response: {auth_resp}")

                    # Subscribe to topics
                    subscribe_message = {
                        "req_id": "spot",
                        "op": "subscribe",
                        "args": ["order"]
                    }
                    
                    await websocket.send(json.dumps(subscribe_message))
                    sub_resp = await websocket.recv()
                    print(f"Subscribe response: {sub_resp}")

                    # Main message loop
                    while True:
                        try:
                            message = await websocket.recv()
                            await self.handle_message(json.loads(message))
                        except Exception as e:
                            print(f"Error in message loop: {e}")
                            break

            except Exception as e:
                print(f"WebSocket connection error: {e}")
                if self.should_reconnect:
                    print(f"Reconnecting in {self.reconnect_interval} seconds...")
                    await asyncio.sleep(self.reconnect_interval)

    async def handle_message(self, message: Dict):
        """Handle incoming WebSocket messages"""
        print(f"Received message: {message}")

    async def start(self):
        """Start the WebSocket connection"""
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                await self.connect_websocket()
                break
            except Exception as e:
                retry_count += 1
                print(f"Connection attempt {retry_count} failed: {e}")
                if retry_count < self.max_retries:
                    await asyncio.sleep(self.reconnect_interval)
                else:
                    print("Max retries reached. Stopping connection attempts.")
                    break

    async def stop(self):
        """Stop the WebSocket connection"""
        self.should_reconnect = False
        if self.ws:
            await self.ws.close()

async def main():
    wallet_manager = None
    try:
        wallet_manager = BybitWalletManager(testnet=True)
        print("Initializing wallet manager...")
        
        balance = wallet_manager.get_wallet_balance()
        if balance:
            print(f"Wallet balance: {balance}")
        else:
            print("Failed to get wallet balance")

        print("Starting WebSocket connection...")
        await wallet_manager.start()
        
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, shutting down...")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if wallet_manager:
            await wallet_manager.stop()
            print("Wallet manager stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Fatal error: {e}")