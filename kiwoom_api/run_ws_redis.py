import os
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

import redis.asyncio as redis
from kiwoom_restapi import KiwoomRESTAPI
from kiwoom_ws import KiwoomWebSocket

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ws_redis_runner")

# In-memory storage to aggregate 1m and 5m klines from realtime ticker (0B)
# Structure: { symbol: { interval: list_of_candle_arrays } }
kline_data = {}



async def save_to_redis(r: redis.Redis, key: str, data: dict):
    try:
        await r.set(key, json.dumps(data))
    except Exception as e:
        logger.error(f"Error saving to Redis: {e}")

def update_kline(r: redis.Redis, symbol: str, price: float, volume: int, timestamp: datetime, intervals: list):
    """
    Update kline data and schedule saving to redis
    """
    if symbol not in kline_data:
        kline_data[symbol] = {}
        
    for interval in intervals:
        if interval not in kline_data[symbol]:
            kline_data[symbol][interval] = []
            
        if interval == '1m':
            candle_time = timestamp.replace(second=0, microsecond=0)
        elif interval == '5m':
            candle_time = timestamp.replace(minute=(timestamp.minute // 5) * 5, second=0, microsecond=0)
        else:
            continue
            
        c_ts_ms = int(candle_time.timestamp() * 1000)
        candles = kline_data[symbol][interval]
        
        if not candles or candles[-1][0] != c_ts_ms:
            # new candle
            candles.append([c_ts_ms, price, price, price, price, volume, c_ts_ms, volume])
            if len(candles) > 200:
                candles.pop(0)
        else:
            # update last candle
            last = candles[-1]
            last[2] = max(last[2], price) # high
            last[3] = min(last[3], price) # low
            last[4] = price # close
            last[5] += volume # volume
            last[7] += volume # volume duplicate

        # Asynchronously save to redis
        asyncio.create_task(save_to_redis(
            r, 
            f"kline:{interval}:{symbol}", 
            {
                "ts": int(datetime.now().timestamp() * 1000),
                "candle": candles
            }
        ))

async def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Load env
    env_path = os.path.join(current_dir, ".env")
    load_dotenv(env_path)
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("SECRET_KEY")
    
    if not api_key or not secret_key:
        logger.error("API_KEY or SECRET_KEY not found in .env file.")
        return

    # Load config
    config_path = os.path.join(current_dir, "config.json")
    if not os.path.exists(config_path):
        logger.error("config.json not found.")
        return
        
    with open(config_path, "r") as f:
        config = json.load(f)

    # Initialize Redis
    redis_conf = config.get("redis", {})
    r = redis.Redis(
        host=redis_conf.get("host", "localhost"),
        port=redis_conf.get("port", 6379),
        db=redis_conf.get("db", 10),
        decode_responses=True
    )
    
    # Authentication
    use_mock = True
    client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=use_mock)
    
    try:
        logger.info("Attempting to get access token (Mock)...")
        token = client.get_access_token()
    except Exception as e:
        logger.warning("Mock token failed, trying production...")
        use_mock = False
        client = KiwoomRESTAPI(appkey=api_key, secretkey=secret_key, use_mock=use_mock)
        try:
            token = client.get_access_token()
        except Exception as e2:
            logger.error(f"Failed to get production token: {e2}")
            return

    ws_client = KiwoomWebSocket(token=token, use_mock=use_mock)
    
    subs = config.get("subscriptions", {})
    ticker_symbols = subs.get("ticker", [])
    orderbook_symbols = subs.get("orderbook", [])
    kline_conf = subs.get("kline", {})
    kline_symbols = kline_conf.get("symbols", [])
    kline_intervals = kline_conf.get("intervals", ["1m", "5m"])

    def on_realtime_price(data):
        # type 0B -> ticker
        try:
            code = data.get("item")
            if not code:
                return
            
            values = data.get("values", {})
            
            price = abs(float(values.get("10", 0)))
            volume = abs(int(values.get("15", 0)))
            ask_pr = abs(float(values.get("27", 0)))
            bid_pr = abs(float(values.get("28", 0)))
            base_vol = abs(float(values.get("13", 0)))
            quote_vol = abs(float(values.get("14", 0)))
            
            ts_ms = int(datetime.now().timestamp() * 1000)
            
            formatted_ticker = values.copy()
            formatted_ticker.update({
                "askPr": ask_pr,
                "askSz": 0,
                "baseVolume": base_vol,
                "bestAsk": ask_pr,
                "bestBid": bid_pr,
                "bidPr": bid_pr,
                "bidSz": 0,
                "high": abs(float(values.get("17", 0))),
                "last": price,
                "lastPr": price,
                "low": abs(float(values.get("18", 0))),
                "open": abs(float(values.get("16", 0))),
                "quoteVolume": quote_vol,
                "symbol": f"{code}-KRW",
                "ts": ts_ms,
                "ts-sv": ts_ms,
                "krwVolume": quote_vol,
                "volume": quote_vol
            })
            
            # Save ticker to redis
            asyncio.create_task(save_to_redis(r, f"ticker:{code}", formatted_ticker))
            
            # Aggregate kline if applicable
            if code in kline_symbols and price > 0:
                now = datetime.now()
                update_kline(r, code, price, volume, now, kline_intervals)
        except Exception as e:
            logger.error(f"Ticker processing error: {e}")

    def on_orderbook(data):
        # type 0D -> orderbook
        try:
            code = data.get("item")
            if not code:
                return
                
            values = data.get("values", {})
            
            bids = []
            asks = []
            
            for i in range(1, 11):
                ask_p = abs(float(values.get(str(40 + i), 0)))
                ask_q = abs(int(values.get(str(60 + i), 0)))
                if ask_p > 0:
                    asks.append([ask_p, ask_q])
                    
                bid_p = abs(float(values.get(str(50 + i), 0)))
                bid_q = abs(int(values.get(str(70 + i), 0)))
                if bid_p > 0:
                    bids.append([bid_p, bid_q])
                    
            formatted_ob = values.copy()
            formatted_ob.update({
                "symbol": f"{code}-KRW",
                "bids": bids,
                "asks": asks,
                "time": values.get("21", ""),
                "total_ask_volume": abs(int(values.get("121", 0))),
                "total_bid_volume": abs(int(values.get("125", 0)))
            })
            
            asyncio.create_task(save_to_redis(r, f"orderbook:{code}", formatted_ob))
        except Exception as e:
            logger.error(f"Orderbook processing error: {e}")

    ws_client.register_on_realtime_price(on_realtime_price)
    ws_client.register_on_orderbook(on_orderbook)

    # Fetch and populate historical klines
    for symbol in kline_symbols:
        for interval in kline_intervals:
            try:
                tic_scope = interval.replace("m", "")
                history = client.get_minute_chart(stk_cd=symbol, tic_scope=tic_scope)
                if history:
                    history = history[:200]
                    history.reverse() # chronological order (oldest first)
                    
                    if symbol not in kline_data:
                        kline_data[symbol] = {}
                    kline_data[symbol][interval] = []
                    
                    for candle in history:
                        cntr_tm_str = candle.get("cntr_tm")
                        if not cntr_tm_str:
                            continue
                            
                        try:
                            c_dt = datetime.strptime(cntr_tm_str, "%Y%m%d%H%M%S")
                            c_ts_ms = int(c_dt.timestamp() * 1000)
                        except:
                            continue
                            
                        open_p = abs(float(candle.get("open_pric", 0)))
                        high_p = abs(float(candle.get("high_pric", 0)))
                        low_p = abs(float(candle.get("low_pric", 0)))
                        close_p = abs(float(candle.get("cur_prc", 0)))
                        vol = abs(int(candle.get("trde_qty", 0)))
                        
                        kline_data[symbol][interval].append([
                            c_ts_ms, open_p, high_p, low_p, close_p, vol, c_ts_ms, vol
                        ])
                        
                    key = f"kline:{interval}:{symbol}"
                    await save_to_redis(r, key, {
                        "ts": int(datetime.now().timestamp() * 1000),
                        "candle": kline_data[symbol][interval]
                    })
                    logger.info(f"Pre-populated {len(history)} historical candles for {symbol} ({interval})")
            except Exception as e:
                logger.error(f"Failed to fetch historical kline for {symbol} ({interval}): {e}")

    try:
        await ws_client.connect()
        
        # Subscribe based on config
        all_price_symbols = list(set(ticker_symbols + kline_symbols))
        if all_price_symbols:
            logger.info(f"Subscribing to realtime price for {all_price_symbols}")
            await ws_client.subscribe_realtime_price(all_price_symbols)
            
        if orderbook_symbols:
            logger.info(f"Subscribing to orderbook for {orderbook_symbols}")
            await ws_client.subscribe_orderbook(orderbook_symbols)
            
        logger.info("Listening for messages... Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("Runner cancelled.")
    except Exception as e:
        logger.error(f"Runner error: {e}")
    finally:
        await ws_client.disconnect()
        await r.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script stopped by user.")
