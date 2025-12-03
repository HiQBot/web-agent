"""
Browser Stream Routes

WebSocket endpoint for proxying live browser view.
Supports both OnKernal (WebRTC) and Chrome (CDP screencast) browsers.
"""
import logging
import asyncio
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from web_agent.config import settings
from web_agent.browser.providers import get_browser_provider
from web_agent.utils.browser_manager import create_browser_session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/browser/init-persistent")
async def init_persistent_browser():
    """
    Initialize a persistent browser session for Live Preview.
    
    This endpoint is called when the user clicks "Show Browser" in Live Preview.
    It creates a browser session that can be streamed via WebSocket.
    """
    try:
        logger.info("Initializing persistent browser session for Live Preview")
        session_id, session = await create_browser_session()
        logger.info(f"✅ Browser session created: {session_id}")
        return {
            "status": "success",
            "session_id": session_id,
            "message": "Browser session initialized for Live Preview"
        }
    except Exception as e:
        logger.error(f"Failed to initialize browser session: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to initialize browser session: {str(e)}"
        }


class BrowserStreamManager:
    """Manages browser stream connections"""

    def __init__(self):
        self.active_streams: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_streams[client_id] = websocket
        logger.info(f"Browser stream client {client_id} connected. Total: {len(self.active_streams)}")

    def disconnect(self, client_id: str):
        """Remove WebSocket connection"""
        if client_id in self.active_streams:
            del self.active_streams[client_id]
            logger.info(f"Browser stream client {client_id} disconnected. Total: {len(self.active_streams)}")


stream_manager = BrowserStreamManager()


