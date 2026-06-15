# Kiwoom REST API — KOSPI200 Futures Investigation Notes

> **Date**: 2026-06-09  
> **Account**: `6660406010` (온라인지점10)  
> **API Library**: [kiwoom-rest-api](https://github.com/bamjun/kiwoom-rest-api)  
> **API Docs**: `/var/www/kiwoom_api/키움_REST_API_translated.pdf`

---

## ✅ Account Status

| Field | Value |
|-------|-------|
| Account Number | `6660406010` |
| Account Name | 김산 |
| Branch | 온라인지점10 (Online Branch 10) |
| Account Type | **현물 (Cash Equity)** only |
| Cash Balance | 10,000,000 KRW |
| Available for Order | 10,000,000 KRW |
| Stock Positions | None (empty) |
| Futures Margin Fields | ❌ Not present |

> **Conclusion**: This is a **stock/ETF account only**. No futures sub-account is attached.

---

## ❌ KOSPI200 Futures via Kiwoom REST API — Not Supported

### What We Tried

| Attempt | Endpoint | api-id | Result |
|---------|----------|--------|--------|
| Stock order with futures code | `/api/dostk/ordr` | `kt10001` | `[1902] 종목 정보가 없습니다` |
| Futures endpoint (guessed) | `/api/dofut/ordr` | `kt10010`/`kt10011` | `500 Internal Server Error` |
| Multiple futures contract codes | `10100000`, `101X6000`, `10166000` | — | All rejected |

### Root Cause

The Kiwoom REST API **only covers domestic stocks** (`dostk`). The full API document (531 pages, 208 endpoints) contains **zero futures/derivatives ordering endpoints**.

All endpoints use the `/api/dostk/...` path:

| Path | Purpose |
|------|---------|
| `/api/dostk/ordr` | Stock orders (`kt10000` buy / `kt10001` sell) |
| `/api/dostk/acnt` | Account inquiry |
| `/api/dostk/chart` | Charts |
| `/api/dostk/stkinfo` | Stock information |
| `/api/dostk/websocket` | Real-time WebSocket |

There is **no `/api/dofut/ordr`** or equivalent in the official documentation.

---

## 📋 KOSPI200 Futures Contract Code Format

Even though the REST API does not support it, the correct format for future reference:

```
Format:  1  +  01  +  [year last digit]  +  [month]  +  000
Example: 1  +  01  +  6 (2026)           +  6 (Jun)  +  000
Result:  10166000
```

| Code | Contract |
|------|----------|
| `10166000` | KOSPI200 Jun-2026 |
| `10169000` | KOSPI200 Sep-2026 |
| `101612000` | KOSPI200 Dec-2026 |

---

## ✅ What DOES Work Right Now

### Stock / ETF Orders via REST API

Using `kt10000` (buy) / `kt10001` (sell) on `/api/dostk/ordr`:

```python
# manual_trade.py — edit TRADE_PARAMS at the top
TRADE_PARAMS = {
    "action": "sell",       # "buy" or "sell"
    "symbol": "069500",     # KODEX 200 ETF
    "qty": 1,
    "price": "",            # "" = market order
    "exchange": "KRX",
}
```

```bash
cd /var/www/kospi-strategy
python manual_trade.py
```

### Proxy ETFs for Short KOSPI200 Exposure

| ETF | Code | Exposure |
|-----|------|----------|
| KODEX 200 (Long) | `069500` | +1× KOSPI200 |
| KODEX Inverse | `114800` | −1× KOSPI200 |
| KODEX Double Inverse | `252670` | −2× KOSPI200 |

---

## 🔮 To Trade Actual KOSPI200 Futures

### Option 1 — Kiwoom OpenAPI+ (OCX)
- **Requires**: Windows machine, 32-bit Python, HTS (영웅문) installed
- **Order function**: `SendOrderFO(sRQName, sScreenNo, sAccNo, sCode, lOrdKind, sSlbyTp, sOrdTp, lQty, sPrice, sOrgOrdNo)`
- **slby_tp**: `1` = sell, `2` = buy
- **ord_tp**: `1` = limit, `3` = market

### Option 2 — Open a Futures Account
1. Open a 선물계좌 (futures account) with Kiwoom via HTS or branch
2. Deposit margin (증거금)
3. Use OpenAPI+ (Windows) to place orders via `SendOrderFO()`

### Option 3 — Use KIS (Korea Investment Securities) API
- KIS REST API natively supports KOSPI200 futures
- Requires a KIS brokerage account

---

## 📁 Related Files

| File | Description |
|------|-------------|
| [`manual_trade.py`](./manual_trade.py) | Manual order placement script |
| [`kiwoom-rest-api/`](./kiwoom-rest-api/) | Python client library (stocks only) |
| [`../kiwoom_api/.env`](../kiwoom_api/.env) | API credentials |
| [`../kiwoom_api/kiwoom_restapi.py`](../kiwoom_api/kiwoom_restapi.py) | Original REST client |
| [`../kiwoom_api/키움_REST_API_translated.pdf`](../kiwoom_api/키움_REST_API_translated.pdf) | Official API docs (translated) |
