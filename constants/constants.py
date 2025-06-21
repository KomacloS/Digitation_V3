# constants/constants.py

import json
import os

# Avoid circular import by delaying LogHandler import
from typing import Optional, Any


class Constants:
    """Singleton wrapper around a JSON dictionary of persistent settings."""

    _instance: Optional["Constants"] = None

    def __new__(cls, file_path: Optional[str] = None, logger: Optional[Any] = None):
        if file_path is None:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
        inst = super().__new__(cls)
        inst._initialized = False
        return inst

    def __init__(self, file_path: Optional[str] = None, logger: Optional[Any] = None):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        if file_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, "constants.txt")

        self.file_path = file_path
        self.data: dict[str, Any] = {}
        if logger is None:
            from logs.log_handler import LogHandler

            logger = LogHandler()
        self.log = logger
        try:
            with open(self.file_path, "r") as file:
                self.data = json.load(file)
        except FileNotFoundError:
            self.log.warning(
                f"Constants file not found at '{self.file_path}'. Using default values."
            )
        except json.JSONDecodeError:
            self.log.error(
                f"Malformed constants file at '{self.file_path}'. Using default values."
            )

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        """
        Sets the value for a given key in the constants.

        :param key: The key to set.
        :param value: The value to assign to the key.
        """
        self.data[key] = value
        self.log.debug(f"Constants updated: {key} = {value}")

    def save(self):
        """
        Saves the current constants back to the constants.txt file.
        """
        try:
            with open(self.file_path, "w") as file:
                json.dump(self.data, file, indent=4)
            self.log.info(f"Constants saved to '{self.file_path}'.")
        except Exception as e:
            self.log.error(f"Error saving constants: {e}")
