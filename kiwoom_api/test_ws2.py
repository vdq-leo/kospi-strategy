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
    
    async with websockets.connect(ws_url, extra_headers=headers, ping_interval=None) as ws:
        payload = {"trnm": "PING", "token": token}
        await ws.send(json.dumps(payload))
        logging.info("Sent PING payload with token.")
        
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            logging.info(f"RECV: {msg}")
        except asyncio.TimeoutError:
            logging.warning("Timeout.")
            
        payload2 = {
            "header": {"token": token, "tr_type": "1"},
            "body": {"input": {"tr_id": "PING", "tr_key": token}}
        }
        await ws.send(json.dumps(payload2))
        logging.info("Sent KIS-style payload.")
        
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            logging.info(f"RECV: {msg}")
        except asyncio.TimeoutError:
            logging.warning("Timeout.")

asyncio.run(test())
