# objects/search_library.py

from typing import Optional, List
from objects.board_object import BoardObject
from objects.object_library import ObjectLibrary


class SearchLibrary:
    def __init__(self, object_library: Optional[ObjectLibrary] = None):
        # Use the provided ObjectLibrary, or fall back to creating a new one
        self.object_library = object_library if object_library is not None else ObjectLibrary()
        self.log = self.object_library.log  # Assuming ObjectLibrary has a logger

    def find_pad(self, component: str, pin: str, signal: str, channel: int) -> Optional[BoardObject]:
        """
        Finds and returns the BoardObject matching the specified criteria.
        """
        self.log.log("debug", f"Searching for pad with Component: {component}, Pin: {pin}, Signal: {signal}, Channel: {channel}")
        for obj in self.object_library.get_all_objects():
            if (obj.component_name.lower() == component.lower() and
                str(obj.pin) == pin and
                obj.signal.lower() == signal.lower() and
                obj.channel == channel):
                self.log.log("info", f"Pad found: {obj}")
                self.log.log("debug", f"Pad coordinates: x={obj.x_coord_mm}, y={obj.y_coord_mm}")
                return obj
        self.log.log("warning", f"No pad found for Component: {component}, Pin: {pin}, Signal: {signal}, Channel: {channel}")
        return None

    def find_pad_by_signal(self, signal: str) -> Optional[BoardObject]:
        """
        Finds and returns the BoardObject matching the specified signal.
        Assumes signals are unique. If multiple pads share the same signal, returns the first match.
        """
        self.log.log("debug", f"Searching for pad with Signal: {signal}")
        for obj in self.object_library.get_all_objects():
            if obj.signal.lower() == signal.lower():
                self.log.log("info", f"Pad found by signal: {obj}")
                return obj
        self.log.log("warning", f"No pad found for Signal: {signal}")
        return None

    def find_pad_by_channel(self, channel: int) -> Optional[BoardObject]:
        """
        Finds and returns the BoardObject matching the specified channel.
        Assumes channels are unique. If multiple pads share the same channel, returns the first match.
        """
        self.log.log("debug", f"Searching for pad with Channel: {channel}")
        for obj in self.object_library.get_all_objects():
            if obj.channel == channel:
                self.log.log("info", f"Pad found by channel: {obj}")
                return obj
        self.log.log("warning", f"No pad found for Channel: {channel}")
        return None

    def get_components(self) -> List[str]:
        """
        Retrieves a list of unique component names.
        """
        components = sorted({obj.component_name for obj in self.object_library.get_all_objects()})
        self.log.log("debug", f"Retrieved components: {components}")
        return components

    def get_pins(self, component: str) -> List[str]:
        """
        Retrieves a list of pins for the specified component.
        """
        pins = sorted({str(obj.pin) for obj in self.object_library.get_all_objects()
                      if obj.component_name.lower() == component.lower()})
        self.log.log("debug", f"Retrieved pins for component '{component}': {pins}")
        return pins

    def get_signals(self, component: str, pin: str) -> List[str]:
        """
        Retrieves a list of signals for the specified component and pin.
        """
        signals = sorted({obj.signal for obj in self.object_library.get_all_objects()
                          if obj.component_name.lower() == component.lower() and str(obj.pin) == pin})
        self.log.log("debug", f"Retrieved signals for component '{component}' and pin '{pin}': {signals}")
        return signals

    def get_channels(self, component: str, pin: str, signal: str) -> List[str]:
        """
        Retrieves a list of channels for the specified component, pin, and signal.
        """
        channels = sorted({str(obj.channel) for obj in self.object_library.get_all_objects()
                           if (obj.component_name.lower() == component.lower() and
                               str(obj.pin) == pin and
                               obj.signal.lower() == signal.lower())})
        self.log.log("debug", f"Retrieved channels for component '{component}', pin '{pin}', signal '{signal}': {channels}")
        return channels
