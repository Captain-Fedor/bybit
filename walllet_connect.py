import json
import time
import asyncio
from typing import List, Dict
from decimal import Decimal
from pybit.unified_trading import HTTP
from pybit.unified_trading import WebSocket
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


class WalletManager:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        self.session = HTTP(
            testnet=self.testnet,
            api_key=self.api_key,
            api_secret=self.api_secret
        )

    def get_wallet_balance(self):
        """Get current unified account wallet balance in a simplified format"""
        try:
            balance = self.session.get_wallet_balance(accountType="UNIFIED")

            # Format the balance in a cleaner way
            if balance['retCode'] == 0:
                coins = balance['result']['list'][0]['coin']
                print("\nWallet Balance:")
                formatted_balance = {}
                for coin in coins:
                    if Decimal(str(coin['equity'])) > 0:  # Only show coins with balance
                        formatted_balance[coin['coin']] = coin['equity']
                        print(f"{coin['coin']}: {coin['equity']}")
                return balance
            else:
                print(f"Error: {balance['retMsg']}")
                return None
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            return None

    def close(self):
        pass


class TriangleWalletExecutor:
    def __init__(self, wallet_manager: WalletManager, initial_trading_amount: str):
        self.wallet_manager = wallet_manager
        self.initial_amount = initial_trading_amount
        self.current_orders = {}
        self.trade_confirmations = {}
        self.executed_amounts = {}

    def _verify_sufficient_balance(self, balance, first_pair: str) -> bool:
        """Verify if there's sufficient balance for the first trade"""
        try:
            quote_currency = first_pair[3:]  # Extract the quote currency (e.g., USDT from ADAUSDT)
            required_amount = Decimal(self.initial_amount)

            # Get the coin list from the unified account response
            coin_list = balance['result']['list'][0]['coin']

            for coin in coin_list:
                if coin['coin'] == quote_currency:
                    available = Decimal(str(coin['equity']))  # Use 'equity' instead of 'availableToWithdraw'
                    print(f"Available {quote_currency} balance: {available}")
                    print(f"Required amount: {required_amount}")
                    return available >= required_amount

            print(f"Could not find {quote_currency} in wallet")
            return False
        except Exception as e:
            print(f"Error verifying balance: {e}")
            print(f"Balance response: {json.dumps(balance, indent=2)}")
            return False

    async def _execute_trade(self, symbol: str, side: str, quantity: str) -> Dict:
        try:
            print(f"Placing {side} order for {symbol}, quantity: {quantity}")
            order_response = self.wallet_manager.session.place_order(
                category="spot",
                symbol=symbol,
                side=side,
                orderType="MARKET",
                qty=str(quantity),
                accountType="UNIFIED"
            )

            print(f"Order response: {json.dumps(order_response, indent=2)}")  # Debug line

            if order_response['retCode'] == 0:  # Check if the order was successful
                order_id = order_response['result']['orderId']
                self.current_orders[order_id] = {
                    'symbol': symbol,
                    'status': 'PENDING'
                }
                return {
                    'orderId': order_id,
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'raw_response': order_response
                }
            else:
                raise Exception(f"Order placement failed: {order_response['retMsg']}")

        except Exception as e:
            print(f"Error placing order for {symbol}: {e}")
            print(f"Full error details: {str(e)}")  # Add more error details
            raise

    async def _wait_for_confirmation(self, order_id: str, timeout: int = 30) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                order_status = self.wallet_manager.session.get_order_history(
                    category="spot",
                    symbol=self.current_orders[order_id]['symbol'],
                    orderId=order_id,
                    limit=1,
                    accountType="UNIFIED"
                )

                print(f"Order status response: {json.dumps(order_status, indent=2)}")

                if order_status['retCode'] == 0:
                    if not order_status['result']['list']:
                        print(f"No order found for ID {order_id}, retrying...")
                        await asyncio.sleep(1)
                        continue

                    order_details = order_status['result']['list'][0]
                    status = order_details['orderStatus']

                    if status == 'Filled':
                        self.trade_confirmations[order_id] = order_details
                        print(f"Order {order_id} filled.")
                        print(f"Executed quantity: {order_details.get('cumExecQty', 'N/A')}")
                        print(f"Executed price: {order_details.get('avgPrice', 'N/A')}")
                        return True

                    elif status in ['Rejected', 'Cancelled']:
                        print(f"Order {order_id} failed with status: {status}")
                        return False

                    print(f"Current order status: {status}")
                else:
                    print(f"Error in order status response: {order_status['retMsg']}")

                await asyncio.sleep(1)

            except Exception as e:
                print(f"Error checking order status: {e}")
                print(f"Full error details: {str(e)}")
                return False

        print(f"Timeout waiting for order {order_id} confirmation")
        return False

    async def execute_triangle_trade(self, trading_pairs: List[str]):
        """
        Execute triangle trades in sequence using unified account
        """
        if len(trading_pairs) != 3:
            raise ValueError("Must provide exactly 3 trading pairs")

        # Check wallet balance before trading
        balance = self.wallet_manager.get_wallet_balance()
        if not self._verify_sufficient_balance(balance, trading_pairs[0]):
            raise ValueError(f"Insufficient balance for initial trade of {self.initial_amount}")

        try:
            # Execute trades as before...
            # First trade
            print(f"\nExecuting first trade for {trading_pairs[0]}")
            first_order = await self._execute_trade(
                symbol=trading_pairs[0],
                side="BUY",
                quantity=self.initial_amount
            )

            if not await self._wait_for_confirmation(first_order['orderId']):
                raise Exception(f"First trade {trading_pairs[0]} failed to confirm")

            first_filled_qty = self.trade_confirmations[first_order['orderId']]['execQty']
            self.executed_amounts[trading_pairs[0]] = first_filled_qty
            print(f"First trade completed. Received: {first_filled_qty}")

            # Second trade
            print(f"\nExecuting second trade for {trading_pairs[1]}")
            second_order = await self._execute_trade(
                symbol=trading_pairs[1],
                side="SELL",
                quantity=first_filled_qty
            )

            if not await self._wait_for_confirmation(second_order['orderId']):
                raise Exception(f"Second trade {trading_pairs[1]} failed to confirm")

            second_filled_qty = self.trade_confirmations[second_order['orderId']]['execQty']
            self.executed_amounts[trading_pairs[1]] = second_filled_qty
            print(f"Second trade completed. Received: {second_filled_qty}")

            # Third trade
            print(f"\nExecuting third trade for {trading_pairs[2]}")
            third_order = await self._execute_trade(
                symbol=trading_pairs[2],
                side="BUY",
                quantity=second_filled_qty
            )

            if not await self._wait_for_confirmation(third_order['orderId']):
                raise Exception(f"Third trade {trading_pairs[2]} failed to confirm")

            third_filled_qty = self.trade_confirmations[third_order['orderId']]['execQty']
            self.executed_amounts[trading_pairs[2]] = third_filled_qty
            print(f"Third trade completed. Received: {third_filled_qty}")

            return {
                "status": "success",
                "orders": [first_order, second_order, third_order],
                "executed_amounts": self.executed_amounts
            }

        except Exception as e:
            print(f"Error executing triangle trade: {e}")
            return {
                "status": "error",
                "message": str(e),
                "executed_amounts": self.executed_amounts
            }


