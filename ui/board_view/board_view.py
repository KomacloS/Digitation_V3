# ui/board_view

import os
from PyQt5.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QMessageBox,
    QGraphicsItemGroup,
    QMenu,
    QAction,
    QShortcut,
    QGraphicsRectItem,
    QInputDialog,
    QFileDialog,
)
from PyQt5.QtCore import Qt, QPointF, pyqtSignal, QEvent, QTimer
from PyQt5.QtGui import QCursor, QKeySequence, QPen
from logs.log_handler import LogHandler
from utils.flag_manager import FlagManager
from ui.marker_manager import MarkerManager
from ui.zoom_manager import ZoomManager
from constants.constants import Constants
from display.display_library import DisplayLibrary, SelectablePadItem
from display.coord_converter import CoordinateConverter
from inputs.input_handler import InputHandler
import edit_pads.actions as actions
from objects.alf_file import export_alf_file
from objects.nod_file import get_pad_code, mm_to_mils
from . import shortcuts, mouse_events, image_manager

# ui/board_view/board_view.py


class BoardView(QGraphicsView):
    clicked = pyqtSignal(QPointF)
    pads_selected = pyqtSignal(list)
    mouse_clicked = pyqtSignal(float, float, str)

    def __init__(
        self,
        parent=None,
        pad_info_label=None,
        component_placer=None,
        object_library=None,
        constants=None,
    ):
        super().__init__(parent)
        self.log = LogHandler(output="both")
        self.flags = FlagManager()

        # --- Keep the side-aware converter (new approach) ---
        self.converter = CoordinateConverter()
        bx = constants.get("BottomImageXCoord", 0.0)
        by = constants.get("BottomImageYCoord", 0.0)
        tx = constants.get("TopImageXCoord", 0.0)
        ty = constants.get("TopImageYCoord", 0.0)
        self.converter.set_origin_mm(tx, ty, side="top")
        self.converter.set_origin_mm(bx, by, side="bottom")

        # UI references
        self.pad_info_label = pad_info_label
        self.object_library = object_library
        self.component_placer = component_placer

        # Re-add base_scale if needed for zoom logic
        self.base_scale = 1.0

        # Re-add panning initialization
        self._panning = False
        self._pan_start = None

        # Marker positions for top/bottom
        self.marker_pos = {"top": None, "bottom": None}

        # Use the passed-in constants
        self.constants = constants if constants else Constants()
        self.z_value_image = self.constants.get("z_value_image", 0)
        self.z_value_cutouts = self.constants.get("z_value_cutouts", 0.5)

        # Explicitly set side to "top" on init if desired (like old code did)
        self.flags.set_flag("side", "top")

        # Debug log
        self.log.log(
            "debug", "BoardView initialized.", module="BoardView", func="__init__"
        )

        # Scene setup
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        # Groups for items
        self.display_group = QGraphicsItemGroup()
        self.marker_group = QGraphicsItemGroup()
        self.cutout_group = QGraphicsItemGroup()
        self.cutout_group.setZValue(self.z_value_cutouts)
        self.log.debug(
            f"Cutout group Z-value set to {self.z_value_cutouts}",
            module="BoardView",
            func="__init__",
        )
        self.scene.addItem(self.display_group)
        self.scene.addItem(self.marker_group)
        self.scene.addItem(self.cutout_group)
        self.cutout_items = []

        self.setCacheMode(QGraphicsView.CacheBackground)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)

        # Image placeholders
        self.top_pixmap_item = None
        self.bottom_pixmap_item = None
        self.current_pixmap_item = None
        self.top_image_size = None
        self.bottom_image_size = None

        # Example state
        self.user_has_zoomed_yet = False
        self.last_clicked_mm = None
        self.last_clicked_side = self.flags.get_flag("side", "top")

        # Marker manager
        self.marker_manager = MarkerManager(self.marker_group)

        # Zoom manager (side-aware, no direct pixels_per_mm)
        self.zoom_manager = ZoomManager(self, self.constants, self.log)

        # Display library uses the same side-aware converter
        self.display_library = DisplayLibrary(
            scene=self.scene,
            object_library=self.object_library,
            converter=self.converter,
            current_side="top",
        )

        # Focus + shortcuts
        self.setFocusPolicy(Qt.StrongFocus)
        self.viewport().setFocusPolicy(Qt.StrongFocus)

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.fit_in_view_and_reset_zoom)

        # (Optional) If you want an event filter on the BoardView itself
        self.installEventFilter(self)

        # Create input handler & install event filters
        self.input_handler = InputHandler(
            board_view=self,
            component_placer=self.component_placer,
            ghost_component=(
                self.component_placer.ghost_component if self.component_placer else None
            ),
        )
        self.installEventFilter(self.input_handler)
        self.viewport().installEventFilter(self.input_handler)
        self.log.debug("InputHandler installed as event filter.")

        # Re-add the line setting up your shortcuts (Ctrl+C, Ctrl+V, etc.)
        shortcuts.setup_board_view_shortcuts(self)

        # Re-add focus/activation lines so window is definitely in focus
        self.setFocus(Qt.OtherFocusReason)
        self.activateWindow()
        self.raise_()

        # Track layer visibility states
        self.image_hidden_by_filter = False
        self.pads_hidden_by_filter = False
        self.digitation_holes_enabled = False

    # --------------------------------------------------------------------------
    #  SELECTION CHANGED HANDLER
    # --------------------------------------------------------------------------
    def on_scene_selection_changed(self):
        """
        Called when the scene selection changes.
        To reduce lag when many items are selected, we throttle the update to the main window.
        """
        # Use a single-shot timer to debounce selection updates.
        if hasattr(self, "_selection_update_timer"):
            self._selection_update_timer.stop()
        else:
            self._selection_update_timer = QTimer(self)
            self._selection_update_timer.setSingleShot(True)
            self._selection_update_timer.timeout.connect(self._update_selected_info)
        self._selection_update_timer.start(50)  # 50 ms delay

    def keyPressEvent(self, event):
        if hasattr(self, "input_handler"):
            handled = self.input_handler.handle_key_press(event)
            cp_active = (
                self.component_placer.is_active if self.component_placer else None
            )
            ghost_active = (
                self.component_placer.ghost_component.is_active
                if self.component_placer and self.component_placer.ghost_component
                else None
            )
            self.log.debug(
                f"After keyPressEvent: BoardView.hasFocus() = {self.hasFocus()}, "
                f"Viewport.hasFocus() = {self.viewport().hasFocus()}, "
                f"ComponentPlacer.is_active = {cp_active}, GhostComponent.is_active = {ghost_active}"
            )
            if handled:
                return
        super().keyPressEvent(event)

    def _update_selected_info(self):
        selected_items = self._get_selected_pads()
        main_win = self.parent()  # or use self.window()
        if hasattr(main_win, "update_selected_pins_info"):
            main_win.update_selected_pins_info(selected_items)
        self.log.debug(f"Selection updated: {len(selected_items)} pad(s) selected.")

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.KeyPress, QEvent.KeyRelease):
            self.log.debug(
                f"BoardView.eventFilter: Received event {event.type()} on {obj} with key {event.key()}"
            )
        return super().eventFilter(obj, event)

    def _get_selected_pads(self):
        """Returns currently selected pads."""
        return [
            item
            for item in self.scene.selectedItems()
            if isinstance(item, SelectablePadItem)
        ]

    def connect_signals(self):
        """
        Connect your own signals or signals from other managers here if needed.
        Currently, DisplayLibrary handles updates internally,
        so there's nothing extra to connect in BoardView.
        """
        self.log.log(
            "debug",
            "BoardView: No additional signal connections required.",
            module="BoardView",
            func="connect_signals",
        )

    def mousePressEvent(self, event):
        if mouse_events.handle_mouse_press(self, event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if mouse_events.handle_mouse_move(self, event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if mouse_events.handle_mouse_release(self, event):
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if mouse_events.handle_wheel(self, event):
            return
        super().wheelEvent(event)

    def load_image(self, file_path: str, side: str):
        image_manager.load_image(self, file_path, side)

    def _get_currently_selected_pad_items(self) -> list:
        """Helper to get all selected pad items in the scene"""
        return [
            item
            for item in self.scene.selectedItems()
            if isinstance(item, SelectablePadItem)
        ]

    def switch_side(self):
        """
        Toggles the side (top/bottom), saves/restores the marker position in mm,
        and re-places the marker after switching sides. It also respects the
        image_hidden_by_filter flag so that if the PCB image is hidden,
        it remains hidden (and a board contour is drawn) even after switching sides.
        """
        current_side = self.flags.get_flag("side", "top")
        new_side = "bottom" if current_side == "top" else "top"

        # 1) Get the marker's mm coordinates BEFORE switching sides
        marker_coords = self.marker_manager.get_marker_board_coords()
        if marker_coords:
            x_mm, y_mm = marker_coords
            self.marker_pos[current_side] = (x_mm, y_mm)  # Save marker position in mm
            self.log.log(
                "debug",
                f"[switch_side] Saved marker for '{current_side}': ({x_mm:.2f}, {y_mm:.2f}) mm",
            )

        # 2) Toggle the side in flags
        self.flags.set_flag("side", new_side)

        # Ensure converter uses the correct image dimensions for the new side
        if new_side == "top" and self.top_image_size:
            self.converter.set_image_size(self.top_image_size)
            self.log.debug(
                f"[switch_side] Image size set to {self.top_image_size} for top"
            )
        elif new_side == "bottom" and self.bottom_image_size:
            self.converter.set_image_size(self.bottom_image_size)
            self.log.debug(
                f"[switch_side] Image size set to {self.bottom_image_size} for bottom"
            )

        # 3) Update image visibility based on image_hidden_by_filter.
        # If the image should remain hidden, hide both images.
        if getattr(self, "image_hidden_by_filter", False):
            if self.top_pixmap_item:
                self.top_pixmap_item.setVisible(False)
            if self.bottom_pixmap_item:
                self.bottom_pixmap_item.setVisible(False)
        else:
            # If images are to be shown normally, show the one corresponding to the new side.
            if new_side == "top":
                if self.top_pixmap_item:
                    self.top_pixmap_item.setVisible(True)
                if self.bottom_pixmap_item:
                    self.bottom_pixmap_item.setVisible(False)
            else:
                if self.bottom_pixmap_item:
                    self.bottom_pixmap_item.setVisible(True)
                if self.top_pixmap_item:
                    self.top_pixmap_item.setVisible(False)

        # Set the current_pixmap_item regardless of its visibility state.
        self.current_pixmap_item = (
            self.top_pixmap_item if new_side == "top" else self.bottom_pixmap_item
        )

        # 4) Update display side in the DisplayLibrary
        self.display_library.current_side = new_side.lower()
        self.display_library.update_display_side()
        self.log.log("info", f"Switched board side to '{new_side}'")

        # Reapply pad visibility state after re-rendering
        if getattr(self, "pads_hidden_by_filter", False):
            for item in self.display_library.displayed_objects.values():
                try:
                    item.setVisible(False)
                except Exception:
                    pass

        # 5) Restore the marker in the correct pixel position
        if marker_coords:
            x_mm, y_mm = marker_coords  # MM coordinates remain unchanged
            scene_x, scene_y = self.converter.mm_to_pixels(
                x_mm, y_mm
            )  # Convert mm → pixels for the new side
            self.marker_manager.place_marker(
                x_mm, y_mm
            )  # Place marker at new pixel position
            self.log.log(
                "debug",
                f"[switch_side] Marker correctly flipped for '{new_side}': ({x_mm:.2f}, {y_mm:.2f}) mm",
            )
            self.log.log(
                "debug",
                f"[switch_side] Marker repositioned in scene: ({scene_x:.2f}, {scene_y:.2f}) pixels for side '{new_side}'",
            )
            self.center_on(scene_x, scene_y)
            self.log.log(
                "info",
                f"[switch_side] Centered view on marker at ({scene_x:.2f}, {scene_y:.2f}) pixels.",
            )

        # 6) Respect the image_hidden_by_filter flag:
        # If the PCB image is supposed to be hidden, ensure the current image remains hidden and add a contour.
        if getattr(self, "image_hidden_by_filter", False):
            if self.current_pixmap_item:
                self.current_pixmap_item.setVisible(False)
            # Add board contour if not already present.
            if (
                not hasattr(self, "board_contour_item")
                or self.board_contour_item is None
            ):
                self.add_board_contour()
        else:
            # If the image is visible, remove any board contour.
            if (
                hasattr(self, "board_contour_item")
                and self.board_contour_item is not None
            ):
                self.scene.removeItem(self.board_contour_item)
                self.board_contour_item = None

        # Reapply digitation holes if the option is enabled
        if getattr(self, "digitation_holes_enabled", False):
            self.show_digitation_holes(True)

        # 7) Update the scene to ensure marker and other items are properly refreshed.
        self.scene.update()

        # 8) If a ghost component is active, refresh it so its scale matches
        # the new side's px↔mm ratio.
        if (
            self.component_placer
            and self.component_placer.ghost_component
            and self.component_placer.ghost_component.is_active
        ):
            ghost = self.component_placer.ghost_component
            follow_mouse = not getattr(ghost, "_draw_arrows", False)
            ghost.show_ghost(
                ghost.footprint,
                ghost.rotation_deg,
                flipped=ghost.flipped,
                follow_mouse=follow_mouse,
            )

    def fit_in_view(self):
        if not self.current_pixmap_item:
            self.log.log("warning", "No current pixmap item to fit.")
            return

        self.fitInView(self.current_pixmap_item, Qt.KeepAspectRatio)

        view_rect = self.viewport().rect()
        scene_rect = self.current_pixmap_item.boundingRect()

        x_scale = view_rect.width() / scene_rect.width()
        y_scale = view_rect.height() / scene_rect.height()
        self.base_scale = min(x_scale, y_scale) * 0.95

        self.resetTransform()
        self.scale(self.base_scale, self.base_scale)

        self.scene.setSceneRect(self.current_pixmap_item.boundingRect())
        self.log.log("debug", f"Scene rect set to: {self.scene.sceneRect()}")

        user_scale = self.zoom_manager.user_scale
        if user_scale != 1.0:
            self.scale(user_scale, user_scale)

        self.log.log(
            "debug",
            f"Fitted image to view. Base scale={self.base_scale:.4f}, user scale={user_scale}.",
        )

    def fit_in_view_and_reset_zoom(self):
        """
        Called after a small timer when the user hasn't zoomed yet.
        We do a typical `fitInView` to fill the window, resetting transforms.
        Because user_has_zoomed_yet=False, there's no custom zoom to preserve.
        """
        if self.user_has_zoomed_yet:
            return  # If user zoomed while the timer was pending, do nothing

        if not self.current_pixmap_item:
            self.log.log("warning", "No current pixmap item => skipping fit.")
            return

        self.log.log(
            "debug", "fit_in_view_and_reset_zoom => resetting transform for best fit."
        )

        # 1) Perform typical fit
        self.fitInView(self.current_pixmap_item, Qt.KeepAspectRatio)

        # 2) The user_scale is effectively 1.0. The transform is handled by QGraphicsView internally
        #    because we just did fitInView. We can also set user_scale=1.0 in the ZoomManager if wanted.
        if hasattr(self, "zoom_manager"):
            self.zoom_manager.user_scale = 1.0  # Not strictly required

        self.log.log("debug", "Window resized => re-fit done. user_scale reset to 1.0.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.user_has_zoomed_yet and self.current_pixmap_item:
            # If user hasn't zoomed, re-fit after a short delay
            self.resize_timer.start(100)
            self.log.log(
                "debug", "Window resized => re-fit in 100ms (no user zoom yet)."
            )

    def scene_to_board_coords(self, x: float, y: float) -> tuple:
        current_side = self.flags.get_flag("side", "top")
        try:
            x_mm, y_mm = self.converter.pixels_to_mm(x, y)
            self.log.log(
                "debug",
                f"scene_to_board_coords: side='{current_side}', scene=({x:.1f}, {y:.1f}) -> board=({x_mm:.2f}, {y_mm:.2f})",
            )
            return x_mm, y_mm
        except Exception as e:
            self.log.log("error", f"scene_to_board_coords: Failed. {e}")
            return (0.0, 0.0)

    def center_on(self, x: float, y: float):
        point = QPointF(x, y)
        self.centerOn(point)
        self.log.log("debug", f"View centered on ({x:.2f}, {y:.2f}).")

    def show_context_menu(self, selected_pads, global_pos):
        """
        Displays the context menu for the selected pads at the specified global position.
        """
        if not selected_pads:
            self.log.log("warning", "show_context_menu called with no pad items.")
            return

        self.log.log(
            "debug",
            f"Context menu opened for {len(selected_pads)} selected pads at {global_pos}",
        )

        menu = QMenu(self)

        # Existing actions
        copy_action = QAction("Copy", self)
        paste_action = QAction("Paste", self)
        delete_action = QAction("Delete", self)
        edit_action = QAction("Edit", self)
        list_action = QAction("List Selected Pads", self)
        cut_action = QAction("Cut", self)
        move_action = QAction("Move", self)

        copy_action.triggered.connect(
            lambda: actions.copy_pads(self.object_library, selected_pads)
        )
        paste_action.triggered.connect(
            lambda: actions.paste_pads(self.object_library, self.component_placer)
        )
        delete_action.triggered.connect(
            lambda: actions.delete_pads(self.object_library, selected_pads)
        )
        edit_action.triggered.connect(
            lambda: actions.edit_pads(self.object_library, selected_pads)
        )
        list_action.triggered.connect(lambda: actions.list_pads(selected_pads))
        cut_action.triggered.connect(
            lambda: actions.cut_pads(self.object_library, selected_pads)
        )
        move_action.triggered.connect(
            lambda: actions.move_pads(
                self.object_library, selected_pads, self.component_placer
            )
        )

        # NEW: "Export Footprint"
        export_footprint_action = QAction("Export Footprint", self)
        export_footprint_action.triggered.connect(
            lambda: self.export_footprint(selected_pads)
        )

        # Add actions to the menu
        menu.addAction(copy_action)
        menu.addAction(cut_action)
        menu.addAction(paste_action)
        menu.addAction(move_action)
        menu.addAction(delete_action)
        menu.addAction(edit_action)
        menu.addSeparator()
        menu.addAction(list_action)
        menu.addSeparator()
        menu.addAction(export_footprint_action)  # <-- new

        if not global_pos:
            global_pos = QCursor.pos()
            self.log.log(
                "warning",
                f"Invalid global_pos provided; using cursor position {global_pos}",
            )

        try:
            self.log.log("debug", f"Executing context menu at {global_pos}")
            menu.exec_(global_pos)
            self.log.log("debug", "Context menu executed successfully.")
        except Exception as e:
            self.log.log("error", f"Error executing context menu: {e}")

    def export_footprint(self, pad_items):
        """
        Exports the selected pads as a footprint (.nod file) and, if any pad
        has a non-empty 'prefix', also exports an .alf file using export_alf_file().
        The user is prompted for a footprint name and folder (defaulting to component_libraries).
        Finally, it refreshes the Components tree so the new files appear immediately.
        """
        if not pad_items:
            QMessageBox.information(
                self, "Export Footprint", "No pads selected to export."
            )
            return

        # 1) Prompt user for footprint name
        footprint_name, ok = QInputDialog.getText(
            self, "Export Footprint", "Enter footprint name:"
        )
        if not ok or not footprint_name.strip():
            return
        footprint_name = footprint_name.strip()

        # 2) Default export directory from MainWindow (if available)
        mw = self.window()
        default_dir = getattr(mw, "libraries_dir", "")  # fallback to empty if not found

        target_dir = QFileDialog.getExistingDirectory(
            self, "Select Export Directory", default_dir
        )
        if not target_dir:
            return

        # 3) Prepare the .nod file lines
        nod_path = os.path.join(target_dir, f"{footprint_name}.nod")
        lines = ["* SIGNAL COMPONENT PIN X Y PAD POS TECN TEST CHANNEL USER", ""]

        # We'll track relationships for ALF
        alf_relationships = []

        # Compute centre X for any bottom-side pads so we can mirror them
        bottom_objs = [
            p.board_object
            for p in pad_items
            if getattr(p.board_object, "test_position", "").lower() == "bottom"
        ]
        center_x_bottom = None
        if bottom_objs:
            xs = [obj.x_coord_mm for obj in bottom_objs]
            center_x_bottom = (min(xs) + max(xs)) / 2.0

        # 4) Build .nod lines (and see if any prefix is present)
        for pad_item in pad_items:
            obj = pad_item.board_object
            signal = obj.signal if obj.signal else f"S{obj.channel}"
            component_name = footprint_name  # override with user's chosen name
            pin = obj.pin
            x_mm = obj.x_coord_mm
            if center_x_bottom is not None and (
                getattr(obj, "test_position", "").lower() == "bottom"
            ):
                x_mm = 2 * center_x_bottom - x_mm
            y_mm = obj.y_coord_mm
            width_mils = mm_to_mils(obj.width_mm)
            height_mils = mm_to_mils(obj.height_mm)
            hole_mils = mm_to_mils(obj.hole_mm)

            pad_code = get_pad_code(
                obj.shape_type, width_mils, height_mils, hole_mils, obj.angle_deg
            )

            # Determine position
            pos_map = {"top": "T", "bottom": "B", "both": "O"}
            test_pos = (obj.test_position or "top").lower()
            pos = pos_map.get(test_pos, "T")

            # Technology map
            tecn_map = {"SMD": "S", "Through Hole": "T", "Mechanical": "M"}
            tecn = tecn_map.get(obj.technology, "S")

            # Testability map
            test_map = {
                "Forced": "F",
                "Testable": "T",
                "Not Testable": "N",
                "Terminal": "E",
            }
            test_ = test_map.get(obj.testability, "N")

            # Build one .nod line
            nod_line = (
                f'"{signal}" '
                f'"{component_name}" '
                f"{pin} "
                f"{x_mm:.3f} "
                f"{y_mm:.3f} "
                f"{pad_code} "
                f"{pos} "
                f"{tecn} "
                f"{test_} "
                f"{obj.channel}"
            )
            lines.append(nod_line)

            # If there's a prefix, we'll record an ALF relationship
            prefix_val = getattr(obj, "prefix", None)
            if prefix_val and prefix_val.strip():
                alf_relationships.append(
                    {
                        "component_name": footprint_name,
                        "prefix": prefix_val.strip(),
                        "pin": str(pin),
                    }
                )

        # 5) Write the .nod file
        try:
            with open(nod_path, "w") as f:
                for line in lines:
                    f.write(line + "\n")
        except Exception as e:
            QMessageBox.critical(
                self, "Export Footprint", f"Failed to write NOD file:\n{e}"
            )
            return

        # 6) If any prefix is found, export an .alf file with your existing helper
        if alf_relationships:
            alf_path = os.path.join(target_dir, f"{footprint_name}.alf")
            success = export_alf_file(alf_relationships, alf_path)
            if not success:
                QMessageBox.critical(
                    self, "Export Footprint", "Failed to write ALF file."
                )
                return

        # 7) Notify and refresh
        QMessageBox.information(
            self,
            "Export Footprint",
            f"Footprint '{footprint_name}' exported to:\n{target_dir}",
        )

        if hasattr(mw, "refresh_component_tree"):
            mw.refresh_component_tree()
        else:
            self.log.log(
                "warning",
                "No 'refresh_component_tree' method found in MainWindow. Footprint tree not updated.",
            )

    # --------------------------------------------------------------------------
    # Methods that call actions via the alias 'actions'
    # --------------------------------------------------------------------------
    def copy_selected_pads(self):
        """Handles Ctrl+C (Copy)"""
        selected_pads = self._get_selected_pads()
        if not selected_pads:
            self.log.log("warning", "No pads selected to copy.")
            return
        actions.copy_pads(self.object_library, selected_pads)

    def paste_selected_pads(self):
        """Handles Ctrl+V (Paste)"""
        # Here you may or may not use selected pads.
        actions.paste_pads(self.object_library, self.component_placer)

    def delete_selected_pads(self):
        """Handles Delete key"""
        selected_pads = self._get_selected_pads()
        if not selected_pads:
            self.log.log("warning", "No pads selected to delete.")
            return
        actions.delete_pads(self.object_library, selected_pads)

    def edit_selected_pads(self):
        """Handles Ctrl+E (Edit)"""
        selected_pads = self._get_selected_pads()
        if not selected_pads:
            self.log.log("warning", "No pads selected to edit.")
            return
        actions.edit_pads(self.object_library, selected_pads)

    def list_selected_pads(self):
        """Handles Ctrl+L (List)"""
        selected_pads = self._get_selected_pads()
        if not selected_pads:
            self.log.log("warning", "No pads selected to list.")
            return
        actions.list_pads(selected_pads)

    def cut_selected_pads(self):
        """Handles Ctrl+X (Cut)"""
        selected = self._get_selected_pads()
        if not selected:
            self.log.log("warning", "No pads selected to cut.")
            return
        try:
            actions.cut_pads(self.object_library, selected)
        except Exception as e:
            self.log.log("error", f"Error in cut_selected_pads: {e}")

    def move_selected_pads(self):
        """Handles Ctrl+M (Move)"""
        selected = self._get_selected_pads()
        if not selected:
            self.log.log("warning", "No pads selected to move.")
            return
        try:
            actions.move_pads(self.object_library, selected, self.component_placer)
        except Exception as e:
            self.log.log("error", f"Error in move_selected_pads: {e}")

    def open_pad_editor_dialog(self, pad_items):
        """
        Opens the PadEditorDialog for the currently selected pad items.
        """
        if not pad_items:
            self.log.log("info", "No pad items selected. Nothing to edit.")
            return

        # Convert pad_items (SelectablePadItem) -> BoardObject
        selected_pads = [p.board_object for p in pad_items]

        from edit_pads.pad_editor_dialog import PadEditorDialog

        dialog = PadEditorDialog(
            selected_pads, object_library=self.object_library, parent=self
        )

        # Optionally connect the dialog's signal so we can refresh if needed
        dialog.pads_updated.connect(self._refresh_scene_after_edit)

        dialog.exec_()  # Modal dialog

    def setup_undo_redo_shortcuts(self):
        # Create shortcuts for undo and redo
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        # Use a context that limits ambiguity to our widget and its children.
        self.undo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self.perform_undo)

        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.redo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.redo_shortcut.activated.connect(self.perform_redo)

    def perform_undo(self):
        if self.object_library.undo():
            self.display_library.clear_all_rendered_objects()
            self.display_library.render_initial_objects()
            self.log.log("info", "Undo performed.")
        else:
            self.log.log("warning", "[BoardView.perform_undo]: Nothing to undo.")

    def perform_redo(self):
        if self.object_library.redo():
            self.display_library.clear_all_rendered_objects()
            self.display_library.render_initial_objects()
            self.log.log("info", "Redo performed.")
        else:
            self.log.log("warning", "[BoardView.perform_redo]: Nothing to redo.")

    def reset_undo_history(self):
        """
        Clears the undo/redo stacks so that the baseline state is the current loaded project.
        This method should be called after a NOD file is loaded and after a successful save.
        """
        self.object_library.undo_redo_manager.clear()
        self.log.log("debug", "Undo/redo history reset.")

    def add_board_contour(self):
        """
        Create and add a rectangle outlining the board area.
        Assumes the board's dimensions are given by the current pixmap's boundingRect()
        or by the sceneRect if no image is present.
        """
        # Determine the contour rectangle. Here, we use the scene's rectangle.
        if self.current_pixmap_item:
            board_rect = self.current_pixmap_item.boundingRect()
        else:
            board_rect = self.scene.sceneRect()

        contour_pen = QPen(Qt.red, 2, Qt.DashLine)
        self.board_contour_item = QGraphicsRectItem(board_rect)
        self.board_contour_item.setPen(contour_pen)
        self.scene.addItem(self.board_contour_item)
        self.log.log("debug", f"Board contour added: {board_rect}")

    def update_scene(self):
        """
        Forces a full refresh of the scene by clearing and re-rendering all objects,
        then invalidating the scene and updating the viewport.
        """
        self.log.log(
            "debug", "update_scene: Forcing a full refresh of the scene and viewport."
        )

        # If we have a DisplayLibrary, let it handle the clearing and re-rendering:
        if hasattr(self, "display_library"):
            self.display_library.clear_all_rendered_objects()
            self.display_library.render_initial_objects()
        else:
            # Otherwise, just force the scene and viewport to update:
            self.scene.update()
            self.viewport().update()

        # Invalidate the entire scene so that all items are re-drawn.
        self.scene.invalidate(self.scene.sceneRect())
        self.viewport().update()

    def _refresh_scene_after_edit(self):
        """Lightweight refresh after pad edits."""
        self.scene.invalidate(self.scene.sceneRect())
        self.viewport().update()

    # --------------------------------------------------------------
    #  Ctrl+H : delegate to actions.flip_ghost_horizontal
    # --------------------------------------------------------------
    def flip_ghost_horizontal(self):
        from edit_pads import actions

        if self.component_placer:
            actions.flip_ghost_horizontal(self.component_placer)

    # ------------------------------------------------------------------
    #  Alt + Double Click Handler
    # ------------------------------------------------------------------
    def mouseDoubleClickEvent(self, event):
        """Select all pads and open the Pad Editor when Alt+double-click."""
        if event.modifiers() & Qt.AltModifier:
            all_pad_items = [
                item
                for key, item in self.display_library.displayed_objects.items()
                if isinstance(item, SelectablePadItem)
                and not str(key).endswith("_secondary")
            ]

            if all_pad_items:
                self.scene.clearSelection()
                for pad in all_pad_items:
                    pad.setSelected(True)

                actions.edit_pads(self.object_library, all_pad_items)
                event.accept()
                return

        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    #  Digitation Holes Handling
    # ------------------------------------------------------------------
    def calculate_component_rects(self):
        """Return bounding rectangles for each component in mm."""
        comp_rects = {}
        for obj in self.object_library.get_all_objects():
            comp = obj.component_name
            half_w = obj.width_mm / 2.0
            half_h = obj.height_mm / 2.0
            x1 = obj.x_coord_mm - half_w
            x2 = obj.x_coord_mm + half_w
            y1 = obj.y_coord_mm - half_h
            y2 = obj.y_coord_mm + half_h
            if comp not in comp_rects:
                comp_rects[comp] = [x1, y1, x2, y2]
            else:
                r = comp_rects[comp]
                r[0] = min(r[0], x1)
                r[1] = min(r[1], y1)
                r[2] = max(r[2], x2)
                r[3] = max(r[3], y2)
        return comp_rects

    def show_digitation_holes(self, enable: bool):
        """Overlay rectangles to simulate holes where digitation was made."""
        self.digitation_holes_enabled = enable
        self.log.debug(
            f"show_digitation_holes called with enable={enable}",
            module="BoardView",
            func="show_digitation_holes",
        )
        for item in list(self.cutout_items):
            self.cutout_group.removeFromGroup(item)
            self.scene.removeItem(item)
        self.cutout_items.clear()

        if not enable:
            self.log.debug(
                "Digitation holes disabled; cleared existing items.",
                module="BoardView",
                func="show_digitation_holes",
            )
            return

        from PyQt5.QtCore import QRectF
        from PyQt5.QtGui import QBrush, QPen

        rects = self.calculate_component_rects()
        self.log.debug(
            f"Creating {len(rects)} digitation hole rectangles.",
            module="BoardView",
            func="show_digitation_holes",
        )
        for rect in rects.values():
            x1, y1, x2, y2 = rect
            x1_px, y1_px = self.converter.mm_to_pixels(x1, y1)
            x2_px, y2_px = self.converter.mm_to_pixels(x2, y2)
            qrect = QRectF(x1_px, y1_px, x2_px - x1_px, y2_px - y1_px)
            item = QGraphicsRectItem(qrect)
            item.setBrush(QBrush(Qt.white))
            item.setPen(QPen(Qt.NoPen))
            item.setZValue(self.z_value_cutouts)
            self.cutout_group.addToGroup(item)
            self.cutout_items.append(item)
        self.log.debug(
            f"Added {len(self.cutout_items)} hole items to the scene.",
            module="BoardView",
            func="show_digitation_holes",
        )
