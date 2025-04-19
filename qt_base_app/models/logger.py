import logging
import sys
import re
# REMOVED: import os
# REMOVED: import inspect
from pathlib import Path
from typing import Optional, Any, Dict

# REMOVED: Dependency on SettingsManager
# from .settings_manager import SettingsManager

def _sanitize_filename(name: str) -> str:
    """Removes invalid characters for filenames."""
    # Remove characters not allowed in common filesystems
    # Use raw string and single backslash for literal backslash in character class
    sanitized = re.sub(r'[\/*?:"<>|]', "", name)
    # Replace potential leading/trailing dots or spaces
    sanitized = sanitized.strip(". ")
    if not sanitized: # Handle case where name becomes empty
        sanitized = "app" # Default if title is invalid/empty
    return sanitized

class Logger:
    """
    Singleton class for application-wide logging.

    Reads configuration from the YAML file loaded via SettingsManager:
    - logging.level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO.
    - logging.log_to_file: Boolean, whether to log to a file. Default: True.
    - logging.log_to_console: Boolean, whether to print logs to stdout. Default: True.
    - logging.clear_on_startup: Boolean, whether to clear the log file on app start. Default: True.
    - app.title: Used for the log filename. Default: 'Application'.

    Log file is created in the project root (dev) or executable directory (built).
    Filename format: [app_title].log
    """
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None # Store the configured logger instance

    _log_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARN': logging.WARNING,
        'ERROR': logging.ERROR
    }

    @classmethod
    def instance(cls) -> 'Logger':
        """Get the singleton instance of Logger. Configuration must be called separately."""
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance._initialized = False # Set flag immediately after creation
            # REMOVED: cls._instance._configure() # Configuration is now explicit
        return cls._instance

    def __init__(self):
        """Prevent direct instantiation or re-initialization after the singleton is created."""
        # This check now primarily prevents direct calls to __init__ after instance exists
        if Logger._instance is not None and Logger._instance._initialized:
            raise RuntimeError("Use Logger.instance() to get the logger, configuration already done.")
        # REMOVED: self._initialized = False # Moved to instance()

    def configure(self, config: Dict[str, Any]):
        """Configures the logger based on the provided config dictionary."""
        if self._initialized: # Check if already configured
             print("[Logger] Logger already configured. Skipping reconfiguration.") # Updated message
             return
        self._configure(config)
        self._initialized = True # Mark as configured

    def _configure(self, config: Dict[str, Any]): # Changed signature
        """Internal method to configure logger from config dict."""
        if self._logger is not None:
            return
        try:
            # Read Configuration from the passed dictionary
            logging_config = config.get('logging', {}) # Get the logging section
            app_config = config.get('app', {})       # Get the app section

            log_level_str = logging_config.get('level', 'INFO').upper()
            log_to_file = logging_config.get('log_to_file', True)
            log_to_console = logging_config.get('log_to_console', True)
            clear_on_startup = logging_config.get('clear_on_startup', True)
            app_title = app_config.get('title', 'Application') # Get title from app section

            # Determine Log Level
            log_level = self._log_levels.get(log_level_str, logging.INFO)

            # Setup Logger instance
            logger_instance = logging.getLogger(app_title)
            logger_instance.setLevel(log_level)
            logger_instance.propagate = False

            # Prevent adding handlers multiple times (redundant due to singleton check, but safe)
            if logger_instance.hasHandlers():
                 print("[Logger] Logger already configured, skipping handler setup.")
                 self._logger = logger_instance # Ensure self._logger is set
                 return

            # Define Formatters
            file_log_format = '[%(asctime)s-%(levelname)-5s][%(caller)s]%(message)s'
            console_log_format = '[%(levelname)-5s][%(caller)s]%(message)s' # No timestamp
            date_format = '%Y-%m-%d %H:%M:%S'
            
            file_formatter = logging.Formatter(file_log_format, datefmt=date_format)
            console_formatter = logging.Formatter(console_log_format)

            # Configure File Handler
            if log_to_file:
                try:
                    if getattr(sys, 'frozen', False):
                        log_dir = Path(sys.executable).parent
                    else:
                        log_dir = Path.cwd()

                    log_filename = f"{_sanitize_filename(app_title)}.log"
                    log_file_path = log_dir / log_filename
                    filemode = 'w' if clear_on_startup else 'a'

                    file_handler = logging.FileHandler(log_file_path, mode=filemode, encoding='utf-8')
                    file_handler.setFormatter(file_formatter) # Use file formatter
                    logger_instance.addHandler(file_handler)
                    # Keep internal setup print simple
                    print(f"[File Logger] Logging to file: {log_file_path}") 
                except Exception as e:
                    print(f"[File Logger Error] Error setting up file logger: {e}", file=sys.stderr)

            # Configure Console Handler
            if log_to_console:
                try:
                    console_handler = logging.StreamHandler(sys.stdout)
                    console_handler.setFormatter(console_formatter) # Use console formatter
                    logger_instance.addHandler(console_handler)
                    # Keep internal setup print simple
                    print(f"[Console Logger] Logging to console enabled") 
                except Exception as e:
                    print(f"[Console Logger Error] Error setting up console logger: {e}", file=sys.stderr)

            # Store the configured logger
            self._logger = logger_instance
            # Log initialization message using the logger itself (will use configured formatters)
            self._logger.info(f"--- Logger Initialized (Level: {log_level_str}) ---", extra={'caller': 'logger'})

        except Exception as e:
            print(f"[FATAL ERROR] Configuring logger: {e}", file=sys.stderr)
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
            self._logger = logging.getLogger("FallbackLogger")
            self._logger.error(f"Logger configuration failed: {e}", exc_info=True)

    # --- Public Logging Methods (Modified Signatures) ---

    def debug(self, caller: str, msg: str, *args, **kwargs):
        """Logs a DEBUG message, prepended with the caller name."""
        if not self._initialized or self._logger is None:
            print(f"[Logger Not Configured] DEBUG from {caller}: {msg}", file=sys.stderr)
            return
        self._logger.debug(msg, *args, extra={'caller': caller}, **kwargs)

    def info(self, caller: str, msg: str, *args, **kwargs):
        """Logs an INFO message, prepended with the caller name."""
        if not self._initialized or self._logger is None:
            print(f"[Logger Not Configured] INFO from {caller}: {msg}", file=sys.stderr)
            return
        self._logger.info(msg, *args, extra={'caller': caller}, **kwargs)

    def warn(self, caller: str, msg: str, *args, **kwargs):
        """Logs a WARNING message (as WARN), prepended with the caller name."""
        if not self._initialized or self._logger is None:
            print(f"[Logger Not Configured] WARN from {caller}: {msg}", file=sys.stderr)
            return
        self._logger.warning(msg, *args, extra={'caller': caller}, **kwargs)

    def error(self, caller: str, msg: str, *args, exc_info=False, **kwargs):
        """Logs an ERROR message, prepended with the caller name."""
        if not self._initialized or self._logger is None:
            print(f"[Logger Not Configured] Error from {caller}: {msg}", file=sys.stderr)
            return
        self._logger.error(msg, *args, exc_info=exc_info, extra={'caller': caller}, **kwargs)

    def exception(self, caller: str, msg: str, *args, **kwargs):
        """Logs an EXCEPTION message, prepended with the caller name."""
        if not self._initialized or self._logger is None:
            print(f"[Logger Not Configured] Exception from {caller}: {msg}", file=sys.stderr)
            return
        # The 'exception' method implicitly handles exc_info=True
        self._logger.exception(msg, *args, extra={'caller': caller}, **kwargs) 