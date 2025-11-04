"""
Logging module with configurable log levels.
Supports DEBUG, INFO, WARNING, and ERROR levels.
Log level can be set via LOG_LEVEL environment variable.
"""
import os
import sys
from enum import IntEnum


class LogLevel(IntEnum):
    """Log level enumeration."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    NONE = 4  # No logging


# Default log level (can be overridden by environment variable)
_DEFAULT_LOG_LEVEL = LogLevel.WARNING

# Get log level from environment variable or use default
_log_level_str = os.environ.get('LOG_LEVEL', '').upper()
_current_log_level = _DEFAULT_LOG_LEVEL

if _log_level_str:
    try:
        _current_log_level = LogLevel[_log_level_str]
    except KeyError:
        # Invalid log level, use default
        print(f"[Logger] Invalid LOG_LEVEL '{_log_level_str}', using default: {_DEFAULT_LOG_LEVEL.name}", 
              file=sys.stderr)


def set_log_level(level: LogLevel):
    """Set the current log level programmatically."""
    global _current_log_level
    _current_log_level = level


def get_log_level() -> LogLevel:
    """Get the current log level."""
    return _current_log_level


def _log(level: LogLevel, message: str, prefix: str = ""):
    """Internal logging function."""
    if level >= _current_log_level:
        if prefix:
            print(f"[{prefix}] {message}", file=sys.stderr)
        else:
            print(message, file=sys.stderr)


def debug(message: str, prefix: str = ""):
    """Log a DEBUG message."""
    _log(LogLevel.DEBUG, message, prefix)


def info(message: str, prefix: str = ""):
    """Log an INFO message."""
    _log(LogLevel.INFO, message, prefix)


def warning(message: str, prefix: str = ""):
    """Log a WARNING message."""
    _log(LogLevel.WARNING, message, prefix)


def error(message: str, prefix: str = ""):
    """Log an ERROR message."""
    _log(LogLevel.ERROR, message, prefix)

