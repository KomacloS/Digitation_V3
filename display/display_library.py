# display/display_library.py

from typing import List
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtGui import QColor, QPen, QBrush, QPainterPath
from PyQt5.QtWidgets import QGraphicsObject, QGraphicsItemGroup
from objects.board_object import BoardObject
from logs.log_handler import LogHandler
from constants.constants import Constants
from utils.flag_manager import FlagManager
from display.pad_shapes import build_pad_path  # Helper to create QPainterPath for a pad


class SelectablePadItem(QGraphicsObject):
    """
    A custom QGraphicsObject that is selectable.
    """

    def __init__(self, path, board_object, log_handler, parent=None):
        super().__init__(parent)
        self.path = path
        self.board_object = board_object
        self.log = log_handler

        # Make it selectable (and focusable if desired).
        self.setFlags(
            QGraphicsObject.ItemIsSelectable | QGraphicsObject.ItemIsFocusable
        )

        # Accept hover, touch, and all mouse buttons
        self.setAcceptHoverEvents(True)
        self.setAcceptTouchEvents(True)
        self.setAcceptedMouseButtons(Qt.RightButton | Qt.LeftButton | Qt.MiddleButton)

        # Store normal pen/brush for reference
        self._normal_pen = QPen(Qt.black, 1.0, Qt.SolidLine)
        self._pen = self._normal_pen
        self._brush = QBrush(Qt.NoBrush)

    def setPath(self, new_path: QPainterPath):
        # Let the scene know geometry is about to change.
        self.prepareGeometryChange()
        self.path = new_path
        self.update()

    def setPen(self, pen: QPen):
        self._pen = pen
        self.update()

    def setBrush(self, brush: QBrush):
        self._brush = brush
        self.update()

    def boundingRect(self):
        return self.path.boundingRect()

    def paint(self, painter, option, widget):
        painter.setPen(self._pen)
        painter.setBrush(self._brush)
        painter.drawPath(self.path)

    def itemChange(self, change, value):
        """
        React to item selection changes (e.g., highlight in dashed blue).
        """
        if change == QGraphicsObject.ItemSelectedChange:
            is_selected = bool(value)
            if is_selected:
                sel_pen = QPen(Qt.blue, 2.5, Qt.DashLine)
                self.setPen(sel_pen)
            else:
                self.setPen(self._normal_pen)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """
        Allow right-click to select the pad if not already selected.
        """
        if event.button() == Qt.RightButton:
            if not self.isSelected():
                self.setSelected(True)
            event.accept()
        else:
            super().mousePressEvent(event)


