"""
Singleton decorator utility

Copied from browser/browser_use/utils.py for compatibility
"""


def singleton(cls):
	"""
	Singleton decorator that ensures only one instance of a class exists

	Args:
		cls: The class to make a singleton

	Returns:
		Wrapper function that returns the singleton instance
	"""
	instance = [None]

	def wrapper(*args, **kwargs):
		if instance[0] is None:
			instance[0] = cls(*args, **kwargs)
		return instance[0]

	return wrapper
