# Kospi Strategy: Paper Trading Guide

This guide explains how to safely run and manage your trading strategies in **Paper Trading / Mock Mode** to test them without any execution risk.

## 1. Prerequisites (Data Feeder)

Before starting any strategy, ensure your Kiwoom WebSocket data feeder is running in the background. The strategy relies on this process to push realtime ticks and candles into Redis.

Check that the data feeder is online:
```bash
sudo pm2 status
```
*You should see `kiwoom-ws` listed as `online`.*

If it is not running, start it using:
```bash
sudo pm2 start /var/www/kiwoom_api/run_ws_redis.py --name "kiwoom-ws" --interpreter python3
```

> [!WARNING]
> Do NOT run the `run_ws_redis.py` data feeder manually in a `screen` session at the same time it is running in PM2. Running two instances simultaneously will cause WebSocket token conflicts.

---

## 2. Running a Strategy Manually (For Testing)

To test a strategy and see its output live in your terminal, you can run `main.py` directly.

**Command syntax:**
```bash
cd /var/www/kospi-strategy
python main.py --strategy <strategy_name> --symbol <symbol_code> --paper
```

**Example (Running Breakout LS on Samsung Electronics):**
```bash
python main.py --strategy kospi_intraday_breakout_ls --symbol 005930 --paper
```

*Press `Ctrl+C` to stop the manual execution.*

---

## 3. Running a Strategy in the Background (PM2)

Once you are satisfied that the strategy is executing correctly, you should move it to a background process using PM2. This ensures it runs continuously 24/7.

**Command syntax:**
```bash
pm2 start /var/www/kospi-strategy/main.py --name "strategy_<symbol>" --interpreter python3 -- --strategy <strategy_name> --symbol <symbol> --paper
```
*(Note: The standalone `--` is required so PM2 passes the remaining arguments to `main.py` instead of consuming them itself).*

**Example:**
```bash
pm2 start /var/www/kospi-strategy/main.py --name "kospi_005930" --interpreter python3 -- --strategy kospi_intraday_breakout_ls --symbol 005930 --paper
```

---

## 4. Viewing Logs & Progress

Every time a strategy runs, it creates a dedicated log file capturing its startup, paper trades, equity updates, and PnL.

The logs are located in the `logs/` directory:
```bash
/var/www/kospi-strategy/logs/<strategy_name>_<symbol>.log
```

**To tail the logs live:**
```bash
tail -f /var/www/kospi-strategy/logs/kospi_intraday_breakout_ls_005930.log
```

---

## 5. Security & Safe Mode

> [!IMPORTANT]
> **Hardcoded Safe Mode is Active!**
> Currently, the base class `KospiStrategyBase` has `SAFE_MODE = True` hardcoded.
> This physical safeguard ensures that **even if you forget to pass `--paper`**, the strategy will default to paper mode and all `place_order_explicit` live network requests to Kiwoom are blocked.

When you are ready to transition to real money trading:
1. Open `core/strategy_base.py`.
2. Change `SAFE_MODE = False`.
3. Restart your PM2 strategy instances *without* the `--paper` flag.
