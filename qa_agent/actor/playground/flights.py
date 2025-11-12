import asyncio

from qa_agent.browser import BrowserSession as Browser
from qa_agent.llm import get_llm

llm = get_llm(model='gpt-4o-mini')


async def main():
	"""
	Main function demonstrating mixed automation with browser and Playwright.
	"""
	print('🚀 Mixed Automation with browser and Actor API')

	browser = Browser(keep_alive=True)
	await browser.start()

	page = await browser.get_current_page() or await browser.new_page()

	# Go to apple wikipedia page
	await page.goto('https://www.google.com/travel/flights')

	await asyncio.sleep(1)

	round_trip_button = await page.must_get_element_by_prompt('round trip button', llm)
	await round_trip_button.click()

	one_way_button = await page.must_get_element_by_prompt('one way button', llm)
	await one_way_button.click()

	await asyncio.sleep(1)

	# Note: Agent class doesn't exist in onkernal - use workflow instead
	# For this playground example, we'll just demonstrate browser interactions
	print('Note: Agent.run() is not available in onkernal. Use workflow.run() instead for full agent functionality.')

	input('Press Enter to continue...')

	await browser.stop()


if __name__ == '__main__':
	asyncio.run(main())
