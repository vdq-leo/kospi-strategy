import os
import time
import logging
from dotenv import load_dotenv
from kiwoom_restapi import KiwoomRESTAPI

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, ".env")
    load_dotenv(env_path)
    
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("SECRET_KEY")
    
    if not api_key or not secret_key:
        print("Error: API_KEY or SECRET_KEY not found in .env")
        return

    # Use live production server
    client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=False)
    
    print("--- 1. Placing BUY order for 069500 (KODEX 200) x 1 @ Market ---")
    try:
        order_res = client.place_order_explicit(
            stk_cd="069500",
            ord_qty=1,
            is_buy=True,
            trde_tp="3" # Market order
        )
        print(f"Order Response: {order_res}")
        if order_res.get("return_code") == 0:
            print(f"✅ BUY Successful! Order No: {order_res.get('ord_no')}")
        else:
            print(f"❌ BUY Failed: {order_res.get('return_msg')}")
            return
    except Exception as e:
        print(f"Exception during buy order: {e}")
        return

    print("\nWaiting 3 seconds for order execution to process...")
    time.sleep(3)

    print("\n--- 2. Retrieving Account Balance & Holdings ---")
    try:
        evaluation = client.get_account_evaluation()
        print("\nAccount Evaluation Summary:")
        print(f"Deposit (D+0 예수금): {evaluation.get('entr', 'N/A')} KRW")
        print(f"D+2 Deposit (D+2 예수금): {evaluation.get('d2_entra', 'N/A')} KRW")
        print(f"Total Valuation (총평가금액): {evaluation.get('aset_evlt_amt', 'N/A')} KRW")
        print(f"Total Purchase (총매입금액): {evaluation.get('tot_pur_amt', 'N/A')} KRW")
        print(f"Total Profit/Loss (총평가손익): {evaluation.get('tot_evlt_pl', 'N/A')} KRW")
        
        holdings = evaluation.get("stk_acnt_evlt_prst", [])
        print(f"\nPositions/Holdings ({len(holdings)} items):")
        for i, h in enumerate(holdings):
            print(f"  {i+1}. Stock Code: {h.get('stk_cd')}, Name: {h.get('stk_nm')}")
            print(f"     Qty: {h.get('rmnd_qty')}, Purchase Price: {h.get('pur_pric')}, Current Price: {h.get('cur_prc')}")
            print(f"     Valuation: {h.get('evlt_amt')}, PnL: {h.get('evltv_prft')} ({h.get('pl_rt')}%)")
    except Exception as e:
        print(f"Exception during balance retrieval: {e}")

if __name__ == "__main__":
    main()
