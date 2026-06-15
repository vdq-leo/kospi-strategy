import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import json
import asyncio

from kiwoom_restapi import KiwoomRESTAPI
from kiwoom_ws import KiwoomWebSocket

class TestKiwoomRESTAPI(unittest.TestCase):
    
    def setUp(self):
        self.api = KiwoomRESTAPI(
            appkey="test_appkey",
            secretkey="test_secretkey",
            account_no="1234567890",
            use_mock=True
        )

    @patch("requests.post")
    def test_get_access_token_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "return_code": 0,
            "return_msg": "Processed normally",
            "token": "mock_token_123",
            "expires_dt": "20260605120000"
        }
        mock_post.return_value = mock_response
        
        token = self.api.get_access_token()
        
        self.assertEqual(token, "mock_token_123")
        self.assertEqual(self.api.token, "mock_token_123")
        self.assertIsNotNone(self.api.token_expiry)
        
        # Verify request headers and payload
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["api-id"], "au10001")
        self.assertEqual(kwargs["json"]["appkey"], "test_appkey")
        self.assertEqual(kwargs["json"]["secretkey"], "test_secretkey")

    @patch("requests.post")
    def test_token_caching(self, mock_post):
        # Setup cached token
        self.api.token = "cached_token"
        self.api.token_expiry = datetime.now() + timedelta(hours=1)
        
        token = self.api.get_access_token()
        
        # Requests.post should NOT be called since token is not expired
        self.assertEqual(token, "cached_token")
        mock_post.assert_not_called()

    @patch("requests.post")
    def test_place_order_market(self, mock_post):
        self.api.token = "test_token"
        self.api.token_expiry = datetime.now() + timedelta(hours=1)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ord_no": "0000111",
            "return_code": 0,
            "return_msg": "Order placed successfully"
        }
        mock_post.return_value = mock_response
        
        # Place buy market order (trde_tp="3")
        res = self.api.place_order_explicit(
            stk_cd="225130",
            ord_qty=10,
            is_buy=True,
            trde_tp="3"
        )
        
        self.assertEqual(res["ord_no"], "0000111")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["api-id"], "kt10000") # kt10000 is buy
        self.assertEqual(kwargs["json"]["stk_cd"], "225130")
        self.assertEqual(kwargs["json"]["ord_qty"], "10")
        self.assertEqual(kwargs["json"]["ord_uv"], "") # price must be empty for market order
        self.assertEqual(kwargs["json"]["trde_tp"], "3")

    @patch("requests.post")
    def test_cancel_order(self, mock_post):
        self.api.token = "test_token"
        self.api.token_expiry = datetime.now() + timedelta(hours=1)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ord_no": "0000222",
            "return_code": 0,
            "return_msg": "Order cancelled successfully"
        }
        mock_post.return_value = mock_response
        
        res = self.api.cancel_order(
            orig_ord_no="0000111",
            stk_cd="225130",
            cncl_qty=0
        )
        
        self.assertEqual(res["ord_no"], "0000222")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["api-id"], "kt10003")
        self.assertEqual(kwargs["json"]["orig_ord_no"], "0000111")
        self.assertEqual(kwargs["json"]["cncl_qty"], "0")


class TestKiwoomWebSocket(unittest.IsolatedAsyncioTestCase):
    
    async def test_websocket_routing(self):
        ws_client = KiwoomWebSocket(token="mock_token", use_mock=True)
        
        # Register mock callbacks
        mock_execution = MagicMock()
        mock_balance = MagicMock()
        mock_price = MagicMock()
        
        ws_client.register_on_execution(mock_execution)
        ws_client.register_on_balance(mock_balance)
        ws_client.register_on_realtime_price(mock_price)
        
        # Mock connection and recv
        mock_ws_conn = AsyncMock()
        
        # We simulate receiving three different messages, then cancellation
        msg_execution = json.dumps({
            "trnm": "REAL",
            "data": [{
                "type": "00",
                "name": "orderexecution",
                "item": "A005930",
                "values": {"9201": "1234567890", "9203": "0000111", "913": "Execution"}
            }]
        })
        msg_balance = json.dumps({
            "trnm": "REAL",
            "data": [{
                "type": "04",
                "name": "balance",
                "item": "A005930",
                "values": {"9201": "1234567890", "930": "10"}
            }]
        })
        msg_price = json.dumps({
            "trnm": "REAL",
            "data": [{
                "type": "0B",
                "name": "stockexecution",
                "item": "225130",
                "values": {"10": "30000", "15": "+50"}
            }]
        })
        
        mock_ws_conn.recv.side_effect = [msg_execution, msg_balance, msg_price, asyncio.CancelledError]
        ws_client.websocket = mock_ws_conn
        ws_client._running = True
        
        # Run receive loop and catch the CancelledError
        try:
            await ws_client._receive_loop()
        except asyncio.CancelledError:
            pass
            
        # Verify callbacks were triggered with correct parsed dictionaries
        mock_execution.assert_called_once_with({
            "type": "00",
            "name": "orderexecution",
            "item": "A005930",
            "values": {"9201": "1234567890", "9203": "0000111", "913": "Execution"}
        })
        
        mock_balance.assert_called_once_with({
            "type": "04",
            "name": "balance",
            "item": "A005930",
            "values": {"9201": "1234567890", "930": "10"}
        })
        
        mock_price.assert_called_once_with({
            "type": "0B",
            "name": "stockexecution",
            "item": "225130",
            "values": {"10": "30000", "15": "+50"}
        })

if __name__ == "__main__":
    unittest.main()
