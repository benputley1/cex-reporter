"""
Logging Utility Module

Provides structured logging setup with JSON formatting, file rotation,
and configurable log levels.
"""

import logging
import logging.handlers
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Formats log records as JSON for easy parsing and analysis.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.

        Args:
            record: Log record to format

        Returns:
            JSON formatted log string
        """
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """
    Custom console formatter with color support.

    Provides human-readable colored output for console logging.
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors for console output.

        Args:
            record: Log record to format

        Returns:
            Formatted log string with colors
        """
        # Get color for log level
        color = self.COLORS.get(record.levelname, '')

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')

        # Build log message
        log_parts = [
            f"{color}{record.levelname}{self.RESET}",
            f"[{timestamp}]",
            f"{record.name}:",
            record.getMessage(),
        ]

        log_line = " ".join(log_parts)

        # Add exception if present
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)

        return log_line


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
    log_file: str = "cex_reporter.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    json_format: bool = True,
    console_output: bool = True,
) -> logging.Logger:
    """
    Setup structured logging with file rotation and console output.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (default: ./logs)
        log_file: Name of log file
        max_bytes: Maximum size of log file before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        json_format: Use JSON formatting for file logs (default: True)
        console_output: Enable console logging (default: True)

    Returns:
        Configured root logger
    """
    # Get root logger
    root_logger = logging.getLogger()

    # Set log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Setup file handler with rotation
    if log_dir:
        log_path = Path(log_dir)
    else:
        # Use LOG_DIR environment variable or default to 'logs'
        import os
        log_path = Path(os.getenv('LOG_DIR', 'logs'))

    # Create log directory if it doesn't exist
    log_path.mkdir(parents=True, exist_ok=True)

    log_file_path = log_path / log_file

    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    file_handler.setLevel(numeric_level)

    # Set formatter for file handler
    if json_format:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )

    root_logger.addHandler(file_handler)

    # Setup console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console_handler)

    # Log initialization message
    root_logger.info(
        f"Logging initialized at {log_level} level. "
        f"Log file: {log_file_path}"
    )

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Name for the logger (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom logger adapter for adding context to log messages.

    Allows adding extra fields to all log messages from this logger.
    """

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Process log message to add extra fields.

        Args:
            msg: Log message
            kwargs: Additional keyword arguments

        Returns:
            Tuple of (message, kwargs)
        """
        # Add extra fields to log record
        if 'extra' not in kwargs:
            kwargs['extra'] = {}

        if hasattr(self, 'extra') and self.extra:
            kwargs['extra']['extra_fields'] = self.extra

        return msg, kwargs


def get_contextual_logger(name: str, **context) -> LoggerAdapter:
    """
    Get a logger with additional context fields.

    Args:
        name: Logger name
        **context: Additional context fields to add to all log messages

    Returns:
        LoggerAdapter with context

    Example:
        logger = get_contextual_logger(__name__, exchange='mexc', user_id=123)
        logger.info("Trade executed")  # Will include exchange and user_id
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, context)


def setup_from_config():
    """
    Setup logging from configuration settings.

    Reads configuration from config.settings and initializes logging.
    """
    try:
        from config.settings import settings

        setup_logging(
            log_level=settings.log_level,
            log_dir="logs",
            log_file="cex_reporter.log",
            max_bytes=10 * 1024 * 1024,  # 10MB
            backup_count=5,
            json_format=True,
            console_output=True,
        )

    except ImportError:
        # Fallback to default settings if config not available
        setup_logging(
            log_level="INFO",
            log_dir="logs",
            log_file="cex_reporter.log",
        )


# Convenience function to log with structured data
def log_with_data(
    logger: logging.Logger,
    level: str,
    message: str,
    **data: Any
) -> None:
    """
    Log message with additional structured data.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **data: Additional data fields to include in log

    Example:
        log_with_data(
            logger, 'info',
            'Trade executed',
            exchange='mexc',
            symbol='ALKIMI',
            amount=1000
        )
    """
    log_method = getattr(logger, level.lower())
    log_method(message, extra={'extra_fields': data})
