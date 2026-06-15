import os
import asyncio
import logging
from dotenv import load_dotenv

from kiwoom_restapi import KiwoomRESTAPI
from kiwoom_ws import KiwoomWebSocket

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, ".env")
    
    logging.info(f"Loading environment variables from {env_path}...")
    load_dotenv(env_path)
    
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("SECRET_KEY")
    
    if not api_key or not secret_key:
        logging.error("API_KEY or SECRET_KEY not found in .env file.")
        return

    # To connect to WebSocket, we first need a valid token.
    # We will try Mock Trading server first.
    use_mock = True
    client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=use_mock)
    
    try:
        logging.info("Attempting to get access token (Mock)...")
        token = client.get_access_token()
        logging.info(f"Token acquired: {token[:15]}...")
    except Exception as e:
        logging.error(f"Failed to get mock token: {e}")
        logging.info("Attempting to get access token (Production)...")
        use_mock = False
        client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=use_mock)
        try:
            token = client.get_access_token()
            logging.info(f"Token acquired: {token[:15]}...")
        except Exception as e2:
            logging.error(f"Failed to get production token: {e2}")
            logging.error("Cannot connect to WebSocket without a valid token. Please fix your authentication settings.")
            return

    # Initialize WebSocket client
    ws_client = KiwoomWebSocket(token=token, use_mock=use_mock)

    # Define callbacks
    def on_execution(data):
        logging.info(f"[EXECUTION] {data}")

    def on_balance(data):
        logging.info(f"[BALANCE] {data}")

    def on_realtime_price(data):
        logging.info(f"[REALTIME PRICE] {data}")

    ws_client.register_on_execution(on_execution)
    ws_client.register_on_balance(on_balance)
    ws_client.register_on_realtime_price(on_realtime_price)

    try:
        # Connect to WebSocket
        await ws_client.connect()
        
        # Subscribe to feeds
        # Example KOSPI 200 ETF code: "069500" (KODEX 200)
        logging.info("Subscribing to feeds...")
        await ws_client.subscribe_realtime_price(["069500"])
        await ws_client.subscribe_order_execution()
        await ws_client.subscribe_balance_updates()
        
        logging.info("Listening for real-time messages. Press Ctrl+C to stop.")
        
        # Keep the script running to listen for messages
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logging.info("WebSocket connection cancelled.")
    except Exception as e:
        logging.error(f"WebSocket Error: {e}")
    finally:
        await ws_client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Script stopped by user.")
