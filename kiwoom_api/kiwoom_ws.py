import json
import logging
import asyncio
import websockets
from typing import Callable, List, Optional, Dict, Any

logger = logging.getLogger("kiwoom_ws")

class KiwoomWebSocket:
    """
    Kiwoom OpenAPI WebSocket Client wrapper based on kiwoom_REST_API specification.
    Connects to wss://api.kiwoom.com:10000/api/dostk/websocket and handles real-time
    feed subscription for stock execution, balances, and order execution.
    """
    
    def __init__(self, token: str, use_mock: bool = False):
        self.token = token
        self.use_mock = use_mock
        
        # Select base wss URL
        self.ws_url = (
            "wss://mockapi.kiwoom.com:10000/api/dostk/websocket" if use_mock
            else "wss://api.kiwoom.com:10000/api/dostk/websocket"
        )
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._read_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        
        # User-defined callbacks
        self.on_message_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_execution_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_balance_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_realtime_price_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_orderbook_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def register_on_message(self, callback: Callable[[Dict[str, Any]], None]):
        self.on_message_callback = callback

    def register_on_execution(self, callback: Callable[[Dict[str, Any]], None]):
        self.on_execution_callback = callback

    def register_on_balance(self, callback: Callable[[Dict[str, Any]], None]):
        self.on_balance_callback = callback

    def register_on_realtime_price(self, callback: Callable[[Dict[str, Any]], None]):
        self.on_realtime_price_callback = callback

    def register_on_orderbook(self, callback: Callable[[Dict[str, Any]], None]):
        self.on_orderbook_callback = callback

    async def connect(self):
        """ Establish connection and start reading loop. """
        headers = {
            "authorization": f"Bearer {self.token}",
            "api-id": "ka00001",
            "Content-Type": "application/json;charset=UTF-8"
        }
        
        logger.info(f"Connecting to Kiwoom WebSocket at {self.ws_url}...")
        self.websocket = await websockets.connect(
            self.ws_url, 
            extra_headers=headers,
            ping_interval=None
        )
        logger.info("Kiwoom WebSocket connected successfully.")
        
        # Send initial LOGIN to perform login authentication
        login_msg = {
            "trnm": "LOGIN",
            "token": self.token
        }
        await self.websocket.send(json.dumps(login_msg))
        logger.info("Sent initial LOGIN for authentication.")
        
        # Wait a moment for authentication to be processed
        await asyncio.sleep(0.5)
        
        self._running = True
        self._read_task = asyncio.create_task(self._receive_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def _ping_loop(self):
        """ Send an application-level ping every 5 seconds. """
        while self._running:
            await asyncio.sleep(5)
            if self.websocket and not self.websocket.closed:
                try:
                    await self.websocket.send(json.dumps({"trnm": "PING"}))
                except Exception as e:
                    logger.debug(f"Ping failed: {e}")

    async def disconnect(self):
        """ Stop tasks and close WebSocket. """
        self._running = False
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
                
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
                
        if self.websocket:
            await self.websocket.close()
            logger.info("Kiwoom WebSocket disconnected.")

    async def _receive_loop(self):
        """ Internal loop to read and route incoming WebSocket messages. """
        while self._running:
            try:
                message = await self.websocket.recv()
                logger.debug(f"[RAW WS MSG] {message}")
                data = json.loads(message)
                
                # Raw callback trigger
                if self.on_message_callback:
                    try:
                        self.on_message_callback(data)
                    except Exception as e:
                        logger.error(f"Error in raw message callback: {e}")
                        
                # Route specific real-time records
                if data.get("trnm") == "REAL" and "data" in data:
                    for item_data in data["data"]:
                        msg_type = item_data.get("type")
                        
                        if msg_type == "00" and self.on_execution_callback:
                            try:
                                self.on_execution_callback(item_data)
                            except Exception as e:
                                logger.error(f"Error in on_execution callback: {e}")
                                
                        elif msg_type == "04" and self.on_balance_callback:
                            try:
                                self.on_balance_callback(item_data)
                            except Exception as e:
                                logger.error(f"Error in on_balance callback: {e}")
                                
                        elif msg_type == "0B" and self.on_realtime_price_callback:
                            try:
                                self.on_realtime_price_callback(item_data)
                            except Exception as e:
                                logger.error(f"Error in on_realtime_price callback: {e}")
                                
                        elif msg_type == "0D" and self.on_orderbook_callback:
                            try:
                                self.on_orderbook_callback(item_data)
                            except Exception as e:
                                logger.error(f"Error in on_orderbook callback: {e}")
                                
            except websockets.ConnectionClosed as e:
                logger.warning(f"Kiwoom WebSocket connection closed by remote peer: code={e.code}, reason={e.reason}")
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                await asyncio.sleep(1)

    async def _send_registration(self, type_str: str, items: List[str]):
        """ Helper to send subscription frame. """
        if not self.websocket:
            raise Exception("WebSocket is not connected.")
            
        payload = {
            "trnm": "REG",
            "grp_no": "1",
            "refresh": "1",
            "data": [
                {
                    "item": items,
                    "type": [type_str]
                }
            ]
        }
        
        logger.info(f"Subscribing to feed type '{type_str}' for items: {items}")
        await self.websocket.send(json.dumps(payload))

    async def subscribe_order_execution(self):
        """
        Subscribes to real-time order execution and order status events.
        Type ID: 00
        """
        await self._send_registration(type_str="00", items=[""])

    async def subscribe_balance_updates(self):
        """
        Subscribes to real-time balance and position changes.
        Type ID: 04
        """
        await self._send_registration(type_str="04", items=[""])

    async def subscribe_realtime_price(self, stock_codes: List[str]):
        """
        Subscribes to real-time stock/ETF transaction data.
        Type ID: 0B
        :param stock_codes: List of 6-digit stock codes (e.g. ["225130", "252620"])
        """
        await self._send_registration(type_str="0B", items=stock_codes)

    async def subscribe_orderbook(self, stock_codes: List[str]):
        """
        Subscribes to real-time stock asking price remaining quantity (orderbook).
        Type ID: 0D
        :param stock_codes: List of 6-digit stock codes (e.g. ["225130", "252620"])
        """
        await self._send_registration(type_str="0D", items=stock_codes)
