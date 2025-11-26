"""
Page Context Analyzer - Detect current page and validate against expectations

Smart page detection that understands:
1. Current page state (URL, title, DOM structure)
2. Expected page from todo.md
3. Mismatches and recovery suggestions
4. Context-aware navigation hints
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
import hashlib

logger = logging.getLogger(__name__)


class PageContextAnalyzer:
	"""Analyze page context to detect current page and todo alignment."""

	def __init__(self, browser_state: Any):
		"""
		Initialize with fresh browser state.

		Args:
			browser_state: BrowserStateSummary from browser_session
		"""
		self.browser_state = browser_state
		self.url = browser_state.url if browser_state else ""
		self.title = browser_state.title if browser_state else ""
		self.dom_elements = self._extract_dom_info(browser_state)
		self.dom_hash = self._calculate_dom_hash(browser_state)

	def _extract_dom_info(self, browser_state: Any) -> Dict[str, Any]:
		"""Extract useful DOM information."""
		if not browser_state or not browser_state.dom_state:
			return {}

		try:
			selector_map = browser_state.dom_state.selector_map or {}
			return {
				"element_count": len(selector_map),
				"element_types": self._get_element_types(selector_map),
				"visible_text_elements": self._extract_text_elements(selector_map),
			}
		except Exception as e:
			logger.debug(f"Could not extract DOM info: {e}")
			return {}

	def _get_element_types(self, selector_map: Dict) -> Dict[str, int]:
		"""Count element types (button, input, link, etc)."""
		types = {}
		for elem_id, elem_info in selector_map.items():
			elem_type = str(elem_info).split("Type:")[1].split("}")[0] if "Type:" in str(elem_info) else "unknown"
			types[elem_type] = types.get(elem_type, 0) + 1
		return types

	def _extract_text_elements(self, selector_map: Dict) -> List[str]:
		"""Extract visible text from buttons, links, labels."""
		texts = []
		for elem_id, elem_info in selector_map.items():
			elem_str = str(elem_info).lower()
			# Extract text hints from element descriptions
			if "login" in elem_str or "sign in" in elem_str:
				texts.append("login")
			if "submit" in elem_str or "next" in elem_str:
				texts.append("submit")
			if "email" in elem_str or "username" in elem_str:
				texts.append("email_field")
			if "password" in elem_str:
				texts.append("password_field")
			if "search" in elem_str:
				texts.append("search")
		return list(set(texts))  # Unique

	def _calculate_dom_hash(self, browser_state: Any) -> str:
		"""
		Calculate hash of DOM structure.
		Used to detect if page changed without URL change.
		"""
		try:
			if not browser_state or not browser_state.dom_state:
				return ""

			selector_map = browser_state.dom_state.selector_map or {}
			# Hash based on number of elements and types
			signature = f"{len(selector_map)}_{self._get_element_types(selector_map)}"
			return hashlib.md5(signature.encode()).hexdigest()[:8]
		except:
			return ""

	def get_page_signature(self) -> Dict[str, Any]:
		"""
		Get current page signature for comparison.

		Returns:
			Dict with: url, title, dom_hash, element_count, key_elements
		"""
		return {
			"url": self.url,
			"title": self.title,
			"dom_hash": self.dom_hash,
			"element_count": self.dom_elements.get("element_count", 0),
			"key_elements": self.dom_elements.get("visible_text_elements", []),
		}

	def infer_current_page(self) -> str:
		"""
		Intelligently infer page type using DYNAMIC structural analysis.

		Uses:
		1. URL path segments (flexible pattern matching)
		2. Page title hints
		3. DOM structure analysis (element presence, not hardcoded keywords)
		4. Form fields presence

		Returns:
			Page type description based on detected pattern
		"""
		url_lower = self.url.lower()
		title_lower = self.title.lower()
		element_types = self.dom_elements.get("element_types", {})
		visible_elements = self.dom_elements.get("visible_text_elements", [])
		element_count = self.dom_elements.get("element_count", 0)

		# ===== DYNAMIC URL PATH ANALYSIS =====
		# Extract path segments (work on any URL structure)
		from urllib.parse import urlparse
		try:
			path = urlparse(self.url).path.lower()
			path_segments = [s for s in path.split("/") if s]  # Remove empty segments
		except:
			path_segments = []

		# Analyze path semantics
		# Keywords indicate page purpose (not hardcoded - just semantic hints)
		page_indicators = {
			"auth_keywords": ["login", "signin", "sign-in", "auth", "authenticate", "account/login"],
			"registration_keywords": ["signup", "sign-up", "register", "registration", "join"],
			"search_keywords": ["search", "query", "find"],
			"checkout_keywords": ["checkout", "cart", "payment", "order", "purchase"],
			"profile_keywords": ["profile", "account", "user", "settings", "preferences"],
			"dashboard_keywords": ["dashboard", "home", "main", "app", "admin"],
		}

		matched_page_type = None

		# Check URL path for semantic keywords
		for page_type, keywords in page_indicators.items():
			for segment in path_segments:
				if any(kw in segment for kw in keywords):
					matched_page_type = page_type.replace("_keywords", "")
					break
			if matched_page_type:
				break

		# ===== DYNAMIC DOM STRUCTURE ANALYSIS =====
		# Analyze DOM composition (no hardcoded expectations)

		# Form field detection (language-agnostic)
		has_password_field = "password" in visible_elements
		has_email_field = "email_field" in visible_elements
		has_username_field = "username" in visible_elements
		has_address_field = "address" in visible_elements
		has_payment_field = "payment" in visible_elements
		has_search_field = "search" in visible_elements

		# Button/interaction detection
		input_count = element_types.get("input", 0)
		button_count = element_types.get("button", 0)
		form_count = element_types.get("form", 0)
		link_count = element_types.get("a", 0)

		# ===== DYNAMIC PAGE TYPE INFERENCE =====

		# If URL matched a page type, validate with DOM structure
		if matched_page_type == "auth":
			# Validate: should have email + password + login button
			if (has_email_field or has_username_field) and has_password_field and button_count > 0:
				return "login"
			# Could be signup instead if more input fields
			if input_count > 3 and button_count > 0:
				return "signup"
			return "auth_page"  # Generic auth

		if matched_page_type == "registration":
			return "signup"

		if matched_page_type == "search":
			return "search"

		if matched_page_type == "checkout":
			# Validate: should have email/address + payment + submit
			if (has_email_field or has_address_field or has_payment_field):
				return "checkout"
			return "commerce_page"

		if matched_page_type == "profile":
			return "profile"

		if matched_page_type == "dashboard":
			return "dashboard"

		# ===== FALLBACK: INFER FROM DOM STRUCTURE ONLY =====
		# When URL doesn't give clear hints, analyze DOM patterns

		# Login/Auth page pattern: email + password + submit button
		if (has_email_field or has_username_field) and has_password_field:
			return "login"

		# Signup page pattern: multiple input fields + email/password
		if input_count >= 3 and (has_email_field or has_password_field):
			return "signup"

		# Checkout page pattern: address + email + payment options
		if has_address_field or has_payment_field:
			return "checkout"

		# Search page pattern: search field + results
		if has_search_field and element_count > 10:
			return "search"

		# Form page pattern: multiple inputs
		if form_count > 0 and input_count >= 2:
			return "form_page"

		# Rich content page: many links and text
		if link_count > 10 and element_count > 20:
			return "content_page"

		# Home/main page: balanced mix of elements
		if element_count >= 5 and link_count >= 3 and button_count >= 2:
			return "main_page"

		# Empty or minimal page
		if element_count < 5:
			return "simple_page"

		return "unknown"

	def validate_against_todo_step(self, current_step_text: str) -> Tuple[bool, str]:
		"""
		Dynamically validate if current page matches todo step.

		Uses semantic analysis:
		1. Extract action keywords from step text
		2. Detect required page types for those actions
		3. Check if current page has required element types
		4. Return validation result with reason

		Args:
			current_step_text: Current todo step (e.g., "Enter email on login page")

		Returns:
			(is_valid, reason) - (bool, str)
		"""
		step_lower = current_step_text.lower()
		inferred_page = self.infer_current_page()
		key_elements = self.dom_elements.get("visible_text_elements", [])
		element_types = self.dom_elements.get("element_types", {})

		# ===== DYNAMIC ACTION EXTRACTION =====
		# Extract actions from step text (not hardcoded)
		step_actions = []

		action_keywords = {
			"login": ["login", "sign in", "signin", "authenticate"],
			"signup": ["signup", "sign up", "register", "create account", "join"],
			"email": ["email", "enter email", "type email", "fill email"],
			"password": ["password", "enter password", "type password"],
			"search": ["search", "find", "query"],
			"checkout": ["checkout", "purchase", "pay", "submit order"],
			"profile": ["profile", "account", "settings"],
			"navigate": ["go to", "navigate to", "visit"],
		}

		for action_name, keywords in action_keywords.items():
			if any(kw in step_lower for kw in keywords):
				step_actions.append(action_name)

		# ===== DYNAMIC PAGE TYPE MAPPING =====
		# Map actions to expected page types (semantic, not hardcoded)
		action_to_page_patterns = {
			"login": ["login", "auth_page"],
			"signup": ["signup", "auth_page", "registration"],
			"email": ["login", "signup", "checkout", "profile", "form_page"],
			"password": ["login", "signup", "auth_page"],
			"search": ["search", "main_page", "content_page"],
			"checkout": ["checkout", "commerce_page"],
			"profile": ["profile", "dashboard"],
			"navigate": None,  # Navigate can go anywhere
		}

		# Get expected pages based on detected actions
		expected_pages = set()
		for action in step_actions:
			if action in action_to_page_patterns:
				page_patterns = action_to_page_patterns[action]
				if page_patterns:
					expected_pages.update(page_patterns)

		# ===== VALIDATION LOGIC =====

		# Special case: "navigate" action can happen on any page
		if "navigate" in step_actions and len(step_actions) == 1:
			return True, f"✅ Navigation action can be performed from any page"

		# If we detected actions, validate page match
		if expected_pages:
			if inferred_page in expected_pages:
				return True, f"✅ On correct page for '{', '.join(step_actions)}': {inferred_page}"

		# ===== FALLBACK: CHECK FOR REQUIRED ELEMENT TYPES =====
		# Don't rely only on page type, check for actual elements needed

		element_availability = {
			"email": "email_field" in key_elements,
			"password": "password_field" in key_elements,
			"search": "search" in key_elements,
			"address": "address_field" in key_elements,
			"payment": "payment_field" in key_elements,
			"username": "username" in key_elements,
		}

		# Check if required elements for actions are present
		required_elements_present = []
		for action in step_actions:
			if action in element_availability:
				if element_availability[action]:
					required_elements_present.append(action)

		# If we found elements for our actions, validation passes
		if required_elements_present:
			return True, f"✅ Found required elements: {', '.join(required_elements_present)}"

		# ===== ADDITIONAL SEMANTIC VALIDATION =====
		# Some actions can happen on multiple page types
		# Check if page structure supports the action

		# Email action can be on any form page
		if "email" in step_actions and element_types.get("form", 0) > 0:
			return True, f"✅ Form page detected, can enter email"

		# Checkout/payment actions on commerce pages
		if "checkout" in step_actions and (element_types.get("payment", 0) > 0 or element_types.get("form", 0) > 1):
			return True, f"✅ Commerce page detected, can checkout"

		# Search action on pages with search elements
		if "search" in step_actions and element_types.get("input", 0) > 0:
			return True, f"✅ Page has input elements for search"

		# ===== MISMATCH DETECTION =====
		# If none of the above matched, return mismatch
		mismatch_reason = f"⚠️  Page mismatch for action(s): {', '.join(step_actions or ['unknown'])}"
		mismatch_reason += f"\n   Expected page types: {', '.join(expected_pages) if expected_pages else 'any'}"
		mismatch_reason += f"\n   Current page: {inferred_page}"

		return False, mismatch_reason

	def suggest_recovery(self, current_step: str, last_action: Optional[str] = None) -> Optional[str]:
		"""
		Dynamically suggest recovery strategy when on wrong page.

		Analyzes:
		1. Current page type
		2. Expected page for the action
		3. Common navigation patterns
		4. Previous action (if available)

		Args:
			current_step: Current todo step text
			last_action: Last executed action (optional context)

		Returns:
			Suggested recovery action, or None if no action needed
		"""
		is_valid, reason = self.validate_against_todo_step(current_step)

		if is_valid:
			return None  # No recovery needed

		current_page = self.infer_current_page()
		step_lower = current_step.lower()

		# ===== DYNAMIC ACTION EXTRACTION FROM STEP =====
		# Determine what action the step is trying to do
		action_to_page = {
			"login": "login",
			"signin": "login",
			"sign in": "login",
			"signup": "signup",
			"register": "signup",
			"search": "search",
			"checkout": "checkout",
			"purchase": "checkout",
			"profile": "profile",
		}

		target_page = None
		for action_keyword, page_type in action_to_page.items():
			if action_keyword in step_lower:
				target_page = page_type
				break

		# ===== GENERATE RECOVERY STRATEGY =====

		# If we identified a target page, suggest navigation
		if target_page:
			if current_page == target_page:
				return None  # Already on correct page

			# Different strategies for different pages
			if target_page == "login" and current_page in ["home", "main_page", "signup"]:
				return "Navigate back to login page (look for 'login', 'sign in', or '/login' in navigation)"

			elif target_page == "signup" and current_page in ["home", "main_page", "login"]:
				return "Navigate to signup page (look for 'sign up', 'register', or '/signup' in navigation)"

			elif target_page == "search" and current_page in ["home", "main_page", "dashboard"]:
				return "Navigate to or open search (look for search box or '/search' page)"

			elif target_page == "checkout" and current_page in ["main_page", "home", "content_page"]:
				return "Navigate to checkout (look for cart or checkout button)"

			elif target_page == "profile" and current_page in ["dashboard", "main_page"]:
				return "Navigate to profile page (look for profile link in menu or settings)"

			else:
				# Generic suggestion based on current and target pages
				return f"Navigate from '{current_page}' to '{target_page}' page"

		# ===== FALLBACK: SUGGEST BASED ON LAST ACTION =====
		# If no target page identified, suggest recovery based on context
		if last_action:
			if "click" in last_action.lower() and current_page in ["unknown", "simple_page"]:
				return "Last click may have failed or navigated unexpectedly. Try clicking the target element again or navigate back."

		# ===== GENERIC RECOVERY =====
		# As last resort, suggest page navigation based on common patterns
		if current_page == "unknown":
			return "Cannot determine current page. Try navigating to the home page or starting fresh."

		return f"Currently on '{current_page}' page. For action '{step_lower[:50]}...', may need to navigate to appropriate page."


def compare_dom_states(before: Any, after: Any) -> Dict[str, Any]:
	"""
	Compare two DOM states to detect changes.

	Args:
		before: BrowserStateSummary before action
		after: BrowserStateSummary after action

	Returns:
		Dict with: page_changed, url_changed, dom_hash_changed, elements_added, elements_removed
	"""
	try:
		before_analyzer = PageContextAnalyzer(before)
		after_analyzer = PageContextAnalyzer(after)

		before_sig = before_analyzer.get_page_signature()
		after_sig = after_analyzer.get_page_signature()

		return {
			"page_changed": before_sig["url"] != after_sig["url"],
			"url_changed": before_sig["url"] != after_sig["url"],
			"dom_hash_changed": before_sig["dom_hash"] != after_sig["dom_hash"],
			"elements_added": after_sig["element_count"] > before_sig["element_count"],
			"elements_removed": after_sig["element_count"] < before_sig["element_count"],
			"before_page": before_analyzer.infer_current_page(),
			"after_page": after_analyzer.infer_current_page(),
			"before_elements": before_sig["element_count"],
			"after_elements": after_sig["element_count"],
		}
	except Exception as e:
		logger.error(f"Error comparing DOM states: {e}")
		return {"error": str(e)}
