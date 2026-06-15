import asyncio
import numpy as np
import time
from datetime import datetime
from core.strategy_base import KospiStrategyBase
from core.indicators import calculate_ema, calculate_atr, calculate_annual_volatility

class KospiIntradayBreakoutLS(KospiStrategyBase):
    def __init__(self, strategy_name: str, symbol: str, redis_config: dict, params: dict, kiwoom_client=None, paper_trade=False):
        super().__init__(strategy_name, symbol, redis_config, params, kiwoom_client, paper_trade)
        self.ema_period = self.params.get("ema_period", 30)
        self.atr_period = self.params.get("atr_period", 30)
        self.breakout_mult = self.params.get("breakout_mult", 0.5)
        self.tp_atr_mult = self.params.get("tp_atr_mult", 7.0)
        self.sl_atr_mult = self.params.get("sl_atr_mult", 2.5)
        self.leverage = self.params.get("leverage", 1.0)
        
        self.vwap_num = 0.0
        self.vwap_den = 0.0
        self.vwap = 0.0
        self.prev_time = None
        
        self.entry_price = 0.0
        self.stop_price = 0.0
        self.take_price = 0.0
        
        self.closes = []
        self.highs = []
        self.lows = []

    async def run(self):
        self.logger.info(f"Starting {self.strategy_name} strategy on {self.symbol}")
        
        # Prepopulate from history
        hist = await self.get_kline_history("1m", 100)
        if hist:
            for candle in hist:
                # new format: [ts_ms, open, high, low, close, vol, ts_ms, vol]
                self.highs.append(float(candle[2]))
                self.lows.append(float(candle[3]))
                self.closes.append(float(candle[4]))
            self.logger.info(f"Loaded {len(self.closes)} historical candles.")
        
        last_log_time = time.time()
        
        while not self.stop_flag:
            try:
                # Ticker info
                ticker = await self.get_latest_ticker()
                if not ticker:
                    await asyncio.sleep(1)
                    continue

                close = float(ticker.get("last") or ticker.get("lastPr", 0))
                high = float(ticker.get("high", close))
                low = float(ticker.get("low", close))
                vol = float(ticker.get("baseVolume", 0) or ticker.get("volume", 0))
                
                if close <= 0:
                    await asyncio.sleep(1)
                    continue
                    
                self.closes.append(close)
                self.highs.append(high)
                self.lows.append(low)
                
                # Keep recent 100 for EMA/ATR
                if len(self.closes) > 100:
                    self.closes.pop(0)
                    self.highs.pop(0)
                    self.lows.pop(0)

                closes_arr = np.array(self.closes, dtype=float)
                highs_arr = np.array(self.highs, dtype=float)
                lows_arr = np.array(self.lows, dtype=float)
                
                emas = calculate_ema(closes_arr, self.ema_period)
                atrs = calculate_atr(highs_arr, lows_arr, closes_arr, self.atr_period)
                
                ema = emas[-1] if len(emas) > 0 else 0
                atr = atrs[-1] if len(atrs) > 0 else 0

                now = datetime.now()
                # VWAP Reset
                if self.prev_time is None or now.day != self.prev_time.day:
                    self.vwap_num = 0
                    self.vwap_den = 0
                    self.prev_time = now
                    
                typical_price = (high + low + close) / 3.0
                self.vwap_num += typical_price * vol
                self.vwap_den += vol
                if self.vwap_den > 0:
                    self.vwap = self.vwap_num / self.vwap_den

                # Time checks
                time_val = now.hour * 100 + now.minute
                is_flat = abs(self.net_position) < 1e-8

                if time_val >= 1500:
                    if not is_flat:
                        side = "SELL" if self.net_position > 0 else "BUY"
                        await self.make_order(side, abs(self.net_position), "MARKET")
                    await asyncio.sleep(1)
                    continue

                if not is_flat:
                    # Check TP/SL
                    if self.net_position > 0:
                        if close <= self.stop_price or close >= self.take_price:
                            await self.make_order("SELL", abs(self.net_position), "MARKET")
                    else:
                        if close >= self.stop_price or close <= self.take_price:
                            await self.make_order("BUY", abs(self.net_position), "MARKET")
                
                else:
                    t_entry = 900
                    if time_val >= t_entry and time_val <= 1430 and atr > 0:
                        breakout_price = self.vwap + self.breakout_mult * atr
                        breakdown_price = self.vwap - self.breakout_mult * atr
                        
                        target_size = self.leverage * 0.15 # rough vol target equivalent
                        
                        if close > breakout_price and close > ema:
                            self.entry_price = close
                            self.stop_price = close - self.sl_atr_mult * atr
                            self.take_price = close + self.tp_atr_mult * atr
                            await self.make_order("BUY", target_size, "MARKET")
                        elif close < breakdown_price and close < ema:
                            self.entry_price = close
                            self.stop_price = close + self.sl_atr_mult * atr
                            self.take_price = close - self.tp_atr_mult * atr
                            await self.make_order("SELL", target_size, "MARKET")
                            
                # Heartbeat logging every 30 seconds
                if time.time() - last_log_time >= 30:
                    self.logger.info(f"Tracking session active | Close: {close:,.0f} | VWAP: {self.vwap:,.2f} | EMA: {ema:,.2f} | ATR: {atr:,.2f} | Pos: {self.net_position}")
                    last_log_time = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                
            await asyncio.sleep(1)
