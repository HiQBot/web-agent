"""
DOM Stability Utilities

Helper functions to wait for network idle and DOM stability after actions.
Based on browser-use's DOMWatchdog pattern.
"""
import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qa_agent.browser.session import BrowserSession

logger = logging.getLogger(__name__)


async def wait_for_dom_stability(
    browser_session: "BrowserSession",
    max_wait_seconds: float = 3.0,
    check_interval: float = 0.5,
) -> None:
    """
    Wait for DOM stability after actions (network idle + DOM settled).
    
    Browser-use pattern: Check for pending network requests and wait if found.
    This ensures dropdowns, modals, and dynamic content are fully rendered.
    
    Args:
        browser_session: Browser session to check
        max_wait_seconds: Maximum time to wait (default 3s, browser-use uses 1s but we wait longer for complex pages)
        check_interval: How often to check (default 0.5s)
    """
    try:
        # Get initial pending requests (browser-use pattern from DOMWatchdog)
        initial_state = await browser_session.get_browser_state_summary(
            include_screenshot=False,
            cached=False  # Force fresh check
        )
        
        pending_requests = initial_state.pending_network_requests if initial_state.pending_network_requests else []
        
        if not pending_requests:
            logger.debug("No pending network requests, DOM appears stable")
            return
        
        logger.info(f"⏳ Found {len(pending_requests)} pending network requests, waiting for DOM stability...")
        
        # Wait for network idle (browser-use pattern: wait 1s if pending requests exist)
        # We use a polling approach to check if requests complete
        waited = 0.0
        while waited < max_wait_seconds:
            await asyncio.sleep(check_interval)
            waited += check_interval
            
            # Check again
            current_state = await browser_session.get_browser_state_summary(
                include_screenshot=False,
                cached=False
            )
            new_pending = current_state.pending_network_requests if current_state.pending_network_requests else []
            
            if len(new_pending) == 0:
                logger.info(f"✅ Network idle after {waited:.1f}s")
                break
            
            # If requests are decreasing, continue waiting
            if len(new_pending) < len(pending_requests):
                logger.debug(f"   Requests decreasing: {len(pending_requests)} → {len(new_pending)}, continuing...")
                pending_requests = new_pending
        
        if waited >= max_wait_seconds:
            remaining = len(pending_requests) if 'pending_requests' in locals() else 0
            if remaining > 0:
                logger.warning(f"⚠️ Still {remaining} pending requests after {max_wait_seconds}s, proceeding anyway")
            else:
                logger.info(f"✅ DOM stability wait complete ({waited:.1f}s)")
    
    except Exception as e:
        logger.debug(f"Could not check network idle: {e}, proceeding with state refresh")
        # Don't fail - just proceed without waiting


async def clear_cache_if_needed(
    browser_session: "BrowserSession",
    action_type: str,
    previous_url: str | None = None,
) -> None:
    """
    Clear browser state cache if action might have changed the page.
    
    Browser-use pattern: Clear cache on tab switch, navigation, or actions that change DOM.
    
    Args:
        browser_session: Browser session to clear cache for
        action_type: Type of action executed (click, navigate, switch, etc.)
        previous_url: Previous URL before action (to detect navigation)
    """
    # Actions that definitely change the page
    page_changing_actions = ["navigate", "switch", "go_back"]
    
    # Actions that might change DOM (dropdowns, modals, dynamic content)
    dom_changing_actions = ["click", "input", "scroll"]
    
    should_clear = False
    
    if action_type in page_changing_actions:
        should_clear = True
        logger.debug(f"🔄 Clearing cache after {action_type} (page-changing action)")
    
    elif action_type in dom_changing_actions:
        # Check if URL changed (indicates navigation)
        try:
            current_state = await browser_session.get_browser_state_summary(
                include_screenshot=False,
                cached=True  # Use cache for quick check
            )
            current_url = current_state.url
            
            if previous_url and current_url != previous_url:
                should_clear = True
                logger.debug(f"🔄 Clearing cache: URL changed ({previous_url} → {current_url})")
        except Exception:
            # If check fails, clear cache to be safe
            should_clear = True
    
    if should_clear:
        # Browser-use pattern: Clear cached browser state
        # Access internal cache (browser-use pattern from session.py line 926)
        if hasattr(browser_session, '_cached_browser_state_summary'):
            browser_session._cached_browser_state_summary = None
        if hasattr(browser_session, '_cached_selector_map'):
            browser_session._cached_selector_map.clear()
        
        # Also clear DOM watchdog cache if available
        if hasattr(browser_session, '_dom_watchdog') and browser_session._dom_watchdog:
            if hasattr(browser_session._dom_watchdog, 'clear_cache'):
                browser_session._dom_watchdog.clear_cache()
        
        logger.debug("✅ Browser state cache cleared")

