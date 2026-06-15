import os
import json
from dotenv import load_dotenv
from kiwoom_restapi import KiwoomRESTAPI

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")
load_dotenv(env_path)

api_key = os.getenv("API_KEY")
secret_key = os.getenv("SECRET_KEY")

client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=False)

client.get_access_token()

url = f"{client.base_url}/api/dostk/chart"
headers = client._get_headers(api_id="ka10080")
payload = {
    "stk_cd": "005930",
    "tic_scope": "1",
    "upd_stkpc_tp": "1"
}

import requests
res = requests.post(url, headers=headers, json=payload)
print(res.status_code)
print(json.dumps(res.json(), indent=2, ensure_ascii=False))
