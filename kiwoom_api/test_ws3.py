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
        "api-id": "ka00001",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    async with websockets.connect(ws_url, extra_headers=headers, ping_interval=None) as ws:
        payload = {"trnm": "LOGIN", "token": token}
        await ws.send(json.dumps(payload))
        logging.info("Sent LOGIN payload.")
        
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            logging.info(f"RECV: {msg}")
        except asyncio.TimeoutError:
            logging.warning("Timeout.")
            
        # Try a subscription just to see if we get the "로그인 인증..." error
        payload2 = {
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
        await ws.send(json.dumps(payload2))
        logging.info("Sent REG payload.")
        
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                logging.info(f"RECV: {msg}")
            except asyncio.TimeoutError:
                logging.warning("Timeout.")
                break

asyncio.run(test())
