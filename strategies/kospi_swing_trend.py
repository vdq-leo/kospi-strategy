import asyncio
import time
import numpy as np
from core.strategy_base import KospiStrategyBase
from core.indicators import calculate_ema, calculate_annual_volatility

class KospiSwingTrend(KospiStrategyBase):
    def __init__(self, strategy_name: str, symbol: str, redis_config: dict, params: dict, kiwoom_client=None, paper_trade=False):
        super().__init__(strategy_name, symbol, redis_config, params, kiwoom_client, paper_trade)
        self.ema_trend_period = self.params.get("ema_trend_period", 200)
        self.macd_fast = self.params.get("macd_fast", 12)
        self.macd_slow = self.params.get("macd_slow", 26)
        self.macd_signal = self.params.get("macd_signal", 9)
        self.tp_atr_mult = self.params.get("tp_atr_mult", 3.0)
        self.sl_atr_mult = self.params.get("sl_atr_mult", 3.0)
        self.leverage = self.params.get("leverage", 1.0)
        
        self.closes = []
        self.entry_price = 0.0
        self.stop_price = 0.0
        self.take_price = 0.0

    async def run(self):
        self.logger.info(f"Starting {self.strategy_name} strategy on {self.symbol}")
        
        # Prepopulate from history to prevent false indicators
        hist = await self.get_kline_history("1m", 250)
        if hist:
            for candle in hist:
                self.closes.append(float(candle[4]))
            self.logger.info(f"Loaded {len(self.closes)} historical candles.")
            
        last_log_time = time.time()
        
        while not self.stop_flag:
            try:
                # Need to use 5m bars for logic and 1m bars for exit checking.
                # Simplified here to just show architecture template.
                ticker = await self.get_latest_ticker()
                if not ticker:
                    await asyncio.sleep(1)
                    continue

                close = float(ticker.get("last") or ticker.get("lastPr", 0) or ticker.get("cur_prc", 0) or ticker.get("price", 0))
                if close <= 0:
                    await asyncio.sleep(1)
                    continue
                    
                # Store and calculate MACD / EMA
                self.closes.append(close)
                if len(self.closes) > 500:
                    self.closes.pop(0)

                closes_arr = np.array(self.closes, dtype=float)
                ema_trend = calculate_ema(closes_arr, self.ema_trend_period)
                ema_fast = calculate_ema(closes_arr, self.macd_fast)
                ema_slow = calculate_ema(closes_arr, self.macd_slow)
                
                if len(ema_fast) == 0 or len(ema_slow) == 0:
                    await asyncio.sleep(1)
                    continue

                macd_line = ema_fast - ema_slow
                macd_sig = calculate_ema(macd_line, self.macd_signal)
                
                curr_macd = macd_line[-1]
                curr_sig = macd_sig[-1] if len(macd_sig) > 0 else 0
                curr_ema_trend = ema_trend[-1] if len(ema_trend) > 0 else 0
                
                is_flat = abs(self.net_position) < 1e-8
                
                if is_flat:
                    if close > curr_ema_trend and curr_macd > curr_sig:
                        self.entry_price = close
                        self.stop_price = close * 0.98 # Simplification
                        self.take_price = close * 1.05 # Simplification
                        
                        target_size = self.leverage * 0.15 
                        await self.make_order("BUY", target_size, "MARKET")
                else:
                    if curr_macd < curr_sig or close < curr_ema_trend or close <= self.stop_price or close >= self.take_price:
                        await self.make_order("SELL", abs(self.net_position), "MARKET")

                # Heartbeat logging every 30 seconds
                if time.time() - last_log_time >= 30:
                    self.logger.info(f"Tracking session active | Close: {close:,.0f} | MACD: {curr_macd:,.2f} | Sig: {curr_sig:,.2f} | EMA Trend: {curr_ema_trend:,.2f} | Pos: {self.net_position}")
                    last_log_time = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                
            await asyncio.sleep(1) # Delay between ticks
