"""
Error Detection and Extraction Utility

This module provides tools to extract error messages from the DOM and browser state,
enabling intelligent error recovery strategies in the THINK node.

Capabilities:
1. Extract error toasts/notifications
2. Detect validation error messages
3. Parse form field errors
4. Analyze console for errors
5. Classify error types for strategy adaptation
"""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedError:
    """Structured error information extracted from page"""
    error_type: str  # "validation", "permission", "network", "not_found", "already_exists", "generic"
    message: str  # The actual error message
    element_id: Optional[int] = None  # Element that caused error (if click-related)
    field_name: Optional[str] = None  # Form field with error (if form-related)
    severity: str = "medium"  # "low", "medium", "high"
    recovery_hint: Optional[str] = None  # Suggested recovery action


class ErrorDetector:
    """Detect and classify errors from browser state and action results"""

    # Common error message patterns (domain-agnostic, works across websites)
    ERROR_PATTERNS = {
        "already_exists": [
            r"already (?:registered|exists|in use|taken)",
            r"(?:email|username|account) already",
            r"(?:this|the) .{0,20}? is already",
            r"duplicate entry",
            r"already (?:have an account|signed up)",
        ],
        "permission_denied": [
            r"(?:access|permission) denied",
            r"(?:you )?(?:do not have|don't have) (?:permission|access)",
            r"unauthorized",
            r"not (?:authorized|allowed)",
            r"forbidden",
        ],
        "not_found": [
            r"not found",
            r"(?:could not find|doesn't exist|no such)",
            r"404",
            r"page not found",
            r"resource not found",
        ],
        "invalid_input": [
            r"invalid",
            r"(?:must be|should be|is) (?:valid|required|filled)",
            r"(?:please|enter a) (?:valid|correct)",
            r"(?:field is )?required",
            r"(?:must|should) not be empty",
            r"incorrect (?:format|length|pattern)",
        ],
        "network_error": [
            r"network error",
            r"(?:failed to (?:load|connect|fetch)|connection lost)",
            r"(?:unable to|can't) connect",
            r"timeout",
            r"offline",
            r"check your (?:internet|connection)",
        ],
        "server_error": [
            r"(?:server|internal|system) error",
            r"500",
            r"something went wrong",
            r"try again (?:later|in a moment)",
            r"temporarily unavailable",
        ],
    }

    @staticmethod
    def extract_errors_from_dom(browser_state: Any, browser_session: Any = None) -> List[ExtractedError]:
        """
        Extract error messages from the DOM and browser console.

        Analyzes:
        - Browser console errors (via ConsoleWatchdog) - PRIORITY
        - DOM text content for error indicators
        - Common error element selectors (.error, .alert, .invalid, etc.)
        - Validation error messages near form fields
        - Toast/notification messages

        Args:
            browser_state: Browser state with DOM and clickable elements
            browser_session: Browser session for accessing console watchdog (optional)

        Returns:
            List of ExtractedError objects found on the page
        """
        errors = []

        try:
            # ===== 1. PRIORITY: Get errors from Browser Console =====
            # These are real, actionable errors from the page itself
            if browser_session:
                try:
                    console_watchdog = getattr(browser_session, 'console_watchdog', None)
                    if console_watchdog:
                        # Get recent errors from console
                        console_errors = console_watchdog.get_recent_errors(count=10)
                        console_validation_errors = console_watchdog.get_validation_errors()

                        # Process console errors
                        for console_err in console_errors:
                            error_type = ErrorDetector._classify_error_message(console_err.get('text', ''))
                            error = ExtractedError(
                                error_type=error_type,
                                message=console_err.get('text', 'Unknown error')[:200],
                                severity=ErrorDetector._classify_severity(error_type),
                                recovery_hint=ErrorDetector._suggest_recovery(error_type),
                            )
                            errors.append(error)

                        # Process validation errors separately (higher priority)
                        for val_err in console_validation_errors[:3]:  # Top 3
                            error = ExtractedError(
                                error_type="invalid_input",
                                message=val_err.get('text', 'Validation error')[:200],
                                severity="medium",
                                recovery_hint="Correct the invalid input and try again",
                            )
                            # Don't add if duplicate
                            if not any(e.message == error.message for e in errors):
                                errors.append(error)

                        if console_errors or console_validation_errors:
                            logger.info(f"📨 Found {len(console_errors)} console errors + {len(console_validation_errors)} validation errors")

                except Exception as e:
                    logger.debug(f"Could not access console watchdog: {e}")

            # ===== 2. FALLBACK: Get DOM-based errors =====
            # Only if no console errors were found
            if not errors:
                # Get DOM from browser state
                dom = browser_state.dom if hasattr(browser_state, 'dom') else None
                if not dom:
                    logger.debug("No DOM available for error extraction")
                    return errors

                # Extract text content from DOM
                dom_text = ErrorDetector._extract_dom_text(dom)

                # Scan for error patterns
                matched_errors = ErrorDetector._scan_for_error_patterns(dom_text)
                errors.extend(matched_errors)

                # Look for common error elements
                element_errors = ErrorDetector._find_error_elements(dom)
                errors.extend(element_errors)

            logger.info(f"🔍 Error Detection: Found {len(errors)} error(s) on page")
            for error in errors:
                logger.info(f"   - [{error.error_type}] {error.message[:60]}...")

        except Exception as e:
            logger.warning(f"⚠️  Error during error extraction: {e}")

        return errors

    @staticmethod
    def _extract_dom_text(dom: Any) -> str:
        """Extract all text from DOM recursively"""
        try:
            if hasattr(dom, 'text'):
                return dom.text
            elif hasattr(dom, 'get_text'):
                return dom.get_text()
            elif hasattr(dom, 'text_content'):
                return dom.text_content()
            else:
                # Try to convert to string and extract text
                return str(dom)
        except Exception as e:
            logger.warning(f"Could not extract DOM text: {e}")
            return ""

    @staticmethod
    def _scan_for_error_patterns(text: str) -> List[ExtractedError]:
        """Scan text for known error message patterns"""
        errors = []
        text_lower = text.lower()

        # Scan each error type
        for error_type, patterns in ErrorDetector.ERROR_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    # Extract surrounding context (50 chars before and after)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    message = text[start:end].strip()

                    error = ExtractedError(
                        error_type=error_type,
                        message=message,
                        severity=ErrorDetector._classify_severity(error_type),
                        recovery_hint=ErrorDetector._suggest_recovery(error_type),
                    )
                    errors.append(error)

        return errors

    @staticmethod
    def _find_error_elements(dom: Any) -> List[ExtractedError]:
        """Find error elements by common selectors"""
        errors = []

        # Common error element indicators
        error_indicators = [
            'error', 'alert-danger', 'alert-error', 'invalid',
            'validation-error', 'form-error', 'field-error',
            'error-message', 'error-text', 'error-feedback'
        ]

        try:
            # If DOM has clickable elements, try to find errors
            if hasattr(dom, 'clickable_elements'):
                for elem in dom.clickable_elements:
                    elem_class = getattr(elem, 'class_name', '') or ''
                    elem_id = getattr(elem, 'id', '') or ''
                    elem_text = getattr(elem, 'text', '') or ''

                    # Check if element matches error indicators
                    combined = f"{elem_class} {elem_id} {elem_text}".lower()
                    for indicator in error_indicators:
                        if indicator in combined and elem_text.strip():
                            error = ExtractedError(
                                error_type="validation",
                                message=elem_text.strip(),
                                element_id=getattr(elem, 'element_id', None),
                                severity="high",
                                recovery_hint="Fix the validation error",
                            )
                            errors.append(error)
                            break

        except Exception as e:
            logger.warning(f"⚠️  Could not scan for error elements: {e}")

        return errors

    @staticmethod
    def _classify_severity(error_type: str) -> str:
        """Classify error severity for prioritization"""
        severity_map = {
            "permission_denied": "high",
            "network_error": "high",
            "server_error": "high",
            "already_exists": "medium",
            "not_found": "medium",
            "invalid_input": "medium",
        }
        return severity_map.get(error_type, "medium")

    @staticmethod
    def _suggest_recovery(error_type: str) -> Optional[str]:
        """Suggest recovery action based on error type"""
        recovery_map = {
            "already_exists": "Try using a different value or switch to login",
            "permission_denied": "Check your permissions or sign in with appropriate account",
            "not_found": "Navigate to the correct page or verify the URL",
            "invalid_input": "Correct the invalid input and try again",
            "network_error": "Check your internet connection and retry",
            "server_error": "Wait a moment and retry the action",
        }
        return recovery_map.get(error_type)

    @staticmethod
    def extract_errors_from_action_result(action_result: Dict[str, Any]) -> List[ExtractedError]:
        """
        Extract structured error information from action result.

        Checks:
        - error field
        - long_term_memory field
        - extracted_content for error indicators

        Args:
            action_result: ActionResult dict from action execution

        Returns:
            List of ExtractedError objects from the action result
        """
        errors = []

        # Check for explicit error
        error_msg = action_result.get('error')
        if error_msg:
            error_type = ErrorDetector._classify_error_message(error_msg)
            error = ExtractedError(
                error_type=error_type,
                message=error_msg,
                severity=ErrorDetector._classify_severity(error_type),
                recovery_hint=ErrorDetector._suggest_recovery(error_type),
            )
            errors.append(error)

        # Check long_term_memory for errors
        ltm = action_result.get('long_term_memory', '')
        if ltm and any(keyword in ltm.lower() for keyword in ['error', 'failed', 'invalid', 'not found']):
            error_type = ErrorDetector._classify_error_message(ltm)
            error = ExtractedError(
                error_type=error_type,
                message=ltm,
                severity="medium",
                recovery_hint=ErrorDetector._suggest_recovery(error_type),
            )
            errors.append(error)

        # Check extracted_content for error indicators
        extracted = action_result.get('extracted_content', '')
        if extracted:
            # If extracted content looks like an error, classify it
            if any(kw in extracted.lower() for kw in ['error:', 'invalid', 'failed']):
                error_type = ErrorDetector._classify_error_message(extracted)
                error = ExtractedError(
                    error_type=error_type,
                    message=extracted[:200],
                    severity="medium",
                    recovery_hint=ErrorDetector._suggest_recovery(error_type),
                )
                errors.append(error)

        return errors

    @staticmethod
    def _classify_error_message(message: str) -> str:
        """Classify error message to determine error type"""
        message_lower = message.lower()

        # Check against patterns
        for error_type, patterns in ErrorDetector.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return error_type

        # Default classification
        if any(kw in message_lower for kw in ['validation', 'invalid', 'required']):
            return "invalid_input"
        elif any(kw in message_lower for kw in ['permission', 'denied', 'unauthorized']):
            return "permission_denied"
        elif any(kw in message_lower for kw in ['not found', 'not exist']):
            return "not_found"
        elif any(kw in message_lower for kw in ['network', 'connection', 'timeout']):
            return "network_error"
        elif any(kw in message_lower for kw in ['server', 'error', 'failed']):
            return "server_error"

        return "generic"

    @staticmethod
    def has_page_errors(browser_state: Any) -> bool:
        """Quick check: does the page have visible errors?"""
        errors = ErrorDetector.extract_errors_from_dom(browser_state)
        return len(errors) > 0

    @staticmethod
    def get_error_summary(errors: List[ExtractedError]) -> str:
        """Create human-readable summary of errors"""
        if not errors:
            return "No errors detected"

        # Group by error type
        by_type = {}
        for error in errors:
            if error.error_type not in by_type:
                by_type[error.error_type] = []
            by_type[error.error_type].append(error)

        summary_parts = []
        for error_type, type_errors in by_type.items():
            # Get the first message of this type
            first_msg = type_errors[0].message[:80]
            summary_parts.append(f"{error_type}: {first_msg}")

        return " | ".join(summary_parts)
