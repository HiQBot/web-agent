"""
Chrome Browser Streaming

Streams Chrome browser viewport using CDP Page.screencast API.
"""
import asyncio
import logging
from typing import Optional, Set, Any
from fastapi import WebSocket, WebSocketDisconnect
from cdp_use import CDPClient

logger = logging.getLogger(__name__)


class ChromeStreamingServer:
	"""WebSocket server for streaming Chrome screencast frames."""
	
	def __init__(self, cdp_client: CDPClient, streaming_port: int = 8080):
		self.cdp_client = cdp_client
		self.streaming_port = streaming_port
		self.connected_clients: Set[WebSocket] = set()
		self._screencast_enabled = False
		self._frame_handler_task: Optional[asyncio.Task] = None
	
	async def start_screencast(self) -> None:
		"""Start CDP screencast."""
		if self._screencast_enabled:
			logger.info("⚠️ Screencast already enabled, skipping")
			return

		try:
			# Enable Page domain first (required for screencast)
			logger.info("🔧 Enabling Page domain for CDP")
			await self.cdp_client.send.Page.enable()

			# Start screencast
			logger.info("🎬 Starting CDP screencast (format=jpeg, quality=80, 1920x1080)")
			await self.cdp_client.send.Page.startScreencast(
				params={
					'format': 'jpeg',
					'quality': 80,
					'maxWidth': 1920,
					'maxHeight': 1080,
				}
			)

			# Register screencast frame handler
			logger.info("📹 Registering screencast frame handler")
			self.cdp_client.register.Page.screencastFrame(self._on_screencast_frame)

			self._screencast_enabled = True
			logger.info("✅ Chrome screencast started successfully")
		except Exception as e:
			logger.error(f"❌ Failed to start screencast: {e}", exc_info=True)
			raise
	
	async def stop_screencast(self) -> None:
		"""Stop CDP screencast."""
		if not self._screencast_enabled:
			return
		
		try:
			await self.cdp_client.send.Page.stopScreencast()
			self._screencast_enabled = False
			logger.info("Chrome screencast stopped")
		except Exception as e:
			logger.error(f"Failed to stop screencast: {e}")
	
	async def _on_screencast_frame(self, event: Any) -> None:
		"""Handle screencast frame from CDP."""
		logger.debug(f"📸 Received screencast frame (sessionId: {event.get('sessionId')}, clients: {len(self.connected_clients)})")

		if not self.connected_clients:
			# No clients connected, acknowledge frame but don't process
			try:
				await self.cdp_client.send.Page.screencastFrameAck(params={'sessionId': event['sessionId']})
			except Exception:
				pass
			return
		
		try:
			# Extract frame data
			frame_data = event.get('data', '')
			metadata = {
				'sessionId': event.get('sessionId'),
				'metadata': event.get('metadata', {}),
			}
			
			# Send frame to all connected clients
			message = {
				'type': 'screencast_frame',
				'data': frame_data,
				'metadata': metadata,
			}
			
			disconnected = set()
			for client in self.connected_clients:
				try:
					await client.send_json(message)
					logger.debug(f"✅ Frame sent to client")
				except Exception as e:
					logger.warning(f"❌ Failed to send frame to client: {e}")
					disconnected.add(client)
			
			# Remove disconnected clients
			for client in disconnected:
				self.connected_clients.discard(client)
			
			# Acknowledge frame to CDP
			await self.cdp_client.send.Page.screencastFrameAck(params={'sessionId': event['sessionId']})
		except Exception as e:
			logger.error(f"Error processing screencast frame: {e}")
	
	async def add_client(self, websocket: WebSocket, already_accepted: bool = False) -> None:
		"""
		Add WebSocket client for streaming.
		
		Args:
			websocket: WebSocket connection
			already_accepted: If True, websocket is already accepted (don't accept again)
		"""
		if not already_accepted:
			await websocket.accept()
		self.connected_clients.add(websocket)
		logger.info(f"Client connected for Chrome streaming (total: {len(self.connected_clients)})")
		
		# Start screencast if not already started
		if not self._screencast_enabled:
			await self.start_screencast()
	
	async def remove_client(self, websocket: WebSocket) -> None:
		"""Remove WebSocket client."""
		self.connected_clients.discard(websocket)
		logger.info(f"Client disconnected from Chrome streaming (total: {len(self.connected_clients)})")
		
		# Stop screencast if no clients connected
		if not self.connected_clients and self._screencast_enabled:
			await self.stop_screencast()
	
	async def handle_client(self, websocket: WebSocket) -> None:
		"""Handle WebSocket client connection."""
		await self.add_client(websocket)
		
		try:
			while True:
				# Keep connection alive, handle any incoming messages
				try:
					data = await websocket.receive_json()
					# Handle ping/pong for keepalive
					if data.get("type") == "ping":
						await websocket.send_json({"type": "pong"})
					elif data.get("type") == "disconnect":
						break
				except Exception as e:
					# If JSON parsing fails, try text
					try:
						message = await websocket.receive_text()
						logger.debug(f"Received text message from client: {message}")
					except Exception:
						# Connection closed or error
						break
		except WebSocketDisconnect:
			pass
		except Exception as e:
			logger.error(f"Error handling client: {e}")
		finally:
			await self.remove_client(websocket)

