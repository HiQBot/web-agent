"""
Simple CDP connection test - just connect and navigate.
Tests kernel-image CDP connection without loading all browser-use watchdogs.
"""
import asyncio
import sys
import httpx
from cdp_use import CDPClient
from qa_agent.config import settings


async def test_simple_cdp():
	"""Test basic CDP connection."""
	print("=" * 60)
	print("Simple CDP Connection Test")
	print("=" * 60)
	print(f"CDP HTTP Endpoint: http://{settings.kernel_cdp_host}:{settings.kernel_cdp_port}")
	print(f"Headless: {settings.headless}")
	print()

	cdp_client = None
	try:
		# Get WebSocket debugger URL from HTTP endpoint
		print("🔄 Getting WebSocket URL from CDP HTTP endpoint...")
		http_url = f"http://{settings.kernel_cdp_host}:{settings.kernel_cdp_port}"
		async with httpx.AsyncClient() as client:
			response = await client.get(f"{http_url}/json/version")
			version_data = response.json()
			ws_url = version_data["webSocketDebuggerUrl"]
			print(f"✓ WebSocket URL: {ws_url[:60]}...")
		print()

		# Connect to CDP
		print("🔄 Connecting to CDP via WebSocket...")
		cdp_client = CDPClient(ws_url)
		await cdp_client.start()
		print(f"✓ CDP client connected")
		print()

		# Get browser version
		print("🔄 Getting browser version...")
		version_info = await cdp_client.send.Browser.getVersion()
		print(f"✓ Browser: {version_info['product']}")
		print(f"✓ User Agent: {version_info['userAgent'][:80]}...")
		print()

		# List targets
		print("🔄 Listing targets...")
		targets = await cdp_client.send.Target.getTargets()
		print(f"✓ Found {len(targets['targetInfos'])} targets")

		# Find a page target to navigate
		page_target = None
		for target in targets['targetInfos']:
			if target['type'] == 'page':
				page_target = target
				break

		if not page_target:
			print("⚠ No page target found, creating new page...")
			new_target = await cdp_client.send.Target.createTarget(params={'url': 'about:blank'})
			page_target_id = new_target['targetId']
		else:
			page_target_id = page_target['targetId']
			print(f"✓ Using existing page target: {page_target_id}")
		print()

		# Attach to the page target
		print("🔄 Attaching to page target...")
		attach_result = await cdp_client.send.Target.attachToTarget(params={
			'targetId': page_target_id,
			'flatten': True
		})
		session_id = attach_result['sessionId']
		print(f"✓ Attached to session: {session_id}")
		print()

		# Navigate to openai.com
		print("🔄 Navigating to https://openai.com ...")
		await cdp_client.send.Page.enable(session_id=session_id)
		nav_result = await cdp_client.send.Page.navigate(
			params={'url': 'https://openai.com'},
			session_id=session_id
		)
		print(f"✓ Navigation started - Frame ID: {nav_result['frameId']}")
		print()

		# Wait for page to load
		print("🔄 Waiting 5 seconds for page to load (check your browser!)...")
		await asyncio.sleep(5)
		print("✓ Page should be visible now in headful Chrome")
		print()

		# Get final page info
		print("🔄 Getting final page info...")
		targets_after = await cdp_client.send.Target.getTargets()
		for target in targets_after['targetInfos']:
			if target['targetId'] == page_target_id:
				print(f"✓ Final page title: {target.get('title', 'No title')}")
				print(f"✓ Final page URL: {target.get('url', 'No URL')}")
		print()

		# Success
		print("=" * 60)
		print("✅ SIMPLE CDP CONNECTION TEST PASSED")
		print("You should see https://openai.com in the headful Chrome!")
		print("=" * 60)
		return True

	except Exception as e:
		print()
		print("=" * 60)
		print(f"❌ SIMPLE CDP CONNECTION TEST FAILED")
		print(f"Error: {e}")
		print("=" * 60)
		import traceback
		traceback.print_exc()
		return False

	finally:
		# Cleanup
		if cdp_client:
			print("\n🔄 Disconnecting CDP client...")
			try:
				await cdp_client.stop()
				print("✓ CDP client disconnected")
			except Exception as e:
				print(f"⚠ Disconnect warning: {e}")


async def main():
	"""Run the simple CDP test."""
	success = await test_simple_cdp()
	sys.exit(0 if success else 1)


if __name__ == "__main__":
	asyncio.run(main())
