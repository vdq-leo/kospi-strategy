import asyncio
import numpy as np
import time
from datetime import datetime
from core.strategy_base import KospiStrategyBase
from core.indicators import calculate_annual_volatility

class KRUSDKRWTrend0002(KospiStrategyBase):
    def __init__(self, strategy_name: str, symbol: str, redis_config: dict, params: dict, kiwoom_client=None, paper_trade=False):
        super().__init__(strategy_name, symbol, redis_config, params, kiwoom_client, paper_trade)
        self.signal_window = self.params.get("signal_window", 20)
        self.use_vol_target = self.params.get("use_vol_target", True)
        self.vol_window = self.params.get("vol_window", 30)
        self.target_vol = self.params.get("target_vol", 0.1)
        self.clip_pos = self.params.get("clip_pos", 2.0)
        
        self.prices = []

    async def run(self):
        self.logger.info(f"Starting {self.strategy_name} strategy on {self.symbol}")
        
        # Load initial history (mocking with a small interval pull)
        history = await self.get_kline_history("1d", self.vol_window + 5)
        self.prices = [h["close"] for h in history] if history else []

        while not self.stop_flag:
            try:
                # In real life, we would wait for a new daily tick or check time
                ticker = await self.get_latest_ticker()
                if not ticker:
                    await asyncio.sleep(1)
                    continue

                current_price = float(ticker.get("cur_prc", 0) or ticker.get("price", 0))
                if current_price <= 0:
                    await asyncio.sleep(1)
                    continue
                    
                # Update prices list
                if len(self.prices) == 0 or self.prices[-1] != current_price:
                    self.prices.append(current_price)
                    if len(self.prices) > self.vol_window * 2:
                        self.prices.pop(0)

                # Need enough data
                if len(self.prices) < self.signal_window:
                    await asyncio.sleep(10)
                    continue

                prices_arr = np.array(self.prices, dtype=float)
                ma = np.mean(prices_arr[-self.signal_window:])
                
                position = 0.0
                if current_price < ma:
                    position = 1.0
                elif current_price > ma:
                    position = -1.0

                if self.use_vol_target and position != 0:
                    vol = calculate_annual_volatility(prices_arr, self.vol_window)
                    if vol and vol > 0:
                        leverage = self.target_vol / vol
                        leverage = np.clip(leverage, 0.0, 2.0)
                        position *= leverage

                position = np.clip(position, -self.clip_pos, self.clip_pos)
                
                if abs(position - self.net_position) > 0.1:
                    side = "BUY" if position > self.net_position else "SELL"
                    qty = abs(position - self.net_position)
                    await self.make_order(side, qty, "MARKET")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                
            await asyncio.sleep(10) # Loop interval
