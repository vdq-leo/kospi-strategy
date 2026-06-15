import asyncio
import argparse
import os
import sys
from dotenv import load_dotenv

# Add the kiwoom_api path so we can import the client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../kiwoom_api")))
try:
    from kiwoom_restapi import KiwoomRESTAPI
except ImportError:
    KiwoomRESTAPI = None

from core.strategy_base import KospiStrategyBase
from strategies.kr_usdkrw_trend0002 import KRUSDKRWTrend0002
from strategies.kospi_intraday_breakout_ls import KospiIntradayBreakoutLS
from strategies.kospi_swing_bb_bounce import KospiSwingBBBounce
from strategies.kospi_swing_trend import KospiSwingTrend
from strategies.kospi_swing_trend_combo import KospiSwingTrendCombo

STRATEGY_MAP = {
    "kr_usdkrw_trend0002": KRUSDKRWTrend0002,
    "kospi_intraday_breakout_ls": KospiIntradayBreakoutLS,
    "kospi_swing_bb_bounce": KospiSwingBBBounce,
    "kospi_swing_trend": KospiSwingTrend,
    "kospi_swing_trend_combo": KospiSwingTrendCombo
}

async def main():
    parser = argparse.ArgumentParser(description="Kospi Strategy Runner")
    parser.add_argument("--strategy", type=str, required=True, help="Name of the strategy to run")
    parser.add_argument("--symbol", type=str, required=True, help="Symbol to run strategy on")
    parser.add_argument("--paper", action="store_true", help="Run in paper trading mode")
    args = parser.parse_args()

    load_dotenv()
    
    redis_config = {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "db": int(os.getenv("REDIS_DB", 10))
    }
    
    strategy_class = STRATEGY_MAP.get(args.strategy)
    if not strategy_class:
        print(f"Strategy {args.strategy} not found.")
        return

    # Initialize KiwoomRESTAPI if env vars are present
    kiwoom_client = None
    if KiwoomRESTAPI and os.getenv("API_KEY") and os.getenv("SECRET_KEY"):
        kiwoom_client = KiwoomRESTAPI(
            appkey=os.getenv("API_KEY"),
            secretkey=os.getenv("SECRET_KEY"),
            use_mock=os.getenv("USE_MOCK", "True").lower() in ("true", "1")
        )
        print("Initialized KiwoomRESTAPI Client for LIVE/MOCK execution.")

    # In production, params would be loaded from a config file or DB
    params = {}
    
    strategy_instance = strategy_class(
        strategy_name=args.strategy, 
        symbol=args.symbol, 
        redis_config=redis_config, 
        params=params,
        kiwoom_client=kiwoom_client,
        paper_trade=args.paper
    )
    
    try:
        await strategy_instance.start()
    except KeyboardInterrupt:
        print("Interrupted by user, shutting down.")
        strategy_instance.stop_flag = True

if __name__ == "__main__":
    asyncio.run(main())
