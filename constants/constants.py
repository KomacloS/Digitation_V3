# constants/constants.py

import json
import os

class Constants:
    def __init__(self, file_path=None):
        if file_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, "constants.txt")
        
        self.file_path = file_path
        self.data = {}
        try:
            with open(self.file_path, "r") as file:
                self.data = json.load(file)
        except FileNotFoundError:
            print(f"Warning: Constants file not found at '{self.file_path}'. Using default values.")
        except json.JSONDecodeError:
            print(f"Error: Malformed constants file at '{self.file_path}'. Using default values.")
    
    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        """
        Sets the value for a given key in the constants.

        :param key: The key to set.
        :param value: The value to assign to the key.
        """
        self.data[key] = value
        print(f"Constants updated: {key} = {value}")

    def save(self):
        """
        Saves the current constants back to the constants.txt file.
        """
        try:
            with open(self.file_path, "w") as file:
                json.dump(self.data, file, indent=4)
            print(f"Constants saved to '{self.file_path}'.")
        except Exception as e:
            print(f"Error saving constants: {e}")
