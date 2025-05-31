import json
import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv
from walllet_connect import WalletManager, TriangleWalletExecutor

async def monitor_and_execute_trades():
    last_modified = None
    wallet_manager = None
    
    try:
        # Load environment variables
        load_dotenv()
        TRADING_AMOUNT_USDT = float(os.getenv('TRADING_AMOUNT_USDT', 1000))
        
        # Initialize wallet manager
        wallet_manager = WalletManager()
        triangle_executor = TriangleWalletExecutor(wallet_manager, str(TRADING_AMOUNT_USDT))
        
        while True:
            try:
                # Check if arbitrage_res_all.json exists and get its modification time
                if os.path.exists('arbitrage_res_all.json'):
                    current_modified = os.path.getmtime('arbitrage_res_all.json')
                    
                    # If file was modified or checking for the first time
                    if last_modified is None or current_modified > last_modified:
                        with open('arbitrage_res_all.json', 'r') as f:
                            arbitrage_data = json.load(f)
                            
                        if arbitrage_data and len(arbitrage_data) > 0:
                            # Get the first triangle
                            first_triangle = arbitrage_data[0]
                            trading_pairs = first_triangle.get('trading_pairs', [])
                            
                            if trading_pairs:
                                print(f"\nExecuting triangle trade at {datetime.now()}")
                                print(f"Trading pairs: {trading_pairs}")
                                
                                # Execute the triangle trade
                                result = await triangle_executor.execute_triangle_trade(trading_pairs)
                                print("\nTrade Result:")
                                print(json.dumps(result, indent=2))
                        
                        last_modified = current_modified
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"Error during execution: {e}")
                await asyncio.sleep(5)  # Wait longer if there's an error
                
    except Exception as e:
        print(f"Critical error: {e}")
    finally:
        if wallet_manager:
            wallet_manager.close()

if __name__ == "__main__":
    load_dotenv()
    
    # Get configuration from environment variables
    SLEEP_TIME = float(os.getenv('SLEEP_TIME', 1))
    TRADING_AMOUNT_USDT = float(os.getenv('TRADING_AMOUNT_USDT', 1000))
    MIN_PROFIT = float(os.getenv('MIN_PROFIT', 0.5))
    MAX_PROFIT = float(os.getenv('MAX_PROFIT', 1000))
    
    # Run the monitoring and trading loop
    asyncio.run(monitor_and_execute_trades())