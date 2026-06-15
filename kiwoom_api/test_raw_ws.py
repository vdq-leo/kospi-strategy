import asyncio
import json
import os
import logging
from dotenv import load_dotenv
from kiwoom_restapi import KiwoomRESTAPI
import websockets

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

async def test():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(current_dir, ".env"))
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("SECRET_KEY")
    
    client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=False)
    token = client.get_access_token()
    
    ws_url = "wss://api.kiwoom.com:10000/api/dostk/websocket"
    headers = {
        "authorization": f"Bearer {token}",
        "api-id": "ka00001",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    logging.info(f"Connecting to {ws_url}...")
    async with websockets.connect(ws_url, extra_headers=headers, ping_interval=None) as ws:
        logging.info("Connected!")
        
        # Subscribe
        payload = {
            "trnm": "REG",
            "grp_no": "1",
            "refresh": "1",
            "data": [
                {
                    "item": ["005930"],
                    "type": ["0B"]
                }
            ]
        }
        await ws.send(json.dumps(payload))
        logging.info("Sent registration payload.")
        
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                logging.info(f"RECV: {msg}")
            except asyncio.TimeoutError:
                logging.warning("No message received for 15s. Sending PING...")
                await ws.ping()
            except websockets.ConnectionClosed as e:
                logging.warning(f"Closed: {e.code} {e.reason}")
                break

asyncio.run(test())
