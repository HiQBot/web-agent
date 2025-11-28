"""
Telemetry for Browser Use.
"""

from typing import TYPE_CHECKING

# Type stubs for lazy imports
if TYPE_CHECKING:
	from web_agent.telemetry.service import ProductTelemetry
	from web_agent.telemetry.views import (
		BaseTelemetryEvent,
		CLITelemetryEvent,
		MCPClientTelemetryEvent,
		MCPServerTelemetryEvent,
	)

# Lazy imports mapping
_LAZY_IMPORTS = {
	'ProductTelemetry': ('web_agent.telemetry.service', 'ProductTelemetry'),
	'BaseTelemetryEvent': ('web_agent.telemetry.views', 'BaseTelemetryEvent'),
	'CLITelemetryEvent': ('web_agent.telemetry.views', 'CLITelemetryEvent'),
	'MCPClientTelemetryEvent': ('web_agent.telemetry.views', 'MCPClientTelemetryEvent'),
	'MCPServerTelemetryEvent': ('web_agent.telemetry.views', 'MCPServerTelemetryEvent'),
}


def __getattr__(name: str):
	"""Lazy import mechanism for telemetry components."""
	if name in _LAZY_IMPORTS:
		module_path, attr_name = _LAZY_IMPORTS[name]
		try:
			from importlib import import_module

			module = import_module(module_path)
			attr = getattr(module, attr_name)
			# Cache the imported attribute in the module's globals
			globals()[name] = attr
			return attr
		except ImportError as e:
			raise ImportError(f'Failed to import {name} from {module_path}: {e}') from e

	raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
	'BaseTelemetryEvent',
	'ProductTelemetry',
	'CLITelemetryEvent',
	'MCPClientTelemetryEvent',
	'MCPServerTelemetryEvent',
]
