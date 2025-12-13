"""
Error Classifier Module

Provides intelligent error classification and user-friendly messaging
with actionable recovery suggestions.
"""

import re
from typing import Tuple, Optional
from enum import Enum
from src.utils import get_logger

logger = get_logger(__name__)


class ErrorType(Enum):
    """Error type classifications."""
    API_ERROR = "APIError"
    AUTH_ERROR = "AuthError"
    RATE_LIMIT_ERROR = "RateLimitError"
    DATA_ERROR = "DataError"
    TIMEOUT_ERROR = "TimeoutError"
    UNKNOWN_ERROR = "UnknownError"


# Mapping of error types to user-friendly messages and recovery suggestions
ERROR_MESSAGES = {
    ErrorType.API_ERROR: (
        "Exchange API is temporarily unavailable",
        "Try again in a few minutes or check if the exchange is experiencing issues"
    ),
    ErrorType.AUTH_ERROR: (
        "Authentication failed",
        "Contact admin to check API keys and permissions"
    ),
    ErrorType.RATE_LIMIT_ERROR: (
        "Too many requests",
        "Wait a moment and try again. Consider reducing query frequency"
    ),
    ErrorType.DATA_ERROR: (
        "Data not found or invalid",
        "Check your query parameters, date ranges, or exchange names"
    ),
    ErrorType.TIMEOUT_ERROR: (
        "Request timed out",
        "Try a simpler query or reduce the date range"
    ),
    ErrorType.UNKNOWN_ERROR: (
        "Something went wrong",
        "Try rephrasing your question or use `/alkimi help` for examples"
    ),
}


