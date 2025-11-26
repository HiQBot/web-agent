"""
Cloud browser stub - exception classes only.
This stub allows imports to work but cloud functionality is NOT implemented.
We use kernel-image CDP connection instead of cloud browser service.
"""


class CloudBrowserError(Exception):
	"""Exception raised when cloud browser operations fail."""
	pass


class CloudBrowserAuthError(CloudBrowserError):
	"""Exception raised when cloud browser authentication fails."""
	pass


class CloudBrowserClient:
	"""
	Stub cloud browser client that does nothing.
	In our implementation, we use kernel-image CDP connection instead.
	This class exists only to satisfy imports in session.py.
	"""

	def __init__(self):
		pass

	async def create_browser(self, params):
		"""Not implemented - we use kernel-image CDP instead."""
		raise CloudBrowserError("Cloud browser service is not available. Use kernel-image CDP connection instead.")

	async def stop_browser(self):
		"""Not implemented - we use kernel-image CDP instead."""
		pass