@router.websocket("/ws/browser-stream")
async def browser_stream_websocket(
    websocket: WebSocket,
    client_id: str = Query(..., description="Unique client identifier"),
    browser_url: str = Query("http://localhost:8080", description="Browser view URL")
):
    """
    WebSocket endpoint for streaming live browser view.

    Supports both OnKernal (WebRTC) and Chrome (CDP screencast) browsers.
    For OnKernal: Returns WebRTC iframe URL
    For Chrome: Streams screencast frames via WebSocket

    Usage:
        ws://localhost:8000/api/v1/ws/browser-stream?client_id=123&browser_url=http://localhost:8080
    """
    provider = get_browser_provider()
    provider_name = type(provider).__name__

    logger.info(f"🔌 WebSocket connection request from client {client_id}")
    logger.info(f"🌐 Browser provider: {provider_name}")

    await stream_manager.connect(websocket, client_id)

    try:
        # For Chrome provider, set up screencast streaming
        if provider_name == "ChromeProvider":
            logger.info("📺 Chrome provider detected - setting up screencast streaming")
            try:
                from web_agent.utils.session_registry import _SESSION_REGISTRY
                from web_agent.browser.session import BrowserSession
                from web_agent.browser.providers.chrome_streaming import ChromeStreamingServer
                import asyncio

                # Wait for browser session to be created (with timeout)
                browser_session: BrowserSession | None = None
                max_wait = 30  # Wait up to 30 seconds
                wait_interval = 0.5

                logger.info(f"⏳ Waiting for Chrome browser session (max {max_wait}s)...")
                logger.info(f"📋 Current sessions in registry: {list(_SESSION_REGISTRY.keys())}")
                for attempt in range(int(max_wait / wait_interval)):
                    for session_id, session in _SESSION_REGISTRY.items():
                        if isinstance(session, BrowserSession) and hasattr(session, '_cdp_client_root') and session._cdp_client_root:
                            browser_session = session
                            logger.info(f"Found browser session: {session_id}")
                            break
                    
                    if browser_session:
                        break
                    
                    await asyncio.sleep(wait_interval)
                
                if browser_session and browser_session._cdp_client_root:
                    logger.info("✅ Browser session found! Setting up Chrome screencast streaming")
                    logger.info(f"📡 CDP client root available: {browser_session._cdp_client_root is not None}")

                    # Send initial connection message
                    connection_msg = {
                        "type": "connected",
                        "message": "Chrome browser stream connected",
                        "provider": "chrome",
                        "browser_url": provider.get_viewer_url(),
                        "streaming_type": "screencast"
                    }
                    logger.info(f"📤 Sending connection message: {connection_msg}")
                    await websocket.send_json(connection_msg)
                    
                    # Create streaming server instance (websocket already accepted)
                    logger.info("🎬 Creating ChromeStreamingServer instance")
                    streaming_server = ChromeStreamingServer(
                        cdp_client=browser_session._cdp_client_root,
                        streaming_port=settings.streaming_port
                    )

                    # Add client (websocket already accepted by stream_manager.connect)
                    logger.info("➕ Adding client to streaming server")
                    await streaming_server.add_client(websocket, already_accepted=True)
                    logger.info("✅ Client added, screencast should be streaming now")
                    
                    # Handle client messages and keep connection alive
                    try:
                        while True:
                            try:
                                data = await websocket.receive_json()
                                if data.get("type") == "ping":
                                    await websocket.send_json({"type": "pong"})
                                elif data.get("type") == "disconnect":
                                    break
                            except WebSocketDisconnect:
                                break
                            except Exception as e:
                                logger.debug(f"Error receiving message: {e}")
                                break
                    finally:
                        await streaming_server.remove_client(websocket)
                    
                    return
                else:
                    logger.warning("Browser session not found - Chrome may not be running yet")
                    # Send message indicating browser not ready
                    await websocket.send_json({
                        "type": "connected",
                        "message": "Waiting for Chrome browser session...",
                        "provider": "chrome",
                        "browser_url": provider.get_viewer_url(),
                        "streaming_type": "screencast",
                        "status": "waiting"
                    })
                    # Keep connection alive and wait for browser session
                    while True:
                        try:
                            data = await websocket.receive_json()
                            if data.get("type") == "ping":
                                await websocket.send_json({"type": "pong"})
                            # Check again for browser session
                            for session_id, session in _SESSION_REGISTRY.items():
                                if isinstance(session, BrowserSession) and hasattr(session, '_cdp_client_root') and session._cdp_client_root:
                                    logger.info("Browser session found, restarting streaming setup")
                                    # Reconnect with streaming
                                    await websocket.send_json({
                                        "type": "reconnect",
                                        "message": "Browser session found, reconnecting..."
                                    })
                                    break
                        except WebSocketDisconnect:
                            break
                    return
            except Exception as e:
                logger.error(f"Failed to set up Chrome streaming: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"Failed to set up Chrome streaming: {str(e)}"
                })
        
        # For OnKernal provider: Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Browser stream connected",
            "provider": provider_name.lower().replace("provider", ""),
            "browser_url": provider.get_viewer_url(),
            "streaming_type": "webrtc"
        })

        # For OnKernal or fallback: Keep connection alive and listen for client messages
        while True:
            try:
                # Receive messages from client
                data = await websocket.receive_json()

                # Handle ping/pong for keepalive
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                # Handle browser URL update request
                elif data.get("type") == "update_url":
                    new_url = data.get("url")
                    await websocket.send_json({
                        "type": "url_updated",
                        "url": new_url
                    })

                # Handle disconnect request
                elif data.get("type") == "disconnect":
                    break

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in browser stream for client {client_id}: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        logger.info(f"Browser stream client {client_id} disconnected normally")
    except Exception as e:
        logger.error(f"Browser stream error for client {client_id}: {e}")
    finally:
        stream_manager.disconnect(client_id)


@router.get("/browser/status")
async def browser_status():
    """Get browser stream status and provider information"""
    try:
        provider = get_browser_provider()
        provider_name = type(provider).__name__.replace("Provider", "").lower()

        # Check if browser container is accessible
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get("http://localhost:8080")
                browser_accessible = response.status_code == 200
            except:
                browser_accessible = False

        return {
            "provider": provider_name,  # "chrome" or "onkernal"
            "streaming_type": "screencast" if provider_name == "chrome" else "webrtc",
            "browser_accessible": browser_accessible,
            "browser_url": provider.get_viewer_url(),
            "cdp_url": provider.get_cdp_url() if hasattr(provider, 'get_cdp_url') else "http://localhost:9222",
            "active_streams": len(stream_manager.active_streams),
            "connected_clients": list(stream_manager.active_streams.keys())
        }
    except Exception as e:
        return {
            "error": str(e),
            "browser_accessible": False,
            "provider": "unknown"
        }


