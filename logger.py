"""
Logging module with configurable log levels.
Supports DEBUG, INFO, WARNING, and ERROR levels.
Log level can be set via LOG_LEVEL environment variable or command-line flag.
Supports file logging for critical errors when running as exe.
"""
import os
import sys
import traceback
from datetime import datetime
from enum import IntEnum
from typing import Optional


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

# File logging support
_log_file: Optional[str] = None
_log_file_handle: Optional[object] = None
_always_log_errors_to_file = False


def set_log_level(level: LogLevel):
    """Set the current log level programmatically."""
    global _current_log_level
    _current_log_level = level


def get_log_level() -> LogLevel:
    """Get the current log level."""
    return _current_log_level


def _write_to_file(message: str):
    """Write message to log file if available."""
    if _log_file_handle:
        try:
            _log_file_handle.write(message)
            _log_file_handle.flush()
        except:
            pass  # Silently fail if file write fails


def set_log_file(log_file: Optional[str], always_log_errors: bool = False):
    """Set log file path. If always_log_errors is True, errors will always be logged to file even if console logging is disabled."""
    global _log_file, _log_file_handle, _always_log_errors_to_file
    
    # Close existing file handle if any
    if _log_file_handle:
        try:
            _log_file_handle.close()
        except:
            pass
        _log_file_handle = None
    
    _log_file = log_file
    _always_log_errors_to_file = always_log_errors
    
    # Open log file if provided
    if _log_file:
        try:
            # Get directory of log file
            log_dir = os.path.dirname(_log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # Open in append mode
            _log_file_handle = open(_log_file, 'a', encoding='utf-8')
            _write_to_file(f"Logging started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception as e:
            print(f"[Logger] Failed to open log file '{_log_file}': {e}", file=sys.stderr)
            _log_file_handle = None
            _log_file = None


def _log(level: LogLevel, message: str, prefix: str = ""):
    """Internal logging function."""
    global _log_file_handle, _log_file, _always_log_errors_to_file
    
    # Track if we've already written to file for this message
    written_to_file = False
    
    # Always log errors to file if enabled, even if console logging is disabled
    if level == LogLevel.ERROR and _always_log_errors_to_file:
        if _log_file_handle:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_msg = f"[{timestamp}] [ERROR] {prefix}: {message}\n" if prefix else f"[{timestamp}] [ERROR] {message}\n"
            _write_to_file(log_msg)
            written_to_file = True
        elif _log_file:
            # File handle not open but we should log errors - try to open it
            try:
                _log_file_handle = open(_log_file, 'a', encoding='utf-8')
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_msg = f"[{timestamp}] [ERROR] {prefix}: {message}\n" if prefix else f"[{timestamp}] [ERROR] {message}\n"
                _write_to_file(log_msg)
                written_to_file = True
            except:
                pass  # Silently fail if we can't open the file
    
    # Console logging (if level is high enough)
    if level >= _current_log_level:
        if prefix:
            log_msg = f"[{prefix}] {message}"
            print(log_msg, file=sys.stderr)
        else:
            print(message, file=sys.stderr)
        
        # Also write to file if file logging is enabled (for all levels, not just errors)
        # But only if we haven't already written it (to avoid duplicates)
        if _log_file_handle and level >= _current_log_level and not written_to_file:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            level_name = level.name
            log_msg = f"[{timestamp}] [{level_name}] {prefix}: {message}\n" if prefix else f"[{timestamp}] [{level_name}] {message}\n"
            _write_to_file(log_msg)


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


def critical_error(message: str, exception: Optional[Exception] = None, prefix: str = "CRITICAL"):
    """Log a critical error with full traceback. Always logged to file if file logging is enabled."""
    global _log_file_handle, _log_file, _always_log_errors_to_file
    
    error_msg = f"{message}"
    if exception:
        error_msg += f"\nException: {type(exception).__name__}: {str(exception)}"
        try:
            tb_str = ''.join(traceback.format_tb(exception.__traceback__))
            error_msg += f"\nTraceback:\n{tb_str}"
        except:
            error_msg += f"\nTraceback: (unable to format)"
    
    # Always log to console at ERROR level (regardless of current log level)
    if prefix:
        log_msg = f"[{prefix}] {error_msg}"
        print(log_msg, file=sys.stderr)
    else:
        print(error_msg, file=sys.stderr)
    
    # Always write critical errors to file if file logging is enabled
    if _log_file_handle:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_msg = f"[{timestamp}] [CRITICAL] {prefix}: {error_msg}\n"
        _write_to_file(full_msg)
    elif _always_log_errors_to_file:
        # If we should always log errors but file handle isn't open, try to open it
        if _log_file:
            try:
                _log_file_handle = open(_log_file, 'a', encoding='utf-8')
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                full_msg = f"[{timestamp}] [CRITICAL] {prefix}: {error_msg}\n"
                _write_to_file(full_msg)
            except:
                pass


def close_log_file():
    """Close the log file handle."""
    global _log_file_handle
    if _log_file_handle:
        try:
            _write_to_file(f"Logging ended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            _log_file_handle.close()
        except:
            pass
        _log_file_handle = None

