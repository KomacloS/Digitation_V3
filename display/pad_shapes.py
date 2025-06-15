# display/pad_shapes.py
from PyQt5.QtGui import QPainterPath
from PyQt5.QtCore import QRectF

def build_pad_path(width_mm: float, height_mm: float, hole_mm: float, shape_type: str, mm_per_pixel: float) -> QPainterPath:
    """
    Builds and returns a QPainterPath for a pad shape based on its dimensions and shape type.
    
    - For "square/rectangle with hole": returns a rectangular pad with a circular hole.
    - For "square/rectangle": returns a simple rectangle.
    - For "ellipse": returns an ellipse.
    - For "round": ignores hole_mm entirely, using width_mm as the circle diameter.
    - For "round with hole" or "hole": uses width_mm for the circle diameter, 
      and if hole_mm > 0, subtracts a hole.
    - Otherwise defaults to a rectangle.
    """
    path = QPainterPath()

    # Convert dimensions from mm to pixels.
    w_px = width_mm / mm_per_pixel
    h_px = height_mm / mm_per_pixel
    hole_px = hole_mm / mm_per_pixel

    st = shape_type.lower()

    if "square/rectangle with hole" in st:
        # Create outer rectangle.
        outer_rect = QRectF(-w_px/2, -h_px/2, w_px, h_px)
        path.addRect(outer_rect)
        if hole_px > 0:
            hole_rect = QRectF(-hole_px/2, -hole_px/2, hole_px, hole_px)
            hole_path = QPainterPath()
            hole_path.addEllipse(hole_rect)
            path = path.subtracted(hole_path)

    elif "square/rectangle" in st:
        rect = QRectF(-w_px/2, -h_px/2, w_px, h_px)
        path.addRect(rect)

    elif "ellipse" in st:
        rect = QRectF(-w_px/2, -h_px/2, w_px, h_px)
        path.addEllipse(rect)

    elif st == "round":
        # Strictly "round": ignore any hole_mm parameter
        hole_px = 0  # Force hole to zero
        radius = w_px / 2.0
        rect = QRectF(-radius, -radius, w_px, w_px)
        path.addEllipse(rect)

    elif st in ("round with hole", "hole"):
        # Outer circle
        radius = w_px / 2.0
        rect = QRectF(-radius, -radius, w_px, w_px)
        path.addEllipse(rect)
        # If there's a hole, subtract it
        if hole_px > 0:
            hole_rect = QRectF(-hole_px/2, -hole_px/2, hole_px, hole_px)
            hole_path = QPainterPath()
            hole_path.addEllipse(hole_rect)
            path = path.subtracted(hole_path)

    else:
        # Default: rectangle
        rect = QRectF(-w_px/2, -h_px/2, w_px, h_px)
        path.addRect(rect)

    return path
