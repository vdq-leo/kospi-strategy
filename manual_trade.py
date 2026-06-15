import sys
import os
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
    print("Make sure you ran: git clone https://github.com/bamjun/kiwoom-rest-api.git")
    sys.exit(1)

# ==========================================
# CONFIGURE YOUR TRADE PARAMETERS HERE
# ==========================================
TRADE_PARAMS = {
    "action": "sell",       # "buy" or "sell"
    "symbol": "10166000",   # Stock/ETF code (e.g. 069500 = KODEX200, 10166000 = KOSPI200 Jun-2026 fut)
    "qty": 1,               # Quantity to trade
    "price": "",            # Limit price (leave "" for market order)
    "exchange": "KRX",      # Exchange: "KRX", "NXT", or "SOR"
}
# ==========================================

def main():
    action  = TRADE_PARAMS.get("action", "").lower()
    symbol  = TRADE_PARAMS.get("symbol", "")
    qty     = TRADE_PARAMS.get("qty", 0)
    price   = str(TRADE_PARAMS.get("price", ""))
    exchange = TRADE_PARAMS.get("exchange", "KRX")

    if action not in ["buy", "sell"]:
        print("Error: 'action' must be 'buy' or 'sell'.")
        sys.exit(1)
    if not symbol:
        print("Error: 'symbol' is required.")
        sys.exit(1)
    if qty <= 0:
        print("Error: 'qty' must be greater than 0.")
        sys.exit(1)

    # Determine order type
    trde_tp = "3" if not price else "0"  # "3" = market, "0" = limit

    # Use live API
    base_url = kiwoom_config.DEFAULT_BASE_URL
    print(f"Using API: {base_url}")

    # Initialise token manager and order client
    token_manager = TokenManager()
    order_client = Order(base_url=base_url, token_manager=token_manager)

    print(f"Placing {action.upper()} order: {symbol} x {qty} @ {'Market' if not price else price} ({exchange})")

    try:
        if action == "buy":
            res = order_client.stock_buy_order_request_kt10000(
                dmst_stex_tp=exchange,
                stk_cd=symbol,
                ord_qty=str(qty),
                trde_tp=trde_tp,
                ord_uv=price,
            )
        else:
            res = order_client.stock_sell_order_request_kt10001(
                dmst_stex_tp=exchange,
                stk_cd=symbol,
                ord_qty=str(qty),
                trde_tp=trde_tp,
                ord_uv=price,
            )

        if res.get("return_code") == 0:
            print(f"✅ Order Successful! Order No: {res.get('ord_no', 'N/A')}")
        else:
            print(f"❌ Order Failed: {res.get('return_msg', 'Unknown Error')}")
        print(f"Full Response: {res}")

    except Exception as e:
        print(f"Exception while placing order: {e}")

if __name__ == "__main__":
    main()
