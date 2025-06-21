# logs/log_handler.py

import logging
import os
from logging.handlers import RotatingFileHandler
from constants.constants import Constants


class LogHandler:
    _instance = None

    def __new__(cls, output="both"):
        if cls._instance is None:
            cls._instance = super(LogHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self, output="both"):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        # Set up the logger early so Constants can use it during loading
        self.logger = logging.getLogger("ProgramLogger")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        constants = Constants(logger=self)
        log_file = constants.get("log_file", "logs/program.txt")
        max_size = constants.get("log_max_size", 5_000_000)
        backup_count = constants.get("log_backup_count", 5)
        debug_mode = constants.get("debug_mode", False)

        level = logging.DEBUG if debug_mode else logging.INFO
        self.logger.setLevel(level)

        # Ensure the logs directory exists
        log_dir = os.path.dirname(log_file)
        try:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                self.logger.debug("Log directory created: %s", log_dir)
        except Exception as e:
            self.logger.error("Failed to create log directory %s: %s", log_dir, e)

        # Set up the logger handlers

        if not self.logger.hasHandlers():
            try:
                if output in ["file", "both"]:
                    file_handler = RotatingFileHandler(
                        log_file,
                        maxBytes=max_size,
                        backupCount=backup_count,
                        encoding="utf-8",
                    )
                    fmt = "%(asctime)s - %(levelname)s - %(message)s"
                    file_handler.setFormatter(logging.Formatter(fmt))
                    self.logger.addHandler(file_handler)
                    self.logger.debug("Logging to file: %s", log_file)
            except Exception as e:
                self.logger.error("Failed to initialize file logging: %s", e)

            if output in ["terminal", "both"]:
                console_handler = logging.StreamHandler()
                fmt = "%(asctime)s - %(levelname)s - %(message)s"
                console_handler.setFormatter(logging.Formatter(fmt))
                self.logger.addHandler(console_handler)

            if output == "none":
                self.logger.disabled = True

    def log(self, level: str, message: str, module: str = "", func: str = ""):
        """Extended logging method."""
        prefix_parts = []
        if module:
            prefix_parts.append(module)
        if func:
            prefix_parts.append(func)
        prefix = f"[{'.'.join(prefix_parts)}]: " if prefix_parts else ""
        full_msg = prefix + message

        if level.lower() == "info":
            self.logger.info(full_msg)
        elif level.lower() == "error":
            self.logger.error(full_msg)
        elif level.lower() == "debug":
            self.logger.debug(full_msg)
        else:
            self.logger.warning(full_msg)

    # --- Convenience methods for standard logging levels ---
    def debug(self, message: str, module: str = "", func: str = ""):
        self.log("debug", message, module, func)

    def info(self, message: str, module: str = "", func: str = ""):
        self.log("info", message, module, func)

    def warning(self, message: str, module: str = "", func: str = ""):
        self.log("warning", message, module, func)

    def error(self, message: str, module: str = "", func: str = ""):
        self.log("error", message, module, func)

    def getEffectiveLevel(self):
        return self.logger.getEffectiveLevel()