@router.get("/browser/health")
async def browser_health():
    """Check browser container health"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check browser view port
            try:
                browser_response = await client.get("http://localhost:8080")
                browser_status = "healthy" if browser_response.status_code == 200 else "unhealthy"
            except Exception as e:
                browser_status = f"unreachable: {e}"

            # Check CDP port
            try:
                cdp_response = await client.get("http://localhost:9222/json/version")
                cdp_data = cdp_response.json() if cdp_response.status_code == 200 else None
                cdp_status = "healthy" if cdp_response.status_code == 200 else "unhealthy"
            except Exception as e:
                cdp_data = None
                cdp_status = f"unreachable: {e}"

            return {
                "browser_view": {
                    "url": "http://localhost:8080",
                    "status": browser_status
                },
                "cdp": {
                    "url": "http://localhost:9222",
                    "status": cdp_status,
                    "data": cdp_data
                }
            }
    except Exception as e:
        return {
            "error": str(e)
        }


@router.post("/browser/stream")
async def browser_stream_resize(width: int, height: int):
    """
    Legacy endpoint for browser viewport resize.
    Redirects to /browser/viewport for backwards compatibility.
    """
    return await set_browser_viewport(width, height)


@router.post("/browser/viewport")
async def set_browser_viewport(width: int, height: int):
    """
    Dynamically resize browser viewport using CDP
    
    Args:
        width: Viewport width in pixels
        height: Viewport height in pixels
    
    Returns:
        Success status
    """
    try:
        from web_agent.utils.session_registry import _SESSION_REGISTRY
        from web_agent.browser.session import BrowserSession
        
        # Try to get active browser session from registry
        browser_session: BrowserSession | None = None
        
        # Get the first active browser session
        for session_id, session in _SESSION_REGISTRY.items():
            if isinstance(session, BrowserSession) and session.agent_focus:
                browser_session = session
                break
        
        if browser_session and browser_session.agent_focus:
            # Use existing session to set viewport
            try:
                await browser_session._cdp_set_viewport(width, height)
                logger.info(f"Viewport resized to {width}x{height} via existing session")
                return {
                    "success": True,
                    "message": f"Viewport resized to {width}x{height}",
                    "method": "existing_session"
                }
            except Exception as e:
                logger.warning(f"Failed to resize via session, trying direct CDP: {e}")
        
        # Fallback: Use direct CDP connection
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get list of targets (tabs/pages)
            targets_response = await client.get("http://localhost:9222/json")
            targets = targets_response.json()
            
            if not targets:
                return {"error": "No browser targets found", "success": False}
            
            # Use the first page target
            target = next((t for t in targets if t.get("type") == "page"), targets[0])
            target_id = target.get("id")
            
            if not target_id:
                return {"error": "No valid target ID found", "success": False}
            
            # Get WebSocket debugger URL for direct CDP connection
            ws_url = target.get("webSocketDebuggerUrl")
            
            if ws_url:
                # Use websockets library to send CDP command
                try:
                    import websockets
                    async with websockets.connect(ws_url.replace("ws://", "ws://").replace("http://", "ws://")) as ws:
                        # Create session
                        session_msg = {
                            "id": 1,
                            "method": "Target.attachToTarget",
                            "params": {"targetId": target_id, "flatten": True}
                        }
                        await ws.send(str(session_msg).replace("'", '"'))
                        session_response = await ws.recv()
                        
                        # Extract session ID from response
                        import json
                        session_data = json.loads(session_response)
                        cdp_session_id = session_data.get("result", {}).get("sessionId")
                        
                        if cdp_session_id:
                            # Send viewport resize command
                            viewport_msg = {
                                "id": 2,
                                "method": "Emulation.setDeviceMetricsOverride",
                                "params": {
                                    "width": width,
                                    "height": height,
                                    "deviceScaleFactor": 1.0,
                                    "mobile": False
                                },
                                "sessionId": cdp_session_id
                            }
                            await ws.send(json.dumps(viewport_msg))
                            response = await ws.recv()
                            
                            logger.info(f"Viewport resized to {width}x{height} via direct CDP")
                            return {
                                "success": True,
                                "message": f"Viewport resized to {width}x{height}",
                                "method": "direct_cdp"
                            }
                except ImportError:
                    logger.warning("websockets library not available, skipping direct CDP")
                except Exception as e:
                    logger.error(f"Error in direct CDP connection: {e}")
            
            # If all else fails, return success (iframe will resize, browser viewport may not)
            logger.info(f"Viewport resize requested: {width}x{height} (iframe will resize)")
            return {
                "success": True,
                "message": f"Viewport resize requested: {width}x{height}",
                "method": "iframe_only",
                "note": "Browser viewport may remain fixed; iframe will resize"
            }
            
    except Exception as e:
        logger.error(f"Error setting browser viewport: {e}")
        return {
            "error": str(e),
            "success": False
        }