import json
import time
import asyncio
from typing import List, Dict
from decimal import Decimal
from pybit.unified_trading import HTTP
from pybit.unified_trading import WebSocket
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Get trading amount from environment variable with validation
    trading_amount = os.getenv('TRADING_AMOUNT_USDT')
    if not trading_amount:
        raise ValueError("TRADING_AMOUNT_USDT not found in .env file")

    try:
        float(trading_amount)  # Validate that it's a valid number
    except ValueError:
        raise ValueError("TRADING_AMOUNT_USDT must be a valid number")

    # Get testnet setting from environment variable
    testnet_value = os.getenv('TESTNET', 'true').lower()
    testnet = testnet_value in ('true', '1', 'yes')

    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')

    if not api_key or not api_secret:
        raise ValueError("API credentials not found in .env file")

    print(f"Running in {'testnet' if testnet else 'mainnet'} mode")
    wallet_manager = WalletManager(api_key, api_secret, testnet)
    triangle_executor = TriangleWalletExecutor(wallet_manager, trading_amount)

    # Define trading pairs
    trading_pairs = ["ADAUSDC", "ADABTC", "BTCUSDC"]



    async def main():
        try:
            # Check initial balance
            print("\nChecking initial balance...")
            initial_balance = wallet_manager.get_wallet_balance()

            # Execute triangle trade
            print("\nExecuting triangle trade...")
            result = await triangle_executor.execute_triangle_trade(trading_pairs)
            print("\nTrade Result:")
            print(json.dumps(result, indent=2))

            # Check final balance
            print("\nChecking final balance...")
            final_balance = wallet_manager.get_wallet_balance()

        except Exception as e:
            print(f"\nError in main execution: {e}")
        finally:
            print("\nClosing connections...")
            wallet_manager.close()


    # Run the async main function
    asyncio.run(main())