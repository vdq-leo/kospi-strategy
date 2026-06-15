import os
import logging
from dotenv import load_dotenv
from kiwoom_restapi import KiwoomRESTAPI

# Setup logging to see token request details
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run_test(api_key, secret_key, use_mock):
    server_name = "Mock Trading" if use_mock else "Production (Real) Trading"
    print(f"\n--- Testing {server_name} Server (use_mock={use_mock}) ---")
    
    client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=use_mock)
    
    token = client.get_access_token()
    print(f"OAuth Token Issued successfully: {token[:15]}...")
    
    acc_no = client.get_account_number()
    print(f"Account Number: {acc_no}")
    
    evaluation = client.get_account_evaluation()
    print("\nAccount Evaluation Summary:")
    print(f"Deposit (예수금): {evaluation.get('entr', 'N/A')} KRW")
    print(f"D+2 Deposit (D+2예수금): {evaluation.get('d2_entra', 'N/A')} KRW")
    print(f"Total Valuation (총평가금액): {evaluation.get('aset_evlt_amt', 'N/A')} KRW")
    print(f"Total Purchase (총매입금액): {evaluation.get('tot_pur_amt', 'N/A')} KRW")
    print(f"Total Profit/Loss (총평가손익): {evaluation.get('tot_evlt_pl', 'N/A')} KRW")
    print(f"Return Rate (수익률): {evaluation.get('tot_prft_rt', 'N/A')}%")
    
    holdings = evaluation.get("stk_acnt_evlt_prst", [])
    print(f"\nPositions/Holdings ({len(holdings)} items):")
    for i, h in enumerate(holdings):
        print(f"  {i+1}. Stock Code: {h.get('stk_cd')}, Name: {h.get('stk_nm')}")
        print(f"     Qty: {h.get('rmnd_qty')}, Purchase Price: {h.get('pur_pric')}, Current Price: {h.get('cur_prc')}")
        print(f"     Valuation: {h.get('evlt_amt')}, PnL: {h.get('evltv_prft')} ({h.get('pl_rt')}%)")

def main():
    # Define paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, ".env")
    
    print(f"Loading environment variables from {env_path}...")
    load_dotenv(env_path)
    
    # Read keys
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("SECRET_KEY")
    
    if not api_key or not secret_key:
        print("Error: API_KEY or SECRET_KEY not found in .env file.")
        return
        
    print(f"API Key loaded (ends with ...{api_key[-5:]})")
    
    try:
        # Try Mock first
        run_test(api_key, secret_key, use_mock=True)
    except Exception as e:
        error_msg = str(e)
        print(f"Mock server request failed: {error_msg}")
        
        # If the error is 8030 (actual/simulated key mismatch), fall back to production
        if "8030" in error_msg:
            print("\nDetected production keys. Falling back to Production server...")
            try:
                run_test(api_key, secret_key, use_mock=False)
            except Exception as prod_err:
                print(f"Production server request failed: {prod_err}")
        else:
            print("\nRetrying with Production server...")
            try:
                run_test(api_key, secret_key, use_mock=False)
            except Exception as prod_err:
                print(f"Production server request failed: {prod_err}")

if __name__ == "__main__":
    main()
