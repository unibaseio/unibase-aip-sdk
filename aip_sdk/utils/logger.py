"""Structured logging for Unibase Framework."""
import logging
import sys
from typing import Optional
from functools import lru_cache


class UnibaseLogger:
    """Centralized logger for the framework with consistent formatting."""

    def __init__(self, name: str, level: int = logging.INFO):
        """Initialize logger with given name and level."""
        self.logger = logging.getLogger(f"unibase.{name}")
        self.logger.setLevel(level)

        # Only add handler if none exists (avoid duplicate handlers)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(level)

            # Consistent formatting across all loggers
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def debug(self, msg: str, **kwargs):
        """Log debug message."""
        self.logger.debug(msg, extra=kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message."""
        self.logger.info(msg, extra=kwargs)

    def warning(self, msg: str, exc_info: bool = False, **kwargs):
        """Log warning message."""
        self.logger.warning(msg, exc_info=exc_info, extra=kwargs)

    def error(self, msg: str, exc_info: bool = False, **kwargs):
        """Log error message."""
        self.logger.error(msg, exc_info=exc_info, extra=kwargs)

    def critical(self, msg: str, **kwargs):
        """Log critical message."""
        self.logger.critical(msg, extra=kwargs)

    def exception(self, msg: str, **kwargs):
        """Log exception message with traceback."""
        self.logger.exception(msg, extra=kwargs)


@lru_cache(maxsize=None)
def get_logger(name: str, level: int = logging.INFO) -> UnibaseLogger:
    """Get or create a logger for a module."""
    return UnibaseLogger(name, level)


def set_log_level(level: int):
    """Set log level for all Unibase loggers."""
    logging.getLogger("unibase").setLevel(level)
