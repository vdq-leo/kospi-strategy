import asyncio
import json
import logging
import os
import time
from typing import Dict, Any, Optional

import redis.asyncio as redis


class KospiStrategyBase:
    """
    Base class for Kospi strategies using Kiwoom data via Redis.
    Matches the structural style of mm-bitget's StrategyBaseClass.
    """

    # SAFE_MODE: Force paper trading and disable real execution
    SAFE_MODE = True

    def __init__(
        self,
        strategy_name: str,
        symbol: str,
        redis_config: Dict[str, Any],
        params: Dict[str, Any],
        kiwoom_client = None,  # Pass the KiwoomRESTAPI instance
        paper_trade: bool = False
    ):
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.redis_config = redis_config
        self.params = params
        self.kiwoom_client = kiwoom_client
        
        # Enforce paper trade in safe mode
        if self.SAFE_MODE:
            self.paper_trade = True
        else:
            self.paper_trade = paper_trade

        # Setup logging
        self.logger = logging.getLogger(f"{self.strategy_name}_{self.symbol}")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            
            # Console handler
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
            
            # File handler
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{self.strategy_name}_{self.symbol}.log")
            fh = logging.FileHandler(log_file)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

        # State
        self.stop_flag = False
        self.net_position = 0.0
        self.orders_placed = []
        
        # Paper Trade Portfolio
        self.cash = 100_000_000.0 # 100m KRW starting cash
        self.avg_price = 0.0
        self.realized_pnl = 0.0
        
        # Redis
        self.r: Optional[redis.Redis] = None

    async def connect_redis(self):
        try:
            self.r = redis.Redis(
                host=self.redis_config.get("host", "localhost"),
                port=self.redis_config.get("port", 6379),
                db=self.redis_config.get("db", 10),
                decode_responses=True
            )
            self.logger.info("Connected to Redis successfully.")
        except Exception as e:
            self.logger.error(f"Redis connection failed: {e}")
            self.stop_flag = True

    async def get_latest_ticker(self) -> Optional[Dict]:
        """Fetch the latest ticker for the symbol from Redis."""
        if not self.r:
            return None
        raw = await self.r.get(f"ticker:{self.symbol}")
        if raw:
            return json.loads(raw)
        return None

    async def get_latest_kline(self, interval: str = "1m") -> Optional[Dict]:
        """Fetch the latest kline for the symbol from Redis."""
        # For simplicity, we can fetch all keys for the symbol and interval and sort them,
        # but in a fast loop it's better if kiwoom_api maintained a "latest" key.
        # Assuming we just need to get recent data or subscribe to it.
        pass

    async def get_kline_history(self, interval: str, limit: int) -> list:
        """Fetch historical klines from Redis by reading the unified list key."""
        if not self.r:
            return []
            
        key = f"kline:{interval}:{self.symbol}"
        raw = await self.r.get(key)
        if raw:
            data = json.loads(raw)
            candles = data.get("candle", [])
            return candles[-limit:] if limit > 0 else candles
        return []

    async def make_order(self, order_side: str, quantity: float, order_type: str, price: Optional[float] = None):
        """Executes an order using KiwoomRESTAPI or simulates it in Paper Trade mode."""
        is_buy = order_side.upper() == "BUY"
        trde_tp = "3" if order_type.upper() == "MARKET" else "0" # "3" is market, "0" is limit
        
        # If market order and price not passed, try to fetch the latest price for paper tracking
        if not price:
            ticker = await self.get_latest_ticker()
            if ticker:
                price = float(ticker.get("last", 0) or ticker.get("lastPr", 0) or ticker.get("cur_prc", 0) or ticker.get("price", 0))
            else:
                price = 0.0

        ord_uv = str(int(price)) if price and trde_tp == "0" else ""
        order_id = f"mock_{int(time.time()*1000)}"
        
        if self.paper_trade:
            self.logger.info(f"[PAPER TRADE] Placed: {order_side} {quantity} @ {price:.2f} ({order_type})")
            
            # Paper trade portfolio tracking
            commission_rate = 1e-05
            trade_value = quantity * price
            commission = trade_value * commission_rate
            
            if is_buy:
                self.cash -= (trade_value + commission)
                total_value = (self.net_position * self.avg_price) + trade_value
                new_position = self.net_position + quantity
                self.avg_price = total_value / new_position if new_position > 0 else 0
                self.net_position = new_position
                self.realized_pnl -= commission # Realized PNL takes an immediate hit from fees
            else:
                self.cash += (trade_value - commission)
                # Calculate realized PNL if we are closing a long
                if self.net_position > 0:
                    gross_pnl = (price - self.avg_price) * quantity
                    self.realized_pnl += (gross_pnl - commission)
                else:
                    self.realized_pnl -= commission
                    
                self.net_position -= quantity
                if self.net_position == 0:
                    self.avg_price = 0.0
                    
            equity = self.cash + (self.net_position * price)
            self.logger.info(f"[PAPER TRADE] Equity: {equity:,.0f} KRW | PNL: {self.realized_pnl:,.0f} KRW | Pos: {self.net_position}")
            self.orders_placed.append((time.time() * 1000, order_side, order_id))
            return order_id

        # If the kiwoom REST client is provided, send the real order
        if self.kiwoom_client and not self.SAFE_MODE and not self.paper_trade:
            try:
                # Run the synchronous requests.post in a background thread so we don't block the async loop
                res = await asyncio.to_thread(
                    self.kiwoom_client.place_order_explicit,
                    stk_cd=self.symbol,
                    ord_qty=int(quantity),
                    is_buy=is_buy,
                    ord_uv=ord_uv,
                    trde_tp=trde_tp
                )
                if res.get("return_code") == 0:
                    order_id = res.get("ord_no", order_id)
                    self.logger.info(f"LIVE Order Success: {order_side} {quantity} @ {price} -> {order_id}")
                else:
                    self.logger.error(f"LIVE Order Failed: {res.get('return_msg')}")
                    return None
            except Exception as e:
                self.logger.error(f"Failed to place order: {e}")
                return None
        elif self.kiwoom_client and self.SAFE_MODE:
            self.logger.info(f"[SAFE MODE ACTIVE] Blocked LIVE order execution: {order_side} {quantity} @ {price} ({order_type}) -> {order_id}")
        else:
            self.logger.info(f"MOCK Order placed: {order_side} {quantity} @ {price} ({order_type}) -> {order_id}")

        self.orders_placed.append((time.time() * 1000, order_side, order_id))
        
        # Update internal position tracking
        if is_buy:
            self.net_position += quantity
        else:
            self.net_position -= quantity
            
        return order_id

    async def run(self):
        """Main strategy execution loop. Must be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement run()")

    async def start(self):
        """Initializes and runs the strategy."""
        await self.connect_redis()
        try:
            await self.run()
        except asyncio.CancelledError:
            self.logger.info("Strategy cancelled.")
        except Exception as e:
            self.logger.error(f"Strategy error: {e}", exc_info=True)
        finally:
            if self.r:
                await self.r.close()
            self.logger.info("Strategy stopped.")
