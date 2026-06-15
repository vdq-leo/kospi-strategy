import sys
import os
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

# Load credentials from kiwoom_api/.env
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../kiwoom_api/.env"))
load_dotenv(dotenv_path=env_path)

# Add kiwoom_api directory to path to import the REST client
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../kiwoom_api")))

try:
    from kiwoom_restapi import KiwoomRESTAPI
except ImportError as e:
    print(f"Error: Could not import KiwoomRESTAPI from kiwoom_api directory: {e}")
    sys.exit(1)

def main():
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("SECRET_KEY")
    
    if not api_key or not secret_key:
        print("Error: API_KEY or SECRET_KEY not found in .env")
        return

    # Initialize client (Production server)
    client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=False)
    
    print("Connecting to Kiwoom and retrieving account information...")
    try:
        # Get account number
        acc_no = client.get_account_number()
        print(f"Account Number: {acc_no}")
        
        # Get evaluation data
        evaluation = client.get_account_evaluation()
        
        print("\n==============================================")
        print("           ACCOUNT BALANCE SUMMARY            ")
        print("==============================================")
        print(f"Deposit (D+0 예수금): {int(evaluation.get('entr', 0)):,} KRW")
        print(f"D+2 Deposit (D+2 예수금): {int(evaluation.get('d2_entra', 0)):,} KRW")
        print(f"Total Valuation (총평가금액): {int(evaluation.get('aset_evlt_amt', 0)):,} KRW")
        print(f"Total Purchase (총매입금액): {int(evaluation.get('tot_pur_amt', 0)):,} KRW")
        
        # Format PnL safely
        tot_evlt_pl = evaluation.get('tot_evlt_pl')
        tot_prft_rt = evaluation.get('tot_prft_rt')
        pnl_str = f"{int(tot_evlt_pl):,} KRW" if tot_evlt_pl and tot_evlt_pl != "N/A" else "0 KRW"
        rt_str = f"{float(tot_prft_rt):.2f}%" if tot_prft_rt and tot_prft_rt != "N/A" else "0.00%"
        print(f"Total Profit/Loss (총평가손익): {pnl_str} ({rt_str})")
        print("==============================================")
        
        holdings = evaluation.get("stk_acnt_evlt_prst", [])
        print(f"\nPositions/Holdings ({len(holdings)} items):")
        if not holdings:
            print("  No open positions.")
        else:
            for i, h in enumerate(holdings):
                # Clean up values (remove leading zeros)
                qty = int(h.get('rmnd_qty', 0))
                pur_price = int(h.get('pur_pric', 0)) if h.get('pur_pric') else 0
                cur_price = int(h.get('cur_prc', 0))
                val_amt = int(h.get('evlt_amt', 0))
                pl_val = int(h.get('evltv_prft', 0)) if h.get('evltv_prft') else 0
                pl_rt = float(h.get('pl_rt', 0)) if h.get('pl_rt') else 0.0
                
                print(f"  {i+1}. Stock Code: {h.get('stk_cd')} | Name: {h.get('stk_nm')}")
                print(f"     Qty: {qty} | Purchase Price: {pur_price:,} KRW | Current Price: {cur_price:,} KRW")
                print(f"     Valuation: {val_amt:,} KRW | PnL: {pl_val:,} KRW ({pl_rt:+.2f}%)")
        print("==============================================")

    except Exception as e:
        print(f"Exception during run: {e}")

if __name__ == "__main__":
    main()
