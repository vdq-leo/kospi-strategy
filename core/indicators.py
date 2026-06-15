import numpy as np

def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Calculates the Exponential Moving Average (EMA)."""
    if len(prices) == 0:
        return np.array([])
    
    alpha = 2 / (period + 1)
    ema = np.zeros_like(prices)
    ema[0] = prices[0]
    
    for i in range(1, len(prices)):
        ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
        
    return ema

def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    """Calculates the Average True Range (ATR)."""
    if len(closes) < 2:
        return np.zeros_like(closes)
        
    tr = np.zeros_like(closes)
    tr[0] = highs[0] - lows[0]
    
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)
        
    atr = np.zeros_like(closes)
    # Simple moving average for the first ATR
    if len(closes) >= period:
        atr[period-1] = np.mean(tr[:period])
        for i in range(period, len(closes)):
            # Smoothed moving average
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
            
    return atr

def calculate_annual_volatility(prices: np.ndarray, period: int) -> float:
    """Calculates the annualized volatility of log returns."""
    if len(prices) < period + 1:
        return 0.0
    
    closes = prices[-(period + 1):]
    rets = np.diff(np.log(closes))
    return np.std(rets, ddof=1) * np.sqrt(252)

def calculate_bollinger_bands(prices: np.ndarray, period: int, num_std: float):
    """Calculates Bollinger Bands."""
    if len(prices) < period:
        return np.zeros_like(prices), np.zeros_like(prices), np.zeros_like(prices)
        
    sma = np.zeros_like(prices)
    upper = np.zeros_like(prices)
    lower = np.zeros_like(prices)
    
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1:i + 1]
        sma[i] = np.mean(window)
        std = np.std(window, ddof=0)
        upper[i] = sma[i] + num_std * std
        lower[i] = sma[i] - num_std * std
        
    return sma, upper, lower
