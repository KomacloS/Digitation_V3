# ui/marker_manager.py

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QBrush, QColor, QPen
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGraphicsItemGroup, QGraphicsLineItem, QGraphicsItem  
from logs.log_handler import LogHandler
from constants.constants import Constants

class MarkerManager:
    """
    Manages the creation and placement of markers on the scene,
    including the normal single‐marker and the Quick Creation anchors.
    """
    def __init__(self, group: QGraphicsItemGroup):
        self.group = group
        self.log = LogHandler()
        self.constants = Constants()
        self.z_value_marker = self.constants.get("z_value_marker", 2)
        self.group.setZValue(self.z_value_marker)

        # Normal single selection marker
        self.marker_item = None

        # Quick‐Creation anchors storage
        self.anchor_items = {}
        self._selection_connected = False

    def place_marker(self, x_mm: float, y_mm: float):
        """
        Places or moves the marker to the specified (x_mm, y_mm) board coordinates.
        """
        try:
            # Convert mm to pixels using CoordinateConverter
            converter = self.group.scene().views()[0].converter
            x_pixels, y_pixels = converter.mm_to_pixels(x_mm, y_mm)
        except Exception as e:
            QMessageBox.critical(None, "Error", "Failed to convert board coordinates to pixels.")
            return

        if self.marker_item is None:
            self.marker_item = self._create_marker_item()
            self.group.addToGroup(self.marker_item)

        # Set the position of the marker
        self.marker_item.setPos(x_pixels, y_pixels)
        self.marker_item.setVisible(True)  # Ensure marker is visible


    def place_marker_from_scene(self, scene_x: float, scene_y: float):
        """
        Places a marker based on scene (pixel) coordinates by converting them to board (mm) coordinates.
        """
        try:
            # Retrieve the BoardView from the scene's views
            views = self.group.scene().views()
            if not views:
                # self.log.log("error", "No views found for the scene.")
                QMessageBox.critical(None, "Error", "No view found for marker placement.")
                return

            board_view = views[0]  # Assuming the first view is the BoardView
            x_mm, y_mm = board_view.scene_to_board_coords(scene_x, scene_y)
            # self.log.log("debug", f"Converted scene coords ({scene_x}, {scene_y}) to board coords ({x_mm}, {y_mm}) mm.")
        except Exception as e:
            # self.log.log("error", f"Failed to convert scene coords to board coords: {e}")
            QMessageBox.critical(None, "Error", "Failed to convert click position to board coordinates.")
            return

        # Place the marker using board coordinates
        self.place_marker(x_mm, y_mm)

    def _create_marker_item(self) -> QGraphicsItemGroup:
        """
        Creates a cross marker as a QGraphicsItemGroup.
        The marker is a yellow cross that ignores transformations (stays the same size during zoom).
        """
        pen = QPen(QColor('yellow'))
        pen.setWidth(2)
        size = 30

        # Create horizontal line of the cross
        line1 = QGraphicsLineItem(-size / 2, 0, size / 2, 0)
        line1.setPen(pen)
        line1.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        # self.log.log("debug", "Created horizontal line for marker cross.")

        # Create vertical line of the cross
        line2 = QGraphicsLineItem(0, -size / 2, 0, size / 2)
        line2.setPen(pen)
        line2.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        # self.log.log("debug", "Created vertical line for marker cross.")

        # Group the lines into a single marker item
        marker_group = QGraphicsItemGroup()
        marker_group.addToGroup(line1)
        marker_group.addToGroup(line2)
        # self.log.log("debug", "Grouped lines into QGraphicsItemGroup for marker.")

        # Set the Z-value for the marker to ensure it appears above other items
        marker_group.setZValue(self.z_value_marker)
        # self.log.log("debug", f"Set marker group's Z-value to {self.z_value_marker}.")

        return marker_group
    


    def get_marker_board_coords(self):
        """
        Returns the (x_mm, y_mm) coordinates of the marker
        if placed, or None if no marker is present.
        """
        if not self.marker_item:
            return None
        # Current marker_item's position is in scene coords (pixels).
        scene_pos = self.marker_item.scenePos()
        
        # Convert that scene pos back to board mm:
        if self.group.scene() and self.group.scene().views():
            board_view = self.group.scene().views()[0]
            x_mm, y_mm = board_view.scene_to_board_coords(scene_pos.x(), scene_pos.y())
            return (x_mm, y_mm)
        return None

    # ------------------------------------------------------------------
    def shift_marker(self, dx_mm: float, dy_mm: float):
        """
        Move the marker by ΔX / ΔY in millimetres, if it exists.
        """
        coords = self.get_marker_board_coords()
        if coords:
            self.place_marker(coords[0] + dx_mm, coords[1] + dy_mm)



    # ─────────────────────────────────────────────────────────────────────────
    # Quick Creation anchors
    # ─────────────────────────────────────────────────────────────────────────

    def place_anchor(self, anchor_id: str, x_mm: float, y_mm: float):
        """
        Place or move a Quick Creation anchor:
        A = red; B = blue. Anchors are selectable and show thicker when selected.
        """
        conv = self.group.scene().views()[0].converter
        x_px, y_px = conv.mm_to_pixels(x_mm, y_mm)

        if anchor_id not in self.anchor_items:
            color = QColor('red') if anchor_id == 'A' else QColor('blue')
            item = self._create_anchor_item(color)
            # make it selectable
            item.setFlag(QGraphicsItem.ItemIsSelectable, True)
            item.setFlag(QGraphicsItem.ItemIsFocusable, True)

            # add directly to scene so it sits above the ghost
            self.group.scene().addItem(item)
            self.anchor_items[anchor_id] = item

            # connect selectionChanged once
            if not self._selection_connected:
                self.group.scene().selectionChanged.connect(self._on_scene_selection_changed)
                self._selection_connected = True

        else:
            item = self.anchor_items[anchor_id]

        item.setPos(x_px, y_px)
        item.setVisible(True)

    def move_anchor(self, anchor_id: str, x_mm: float, y_mm: float):
        """Reposition an existing anchor."""
        item = self.anchor_items.get(anchor_id)
        if not item:
            return
        conv = self.group.scene().views()[0].converter
        x_px, y_px = conv.mm_to_pixels(x_mm, y_mm)
        item.setPos(x_px, y_px)

    def clear_quick_anchors(self):
        """Remove all Quick Creation anchors."""
        scene = self.group.scene()
        for item in self.anchor_items.values():
            if item.isSelected():
                item.setSelected(False)
            scene.removeItem(item)
        self.anchor_items.clear()

    def _create_anchor_item(self, color: QColor) -> QGraphicsItemGroup:
        """
        Create a fixed-size cross marker that ignores zoom.
        """
        pen = QPen(color)
        pen.setWidth(2)
        size = 30

        h_line = QGraphicsLineItem(-size/2, 0, size/2, 0)
        h_line.setPen(pen)
        h_line.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)

        v_line = QGraphicsLineItem(0, -size/2, 0, size/2)
        v_line.setPen(pen)
        v_line.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)

        grp = QGraphicsItemGroup()
        grp.addToGroup(h_line)
        grp.addToGroup(v_line)
        z_ghost = self.constants.get("z_value_ghost", 3)
        grp.setZValue(z_ghost + 1)
        return grp

    def _on_scene_selection_changed(self):
        """
        Highlight selected anchors by thickening their lines.
        """
        for anchor_id, item in self.anchor_items.items():
            selected = item.isSelected()
            for child in item.childItems():
                pen = child.pen()
                pen.setWidth(4 if selected else 2)
                child.setPen(pen)