from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv


def connect_to_bybit():
    load_dotenv()
    try:
        # Replace these with your API credentials
        api_key = os.getenv("TEST_API_KEY")
        api_secret = os.getenv("TEST_API_SECRET")

        # Initialize the client (testnet for safety)
        session = HTTP(
            testnet=True,  # Set to False for live trading
            api_key=api_key,
            api_secret=api_secret
        )

        # Test connection by getting wallet balance
        wallet_balance = session.get_wallet_balance(
            accountType="UNIFIED",
            coin="USDT"
        )
        print("Successfully connected to Bybit!")
        return session

    except Exception as e:
        print(f"Error connecting to Bybit: {e}")
        return None


if __name__ == "__main__":
    client = connect_to_bybit()