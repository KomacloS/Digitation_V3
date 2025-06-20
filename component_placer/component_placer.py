# component_placer.py

from PyQt5.QtCore import QObject, QPointF, pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QMessageBox
from typing import Optional, Dict, Any, List
import copy
from logs.log_handler import LogHandler
from objects.board_object import BoardObject
from objects.nod_file import BoardNodFile
from component_placer.normalizer import normalize_footprint
from edit_pads import actions
from math import radians, sin, cos
import os
from component_placer.component_input_dialog import ComponentInputDialog
from constants.constants import Constants


class Clipboard:
    def __init__(self):
        self.copied_objects = []

    def copy(self, objects: List[BoardObject]):
        self.copied_objects = copy.deepcopy(objects)
        LogHandler().info(
            f"Clipboard: Copied {len(self.copied_objects)} objects.",
            module="Clipboard",
            func="copy",
        )

    def paste(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.copied_objects) if self.copied_objects else []


clipboard = Clipboard()


class ComponentPlacer(QObject):
    component_placed = pyqtSignal(str)

    def __init__(
        self,
        board_view,
        object_library,
        ghost_component=None,
        project_manager=None,
        bom_handler=None,
        parent=None,
    ):
        super().__init__(parent)
        self.log = LogHandler()
        self.log.log("info", "ComponentPlacer initialized.")
        self.board_view = board_view
        self.object_library = object_library
        self.constants = Constants()
        self.nod_file = None
        self.footprint = None
        self.footprint_rotation = 0.0
        self.is_active = False
        self.ghost_component = ghost_component
        self.is_flipped = False
        self.project_manager = project_manager
        self.quick_anchors = {"A": None, "B": None}
        self.quick_params = None
        # Use the shared BOMHandler if provided; otherwise (should not happen) create a new one.
        if bom_handler is None:
            from component_placer.bom_handler import BOMHandler

            self.bom_handler = BOMHandler()
            self.log.log(
                "warning",
                "No BOMHandler provided; created a new instance.",
                module="ComponentPlacer",
                func="__init__",
            )
        else:
            self.bom_handler = bom_handler
            self.log.log(
                "info",
                "Using shared BOMHandler.",
                module="ComponentPlacer",
                func="__init__",
            )

    def copy_selected_objects(self, selected_objects: List[BoardObject]):
        if not selected_objects:
            QMessageBox.warning(None, "Copy Failed", "No objects selected to copy.")
            return
        clipboard.copy(selected_objects)
        self.log.log("info", f"Copied {len(selected_objects)} object(s) to clipboard.")

    def paste_objects(self):
        copied_data = clipboard.paste()
        if not copied_data:
            QMessageBox.warning(None, "Paste Failed", "Clipboard is empty.")
            return
        self.load_footprint_from_clipboard(copied_data)
        self.activate_placement()
        self.log.log("info", f"Pasting {len(copied_data)} objects.")

    def load_footprint_from_clipboard(self, copied_data: list) -> None:
        if not copied_data:
            self.log.log("warning", "Clipboard is empty. Cannot load footprint.")
            return
        source = {"pads": copied_data}
        self.footprint = normalize_footprint(source)
        self.log.log(
            "info",
            f"Loaded clipboard footprint with {len(self.footprint['pads'])} pads.",
        )

    def set_nod_file(self, nod_file: BoardNodFile) -> None:
        self.nod_file = nod_file
        self.log.log("info", f"ComponentPlacer: nod_file set to {nod_file.nod_path}")

    def load_footprint_from_nod(self, nod_file_path: str) -> bool:
        if not nod_file_path.lower().endswith(".nod"):
            self.log.log(
                "warning",
                f"Invalid file format for {nod_file_path}. Expected .nod extension.",
            )
            return False
        try:
            new_nod = BoardNodFile(nod_path=nod_file_path)
            new_nod.load()
            self.footprint = self._convert_objects_to_footprint(
                new_nod.get_all_objects()
            )
            self.log.log(
                "info",
                f"Footprint loaded from {nod_file_path}, containing {len(self.footprint['pads'])} pads.",
            )
            return True
        except Exception as e:
            self.log.log("error", f"Failed to parse .nod file: {e}")
            return False

    def on_user_left_click(self, scene_x: float, scene_y: float):
        if not self.is_active or not self.footprint:
            return
        if getattr(self, "align_mode", False):
            x_mm, y_mm = self.board_view.converter.pixels_to_mm(scene_x, scene_y)
            actions.align_pads(self.object_library, self, x_mm, y_mm)
        elif hasattr(self, "_move_channels") and self._move_channels:
            comp_name = self.footprint["pads"][0].get("component_name", "Unnamed")
            x_mm, y_mm = self.board_view.converter.pixels_to_mm(scene_x, scene_y)
            self._finalize_footprint_placement(
                x_mm, y_mm, {"component_name": comp_name}
            )
        else:
            # Create the input dialog and pass the shared BOMHandler so the dialog can update the BOM directly.
            dialog = ComponentInputDialog(bom_handler=self.bom_handler)
            # Connect the project_loaded_signal so that the dialog resets numbering if a project is loaded.
            if self.project_manager is not None:
                self.project_manager.project_loaded_signal.connect(
                    dialog.reset_auto_numbering
                )

            params = None
            while True:
                if params:
                    dialog.set_data(params)

                if dialog.exec_() != dialog.Accepted:
                    self.log.log("warning", "Placement canceled via input dialog.")
                    self.deactivate_placement()
                    return

                input_data = dialog.get_data()
                comp_name = input_data.get("component_name", "").strip()
                if not comp_name:
                    self.log.log(
                        "warning", "Placement canceled => no component name provided."
                    )
                    self.deactivate_placement()
                    return

                x_mm, y_mm = self.board_view.converter.pixels_to_mm(scene_x, scene_y)
                if self._finalize_footprint_placement(x_mm, y_mm, input_data):
                    break
                params = input_data

    def activate_placement(self, reset_orientation: bool = True):
        if not self.footprint:
            QMessageBox.warning(None, "No Footprint", "No footprint loaded to place.")
            return
        if self.ghost_component is None:
            self.log.log(
                "error",
                "ComponentPlacer: Ghost component is None. Cannot activate placement.",
            )
            QMessageBox.critical(
                None, "Error", "Ghost Component is missing. Restart application."
            )
            return

        if reset_orientation:
            self.footprint_rotation = 0.0
            self.is_flipped = False

        self.is_active = True
        self.ghost_component.show_ghost(
            self.footprint, self.footprint_rotation, flipped=self._should_flip()
        )
        self.log.log("info", "ComponentPlacer: Placement mode activated.")

        self.board_view.setFocus(Qt.ActiveWindowFocusReason)
        self.board_view.activateWindow()
        self.board_view.raise_()
        QTimer.singleShot(
            0, lambda: self.board_view.setFocus(Qt.ActiveWindowFocusReason)
        )
        QTimer.singleShot(
            0, lambda: self.board_view.viewport().setFocus(Qt.ActiveWindowFocusReason)
        )
        if hasattr(self.board_view, "input_handler"):
            self.board_view.input_handler.set_ghost_component(self.ghost_component)
            self.log.log(
                "info",
                "InputHandler updated with new ghost component after activation.",
            )
        self.log.log(
            "info",
            f"After activation: ghost_component.is_active = {self.ghost_component.is_active}",
        )

    def deactivate_placement(self, reset_orientation: bool = True):
        self.is_active = False
        # self.footprint = None  # <--- Remove or comment out this line
        if self.ghost_component:
            self.ghost_component.remove_ghost()
        if reset_orientation:
            self.footprint_rotation = 0.0
            self.is_flipped = False
        self.log.log("info", "ComponentPlacer: Placement mode deactivated.")
        self.board_view.setFocus()

    def rotate_footprint(self, angle_deg: float = 90.0) -> None:
        if not self.is_active or not self.footprint:
            self.log.log("debug", "rotate_footprint: Not active, returning.")
            return
        self.footprint_rotation = (self.footprint_rotation + angle_deg) % 360
        self.ghost_component.show_ghost(self.footprint, self.footprint_rotation)
        self.log.log(
            "info", f"ComponentPlacer: Ghost rotated to {self.footprint_rotation:.2f}°"
        )

    def on_board_clicked(self, scene_pos: QPointF):
        if not self.is_active or not self.footprint:
            return
        # Create the input dialog with the shared BOMHandler, same as on_user_left_click
        dialog = ComponentInputDialog(bom_handler=self.bom_handler)

        if self.project_manager is not None:
            self.project_manager.project_loaded_signal.connect(
                dialog.reset_auto_numbering
            )

        params = None
        while True:
            if params:
                dialog.set_data(params)

            if dialog.exec_() != dialog.Accepted:
                self.log.log("warning", "Placement canceled via input dialog.")
                self.deactivate_placement()
                return

            input_data = dialog.get_data()
            comp_name = input_data.get("component_name", "").strip()
            if not comp_name:
                self.log.log(
                    "warning", "Placement canceled => no component name provided."
                )
                self.deactivate_placement()
                return

            x_mm, y_mm = self.board_view.converter.pixels_to_mm(
                scene_pos.x(), scene_pos.y()
            )
            if self._finalize_footprint_placement(x_mm, y_mm, input_data):
                break
            params = input_data

    def _finalize_footprint_placement(
        self, x_mm: float, y_mm: float, input_data: dict
    ) -> bool:

        def transform_pad(pad):
            rad_val = radians(self.footprint_rotation)
            rel_x = pad["x_coord_mm"] - self.footprint["center_x"]
            rel_y = pad["y_coord_mm"] - self.footprint["center_y"]

            # rotate
            rx = rel_x * cos(rad_val) - rel_y * sin(rad_val)
            ry = rel_x * sin(rad_val) + rel_y * cos(rad_val)

            if self.is_flipped:  # mirror X if flip active
                rx = -rx

            # mirror pins horizontally when placing on bottom side so the
            # numbering matches the ghost orientation
            if side == "bottom":
                rx = -rx

            pos_x = x_mm + rx
            pos_y = y_mm + ry

            final_angle = (pad.get("angle_deg", 0.0) + self.footprint_rotation) % 360
            return pos_x, pos_y, final_angle

        def calc_new_pin(original_pin):
            if merge_choice:
                if missing_pins:
                    return missing_pins.pop(0)
                else:
                    nonlocal merge_counter
                    new_val = highest_pin + merge_counter
                    merge_counter += 1
                    return new_val
            else:
                return original_pin + highest_pin

        def get_alf_mapping(comp_base, comp_dir):
            alf_path = (
                os.path.join(comp_dir, comp_base + ".alf")
                if comp_dir
                else comp_base + ".alf"
            )
            self.log.log("info", f"Attempting ALF lookup at: {alf_path}")
            mapping = {}
            if os.path.exists(alf_path):
                from objects.alf_file import parse_alf_file

                relationships = parse_alf_file(alf_path)
                if relationships:
                    try:
                        mapping = {
                            int(rel["pin"]): rel["prefix"] for rel in relationships
                        }
                        self.log.log(
                            "info",
                            f"ALF mapping obtained (total {len(mapping)} entries).",
                        )
                    except Exception as e:
                        self.log.log("error", f"Error processing ALF file: {e}")
                else:
                    self.log.log(
                        "info",
                        f"ALF file found at {alf_path} but no valid relationships detected.",
                    )
            else:
                self.log.log("info", f"No ALF file found at {alf_path}.")
            return mapping

        side_flag = self.board_view.flags.get_flag("side", "top")
        side = side_flag.lower()
        is_move = hasattr(self, "_move_channels") and self._move_channels

        if is_move:
            comp_name = self.footprint["pads"][0].get(
                "component_name", input_data.get("component_name", "Unnamed")
            )
        else:
            comp_name = input_data.get("component_name", "")
            comp_name_result, merge_choice, highest_pin, missing_pins = (
                self._handle_duplicate_name_or_offset_pins(comp_name)
            )
            if comp_name_result is None:
                return False
            user_comp_name = comp_name_result
            comp_name = user_comp_name
            if self.nod_file and os.path.exists(self.nod_file.nod_path):
                comp_dir = os.path.dirname(self.nod_file.nod_path)
                comp_base = os.path.splitext(os.path.basename(self.nod_file.nod_path))[
                    0
                ]
            else:
                comp_dir = None
                comp_base = user_comp_name
            merge_counter = 1
            alf_mapping = get_alf_mapping(comp_base, comp_dir)

        if is_move:
            # -------------------------------------------
            #   MOVE MODE: Updating existing objects
            # -------------------------------------------
            updates = []
            for idx, pad in enumerate(self.footprint["pads"]):
                pos_x, pos_y, final_angle = transform_pad(pad)

                # Channel that this ghost-pad belongs to
                try:
                    ch = self._move_channels[idx]
                except IndexError:
                    self.log.log(
                        "error", "Mismatch between ghost pads and stored move channels."
                    )
                    continue

                orig_obj = self.object_library.objects.get(ch)
                if orig_obj is None:
                    self.log.log("warning", f"No object found for channel {ch}.")
                    continue

                # Create a copy so we don't mutate the library before push_state
                obj_copy = copy.deepcopy(orig_obj)

                # --------- 1) update live fields on the copy ----------
                obj_copy.x_coord_mm = pos_x
                obj_copy.y_coord_mm = pos_y
                obj_copy.angle_deg = final_angle
                obj_copy.test_position = side  # keep side in sync

                # --------- 2) sync backup fields on the copy ----------
                for attr_name, value in (
                    ("x_coord_mm_original", pos_x),
                    ("y_coord_mm_original", pos_y),
                    ("angle_deg_original", final_angle),
                ):
                    setattr(obj_copy, attr_name, value)

                updates.append(obj_copy)

            # Push the mutations through the partial-render path
            if updates:
                self.object_library.bulk_update_objects(updates, {})
                self.log.log(
                    "info",
                    f"Move mode: updated {len(updates)} pads and synchronised "
                    "backup coordinates.",
                )

            # Reset move state
            self._move_channels = []

        else:
            # -------------------------------------------
            #   NORMAL PLACEMENT: Creating new objects
            # -------------------------------------------
            new_objects = []
            for pad in self.footprint["pads"]:
                pos_x, pos_y, final_angle = transform_pad(pad)
                try:
                    original_pin = int(str(pad.get("pin", "0")).strip())
                except Exception:
                    original_pin = 0

                new_pin = calc_new_pin(original_pin)
                new_pin_str = str(new_pin)
                pad_prefix = pad.get("prefix", "")
                new_prefix = pad_prefix or alf_mapping.get(new_pin, "")

                board_obj = BoardObject(
                    component_name=comp_name,
                    pin=new_pin_str,
                    channel=None,
                    test_position=side,
                    testability=pad.get("testability", "Not Testable"),
                    x_coord_mm=pos_x,
                    y_coord_mm=pos_y,
                    technology=pad["technology"],
                    shape_type=pad["shape_type"],
                    width_mm=pad["width_mm"],
                    height_mm=pad["height_mm"],
                    hole_mm=pad["hole_mm"],
                    angle_deg=final_angle,
                    prefix=new_prefix,
                )
                new_objects.append(board_obj)

            self.log.log(
                "info",
                f"bulk_add: creating {len(new_objects)} new pads for component '{comp_name}'.",
            )

            # PARTIAL RENDER: no big re-render
            self.object_library.bulk_add(new_objects, skip_render=False)

        """
        # Attempt saving to the project file, if present
        project_nod = getattr(self, "project_nod_file", None)
        if project_nod and os.path.exists(project_nod.nod_path):
            try:
                project_nod.objects = self.object_library.get_all_objects()
                project_nod.save()
                self.log.log("info", f"Project nod file saved: {project_nod.nod_path}")
            except Exception as e:
                self.log.log("error", f"Error saving project nod file: {e}")
        else:
            self.log.log("warning", "Project nod file not available; skipping save.")
        """
        self.deactivate_placement(reset_orientation=False)
        self.component_placed.emit(comp_name)
        self.log.log("info", f"Placed component '{comp_name}'.")
        if not is_move:
            # Optionally auto-reactivate so user can place another copy
            self.activate_placement(reset_orientation=False)

        return True

    def _convert_objects_to_footprint(self, board_objects: List[BoardObject]) -> dict:
        if not board_objects:
            return {"pads": [], "center_x": 0.0, "center_y": 0.0}
        pads_list = []
        xs, ys = [], []
        for obj in board_objects:
            pad_data = {
                "pin": obj.pin,
                "x_coord_mm": obj.x_coord_mm,
                "y_coord_mm": obj.y_coord_mm,
                "shape_type": obj.shape_type,
                "width_mm": obj.width_mm,
                "height_mm": obj.height_mm,
                "hole_mm": obj.hole_mm,
                "angle_deg": obj.angle_deg,
                "testability": obj.testability,
                "technology": obj.technology,
            }
            pads_list.append(pad_data)
            xs.append(obj.x_coord_mm)
            ys.append(obj.y_coord_mm)
        center_x = (min(xs) + max(xs)) / 2.0
        center_y = (min(ys) + max(ys)) / 2.0
        return {"pads": pads_list, "center_x": center_x, "center_y": center_y}

    def _handle_duplicate_name_or_offset_pins(
        self, comp_name: str
    ) -> tuple[Optional[str], Optional[bool], int, Optional[List[int]]]:
        """
        Checks whether a component with the same name already exists.

        Returns a tuple:
          - comp_name (or None if the user cancels),
          - merge_choice: True if the user chooses to fill missing pins, False if they choose to append,
          - highest_pin: the highest pin number currently in use,
          - missing_pins: a sorted list of missing pin numbers (if any; otherwise None).
        """
        existing_objs = self.object_library.get_all_objects()
        same_name_objs = [
            o for o in existing_objs if o.component_name.lower() == comp_name.lower()
        ]
        if not same_name_objs:
            # No existing component with this name.
            return (comp_name, None, 0, None)
        # Collect existing pin numbers as integers.
        existing_pins = []
        for obj in same_name_objs:
            try:
                existing_pins.append(int(obj.pin))
            except Exception:
                pass
        highest_pin = max(existing_pins) if existing_pins else 0
        # Compute missing pins in the sequence 1 ... highest_pin.
        full_set = set(range(1, highest_pin + 1))
        missing = sorted(list(full_set - set(existing_pins)))

        # Prepare a message for the user.
        msg = f"Component '{comp_name}' already exists with pins: {sorted(existing_pins)}.\n"
        if missing:
            msg += f"Missing pins: {missing}.\nDo you want to fill these gaps with new pads?"
        else:
            msg += "No gaps found. Do you want to append new pads at the end?"

        # Show a dialog with three options.
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Duplicate Component Name")
        msg_box.setText(msg)
        fill_btn = msg_box.addButton("Fill Missing", QMessageBox.AcceptRole)
        append_btn = msg_box.addButton("Append", QMessageBox.RejectRole)
        msg_box.addButton("Cancel", QMessageBox.DestructiveRole)
        # Default button: if missing pins exist, default to Fill.
        msg_box.setDefaultButton(fill_btn if missing else append_btn)
        msg_box.exec_()
        clicked = msg_box.clickedButton()
        if clicked == fill_btn:
            return (comp_name, True, highest_pin, missing)
        elif clicked == append_btn:
            return (comp_name, False, highest_pin, None)
        else:
            # Cancelled.
            return (None, None, 0, None)

    @staticmethod
    def align_selected_pads(object_library, selected_pads, component_placer):
        """
        Activates the ghost component in align mode for the selected pads.
        Once the user places the ghost at the new location, the new center is used
        to compute a delta and align all pads.
        """
        from statistics import mean

        # Build a footprint dictionary from the selected pads.
        pads_data = []
        for pad in selected_pads:
            obj = pad.board_object
            pad_data = {
                "pin": obj.pin,
                "component_name": obj.component_name,
                "x_coord_mm": getattr(obj, "x_coord_mm_original", obj.x_coord_mm),
                "y_coord_mm": getattr(obj, "y_coord_mm_original", obj.y_coord_mm),
                "shape_type": obj.shape_type,
                "width_mm": obj.width_mm,
                "height_mm": obj.height_mm,
                "hole_mm": obj.hole_mm,
                "angle_deg": obj.angle_deg,  # In align mode we ignore rotation changes.
                "testability": obj.testability,
                "technology": obj.technology,
            }
            pads_data.append(pad_data)

        if not pads_data:
            return

        # Compute the original center of the selected pads.
        center_x = mean([pad["x_coord_mm"] for pad in pads_data])
        center_y = mean([pad["y_coord_mm"] for pad in pads_data])

        # Create a ghost footprint with these pads and center.
        footprint = {"pads": pads_data, "center_x": center_x, "center_y": center_y}
        component_placer.footprint = footprint

        # Activate ghost placement.
        component_placer.activate_placement()

    def flip_current_ghost(self):
        """Mirror the active ghost footprint and remember the state."""
        if not self.is_active or not self.ghost_component:
            return
        self.is_flipped = not self.is_flipped
        self.ghost_component.flip_horizontal()

    # 1) called by InputHandler.set_quick_anchor()
    def set_quick_anchor(self, anchor_id: str, x_px: float, y_px: float):
        """Store anchor A or B in mm coords and show its marker."""
        # convert from pixels → mm
        mm = self.board_view.converter.pixels_to_mm(x_px, y_px)
        self.quick_anchors[anchor_id] = mm
        # show the blue-cross anchor
        self.board_view.marker_manager.place_anchor(anchor_id, mm[0], mm[1])

    # 2) called on drag or nudge
    def nudge_quick_anchor(self, anchor_id: str, dx_mm: float, dy_mm: float):
        """Move one anchor by (dx,dy) mm and update its marker."""
        old = self.quick_anchors.get(anchor_id)
        if not old:
            return
        new = (old[0] + dx_mm, old[1] + dy_mm)
        self.quick_anchors[anchor_id] = new
        # update marker in px
        px = self.board_view.coord_converter.mm_to_px(*new)
        self.board_view.marker_manager.move_anchor(anchor_id, px.x(), px.y())

    # 3) build or refresh the fixed ghost footprint between A & B
    def update_quick_ghost(self):
        """
        Refresh the Quick Creation ghost footprint.
        - Before params: only anchors are shown via MarkerManager.
        - After params: build full footprint dict and call GhostComponent.
        """
        # need both anchors to proceed
        if None in self.quick_anchors.values():
            return

        # only once dialog params exist do we build & show a real ghost
        if self.quick_params:
            fp = self._generate_quick_footprint(self.quick_params)
            # the footprint dict must include center_x/center_y
            # Your _generate_quick_footprint should set these
            self.ghost_component.remove_ghost()
            self.ghost_component.show_ghost(
                fp, rotation_deg=0.0, flipped=self._should_flip(), follow_mouse=False
            )
        else:
            # No params yet: just ensure the two blue-cross anchors are drawn
            # (Markers were already placed by set_quick_anchor)
            # No need to call show_ghost() here
            return

    # 4) when the user presses Enter
    def open_quick_dialog(self):
        """Pop up the full ‘Set New Pins Information’ dialog."""
        dlg = ComponentInputDialog(parent=self.board_view.window())
        # you will need to adapt the dialog to capture all your fields
        if dlg.exec_() != dlg.Accepted:
            self.cancel_quick()
            return
        # collect parameters (you’ll implement get_quick_params())
        self.quick_params = dlg.get_quick_params()
        # refresh ghost now that we know pin counts, shape, etc.
        self.update_quick_ghost()
        # commit placement
        self.place_quick()

    # -------------------------------------------------------------------------
    #  QUICK-CREATION ─ commit pads as real BoardObjects
    # -------------------------------------------------------------------------
    def place_quick(self, dup_result=None):
        """
        Commit the last ghost-footprint and emit a detailed coordinate report:
          • Anchor A, Anchor B (mm)
          • For every pad:  Pin | Ghost-X Ghost-Y | Placed-X Placed-Y
        """
        log = LogHandler()
        fp = getattr(self, "_latest_quick_fp", None)

        if not fp or not fp.get("pads"):
            log.warning(
                "[QC] place_quick: nothing to place.",
                module="QuickCreate",
                func="place_quick",
            )
            return

        # ------------------------------------------------------------------
        # 1)  Prepare pads in **numeric** order
        # ------------------------------------------------------------------
        pads_sorted = sorted(fp["pads"], key=lambda p: int(str(p["pin"])))
        input_name = self.quick_params.get("component_name", "QC-COMP")

        if dup_result is None:
            while True:
                comp_name_res, merge_choice, highest_pin, missing_pins = (
                    self._handle_duplicate_name_or_offset_pins(input_name)
                )
                if comp_name_res is None:
                    log.warning(
                        "[QC] placement canceled due to duplicate name dialog.",
                        module="QuickCreate",
                        func="place_quick",
                    )
                    self.cancel_quick()
                    return
                break
        else:
            comp_name_res, merge_choice, highest_pin, missing_pins = dup_result

        comp_name = comp_name_res
        merge_counter = 1

        def calc_new_pin(original_pin: int) -> int:
            if merge_choice is None:
                return original_pin
            if merge_choice:
                if missing_pins:
                    return missing_pins.pop(0)
                nonlocal merge_counter
                new_val = highest_pin + merge_counter
                merge_counter += 1
                return new_val
            return original_pin + highest_pin

        # ------------------------------------------------------------------
        # 2)  Build BoardObject list
        # ------------------------------------------------------------------
        new_objs = []
        for pad in pads_sorted:
            try:
                orig_pin = int(str(pad["pin"]))
            except Exception:
                orig_pin = 0

            new_pin = calc_new_pin(orig_pin)

            obj = BoardObject(
                component_name=comp_name,
                pin=str(new_pin),
                x_coord_mm=pad["x_coord_mm"],
                y_coord_mm=pad["y_coord_mm"],
                width_mm=pad["width_mm"],
                height_mm=pad["height_mm"],
                hole_mm=pad["hole_mm"],
                shape_type=pad["shape_type"],
                test_position=pad["test_position"],
                testability=pad.get("testability", "Forced"),
                technology=pad["technology"],
                angle_deg=pad["angle_deg"],
                prefix=pad.get("prefix"),
            )
            new_objs.append(obj)

        # ------------------------------------------------------------------
        # 3) ── DEBUG REPORT ── anchors + per-pad coordinates
        # ------------------------------------------------------------------
        ax, ay = self.quick_anchors.get("A", (None, None))
        bx, by = self.quick_anchors.get("B", (None, None))

        pads_in_order = fp["pads"]  # exact order drawn by GhostComponent

        header = (
            f"[QC] Coordinate report for '{comp_name}':\n"
            + (
                f" Anchors →  A=({ax:.3f}, {ay:.3f})   " f"B=({bx:.3f}, {by:.3f})\n"
                if None not in (ax, ay, bx, by)
                else " Anchors →  A/B not defined\n"
            )
            + " Idx | Pin |   Ghost-X   Ghost-Y |  Placed-X  Placed-Y"
        )

        lines = [header]
        for idx, (pad, obj) in enumerate(zip(pads_in_order, new_objs), start=1):
            lines.append(
                f" {idx:>3} | {int(pad['pin']):>3} | "
                f"{pad['x_coord_mm']:9.3f} {pad['y_coord_mm']:9.3f} | "
                f"{obj.x_coord_mm:9.3f} {obj.y_coord_mm:9.3f}"
            )

        log.debug("\n".join(lines), module="QuickCreate", func="coord_report")

        # ------------------------------------------------------------------
        # 4)  Add to library + BOM + UI niceties
        # ------------------------------------------------------------------
        if hasattr(self.object_library, "bulk_add"):
            self.object_library.bulk_add(new_objs, skip_render=False)
        else:
            self.object_library.objects.extend(new_objs)

        if self.bom_handler:
            self.bom_handler.add_component(
                self.quick_params.get("component_name", ""),
                self.quick_params.get("function", ""),
                self.quick_params.get("value", ""),
                self.quick_params.get("package", ""),
                self.quick_params.get("part_number", ""),
            )

        if hasattr(self.board_view, "select_objects"):
            self.board_view.select_objects(new_objs)

        log.info(
            f"Quick-Created {len(new_objs)} pad(s) for '{comp_name}'",
            module="QuickCreate",
            func="place_quick",
        )

        # Clean up & (optionally) ready for next placement
        self.cancel_quick()

    def cancel_quick(self):
        """Abort Quick Creation: clear anchors, ghost, markers."""
        # reset internal state
        self.quick_anchors = {"A": None, "B": None}
        self.quick_params = None

        # remove any existing ghost
        if self.ghost_component:
            self.ghost_component.remove_ghost()

        # clear the two blue-cross anchors
        self.board_view.marker_manager.clear_quick_anchors()

    # ────────────────────────────────────────────────────────────────────────────
    # Helpers (stubs for you to fill in)
    # ────────────────────────────────────────────────────────────────────────────
    # ------------------------------------------------------------------
    #  Helper that produces the “IC-style snake” list used above
    # ------------------------------------------------------------------
    @staticmethod
    def snake_circular(cols: int, rows: int) -> list[tuple[int, int]]:
        """
        Build a “true circular” (IC‐style) snake order over a rows×cols grid.
        If rows >= cols, we snake **down** each column, then up the next column, etc.
        If cols  > rows, we snake **across** each row, then back across the next row, etc.

        Returns a flat list of (row, col) indices in the desired visitation order.
        """
        order: list[tuple[int, int]] = []

        if rows >= cols:
            # Vertical‐major snake: go down column 0, up column 1, down column 2, …
            for c in range(cols):
                if (c % 2) == 0:
                    # even column: top → bottom
                    for r in range(rows):
                        order.append((r, c))
                else:
                    # odd column: bottom → top
                    for r in reversed(range(rows)):
                        order.append((r, c))
        else:
            # Horizontal‐major snake: go left → right on row 0, then right → left on row 1, …
            for r in range(rows):
                if (r % 2) == 0:
                    # even row: left → right
                    for c in range(cols):
                        order.append((r, c))
                else:
                    # odd row: right → left
                    for c in reversed(range(cols)):
                        order.append((r, c))

        return order

    # ------------------------------------------------------------------
    #  Build footprint respecting the selected numbering scheme
    # ------------------------------------------------------------------
    def _generate_quick_footprint(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a rectangular pad grid and renumber it so that:
        - The chosen scheme (0=circular, 1=rows, 2=columns) is respected.
        - On the bottom side we mirror only the X axis.
        - Pin 1 is always the pad under Anchor A.
        """
        if None in self.quick_anchors.values() or not params:
            return {"pads": []}

        rows = max(int(params["y_pins"]), 1)
        cols = max(int(params["x_pins"]), 1)
        fp = self._build_grid_footprint(self.quick_anchors, params)

        # Build a 2D grid for lookup
        pad_grid = [[None] * cols for _ in range(rows)]
        for i, pad in enumerate(fp["pads"]):
            r, c = divmod(i, cols)
            pad_grid[r][c] = pad

        scheme = int(params.get("number_scheme", 0))

        # Find Anchor-A’s position in the grid
        ax, ay = self.quick_anchors["A"]
        a_r = min(range(rows), key=lambda r: abs(pad_grid[r][0]["y_coord_mm"] - ay))
        a_c = min(range(cols), key=lambda c: abs(pad_grid[0][c]["x_coord_mm"] - ax))

        # Build the index list according to the numbering scheme
        if scheme == 0:
            # Circular / IC‐snake
            idx_list = self.snake_circular(cols, rows)
            # rotate so Anchor-A is first
            start = next(
                i for i, (r, c) in enumerate(idx_list) if r == a_r and c == a_c
            )
            idx = idx_list[start:] + idx_list[:start]

        elif scheme == 1:
            # By rows: natural row order, mirror X only
            row_vis = list(range(rows))
            col_vis = list(range(cols))

            # rotate rows so Anchor-A’s row leads
            r0 = row_vis.index(a_r)
            row_vis = row_vis[r0:] + row_vis[:r0]
            # rotate columns so Anchor-A’s column leads
            c0 = col_vis.index(a_c)
            col_vis = col_vis[c0:] + col_vis[:c0]

            idx = [(r, c) for r in row_vis for c in col_vis]

        else:  # scheme == 2
            # By columns: natural row order, mirror X only
            col_vis = list(range(cols))
            row_vis = list(range(rows))

            # rotate columns so Anchor-A’s column leads
            c0 = col_vis.index(a_c)
            col_vis = col_vis[c0:] + col_vis[:c0]

            idx = [(r, c) for c in col_vis for r in row_vis]

        # Renumber and rebuild pad list
        create_prefix = bool(params.get("create_prefix"))
        prefix_table = self.constants.get(
            "quick_prefix_table",
            [
                "A",
                "B",
                "C",
                "D",
                "E",
                "F",
                "G",
                "H",
                "J",
                "K",
                "L",
                "M",
                "N",
                "P",
                "R",
                "T",
                "U",
                "V",
                "W",
                "Y",
                "AA",
                "AB",
                "AC",
                "AD",
                "AE",
                "AF",
                "AG",
                "AH",
            ],
        )

        ordered = []
        for r, c in idx:
            pad = pad_grid[r][c]
            pad["pin"] = len(ordered) + 1
            if create_prefix and scheme in (1, 2):
                if scheme == 1:
                    prefix_idx = row_vis.index(r)
                    number_idx = col_vis.index(c) + 1
                else:
                    prefix_idx = col_vis.index(c)
                    number_idx = row_vis.index(r) + 1
                letter = prefix_table[prefix_idx % len(prefix_table)]
                pad["prefix"] = f"{letter}{number_idx}"
            ordered.append(pad)

        fp["pads"] = ordered
        return fp

    # ------------------------------------------------------------------
    #  QUICK-CREATION  – live rebuild & redraw
    # ------------------------------------------------------------------
    def update_quick_footprint(self, anchors: dict, params: dict):
        """
        Called every time either an anchor moves **or** the dialog emits
        quick_params_changed.  We now:

        1. Run the full `_generate_quick_footprint()` helper so the pad
        order respects *params["number_scheme"]*.
        2. Cache the footprint in `_latest_quick_fp` for the final commit.
        3. Redraw the fixed ghost (follow_mouse = False) so numbering
        arrows are visible while the user tweaks values.
        """
        LogHandler().debug(
            f"[QC] update_quick_fp anchors={anchors} "
            f"x_pins={params.get('x_pins')} y_pins={params.get('y_pins')} "
            f"scheme={params.get('number_scheme')}",
            module="QuickCreate",
            func="update_quick_fp",
        )

        if None in anchors.values() or not params:
            return

        # <-- use the single entry-point that applies the numbering pattern
        fp = self._generate_quick_footprint(params)
        self._latest_quick_fp = fp  # keep for place_quick()

        # refresh the fixed ghost preview (with arrows)
        if self.ghost_component:
            self.ghost_component.remove_ghost()
            self.ghost_component.show_ghost(
                fp, flipped=self._should_flip(), follow_mouse=False
            )

    # -------------------------------------------------------------------------
    #  QUICK-CREATION ─ (re)build rectangular grid footprint from anchors
    # -------------------------------------------------------------------------
    def _build_grid_footprint(self, anchors: dict, p: dict) -> dict:
        """Create canonical pad list for ghost + final commit."""
        ax, ay = anchors["A"]
        bx, by = anchors["B"]

        cols = max(int(p.get("x_pins", 1)), 1)
        rows = max(int(p.get("y_pins", 1)), 1)

        width = float(p.get("width", 0.5))
        height = float(p.get("height", 0.5))
        hole = float(p.get("hole", 0.0))

        gui_shape = p.get("shape", "Round").lower()
        shape_map = {
            "round": "Round",
            "ellipse": "Ellipse",
            "square/rectangle": "Square/rectangle",
            "square/rectangle with hole": "Square/rectangle with Hole",
            "hole": "Hole",
        }
        shape_type = shape_map.get(gui_shape, "Square/rectangle")

        test_pos = p.get("test_side", "top").lower()  # always lower-case
        testab = p.get("testability", "Force")
        tech = p.get("technology", "SMD")

        dx = (bx - ax) / (cols - 1) if cols > 1 else 0.0
        dy = (by - ay) / (rows - 1) if rows > 1 else 0.0

        pads, pin = [], 1
        for r in range(rows):
            for c in range(cols):
                pads.append(
                    {
                        "pin": pin,
                        "x_coord_mm": ax + c * dx,
                        "y_coord_mm": ay + r * dy,
                        "width_mm": width,
                        "height_mm": height,
                        "hole_mm": hole,
                        "shape_type": shape_type,
                        "test_position": test_pos,
                        "testability": testab,
                        "technology": tech,
                        "angle_deg": 0.0,
                    }
                )
                pin += 1

        LogHandler().debug(
            f"[QC] built_fp rows={rows} cols={cols} pads={len(pads)} "
            f"shape_type={shape_type} "
            f"w={width:.2f} h={height:.2f} hole={hole:.2f}",
            module="QuickCreate",
            func="_build_grid_fp",
        )

        return {"center_x": (ax + bx) / 2.0, "center_y": (ay + by) / 2.0, "pads": pads}

    # ------------------------------------------------------------------
    #  generic adaptor: pushes one pad into ObjectLibrary no matter
    #  which actual helper names the project uses.
    # ------------------------------------------------------------------
    def _push_pad_to_library(self, pad_obj):
        """
        Try every known API variation to register a BoardObject pad
        in the ObjectLibrary instance.  Add here if you discover more.
        """
        lib = self.object_library
        for fn in ("add_pad", "add_object", "add_board_object", "add"):
            if hasattr(lib, fn):
                getattr(lib, fn)(pad_obj)
                return
        # last resort: list append (but still keeps undo/redo out)
        if hasattr(lib, "objects"):
            lib.objects.append(pad_obj)

    # ── helper: should the ghost be flipped? ──────────────────────────────
    def _should_flip(self) -> bool:
        """Return True only when the user toggled flipping."""
        return self.is_flipped
