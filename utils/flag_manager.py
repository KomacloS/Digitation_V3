# utils/flag_manager.py

class FlagManager:
    """
    A singleton class to manage dynamic flags for the application.
    Provides a centralized location for setting and retrieving global state flags.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FlagManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.flags = {}
        return cls._instance

    def set_flag(self, key, value):
        """
        Sets the value of a flag.
        :param key: The name of the flag.
        :param value: The value to set for the flag.
        """
        self.flags[key] = value

    def get_flag(self, key, default=None):
        """
        Retrieves the value of a flag.
        :param key: The name of the flag.
        :param default: The default value to return if the flag is not set.
        :return: The value of the flag or the default value.
        """
        return self.flags.get(key, default)

    def reset_flag(self, key):
        """
        Resets the value of a specific flag.
        :param key: The name of the flag to reset.
        """
        if key in self.flags:
            del self.flags[key]

    def reset_all_flags(self):
        """
        Resets all flags to an empty state.
        """
        self.flags.clear()

# Example usage:
# from utils.flag_manager import FlagManager
# flags = FlagManager()
# flags.set_flag("side", "top")
# current_side = flags.get_flag("side", "bottom")  # Returns "top"
# flags.reset_flag("side")
# flags.reset_all_flags()
