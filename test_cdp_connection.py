"""
Test CDP connection to kernel-image container.
This script verifies that we can connect to the headful Chrome in kernel-image via CDP.
Tests full BrowserSession lifecycle with browser-use integration.
"""
import asyncio
import sys
from qa_agent.config import settings
from qa_agent.utils.browser_manager import create_browser_session, cleanup_browser_session


async def test_cdp_connection():
	"""Test connecting to kernel-image CDP endpoint with full BrowserSession."""
	print("=" * 60)
	print("Testing CDP Connection to kernel-image")
	print("=" * 60)
	print(f"CDP Host: {settings.kernel_cdp_host}")
	print(f"CDP Port: {settings.kernel_cdp_port}")
	print(f"Headless: {settings.headless}")
	print()

	session_id = None
	try:
		# Create browser session with start URL
		print("🔄 Creating browser session with navigation to openai.com...")
		session_id, session = await create_browser_session(start_url="https://openai.com")
		print(f"✓ Browser session created: {session_id}")
		print(f"✓ CDP URL: {session.browser_profile.cdp_url}")
		print()

		# Wait for page to settle
		print("🔄 Waiting for page to load...")
		await asyncio.sleep(3)

		# Get current page info (use BrowserSession methods, not Page attributes)
		print("🔄 Getting current page info...")
		try:
			current_title = await session.get_current_page_title()
			current_url = await session.get_current_page_url()
			print(f"✓ Current page title: {current_title}")
			print(f"✓ Current page URL: {current_url}")
		except Exception as e:
			print(f"⚠ Could not get page info: {e}")
		print()

		# Test browser state summary (this is what THINK node will use!)
		print("🔄 Getting browser state summary (DOM extraction)...")
		browser_state = await session.get_browser_state_summary(
			include_screenshot=False,
			include_recent_events=False
		)
		print(f"✓ Browser state retrieved")
		print(f"✓ URL: {browser_state.url}")
		print(f"✓ Title: {browser_state.title}")
		if browser_state.dom_state and browser_state.dom_state.selector_map:
			element_count = len(browser_state.dom_state.selector_map)
			print(f"✓ Interactive elements found: {element_count}")
			# Show first few elements
			for idx, elem in list(browser_state.dom_state.selector_map.items())[:3]:
				# EnhancedDOMTreeNode has: tag_name, node_value, ax_node.name, ax_node.role
				tag = elem.tag_name if hasattr(elem, 'tag_name') else elem.node_name
				text = elem.node_value or (elem.ax_node.name if elem.ax_node else None) or '(no text)'
				role = f" role={elem.ax_node.role}" if elem.ax_node and elem.ax_node.role else ""
				print(f"  [{idx}] <{tag}>{role} - {text[:30]}")
		print()

		# Success
		print("=" * 60)
		print("✅ CDP CONNECTION TEST PASSED")
		print("✅ BrowserSession with DOM extraction working!")
		print("=" * 60)
		return True

	except Exception as e:
		print()
		print("=" * 60)
		print(f"❌ CDP CONNECTION TEST FAILED")
		print(f"Error: {e}")
		print("=" * 60)
		import traceback
		traceback.print_exc()
		return False

	finally:
		# Cleanup
		if session_id:
			print("\n🔄 Cleaning up browser session...")
			try:
				await cleanup_browser_session(session_id)
				print("✓ Browser session cleaned up")
			except Exception as e:
				print(f"⚠ Cleanup warning: {e}")


async def main():
	"""Run the CDP connection test."""
	success = await test_cdp_connection()
	sys.exit(0 if success else 1)


if __name__ == "__main__":
	asyncio.run(main())
