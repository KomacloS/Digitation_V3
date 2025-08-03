# objects/board_object.py

from typing import Optional

class BoardObject:
    def __init__(
        self,
        component_name: str,
        pin: int,
        channel: Optional[int] = None,
        signal: Optional[str] = None,
        test_position: str = "Top",
        testability: str = "Not Testable",
        x_coord_mm: float = 0.0,
        y_coord_mm: float = 0.0,
        technology: str = "SMD",
        shape_type: str = "Square/rectangle",
        width_mm: float = 20.0,
        height_mm: float = 20.0,
        hole_mm: float = 0.0,
        angle_deg: float = 0.0,
        prefix: Optional[str] = None  # New attribute for prefix
    ):
        self.component_name = component_name
        self.pin = pin
        self.channel = channel
        self.signal = signal or (f"S{channel}" if channel is not None else "S0")
        self.test_position = test_position
        self.testability = testability

        # Current display coordinates
        self.x_coord_mm = x_coord_mm
        self.y_coord_mm = y_coord_mm

        # Original mechanical coordinates (immutable)
        self.x_coord_mm_original = x_coord_mm
        self.y_coord_mm_original = y_coord_mm

        self.technology = technology
        self.shape_type = shape_type
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.hole_mm = hole_mm
        self.angle_deg = angle_deg

        # New attribute for the ALF prefix.
        self.prefix = prefix

        # Link to the graphical item (to be set when added to the scene)
        self.graphic_item = None

        # New attribute to control visibility (default is True)
        self.visible = True

    def update_coordinates(self, x_mm: float, y_mm: float):
        self.x_coord_mm = x_mm
        self.y_coord_mm = y_mm

    def to_dict(self) -> dict:
        return {
            "component_name": self.component_name,
            "pin": self.pin,
            "channel": self.channel,
            "signal": self.signal,
            "test_position": self.test_position,
            "testability": self.testability,
            "x_coord_mm": self.x_coord_mm,
            "y_coord_mm": self.y_coord_mm,
            "technology": self.technology,
            "shape_type": self.shape_type,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "hole_mm": self.hole_mm,
            "angle_deg": self.angle_deg,
            "visible": self.visible,
            "prefix": self.prefix  # Include prefix in serialization
        }

    @classmethod
    def from_dict(cls, data: dict):
        obj = cls(**data)
        if "visible" in data:
            obj.visible = data["visible"]
        return obj
