"""
Port Management Utilities

Provides utilities for checking port availability and finding available ports.
Used by browser providers to handle port conflicts.
"""
import socket
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def check_port_available(port: int, host: str = 'localhost') -> bool:
	"""
	Check if a port is available for binding.
	
	Args:
		port: Port number to check
		host: Host address (default: 'localhost')
		
	Returns:
		True if port is available, False if already in use
	"""
	try:
		with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
			s.settimeout(1)
			result = s.connect_ex((host, port))
			return result != 0  # Port is available if connection fails
	except Exception as e:
		logger.debug(f"Error checking port {port}: {e}")
		return False


def find_available_port(start_port: int, max_attempts: int = 10, host: str = 'localhost') -> Optional[int]:
	"""
	Find an available port starting from start_port.
	
	Args:
		start_port: Starting port number
		max_attempts: Maximum number of ports to try
		host: Host address (default: 'localhost')
		
	Returns:
		Available port number, or None if no port found
	"""
	for i in range(max_attempts):
		port = start_port + i
		if check_port_available(port, host):
			logger.debug(f"Found available port: {port}")
			return port
		logger.debug(f"Port {port} is in use, trying next...")
	
	logger.warning(f"No available port found in range {start_port}-{start_port + max_attempts - 1}")
	return None


def get_available_cdp_port(requested_port: Optional[int] = None, default_port: int = 9222) -> int:
	"""
	Get an available CDP port, checking requested port first, then default.
	
	Args:
		requested_port: Requested port from config/env (None to use default)
		default_port: Default CDP port (9222)
		
	Returns:
		Available port number
	"""
	port = requested_port or default_port
	
	if check_port_available(port):
		logger.info(f"CDP port {port} is available")
		return port
	
	logger.warning(f"CDP port {port} is in use, searching for alternative...")
	alternative = find_available_port(port + 1, max_attempts=10)
	if alternative:
		logger.info(f"Using alternative CDP port: {alternative}")
		return alternative
	
	raise RuntimeError(f"Could not find available CDP port. Port {port} is in use and no alternatives found.")


def get_available_streaming_port(requested_port: Optional[int] = None, default_port: int = 8080) -> int:
	"""
	Get an available streaming port, checking requested port first, then default.
	
	Args:
		requested_port: Requested port from config/env (None to use default)
		default_port: Default streaming port (8080)
		
	Returns:
		Available port number
	"""
	port = requested_port or default_port
	
	if check_port_available(port):
		logger.info(f"Streaming port {port} is available")
		return port
	
	logger.warning(f"Streaming port {port} is in use, searching for alternative...")
	alternative = find_available_port(port + 1, max_attempts=10)
	if alternative:
		logger.info(f"Using alternative streaming port: {alternative}")
		return alternative
	
	raise RuntimeError(f"Could not find available streaming port. Port {port} is in use and no alternatives found.")

