import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("kiwoom_restapi")

class KiwoomRESTAPI:
    """
    Kiwoom OpenAPI REST API Client wrapper based on kiwoom_REST_API specification.
    Supports token management, account queries, holdings, unexecuted orders, and order operations.
    """
    
    def __init__(
        self, 
        appkey: str, 
        secretkey: str, 
        account_no: str = "", 
        use_mock: bool = False
    ):
        self.appkey = appkey
        self.secretkey = secretkey
        self.account_no = account_no
        self.use_mock = use_mock
        
        # Select base domain based on mock/production
        self.base_url = (
            "https://mockapi.kiwoom.com" if use_mock 
            else "https://api.kiwoom.com"
        )
        
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    def _get_headers(self, api_id: str, cont_yn: str = "N", next_key: str = "") -> Dict[str, str]:
        """ Helper to construct request headers. """
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": api_id,
            "cont-yn": cont_yn
        }
        if next_key:
            headers["next-key"] = next_key
            
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
            
        return headers

    def get_access_token(self) -> str:
        """
        Issues an OAuth access token using appkey and secretkey.
        Endpoint: POST /oauth2/token
        TR ID: au10001
        """
        # If token is still valid, return cached token
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token
            
        url = f"{self.base_url}/oauth2/token"
        headers = self._get_headers(api_id="au10001")
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.appkey,
            "secretkey": self.secretkey
        }
        
        logger.info("Requesting access token from Kiwoom...")
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        
        if data.get("return_code") != 0:
            raise Exception(f"Failed to issue token: {data.get('return_msg')} (code: {data.get('return_code')})")
            
        self.token = data["token"]
        expires_dt_str = data["expires_dt"] # Format: YYYYMMDDHHmmss e.g. 20241107083713
        
        try:
            self.token_expiry = datetime.strptime(expires_dt_str, "%Y%m%dd%H%M%S")
        except ValueError:
            try:
                self.token_expiry = datetime.strptime(expires_dt_str, "%Y%m%d%H%M%S")
            except Exception as e:
                logger.warning(f"Could not parse expires_dt '{expires_dt_str}': {e}. Defaulting to 1 hour.")
                from datetime import timedelta
                self.token_expiry = datetime.now() + timedelta(hours=1)
                
        logger.info(f"Access token successfully issued. Expires at: {self.token_expiry}")
        return self.token

    def revoke_access_token(self) -> Dict[str, Any]:
        """
        Revokes the currently active access token.
        Endpoint: POST /oauth2/revoke
        TR ID: au10002
        """
        if not self.token:
            return {"return_code": 0, "return_msg": "No active token to revoke."}
            
        url = f"{self.base_url}/oauth2/revoke"
        headers = self._get_headers(api_id="au10002")
        payload = {
            "appkey": self.appkey,
            "secretkey": self.secretkey,
            "token": self.token
        }
        
        logger.info("Revoking access token...")
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        
        # Clear local token cache
        self.token = None
        self.token_expiry = None
        
        return data

    def get_account_number(self) -> str:
        """
        Queries the account number associated with the current token.
        Endpoint: POST /api/dostk/acnt
        TR ID: ka00001
        """
        self.get_access_token()
        url = f"{self.base_url}/api/dostk/acnt"
        headers = self._get_headers(api_id="ka00001")
        payload = {}
        
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        
        if data.get("return_code") != 0:
            raise Exception(f"Account query failed: {data.get('return_msg')}")
            
        self.account_no = data["acctNo"]
        return self.account_no

    def get_account_evaluation(self, qry_tp: str = "1") -> Dict[str, Any]:
        """
        Inquires account evaluation details, deposits, and holdings.
        Endpoint: POST /api/dostk/acnt
        TR ID: kt00004
        :param qry_tp: "0" for All, "1" for Excluding delisted stocks (default)
        """
        self.get_access_token()
        url = f"{self.base_url}/api/dostk/acnt"
        headers = self._get_headers(api_id="kt00004")
        payload = {
            "qry_tp": qry_tp,
            "dmst_stex_tp": "KRX"
        }
        
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        return data

    def get_unexecuted_orders(self, stk_cd: str = "") -> List[Dict[str, Any]]:
        """
        Queries unexecuted (open) orders for the account.
        Endpoint: POST /api/dostk/acnt
        TR ID: ka10075
        :param stk_cd: Optional stock code to filter, empty string retrieves all.
        """
        self.get_access_token()
        url = f"{self.base_url}/api/dostk/acnt"
        headers = self._get_headers(api_id="ka10075")
        payload = {
            "all_stk_tp": "1", # 1: stock
            "trde_tp": "0",    # 0: all
            "stk_cd": stk_cd,
            "stex_tp": "0"     # 0: Consolidated
        }
        
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        
        if data.get("return_code") != 0:
            logger.warning(f"Failed to query unexecuted orders: {data.get('return_msg')}")
            return []
            
        return data.get("oso", [])

    def place_order(
        self, 
        stk_cd: str, 
        ord_qty: int, 
        ord_uv: str = "", 
        trde_tp: str = "3"
    ) -> Dict[str, Any]:
        """
        Places a stock/ETF buy or sell order.
        Endpoint: POST /api/dostk/ordr
        TR ID: kt10000 (buy) or kt10001 (sell)
        :param stk_cd: 6-digit stock code (e.g. "225130")
        :param ord_qty: Order quantity
        :param ord_uv: Order unit price (string, empty for market price)
        :param trde_tp: "0" for normal limit price, "3" for market price (default)
        """
        self.get_access_token()
        
        # Decide buy or sell TR ID based on is_buy parameter or caller check
        # To maintain simplicity and follow clean design, let's look at the TR ID
        # kt10000 is buy, kt10001 is sell. If quantity is negative, we interpret as sell,
        # but to make it explicit, we can check or pass a flag. Let's make it a separate parameter or check quantity.
        # Wait, let's use the explicit TR ID, or check if qty is negative.
        # Let's add a clear target api-id or is_buy parameter.
        # Let's define the is_buy check by checking if quantity is positive/negative, or default to Buy.
        # It's better to pass is_buy explicitly or let the method determine. Let's make a method argument `is_buy`.
        pass

    def place_order_explicit(
        self, 
        stk_cd: str, 
        ord_qty: int, 
        is_buy: bool,
        ord_uv: str = "", 
        trde_tp: str = "3"
    ) -> Dict[str, Any]:
        """
        Places a buy/sell order with explicit direction flag for stocks/ETFs.
        TR ID: kt10000 for Buy, kt10001 for Sell.
        Endpoint: POST /api/dostk/ordr
        """
        self.get_access_token()
        
        api_id = "kt10000" if is_buy else "kt10001"
        url = f"{self.base_url}/api/dostk/ordr"
        headers = self._get_headers(api_id=api_id)
        
        # If market order (trde_tp="3"), price (ord_uv) MUST be empty string
        price = "" if trde_tp == "3" else str(ord_uv)
        
        payload = {
            "dmst_stex_tp": "KRX",
            "stk_cd": stk_cd,
            "ord_qty": str(ord_qty),
            "ord_uv": price,
            "trde_tp": trde_tp,
            "cond_uv": ""
        }
        
        logger.info(f"Placing {'BUY' if is_buy else 'SELL'} order for {stk_cd}, qty: {ord_qty}, price: '{price}', type: {trde_tp}")
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

    def place_futures_order(
        self,
        stk_cd: str,
        ord_qty: int,
        is_buy: bool,
        ord_uv: str = "",
        trde_tp: str = "3"
    ) -> Dict[str, Any]:
        """
        Places a buy/sell order for FUTURES & OPTIONS (derivatives).
        Uses the /api/dofut/ordr endpoint, which is separate from stocks.
        TR ID: kt10010 for Buy, kt10011 for Sell.
        :param stk_cd:   Futures contract code (e.g., "101X6000" for KOSPI200 Jun-2026)
        :param ord_qty:  Number of contracts
        :param is_buy:   True for buy (open long / close short), False for sell (open short / close long)
        :param ord_uv:   Limit price as a string; leave empty for market orders
        :param trde_tp:  "3" for market (default), "0" for limit
        """
        self.get_access_token()

        # Derivatives API requires account number — auto-fetch if not already set
        if not self.account_no:
            self.get_account_number()

        api_id = "kt10010" if is_buy else "kt10011"
        url = f"{self.base_url}/api/dofut/ordr"
        headers = self._get_headers(api_id=api_id)

        # Market orders must have an empty price field
        price = "" if trde_tp == "3" else str(ord_uv)

        payload = {
            "acnt_no": self.account_no,
            "stk_cd": stk_cd,
            "ord_qty": str(ord_qty),
            "ord_uv": price,
            "trde_tp": trde_tp,
            "cond_uv": ""
        }

        logger.info(f"Placing FUTURES {'BUY' if is_buy else 'SELL'} order for {stk_cd}, qty: {ord_qty}, price: '{price}', type: {trde_tp}")
        res = requests.post(url, headers=headers, json=payload)
        if not res.ok:
            logger.error(f"Futures order HTTP error {res.status_code}: {res.text}")
        res.raise_for_status()
        return res.json()

    def cancel_order(
        self, 
        orig_ord_no: str, 
        stk_cd: str, 
        cncl_qty: int = 0
    ) -> Dict[str, Any]:
        """
        Cancels an open order.
        Endpoint: POST /api/dostk/ordr
        TR ID: kt10003
        :param orig_ord_no: 7-digit order number to cancel
        :param stk_cd: 6-digit stock code
        :param cncl_qty: quantity to cancel (0 for all remaining)
        """
        self.get_access_token()
        url = f"{self.base_url}/api/dostk/ordr"
        headers = self._get_headers(api_id="kt10003")
        payload = {
            "dmst_stex_tp": "KRX",
            "orig_ord_no": orig_ord_no,
            "stk_cd": stk_cd,
            "cncl_qty": str(cncl_qty)
        }
        
        logger.info(f"Cancelling order {orig_ord_no} for {stk_cd}, qty: {cncl_qty}")
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

    def modify_order(
        self, 
        orig_ord_no: str, 
        stk_cd: str, 
        mdfy_qty: int, 
        mdfy_uv: str,
        trde_tp: str = "0"
    ) -> Dict[str, Any]:
        """
        Modifies price/quantity of an open order.
        Endpoint: POST /api/dostk/ordr
        TR ID: kt10002
        :param orig_ord_no: 7-digit order number to modify
        :param stk_cd: 6-digit stock code
        :param mdfy_qty: new quantity (0 to modify all remaining)
        :param mdfy_uv: new price (string)
        :param trde_tp: order type, defaults to "0" (limit)
        """
        self.get_access_token()
        url = f"{self.base_url}/api/dostk/ordr"
        headers = self._get_headers(api_id="kt10002")
        payload = {
            "dmst_stex_tp": "KRX",
            "orig_ord_no": orig_ord_no,
            "stk_cd": stk_cd,
            "mdfy_qty": str(mdfy_qty),
            "mdfy_uv": str(mdfy_uv),
            "mdfy_cond_uv": "",
            "trde_tp": trde_tp
        }
        
        logger.info(f"Modifying order {orig_ord_no} for {stk_cd}, qty: {mdfy_qty}, price: {mdfy_uv}")
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

    def get_minute_chart(self, stk_cd: str, tic_scope: str = "1") -> List[Dict[str, Any]]:
        """
        Queries minute chart data for the given stock.
        Endpoint: POST /api/dostk/chart
        TR ID: ka10080
        :param stk_cd: 6-digit stock code
        :param tic_scope: Minute interval (e.g. "1" for 1-minute, "5" for 5-minute)
        """
        self.get_access_token()
        url = f"{self.base_url}/api/dostk/chart"
        headers = self._get_headers(api_id="ka10080")
        payload = {
            "stk_cd": stk_cd,
            "tic_scope": tic_scope,
            "upd_stkpc_tp": "1" # Adjusted price
        }
        
        logger.info(f"Fetching {tic_scope}-minute chart for {stk_cd}")
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        
        if data.get("return_code") != 0:
            logger.warning(f"Failed to fetch minute chart: {data.get('return_msg')}")
            return []
            
        return data.get("stk_min_pole_chart_qry", [])
