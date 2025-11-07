"""
INIT Node: Initialize browser session at workflow start

This node creates the BrowserSession connected to kernel-image CDP
and prepares it for use by THINK and ACT nodes.
"""
import logging
import re
from typing import Any, Dict, Optional

from qa_agent.state import QAAgentState
from qa_agent.utils.browser_manager import create_browser_session

logger = logging.getLogger(__name__)


def _extract_url_from_task(task: str) -> Optional[str]:
	"""Extract URL from task string using browser-use pattern matching.
	
	Args:
		task: Task string that may contain a URL
		
	Returns:
		Extracted URL if exactly one found, None otherwise
	"""
	# Remove email addresses from task before looking for URLs
	task_without_emails = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', task)

	# Look for common URL patterns (browser-use pattern)
	patterns = [
		r'https?://[^\s<>"\']+',  # Full URLs with http/https
		r'(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}(?:/[^\s<>"\']*)?',  # Domain names with subdomains and optional paths
	]

	# File extensions that should be excluded from URL detection
	excluded_extensions = {
		'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp',
		'txt', 'md', 'csv', 'json', 'xml', 'yaml', 'yml',
		'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz',
		'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'ico',
		'mp3', 'mp4', 'avi', 'mkv', 'mov', 'wav', 'flac', 'ogg',
		'py', 'js', 'css', 'java', 'cpp',
		'bib', 'bibtex', 'tex', 'latex', 'cls', 'sty',
		'exe', 'msi', 'dmg', 'pkg', 'deb', 'rpm', 'iso',
	}

	excluded_words = {'never', 'dont', 'not', "don't"}

	found_urls = []
	for pattern in patterns:
		matches = re.finditer(pattern, task_without_emails)
		for match in matches:
			url = match.group(0)
			original_position = match.start()

			# Remove trailing punctuation that's not part of URLs
			url = re.sub(r'[.,;:!?()\[\]]+$', '', url)

			# Check if URL ends with a file extension that should be excluded
			url_lower = url.lower()
			should_exclude = False
			for ext in excluded_extensions:
				if f'.{ext}' in url_lower:
					should_exclude = True
					break

			if should_exclude:
				logger.debug(f'Excluding URL with file extension from auto-navigation: {url}')
				continue

			# If in the 20 characters before the url position is a word in excluded_words skip
			context_start = max(0, original_position - 20)
			context_text = task_without_emails[context_start:original_position]
			if any(word.lower() in context_text.lower() for word in excluded_words):
				logger.debug(
					f'Excluding URL with word in excluded words from auto-navigation: {url} (context: "{context_text.strip()}")'
				)
				continue

			# Add https:// if missing
			if not url.startswith(('http://', 'https://')):
				url = 'https://' + url

			found_urls.append(url)

	unique_urls = list(set(found_urls))
	# If multiple URLs found, skip auto-navigation to avoid ambiguity
	if len(unique_urls) > 1:
		logger.debug(f'Multiple URLs found ({len(unique_urls)}), skipping auto-navigation to avoid ambiguity')
		return None

	# If exactly one URL found, return it
	if len(unique_urls) == 1:
		return unique_urls[0]

	return None


