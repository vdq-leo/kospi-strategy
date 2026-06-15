import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the kiwoom_api path so we can import the client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../kiwoom_api")))
try:
    from kiwoom_restapi import KiwoomRESTAPI
except ImportError:
    KiwoomRESTAPI = None

from main import STRATEGY_MAP

async def run_all():
    load_dotenv()
    
    redis_config = {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "db": int(os.getenv("REDIS_DB", 10))
    }
    
    kiwoom_client = None
    if KiwoomRESTAPI and os.getenv("API_KEY") and os.getenv("SECRET_KEY"):
        kiwoom_client = KiwoomRESTAPI(
            appkey=os.getenv("API_KEY"),
            secretkey=os.getenv("SECRET_KEY"),
            use_mock=os.getenv("USE_MOCK", "True").lower() in ("true", "1")
        )
        print("Initialized KiwoomRESTAPI Client for LIVE/MOCK execution.")

    # The combinations we want to run
    strategies_to_run = [
        "kospi_intraday_breakout_ls",
        "kospi_swing_bb_bounce",
        "kospi_swing_trend",
        "kospi_swing_trend_combo"
    ]
    symbols_to_run = ["005930", "069500"]

    tasks = []
    instances = []

    for strategy_name in strategies_to_run:
        strategy_class = STRATEGY_MAP.get(strategy_name)
        if not strategy_class:
            print(f"Warning: Strategy {strategy_name} not found in STRATEGY_MAP.")
            continue
            
        for symbol in symbols_to_run:
            instance = strategy_class(
                strategy_name=strategy_name,
                symbol=symbol,
                redis_config=redis_config,
                params={},
                kiwoom_client=kiwoom_client,
                paper_trade=True  # Ensure paper mode is selected
            )
            instances.append(instance)
            # Create async tasks for each strategy's start() method
            tasks.append(asyncio.create_task(instance.start()))
            print(f"Queued {strategy_name} for symbol {symbol}")

    print(f"\n🚀 Successfully launched {len(tasks)} strategy instances concurrently in one process!")
    print("Logs are being safely written to the 'logs/' folder. Press Ctrl+C to stop.\n")
    
    try:
        # Run them all concurrently
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\nInterrupted by user, shutting down all strategies safely...")
        for inst in instances:
            inst.stop_flag = True

if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        print("Script fully stopped.")
