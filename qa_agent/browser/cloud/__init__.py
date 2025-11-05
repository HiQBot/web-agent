"""
Cloud browser stub module - provides exception classes only.
Cloud browser service is NOT used in this implementation.
"""
from qa_agent.browser.cloud.cloud import CloudBrowserAuthError, CloudBrowserClient, CloudBrowserError
from qa_agent.browser.cloud.views import CloudBrowserParams, CreateBrowserRequest, ProxyCountryCode

__all__ = [
	"CloudBrowserAuthError",
	"CloudBrowserClient",
	"CloudBrowserError",
	"CloudBrowserParams",
	"CreateBrowserRequest",
	"ProxyCountryCode",
]