async def init_node(state: QAAgentState) -> Dict[str, Any]:
	"""Initialize browser session for the workflow.

	Args:
		state: Current workflow state (may contain start_url or task with URL)

	Returns:
		Dict with browser_session_id and current_url
	"""
	logger.info("INIT: Starting browser session initialization")

	# Get start URL from state if provided, otherwise extract from task (browser-use pattern)
	start_url = state.get("start_url")
	if not start_url:
		task = state.get("task", "")
		if task:
			extracted_url = _extract_url_from_task(task)
			if extracted_url:
				start_url = extracted_url
				logger.info(f"INIT: Extracted URL from task: {start_url}")

	# Create browser session (this connects to kernel-image CDP)
	logger.info(f"INIT: Creating browser session{' with start_url=' + start_url if start_url else ''}")
	session_id, session = await create_browser_session(start_url=start_url)

	logger.info(f"INIT: Browser session created successfully: {session_id}")

	# Get current URL after navigation
	current_url = None
	if start_url:
		try:
			current_url = await session.get_current_page_url()
			logger.info(f"INIT: Navigated to {current_url}")
		except Exception as e:
			logger.warning(f"INIT: Could not get current page URL: {e}")
			current_url = start_url  # Fallback to requested URL

	# Initialize tab tracking for new tab detection (browser-use pattern)
	tab_count = 1  # Start with 1 tab
	previous_tabs = []  # Track tab IDs for comparison
	try:
		browser_state = await session.get_browser_state_summary(include_screenshot=False)
		if browser_state.tabs:
			tab_count = len(browser_state.tabs)
			previous_tabs = [t.target_id for t in browser_state.tabs]  # Track initial tabs
			logger.info(f"INIT: Initial tabs: {tab_count} tabs detected")
	except Exception as e:
		logger.debug(f"Could not get initial tab count: {e}")

	# CRITICAL: Compulsory LLM-driven todo.md creation (browser-use style but mandatory)
	# Use LLM to dynamically parse task and create todo.md structure
	# No hardcoded keywords - LLM intelligently breaks down any task
	task = state.get("task", "")
	file_system_state = None
	
	if task:
		logger.info(f"INIT: Starting todo.md creation for task (length: {len(task)} chars)")
		try:
			from qa_agent.filesystem.file_system import FileSystem
			from qa_agent.utils.llm_task_parser import llm_create_todo_structure
			from qa_agent.llm import get_llm
			from pathlib import Path
			
			# Create FileSystem for this session
			file_system_dir = Path("qa_agent_workspace") / f"session_{session_id[:8]}"
			logger.info(f"INIT: Creating FileSystem at {file_system_dir}")
			file_system = FileSystem(base_dir=file_system_dir, create_default_files=True)
			logger.info(f"INIT: FileSystem created, default files: {file_system.list_files()}")
			
			# Use LLM to dynamically create todo.md structure (compulsory, LLM-driven)
			logger.info("INIT: Calling LLM to create todo.md structure...")
			todo_llm = get_llm()
			logger.info(f"INIT: LLM instance obtained: {type(todo_llm)}")
			
			todo_content = await llm_create_todo_structure(task, todo_llm)
			logger.info(f"INIT: LLM returned todo content (length: {len(todo_content)} chars)")
			logger.debug(f"INIT: Todo content preview: {todo_content[:200]}...")
			
			# Write todo.md using FileSystem
			logger.info("INIT: Writing todo.md to FileSystem...")
			write_result = await file_system.write_file("todo.md", todo_content)
			logger.info(f"INIT: write_file result: {write_result}")
			
			# Verify file was written
			written_content = file_system.get_todo_contents()
			if written_content:
				logger.info(f"INIT: Verified todo.md written (length: {len(written_content)} chars)")
			else:
				logger.error("INIT: CRITICAL - todo.md is empty after write!")
			
			# Save FileSystem state to persist todo.md
			file_system_state = file_system.get_state()
			if file_system_state:
				logger.info(f"INIT: FileSystem state saved (files: {list(file_system_state.files.keys())})")
			else:
				logger.error("INIT: CRITICAL - file_system_state is None!")
			
			step_count = len([line for line in todo_content.split('\n') if line.strip().startswith('- [')])
			logger.info(f"INIT: ✅ LLM created todo.md with {step_count} steps (compulsory, LLM-driven)")
		except Exception as e:
			logger.error(f"INIT: ❌ Failed to create todo.md with LLM: {e}", exc_info=True)
			logger.error(f"INIT: Exception type: {type(e).__name__}, message: {str(e)}")
			# Fallback: create simple todo.md with basic structure (CRITICAL - must not be empty)
			try:
				logger.info("INIT: Attempting fallback todo.md creation...")
				from qa_agent.filesystem.file_system import FileSystem
				from pathlib import Path
				file_system_dir = Path("qa_agent_workspace") / f"session_{session_id[:8]}"
				file_system = FileSystem(base_dir=file_system_dir, create_default_files=True)
				
				# Create a simple todo.md structure as fallback (better than empty)
				# Extract a simple title from task
				task_preview = task[:80].replace('\n', ' ') if task else "Complete the task"
				fallback_todo = f"# Task\n\n## Goal: {task_preview}\n\n## Tasks:\n- [ ] Complete the task\n"
				write_result = await file_system.write_file("todo.md", fallback_todo)
				logger.info(f"INIT: Fallback write_file result: {write_result}")
				
				# Verify fallback was written
				written_content = file_system.get_todo_contents()
				if written_content:
					logger.info(f"INIT: Verified fallback todo.md written (length: {len(written_content)} chars)")
				else:
					logger.error("INIT: CRITICAL - fallback todo.md is empty!")
				
				file_system_state = file_system.get_state()
				if file_system_state:
					logger.warning(f"INIT: ✅ Created fallback todo.md (LLM creation failed: {str(e)[:50]})")
					logger.info(f"INIT: Fallback FileSystem state saved (files: {list(file_system_state.files.keys())})")
				else:
					logger.error("INIT: CRITICAL - fallback file_system_state is None!")
			except Exception as e2:
				logger.error(f"INIT: ❌ Failed to create FileSystem fallback: {e2}", exc_info=True)
				# Last resort: create empty FileSystem (will have default empty todo.md)
				try:
					logger.info("INIT: Attempting last resort FileSystem creation...")
					file_system_dir = Path("qa_agent_workspace") / f"session_{session_id[:8]}"
					file_system = FileSystem(base_dir=file_system_dir, create_default_files=True)
					file_system_state = file_system.get_state()
					if file_system_state:
						logger.error(f"INIT: ⚠️ Created FileSystem with default empty todo.md (last resort)")
						logger.info(f"INIT: Last resort FileSystem state saved (files: {list(file_system_state.files.keys())})")
					else:
						logger.error("INIT: CRITICAL - last resort file_system_state is None!")
				except Exception as e3:
					logger.error(f"INIT: ❌ Complete failure to create FileSystem: {e3}", exc_info=True)
					file_system_state = None
	else:
		logger.warning("INIT: No task provided, skipping todo.md creation")

	return {
		"browser_session_id": session_id,
		"current_url": current_url,
		"tab_count": tab_count,  # Track tab count for new tab detection
		"previous_tabs": previous_tabs,  # Track tab IDs for comparison after actions
		"file_system_state": file_system_state,  # Persist todo.md across nodes
	}
