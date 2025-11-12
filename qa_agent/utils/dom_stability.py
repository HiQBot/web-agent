"""
DOM Stability Utilities

Helper functions to wait for network idle and DOM stability after actions.
Based on browser's DOMWatchdog pattern.

Enhanced with adaptive detection for dynamic content.
"""
import asyncio
import logging
from typing import TYPE_CHECKING, Tuple, Set

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
    
    browser pattern: Check for pending network requests and wait if found.
    This ensures dropdowns, modals, and dynamic content are fully rendered.
    
    Args:
        browser_session: Browser session to check
        max_wait_seconds: Maximum time to wait (default 3s, browser uses 1s but we wait longer for complex pages)
        check_interval: How often to check (default 0.5s)
    """
    try:
        # Get initial pending requests (browser pattern from DOMWatchdog)
        initial_state = await browser_session.get_browser_state_summary(
            include_screenshot=False,
            cached=False  # Force fresh check
        )
        
        pending_requests = initial_state.pending_network_requests if initial_state.pending_network_requests else []
        
        if not pending_requests:
            logger.debug("No pending network requests, DOM appears stable")
            return
        
        logger.info(f"⏳ Found {len(pending_requests)} pending network requests, waiting for DOM stability...")
        
        # Wait for network idle (browser pattern: wait 1s if pending requests exist)
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


async def detect_dom_changes_adaptively(
    browser_session: "BrowserSession",
    previous_element_ids: Set[int] | None = None,
    max_passes: int = 5,
    stability_threshold: int = 2,
    pass_interval: float = 0.3,
) -> Tuple[Set[int], int]:
    """
    Detect DOM changes adaptively across multiple passes.
    
    Waits until element count stabilizes (same count for stability_threshold passes).
    This ensures dropdowns, modals, and animated content are fully rendered.
    
    Args:
        browser_session: Browser session to check
        previous_element_ids: Set of element IDs from before action (None to detect from current state)
        max_passes: Maximum number of passes to check (default 5)
        stability_threshold: Number of consecutive passes with same count needed for stability (default 2)
        pass_interval: Time between passes in seconds (default 0.3s)
    
    Returns:
        Tuple of (final_element_ids, passes_taken)
    """
    element_counts = []
    element_ids_history = []
    
    # Get initial state if previous_element_ids not provided
    if previous_element_ids is None:
        try:
            initial_state = await browser_session.get_browser_state_summary(
                include_screenshot=False, cached=False
            )
            previous_element_ids = set(
                initial_state.dom_state.selector_map.keys() 
                if initial_state.dom_state and initial_state.dom_state.selector_map 
                else []
            )
        except Exception as e:
            logger.debug(f"Could not get initial element IDs: {e}")
            previous_element_ids = set()
    
    logger.info(f"🔍 Adaptive DOM change detection: Starting with {len(previous_element_ids)} elements")
    
    for pass_num in range(max_passes):
        try:
            state = await browser_session.get_browser_state_summary(
                include_screenshot=False, cached=False
            )
            current_ids = set(
                state.dom_state.selector_map.keys() 
                if state.dom_state and state.dom_state.selector_map 
                else []
            )
            element_counts.append(len(current_ids))
            element_ids_history.append(current_ids)
            
            # Log change if detected
            if pass_num > 0 and element_counts[-1] != element_counts[-2]:
                change = element_counts[-1] - element_counts[-2]
                logger.debug(f"   Pass {pass_num + 1}: {element_counts[-1]} elements ({change:+d})")
            
            # Check if count stabilized (same for stability_threshold passes)
            if len(element_counts) >= stability_threshold:
                recent_counts = element_counts[-stability_threshold:]
                if len(set(recent_counts)) == 1:  # All same
                    new_elements = current_ids - previous_element_ids
                    logger.info(
                        f"✅ DOM stabilized after {pass_num + 1} passes "
                        f"({element_counts[-1]} elements, {len(new_elements)} new)"
                    )
                    return current_ids, pass_num + 1
            
            # Wait before next pass (except last pass)
            if pass_num < max_passes - 1:
                await asyncio.sleep(pass_interval)
        
        except Exception as e:
            logger.debug(f"Error in pass {pass_num + 1}: {e}")
            # Continue to next pass
    
    # Max passes reached - return final state
    final_ids = element_ids_history[-1] if element_ids_history else previous_element_ids
    new_elements = final_ids - previous_element_ids
    logger.info(
        f"⏱️ Max passes ({max_passes}) reached: {len(final_ids)} elements "
        f"({len(new_elements)} new since start)"
    )
    return final_ids, max_passes


async def get_adaptive_visibility_state(
    browser_session: "BrowserSession",
    max_passes: int = 3,
    pass_interval: float = 0.3,
) -> dict[int, bool]:
    """
    Check visibility across multiple passes to catch animated elements.
    
    Elements that appear gradually (via CSS animations, transitions) may not be
    visible in the first pass. This function checks multiple times to catch them.
    
    Args:
        browser_session: Browser session to check
        max_passes: Number of passes to check (default 3)
        pass_interval: Time between passes in seconds (default 0.3s)
    
    Returns:
        Dictionary mapping backend_node_id to visibility (True if visible in ANY pass)
    """
    visibility_states = {}
    
    for pass_num in range(max_passes):
        try:
            state = await browser_session.get_browser_state_summary(
                include_screenshot=False, cached=False
            )
            
            if state.dom_state and state.dom_state.selector_map:
                for node_id, node in state.dom_state.selector_map.items():
                    is_visible = (
                        node.is_visible 
                        if hasattr(node, 'is_visible') 
                        else False
                    )
                    
                    if node_id not in visibility_states:
                        visibility_states[node_id] = []
                    visibility_states[node_id].append(is_visible)
            
            if pass_num < max_passes - 1:
                await asyncio.sleep(pass_interval)
        
        except Exception as e:
            logger.debug(f"Error in visibility pass {pass_num + 1}: {e}")
    
    # Element is visible if visible in ANY pass (catches animated elements)
    final_visibility = {
        node_id: any(visits) 
        for node_id, visits in visibility_states.items()
    }
    
    if max_passes > 1:
        logger.debug(
            f"Multi-pass visibility check: {len(final_visibility)} elements checked "
            f"across {max_passes} passes"
        )
    
    return final_visibility


async def clear_cache_if_needed(
    browser_session: "BrowserSession",
    action_type: str,
    previous_url: str | None = None,
) -> None:
    """
    Clear browser state cache if action might have changed the page.
    
    browser pattern: Clear cache on tab switch, navigation, or actions that change DOM.
    
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
        # browser pattern: Clear cached browser state
        # Access internal cache (browser pattern from session.py line 926)
        if hasattr(browser_session, '_cached_browser_state_summary'):
            browser_session._cached_browser_state_summary = None
        if hasattr(browser_session, '_cached_selector_map'):
            browser_session._cached_selector_map.clear()
        
        # Also clear DOM watchdog cache if available
        if hasattr(browser_session, '_dom_watchdog') and browser_session._dom_watchdog:
            if hasattr(browser_session._dom_watchdog, 'clear_cache'):
                browser_session._dom_watchdog.clear_cache()
        
        logger.debug("✅ Browser state cache cleared")

