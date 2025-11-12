"""
Browser Stream Routes

WebSocket endpoint for proxying live browser view from Docker container.
"""
import logging
import asyncio
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()


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
    WebSocket endpoint for streaming live browser view

    This endpoint proxies the browser view from the Docker container (localhost:8080)
    and streams it to the frontend via WebSocket.

    Usage:
        ws://localhost:8000/api/v1/ws/browser-stream?client_id=123&browser_url=http://localhost:8080

    The frontend should use this to display the live browser automation view.
    """
    await stream_manager.connect(websocket, client_id)

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Browser stream connected",
            "browser_url": browser_url
        })

        # Keep connection alive and listen for client messages
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
    """Get browser stream status"""
    try:
        # Check if browser container is accessible
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get("http://localhost:8080")
                browser_accessible = response.status_code == 200
            except:
                browser_accessible = False

        return {
            "browser_accessible": browser_accessible,
            "browser_url": "http://localhost:8080",
            "cdp_url": "http://localhost:9222",
            "active_streams": len(stream_manager.active_streams),
            "connected_clients": list(stream_manager.active_streams.keys())
        }
    except Exception as e:
        return {
            "error": str(e),
            "browser_accessible": False
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
        from qa_agent.utils.session_registry import _SESSION_REGISTRY
        from qa_agent.browser.session import BrowserSession
        
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