class ErrorClassifier:
    """
    Classifies exceptions into user-friendly error categories.

    Examines exception types and messages to determine the most
    appropriate error category and provides actionable guidance.
    """

    # Patterns for error classification
    API_ERROR_PATTERNS = [
        r"api.*error",
        r"exchange.*unavailable",
        r"service.*unavailable",
        r"connection.*failed",
        r"network.*error",
        r"http.*error",
        r"502|503|504",  # HTTP error codes
        r"bad gateway",
        r"gateway timeout",
    ]

    AUTH_ERROR_PATTERNS = [
        r"auth.*failed",
        r"authentication",
        r"permission.*denied",
        r"unauthorized",
        r"invalid.*key",
        r"invalid.*credentials",
        r"api.*key",
        r"401|403",  # HTTP status codes
    ]

    RATE_LIMIT_PATTERNS = [
        r"rate.*limit",
        r"too.*many.*requests",
        r"429",  # HTTP status code
        r"throttle",
        r"exceeded.*limit",
    ]

    DATA_ERROR_PATTERNS = [
        r"not.*found",
        r"no.*data",
        r"empty.*result",
        r"invalid.*parameter",
        r"missing.*data",
        r"404",  # HTTP status code
        r"does.*not.*exist",
        r"no.*such",
    ]

    TIMEOUT_ERROR_PATTERNS = [
        r"timeout",
        r"timed.*out",
        r"connection.*timeout",
        r"read.*timeout",
        r"408",  # HTTP status code
    ]

    def __init__(self):
        """Initialize the error classifier."""
        # Compile patterns for efficiency
        self.api_error_regex = self._compile_patterns(self.API_ERROR_PATTERNS)
        self.auth_error_regex = self._compile_patterns(self.AUTH_ERROR_PATTERNS)
        self.rate_limit_regex = self._compile_patterns(self.RATE_LIMIT_PATTERNS)
        self.data_error_regex = self._compile_patterns(self.DATA_ERROR_PATTERNS)
        self.timeout_error_regex = self._compile_patterns(self.TIMEOUT_ERROR_PATTERNS)

    @staticmethod
    def _compile_patterns(patterns: list) -> re.Pattern:
        """
        Compile list of patterns into single regex.

        Args:
            patterns: List of regex patterns

        Returns:
            Compiled regex pattern
        """
        combined = "|".join(f"({pattern})" for pattern in patterns)
        return re.compile(combined, re.IGNORECASE)

    def classify_error(self, exception: Exception) -> ErrorType:
        """
        Classify an exception into an error type.

        Args:
            exception: Exception to classify

        Returns:
            ErrorType classification
        """
        # Get exception type name and message
        exc_type = type(exception).__name__
        exc_message = str(exception).lower()

        # Combine for matching
        error_text = f"{exc_type} {exc_message}"

        # Log the original error for debugging
        logger.debug(f"Classifying error: {exc_type}: {exc_message}")

        # Check patterns in order of specificity
        if self.auth_error_regex.search(error_text):
            logger.debug("Classified as AUTH_ERROR")
            return ErrorType.AUTH_ERROR

        if self.rate_limit_regex.search(error_text):
            logger.debug("Classified as RATE_LIMIT_ERROR")
            return ErrorType.RATE_LIMIT_ERROR

        if self.timeout_error_regex.search(error_text):
            logger.debug("Classified as TIMEOUT_ERROR")
            return ErrorType.TIMEOUT_ERROR

        if self.data_error_regex.search(error_text):
            logger.debug("Classified as DATA_ERROR")
            return ErrorType.DATA_ERROR

        if self.api_error_regex.search(error_text):
            logger.debug("Classified as API_ERROR")
            return ErrorType.API_ERROR

        # Check exception types directly
        if "timeout" in exc_type.lower():
            logger.debug("Classified as TIMEOUT_ERROR (by type)")
            return ErrorType.TIMEOUT_ERROR

        if any(keyword in exc_type.lower() for keyword in ["connection", "network", "http"]):
            logger.debug("Classified as API_ERROR (by type)")
            return ErrorType.API_ERROR

        if any(keyword in exc_type.lower() for keyword in ["permission", "auth"]):
            logger.debug("Classified as AUTH_ERROR (by type)")
            return ErrorType.AUTH_ERROR

        # Default to unknown error
        logger.debug("Classified as UNKNOWN_ERROR (default)")
        return ErrorType.UNKNOWN_ERROR

    def get_user_message(self, error_type: ErrorType) -> Tuple[str, str]:
        """
        Get user-friendly message and suggestion for error type.

        Args:
            error_type: Type of error

        Returns:
            Tuple of (error_message, suggestion)
        """
        return ERROR_MESSAGES.get(
            error_type,
            ERROR_MESSAGES[ErrorType.UNKNOWN_ERROR]
        )

    def format_error_response(
        self,
        exception: Exception,
        preserve_details: bool = False
    ) -> Tuple[str, str]:
        """
        Format a complete error response for users.

        Args:
            exception: Exception to format
            preserve_details: If True, include original error in message

        Returns:
            Tuple of (user_message, suggestion)
        """
        # Classify the error
        error_type = self.classify_error(exception)

        # Get user-friendly message
        user_message, suggestion = self.get_user_message(error_type)

        # Optionally preserve technical details for debugging
        if preserve_details:
            technical_details = f"\n\nTechnical details: {type(exception).__name__}: {str(exception)}"
            user_message += technical_details

        return user_message, suggestion


# Global instance for convenience
_classifier = None


def get_classifier() -> ErrorClassifier:
    """
    Get or create the global error classifier instance.

    Returns:
        ErrorClassifier instance
    """
    global _classifier
    if _classifier is None:
        _classifier = ErrorClassifier()
    return _classifier


def classify_error(exception: Exception) -> ErrorType:
    """
    Convenience function to classify an error.

    Args:
        exception: Exception to classify

    Returns:
        ErrorType classification
    """
    return get_classifier().classify_error(exception)


def format_error_response(
    exception: Exception,
    preserve_details: bool = False
) -> Tuple[str, str]:
    """
    Convenience function to format an error response.

    Args:
        exception: Exception to format
        preserve_details: If True, include original error in message

    Returns:
        Tuple of (user_message, suggestion)
    """
    return get_classifier().format_error_response(exception, preserve_details)
