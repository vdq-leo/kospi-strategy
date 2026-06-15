import sys
import os
import time
from dotenv import load_dotenv

# Load credentials from kiwoom_api/.env before importing the library
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../kiwoom_api/.env"))
load_dotenv(dotenv_path=env_path)

# The kiwoom-rest-api library reads KIWOOM_API_KEY / KIWOOM_API_SECRET from env
os.environ.setdefault("KIWOOM_API_KEY", os.getenv("API_KEY", ""))
os.environ.setdefault("KIWOOM_API_SECRET", os.getenv("SECRET_KEY", ""))

# Add kiwoom-rest-api to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "kiwoom-rest-api/src")))

try:
    from kiwoom_rest_api.auth.token import TokenManager
    from kiwoom_rest_api.koreanstock.order import Order
    from kiwoom_rest_api import config as kiwoom_config
except ImportError as e:
    print(f"Error: Could not import kiwoom_rest_api: {e}")
    sys.exit(1)

def main():
    symbol = "069500" # KODEX 200 ETF
    qty = 1
    exchange = "KRX"
    trde_tp = "3" # Market order

    # Use live API
    base_url = kiwoom_config.DEFAULT_BASE_URL
    print(f"Using API: {base_url}")

    # Initialise token manager and order client
    token_manager = TokenManager()
    order_client = Order(base_url=base_url, token_manager=token_manager)

    print(f"--- 1. Placing BUY order: {symbol} (KODEX 200) x {qty} @ Market ---")
    
    try:
        buy_res = order_client.stock_buy_order_request_kt10000(
            dmst_stex_tp=exchange,
            stk_cd=symbol,
            ord_qty=str(qty),
            trde_tp=trde_tp,
            ord_uv="",
        )
        
        if buy_res.get("return_code") == 0:
            print(f"✅ BUY Successful! Order No: {buy_res.get('ord_no', 'N/A')}")
            print(f"Response: {buy_res}")
            
            # Wait a brief moment to ensure execution (market orders are usually instant)
            print("Waiting 2 seconds before selling...")
            time.sleep(2)
            
            print(f"--- 2. Placing SELL order: {symbol} x {qty} @ Market ---")
            sell_res = order_client.stock_sell_order_request_kt10001(
                dmst_stex_tp=exchange,
                stk_cd=symbol,
                ord_qty=str(qty),
                trde_tp=trde_tp,
                ord_uv="",
            )
            if sell_res.get("return_code") == 0:
                print(f"✅ SELL Successful! Order No: {sell_res.get('ord_no', 'N/A')}")
                print(f"Response: {sell_res}")
            else:
                print(f"❌ SELL Failed: {sell_res.get('return_msg', 'Unknown Error')}")
                print(f"Response: {sell_res}")
                print("WARNING: You may have an open position!")
        else:
            print(f"❌ BUY Failed: {buy_res.get('return_msg', 'Unknown Error')}")
            print(f"Full Response: {buy_res}")

    except Exception as e:
        print(f"Exception while placing order: {e}")

if __name__ == "__main__":
    main()