class DisplayLibrary(QObject):
    """
    Manages the rendering of BoardObjects in the scene, with partial updates.
    """

    def __init__(self, scene, object_library, converter, current_side="top"):
        super().__init__()
        self.scene = scene
        self.object_library = object_library
        self.converter = converter
        self.current_side = current_side.lower()

        self.constants = Constants()
        self.log = LogHandler(output="both")

        self.z_value_pads = self.constants.get("z_value_pads", 1)
        self.group = QGraphicsItemGroup()
        self.group.setZValue(self.z_value_pads)
        self.scene.addItem(self.group)

        # Keep references to displayed QGraphicsObject items by channel
        self.displayed_objects = {}

        # Optionally connect single-object signals if you still want those
        if hasattr(self.object_library, "object_added"):
            self.object_library.object_added.connect(self.on_object_added)
        if hasattr(self.object_library, "object_removed"):
            self.object_library.object_removed.connect(self.on_object_removed)
        if hasattr(self.object_library, "object_updated"):
            self.object_library.object_updated.connect(self.on_object_updated)

        FlagManager().set_flag("side", self.current_side)

        self.log.log(
            "info",
            f"DisplayLibrary initialized for side '{self.current_side}'. Starting render with 0 objects.",
            module="DisplayLibrary",
            func="__init__",
        )

        # Render everything initially
        self.render_initial_objects()

    # --------------------------------------------------------------------------
    #  INITIAL RENDER
    # --------------------------------------------------------------------------
    def render_initial_objects(self):
        """
        Renders every object from the ObjectLibrary once, e.g. on program start or file load.
        """
        all_objects = self.object_library.get_all_objects()
        self.log.log(
            "info",
            f"Rendering initial objects: found {len(all_objects)} in library.",
            module="DisplayLibrary",
            func="render_initial_objects",
        )
        rendered_count = 0
        for obj in all_objects:
            if self.render_object(obj):
                rendered_count += 1
        self.log.log(
            "info",
            f"Rendered {rendered_count} object(s) for side '{self.current_side}'. "
            f"Display now has {len(self.displayed_objects)} objects.",
            module="DisplayLibrary",
            func="render_initial_objects",
        )

    # --------------------------------------------------------------------------
    #  SINGLE-OBJECT SIGNAL HANDLERS (optional)
    # --------------------------------------------------------------------------
    def on_object_added(self, board_obj: BoardObject):
        """
        Called automatically if object_library emits 'object_added' for a single BoardObject.
        Renders just that object.
        """
        # If you use bulk_add without signals, you can skip this
        self.log.log(
            "info",
            f"Object added: '{board_obj.component_name}' (ch {board_obj.channel}). Now rendering...",
            module="DisplayLibrary",
            func="on_object_added",
        )
        self.render_object(board_obj)
        self.log.log(
            "info",
            f"Display now has {len(self.displayed_objects)} objects after addition.",
            module="DisplayLibrary",
            func="on_object_added",
        )

    def on_object_removed(self, board_obj: BoardObject):
        """
        Called automatically if object_library emits 'object_removed' for a single BoardObject.
        Removes just that object.
        """
        self.log.log(
            "info",
            f"Removing object '{board_obj.component_name}' (ch {board_obj.channel}).",
            module="DisplayLibrary",
            func="on_object_removed",
        )
        self.remove_rendered_object(board_obj.channel)
        self.log.log(
            "info",
            f"Display now has {len(self.displayed_objects)} objects after removal.",
            module="DisplayLibrary",
            func="on_object_removed",
        )

    def on_object_updated(self, board_obj: BoardObject):
        """
        Called automatically if object_library emits 'object_updated' for a single BoardObject.
        Removes and re-renders that object.
        """
        self.log.log(
            "info",
            f"Updating object '{board_obj.component_name}' (ch {board_obj.channel}).",
            module="DisplayLibrary",
            func="on_object_updated",
        )
        self.remove_rendered_object(board_obj.channel)
        self.render_object(board_obj)
        self.log.log(
            "info",
            f"Display now has {len(self.displayed_objects)} objects after update.",
            module="DisplayLibrary",
            func="on_object_updated",
        )

    # --------------------------------------------------------------------------
    #  RENDERING SINGLE OBJECT
    # --------------------------------------------------------------------------
    def render_object(self, board_obj: BoardObject) -> bool:
        """
        Creates and displays a QGraphicsItem for the BoardObject if:
          - board_obj.visible == True
          - board_obj.test_position matches or is 'both' for the current side
          - for through-hole objects, also create a "secondary" pad on the opposite side
        Returns True if something was created, False otherwise.
        """
        # Skip if not visible
        if not board_obj.visible:
            self.log.log(
                "debug",
                f"Skipping render: Channel {board_obj.channel} => visible=False.",
                module="DisplayLibrary",
                func="render_object",
            )
            return False

        tp = board_obj.test_position.lower()  # e.g. 'top', 'bottom', or 'both'
        tech = board_obj.technology.lower()  # e.g. 'smd', 'through hole'
        current = self.current_side
        created_anything = False

        # 1) Primary pad
        if tp in (current, "both"):
            code = self.testability_to_code(board_obj.testability)
            color = self.get_pad_color(code)
            pen = QPen(Qt.black, 1.0, Qt.SolidLine)
            brush = QBrush(color)
            primary_item = self.create_pad_item(board_obj, pen, brush)
            if primary_item:
                self.scene.addItem(primary_item)
                self.displayed_objects[board_obj.channel] = primary_item
                created_anything = True
            else:
                self.log.log(
                    "warning",
                    f"Failed to create primary pad item for channel={board_obj.channel}.",
                    module="DisplayLibrary",
                    func="render_object",
                )

        # 2) Secondary pad for through-hole if on opposite side
        if tech == "through hole" and tp not in (current, "both"):
            s_pen = QPen(Qt.black, 1.0, Qt.SolidLine)
            s_brush = QBrush(QColor(0, 255, 0))  # green or any color for secondary
            secondary_item = self.create_pad_item(board_obj, s_pen, s_brush)
            if secondary_item:
                # Non-selectable
                secondary_item.setFlag(QGraphicsObject.ItemIsSelectable, False)
                key = f"{board_obj.channel}_secondary"
                self.scene.addItem(secondary_item)
                self.displayed_objects[key] = secondary_item
                created_anything = True

        return created_anything

    def create_pad_item(
        self, pad: BoardObject, pen: QPen, brush: QBrush
    ) -> QGraphicsObject:
        """
        Builds the QPainterPath for the pad, then creates a SelectablePadItem,
        positions it, and returns it. Returns None if build_pad_path fails.
        """
        path = self._build_pad_path(
            pad.width_mm, pad.height_mm, pad.hole_mm, pad.shape_type
        )
        if not path:
            return None

        x_scene, y_scene = self.converter.mm_to_pixels(pad.x_coord_mm, pad.y_coord_mm)
        item = SelectablePadItem(path, pad, self.log)
        item.setPen(pen)
        item.setBrush(brush)
        item.setPos(x_scene, y_scene)

        angle = pad.angle_deg
        if self.current_side == "bottom":
            angle = (180 - angle) % 360
        # Rotate counter-clockwise for positive angles
        item.setRotation(-angle)
        item.setZValue(self.z_value_pads)
        return item

    def _build_pad_path(self, width_mm, height_mm, hole_mm, shape_type):
        """
        Creates a QPainterPath for the pad using your 'build_pad_path' helper,
        passing the correct mm-per-pixel factor depending on top/bottom side.
        """
        if self.current_side == "top":
            mm_per_pixel = self.converter.mm_per_pixels_top
        else:
            mm_per_pixel = self.converter.mm_per_pixels_bot

        return build_pad_path(width_mm, height_mm, hole_mm, shape_type, mm_per_pixel)

    # --------------------------------------------------------------------------
    #  REMOVING / CLEARING
    # --------------------------------------------------------------------------
    def remove_rendered_object(self, channel: int):
        """
        Removes the QGraphicsItem for 'channel' and the associated secondary key, if any.
        """
        item = self.displayed_objects.pop(channel, None)
        if item:
            self.group.removeFromGroup(item)
            self.scene.removeItem(item)

        secondary_key = f"{channel}_secondary"
        secondary_item = self.displayed_objects.pop(secondary_key, None)
        if secondary_item:
            self.group.removeFromGroup(secondary_item)
            self.scene.removeItem(secondary_item)

    def clear_all_rendered_objects(self):
        """
        Removes every item from the scene and clears 'displayed_objects'.
        """
        for itm in list(self.displayed_objects.values()):
            self.group.removeFromGroup(itm)
            self.scene.removeItem(itm)
        self.displayed_objects.clear()
        self.log.log(
            "info",
            "All rendered objects cleared.",
            module="DisplayLibrary",
            func="clear_all_rendered_objects",
        )

    # --------------------------------------------------------------------------
    #  PARTIAL UPDATE METHODS (for bulk operations)
    # --------------------------------------------------------------------------
    def add_rendered_objects(self, board_objects: List[BoardObject]) -> None:
        """
        Renders each BoardObject without clearing others. (Bulk-add partial update)
        """
        for obj in board_objects:
            if obj.visible:
                self.render_object(obj)

    def remove_rendered_objects(self, channels: List[int]) -> None:
        """
        Removes each channel from the scene. (Bulk-delete partial update)
        """
        for ch in channels:
            self.remove_rendered_object(ch)

    def update_rendered_objects_for_updates(self, updates: List[BoardObject]):
        """Refresh just the changed pads without a full scene redraw."""
        for obj in updates:
            # remove any existing graphics for this channel (primary or secondary)
            self.remove_rendered_object(obj.channel)

            # if still visible after the edit, re-render it using current logic
            if obj.visible:
                self.render_object(obj)

    # --------------------------------------------------------------------------
    #  SIDE-SWITCHING
    # --------------------------------------------------------------------------
    def update_display_side(self):
        """
        Called when the user switches from top to bottom or vice versa.
        Clears all items and re-renders everything on the new side.
        """
        self.log.log(
            "info",
            f"Side changed to '{self.current_side}'. Re-rendering display...",
            module="DisplayLibrary",
            func="update_display_side",
        )
        self.clear_all_rendered_objects()
        self.render_initial_objects()

    # --------------------------------------------------------------------------
    #  COLOR / TESTABILITY HELPERS
    # --------------------------------------------------------------------------
    def get_pad_color(self, testability_code: str) -> QColor:
        color_mapping = {
            "F": QColor(0xC0, 0x60, 0xC0),  # Forced  (magenta-ish)
            "T": QColor(0x00, 0x64, 0x00),  # Testable (dark green)
            "N": QColor(0x60, 0x60, 0x60),  # Not testable (grey)
            "E": QColor(0x80, 0x80, 0x00),  # Terminal (olive)
        }
        return color_mapping.get(testability_code, QColor(0, 0, 0))

    def testability_to_code(self, testability_str: str) -> str:
        mapping = {"Forced": "F", "Testable": "T", "Not Testable": "N", "Terminal": "E"}
        return mapping.get(testability_str, "N")
