# coord_converter.py

from constants.constants import Constants
from utils.flag_manager import FlagManager
from logs.log_handler import LogHandler

class CoordinateConverter:
    """
    A utility class for converting between pixel and millimeter coordinates,
    supporting separate scale factors for top vs. bottom side:
      - mm_per_pixels_top
      - mm_per_pixels_bot
    """

    def __init__(self, image_size=(0, 0)):
        """
        Initialize the converter with the scaling factor and image dimensions.

        :param image_size: The dimensions of the PCB image (width, height) in pixels.
        """
        self.constants = Constants()  # Reads JSON, which includes mm_per_pixels_top / mm_per_pixels_bot
        self.mm_per_pixels_top = self.constants.get("mm_per_pixels_top", 0.0333)
        self.mm_per_pixels_bot = self.constants.get("mm_per_pixels_bot", 0.0333)

        self.flags = FlagManager()
        self.image_width = image_size[0]
        self.image_height = image_size[1]
        self.log = LogHandler()
        self.origin_x_mm = 0.0
        self.origin_y_mm = 0.0

    def set_origin_mm(self, x0: float, y0: float):
        """Store a board-origin (mm) that will be added to every conversion."""
        self.origin_x_mm = x0
        self.origin_y_mm = y0

    def set_image_size(self, image_size):
        """
        Set or update the image dimensions in pixels.
        """
        self.image_width = image_size[0]
        self.image_height = image_size[1]

    # If you still want a function to update top/bottom scale factors at runtime, add:
    def set_mm_per_pixels_top(self, new_value: float):
        self.mm_per_pixels_top = new_value
        if self.log:
            self.log.log("info", f"CoordinateConverter: mm_per_pixels_top updated to {new_value}")

    def set_mm_per_pixels_bot(self, new_value: float):
        self.mm_per_pixels_bot = new_value
        if self.log:
            self.log.log("info", f"CoordinateConverter: mm_per_pixels_bot updated to {new_value}")


    # ------------------------------------------------------------------
    #  PIXELS ⇄ MM  (now origin–aware + side–aware)
    # ------------------------------------------------------------------
    def pixels_to_mm(self, x_px: float, y_px: float) -> tuple[float, float]:
        """
        Scene-pixel  →  board-mm, honouring current side and any non-zero origin.
        The stored origin (origin_x_mm, origin_y_mm) is *added* so the values
        returned are already expressed in the user-defined coordinate system.
        """
        side = self.flags.get_flag("side", "top").lower()

        if side == "top":
            x_mm =  x_px * self.mm_per_pixels_top
            y_mm = (self.image_height - y_px) * self.mm_per_pixels_top   # flip Y only
        else:                                       # ---- bottom side ----
            x_mm = (self.image_width  - x_px) * self.mm_per_pixels_bot   # flip X
            y_mm = (self.image_height - y_px) * self.mm_per_pixels_bot   # flip Y

        # shift into user coordinate system
        return x_mm + self.origin_x_mm, y_mm + self.origin_y_mm


    def mm_to_pixels(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        """
        Board-mm  →  scene-pixel, honouring current side and origin.
        The incoming mm coordinates are assumed to be in the *user* system,
        so we first translate them back to the internal (image-anchored) system
        by subtracting the stored origin.
        """
        # remove user origin offset
        x_loc = x_mm - self.origin_x_mm
        y_loc = y_mm - self.origin_y_mm

        side = self.flags.get_flag("side", "top").lower()

        if side == "top":
            x_px =  x_loc / self.mm_per_pixels_top
            y_px = self.image_height - (y_loc / self.mm_per_pixels_top)
        else:                                       # ---- bottom side ----
            x_px = self.image_width  - (x_loc / self.mm_per_pixels_bot)
            y_px = self.image_height - (y_loc / self.mm_per_pixels_bot)

        return x_px, y_px
