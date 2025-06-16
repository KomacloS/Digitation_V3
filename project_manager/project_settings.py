import os
import json
from logs.log_handler import LogHandler
from constants.constants import Constants

PROJECT_KEYS = [
    "mm_per_pixels_top",
    "mm_per_pixels_bot",
    "origin_x_mm",
    "origin_y_mm",
]


def load_settings(project_dir: str, constants: Constants, logger: LogHandler | None = None) -> None:
    """Load project specific constants into ``constants`` from ``project_dir``."""
    if logger is None:
        logger = LogHandler()
    settings_path = os.path.join(project_dir, "project_settings.json")
    if not os.path.exists(settings_path):
        logger.log("info", f"No project settings found at {settings_path}. Using defaults.")
        return
    try:
        with open(settings_path, "r") as f:
            data = json.load(f)
        for key in PROJECT_KEYS:
            if key in data:
                constants.set(key, data[key])
        constants.save()
        logger.log("info", f"Loaded project settings from {settings_path}")
    except Exception as e:
        logger.log("error", f"Failed to load project settings: {e}")


def save_settings(project_dir: str, constants: Constants, logger: LogHandler | None = None) -> None:
    """Save project specific constants from ``constants`` into ``project_dir``."""
    if logger is None:
        logger = LogHandler()
    settings_path = os.path.join(project_dir, "project_settings.json")
    data = {key: constants.get(key) for key in PROJECT_KEYS}
    try:
        with open(settings_path, "w") as f:
            json.dump(data, f, indent=4)
        logger.log("info", f"Project settings saved to {settings_path}")
    except Exception as e:
        logger.log("error", f"Failed to save project settings: {e}")
