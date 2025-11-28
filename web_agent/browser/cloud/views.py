"""
Cloud browser views stub - data models only.
These models are referenced in session.py but not actively used in our implementation.
"""
from typing import Literal

from pydantic import BaseModel


# Country codes for cloud proxy
ProxyCountryCode = Literal[
	"US", "GB", "DE", "FR", "CA", "AU", "JP", "BR", "IN", "MX",
	"ES", "IT", "NL", "SE", "CH", "PL", "BE", "AT", "NO", "DK",
]


class CreateBrowserRequest(BaseModel):
	"""Request model for creating a cloud browser."""
	cloud_profile_id: str | None = None
	cloud_proxy_country_code: ProxyCountryCode | None = None
	cloud_timeout: int | None = None


class CloudBrowserParams(BaseModel):
	"""Parameters for cloud browser configuration."""
	profile_id: str | None = None
	proxy_country_code: ProxyCountryCode | None = None
	timeout: int | None = None
