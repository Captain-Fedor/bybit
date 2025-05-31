import os
from dotenv import load_dotenv
import asyncio
from pybit.unified_trading import HTTP
import json
import traceback
from typing import Dict  # Add this import

# Load environment variables from .env file
load_dotenv()

class WalletManager:
    def __init__(self):
        # Get API credentials from environment variables
        api_key = os.getenv('BYBIT_API_KEY')
        api_secret = os.getenv('BYBIT_API_SECRET')
        testnet = os.getenv('TESTNET', 'True').lower() == 'true'
        
        if not api_key or not api_secret:
            raise ValueError("API key and secret must be set in .env file")
        
        # Initialize session
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )

class WalletExecutor:
    def __init__(self, wallet_manager: WalletManager, initial_trading_amount: str):
        self.wallet_manager = wallet_manager
        self.initial_amount = initial_trading_amount
        self.current_order = None

    def _format_quantity(self, quantity: float, symbol: str) -> str:
        """Format the quantity according to the symbol's precision."""
        try:
            # Get symbol info
            symbol_info = self.wallet_manager.session.get_instruments_info(
                category="spot",
                symbol=symbol
            )
            
            # Get lot size filter
            lot_size_filter = symbol_info['result']['list'][0]['lotSizeFilter']
            min_qty = float(lot_size_filter['minOrderQty'])
            qty_step = float(lot_size_filter.get('qtyStep', min_qty))
            
            # Round down to the nearest step
            formatted_qty = float(int(quantity / qty_step) * qty_step)
            
            # Ensure quantity is not less than minimum
            if formatted_qty < min_qty:
                formatted_qty = min_qty
                
            # Convert to string with appropriate precision
            decimals = str(qty_step)[::-1].find('.')
            if decimals > 0:
                return f"{formatted_qty:.{decimals}f}"
            return str(int(formatted_qty))
            
        except Exception as e:
            print(f"Error formatting quantity: {e}")
            # If formatting fails, return the original quantity as string
            return str(quantity)

    async def _execute_trade(self, symbol: str, side: str, quantity: str) -> Dict:
        try:
            # Format quantity according to symbol's precision
            formatted_quantity = self._format_quantity(float(quantity), symbol)
            
            print(f"Placing {side} market order for {symbol}, quantity: {formatted_quantity}")
            order_response = self.wallet_manager.session.place_order(
                category="spot",
                symbol=symbol,
                side=side,
                orderType="MARKET",
                qty=formatted_quantity,
                accountType="UNIFIED"
            )

            print(f"Order response: {json.dumps(order_response, indent=2)}")

            if order_response['retCode'] == 0:
                order_id = order_response['result']['orderId']
                self.current_order = {
                    'orderId': order_id,
                    'symbol': symbol,
                    'status': 'PENDING'
                }
                return {
                    'orderId': order_id,
                    'symbol': symbol,
                    'side': side,
                    'quantity': formatted_quantity,
                    'raw_response': order_response
                }
            else:
                raise Exception(f"Order placement failed: {order_response['retMsg']}")

        except Exception as e:
            print(f"Error placing order for {symbol}: {e}")
            print(f"Full error details: {str(e)}")
            raise

async def main():
    try:
        # Initialize WalletManager
        wallet_manager = WalletManager()
        
        # Check initial balance
        print("\nChecking initial balance...")
        initial_balance = wallet_manager.session.get_wallet_balance(
            accountType="UNIFIED"
        )
        if initial_balance['retCode'] == 0:
            print("\nWallet Balance:")
            for coin in initial_balance['result']['list'][0]['coin']:
                print(f"{coin['coin']}: {coin['equity']}")

        # Initialize WalletExecutor
        executor = WalletExecutor(wallet_manager, "10")
        
        # Execute trade
        print("\nExecuting trade...")
        result = await executor._execute_trade("ADAUSDT", "Buy", "10")
        
        print("\nTrade Result:")
        print(json.dumps(result, indent=2))
        
        # Check final balance
        print("\nChecking final balance...")
        final_balance = wallet_manager.session.get_wallet_balance(
            accountType="UNIFIED"
        )
        if final_balance['retCode'] == 0:
            print("\nFinal Wallet Balance:")
            for coin in final_balance['result']['list'][0]['coin']:
                print(f"{coin['coin']}: {coin['equity']}")

    except Exception as e:
        print(f"Error during execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())