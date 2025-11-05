"""
Test CDP connection to kernel-image container.
This script verifies that we can connect to the headful Chrome in kernel-image via CDP.
"""
import asyncio
import sys
from qa_agent.config import settings
from qa_agent.browser.profile import BrowserProfile
from qa_agent.utils.browser_manager import create_browser_session, cleanup_browser_session


async def test_cdp_connection():
	"""Test connecting to kernel-image CDP endpoint."""
	print("=" * 60)
	print("Testing CDP Connection to kernel-image")
	print("=" * 60)
	print(f"CDP Host: {settings.kernel_cdp_host}")
	print(f"CDP Port: {settings.kernel_cdp_port}")
	print(f"Headless: {settings.headless}")
	print()

	session_id = None
	try:
		# Create browser session
		print("🔄 Creating browser session...")
		session_id, session = await create_browser_session()
		print(f"✓ Browser session created: {session_id}")
		print(f"✓ CDP URL: {session.browser_profile.cdp_url}")
		print()

		# Get current page info
		print("🔄 Getting current page...")
		current_page = await session.get_current_page()
		if current_page:
			print(f"✓ Current page title: {current_page.title}")
			print(f"✓ Current page URL: {current_page.url}")
		else:
			print("⚠ No current page found")
		print()

		# Navigate to a test page
		print("🔄 Navigating to example.com...")
		await session.navigate_to("https://example.com")
		await asyncio.sleep(2)  # Wait for page load

		current_page = await session.get_current_page()
		if current_page:
			print(f"✓ Page title: {current_page.title}")
			print(f"✓ Page URL: {current_page.url}")
		print()

		# Success
		print("=" * 60)
		print("✅ CDP CONNECTION TEST PASSED")
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
