import logging
from PyQt5.QtWidgets import QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, QTimer
from logs.log_handler import LogHandler
from edit_pads.pad_editor_dialog import PadEditorDialog
from objects.board_object import BoardObject
from objects.nod_file import BoardNodFile
from component_placer.component_placer import clipboard, ComponentPlacer
from component_placer.ghost import GhostComponent
from statistics import mean
import copy

# Initialize a logger
log = LogHandler(output="both")

from PyQt5.QtWidgets import QMessageBox


# --------------------
# Helper Protection Functions
# --------------------
def _ensure_selection(action_title, pads):
    """
    Checks if there is at least one pad selected.
    Displays a warning and returns False if not.
    """
    if not pads:
        QMessageBox.warning(
            None, action_title, f"No pads selected for {action_title.lower()}."
        )
        return False
    return True


def _ensure_clipboard_has_data():
    """
    Checks if there is valid data in the clipboard.
    Displays a warning and returns False if empty.
    """
    copied_data = clipboard.paste()  # Clipboard.paste() returns the current data.
    if not copied_data:
        QMessageBox.warning(None, "Paste Pads", "No valid pads in clipboard.")
        return False
    return True


def _get_valid_pads(action_title, pad_items):
    """
    Filters the provided pad_items to include only those that have a board_object attribute.
    If none are valid, a warning is displayed.
    Returns the filtered list.
    """
    valid_pads = [pad for pad in pad_items if hasattr(pad, "board_object")]
    if not valid_pads:
        QMessageBox.warning(
            None, action_title, f"No valid pads selected for {action_title.lower()}."
        )
    return valid_pads


def _extract_pad_data(pad, current_side, board_view):
    """
    Extracts pad data from a pad item (which must have a board_object attribute).
    - Uses original coordinates if available.
    - If the current board side is 'bottom', flips the x-coordinate using the board width in mm.
    - Returns a dictionary with the pad’s parameters.
    """
    obj = pad.board_object

    # Get the "original" mm coords if they exist, otherwise the current coords
    x_mm = getattr(obj, "x_coord_mm_original", obj.x_coord_mm)
    y_mm = getattr(obj, "y_coord_mm_original", obj.y_coord_mm)
    angle = obj.angle_deg

    # If side is "bottom", flip x by the board's physical width in mm
    if current_side == "bottom":
        # The bottom scale factor for width
        mm_per_pixel = board_view.converter.mm_per_pixels_bot
        # The board's pixel width * mm_per_pixel => total width in mm
        board_width_mm = board_view.converter.image_width * mm_per_pixel
        x_mm = board_width_mm - x_mm

    # Build a data dict describing this pad
    pad_data = {
        "pin": obj.pin,
        "x_coord_mm": x_mm,
        "y_coord_mm": y_mm,
        "angle_deg": angle,
        "shape_type": obj.shape_type,
        "width_mm": obj.width_mm,
        "height_mm": obj.height_mm,
        "hole_mm": obj.hole_mm,
        "testability": obj.testability,
        "technology": obj.technology,
        "prefix": getattr(obj, "prefix", ""),
    }
    return pad_data


def _update_scene(board_view):
    """
    Forces the board view to update its scene.
    If the board view has a display_library, it calls its update_display_side() method;
    otherwise, it updates the scene and viewport directly.
    """
    if hasattr(board_view, "display_library"):
        board_view.display_library.update_display_side()
    else:
        board_view.scene().update()
        board_view.viewport().update()


# --------------------
# Actions
# --------------------
def copy_pads(object_library, pad_items):
    """
    Copies the selected pads into the clipboard.
    The copied pad data are normalized so that they are expressed in a top‑oriented coordinate system.
    If the current board side is 'bottom', the x‑coordinate is flipped using the board width.
    Pin numbers are preserved by default and the pad's prefix is copied. If the
    selected pins have numeric gaps (e.g. 1, 3 or 1, 2, 4), the user is asked
    whether to keep the numbering or renumber sequentially starting at 1.
    """
    if not _ensure_selection("Copy Pads", pad_items):
        return

    valid_pad_items = _get_valid_pads("Copy Pads", pad_items)
    if not valid_pad_items:
        return

    board_view = valid_pad_items[0].scene().views()[0]
    current_side = board_view.flags.get_flag("side", "top").lower()

    log = board_view.log
    log.log(
        "info",
        f"copy_pads: current_side = {current_side}",
        module="copy_pads",
        func="start",
    )

    try:
        sorted_pad_items = sorted(
            valid_pad_items, key=lambda pad: int(pad.board_object.pin)
        )
    except Exception as e:
        log.log(
            "warning",
            f"Sorting pads by pin failed: {e}. Using original order.",
            module="copy_pads",
            func="start",
        )
        sorted_pad_items = valid_pad_items

    preserve_numbers = True
    numeric_pins = []
    for pad in sorted_pad_items:
        pin_str = str(pad.board_object.pin)
        if pin_str.isdigit():
            numeric_pins.append(int(pin_str))
        else:
            numeric_pins = []
            break

    if len(numeric_pins) > 1:
        numbers_sorted = sorted(numeric_pins)
        gaps = any(b - a != 1 for a, b in zip(numbers_sorted, numbers_sorted[1:]))
        starts_at_one = numbers_sorted[0] == 1
        if gaps or not starts_at_one:
            reply = QMessageBox.question(
                None,
                "Copy Pads",
                "Gaps detected or numbering doesn't start at 1. Preserve numbering?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            preserve_numbers = reply == QMessageBox.Yes

    pads_data = []
    for idx, pad in enumerate(sorted_pad_items):
        pad_data = _extract_pad_data(pad, current_side, board_view)
        pad_data["order"] = idx
        if not preserve_numbers:
            pad_data["pin"] = str(idx + 1)
        pads_data.append(pad_data)

        log.log(
            "debug",
            f"Copied pad: pin={pad.board_object.pin}, x={pad_data['x_coord_mm']:.2f} mm, y={pad_data['y_coord_mm']:.2f} mm, "
            f"angle={pad_data['angle_deg']:.2f}°, shape={pad_data['shape_type']}, width={pad_data['width_mm']:.2f}, "
            f"height={pad_data['height_mm']:.2f}, hole={pad_data['hole_mm']:.2f}, prefix='{pad_data['prefix']}'",
            module="copy_pads",
            func="for-loop",
        )

    if pads_data:
        xs = [pad["x_coord_mm"] for pad in pads_data]
        ys = [pad["y_coord_mm"] for pad in pads_data]
        center_x = (min(xs) + max(xs)) / 2.0
        center_y = (min(ys) + max(ys)) / 2.0
    else:
        center_x, center_y = 0.0, 0.0

    clipboard.copy(pads_data)
    clipboard.center_x = center_x
    clipboard.center_y = center_y

    QMessageBox.information(None, "Copy Pads", f"Copied {len(pads_data)} pads.")


def paste_pads(object_library, component_placer):
    """
    Pastes pads from the clipboard.
    Protection: if there is no valid copied pad data in the clipboard, the paste is aborted.
    After activation, the scene is updated.
    """
    if not _ensure_clipboard_has_data():
        return

    copied_data = clipboard.paste()  # Returns list of copied pad dictionaries
    log.log("info", f"Pasting {len(copied_data)} pads.")

    if component_placer.ghost_component is None:
        from component_placer.ghost import GhostComponent

        component_placer.ghost_component = GhostComponent(component_placer.board_view)
        component_placer.log.log("info", "Ghost component created for pasting.")

    log.log(
        "debug", f"ComponentPlacer ghost_component: {component_placer.ghost_component}"
    )

    component_placer.load_footprint_from_clipboard(copied_data)
    component_placer.activate_placement()

    # Delay focus enforcement as before.
    QTimer.singleShot(
        150,
        lambda: (
            component_placer.board_view.setFocus(Qt.ActiveWindowFocusReason),
            component_placer.board_view.viewport().setFocus(Qt.ActiveWindowFocusReason),
            component_placer.board_view.activateWindow(),
            component_placer.board_view.raise_(),
            log.log("debug", "Paste action post-delay focus enforced."),
        ),
    )

    log.log("info", "ComponentPlacer activated for pasting.")


def delete_pads(object_library, pad_items, display_library=None):
    """
    Deletes the selected pads from the object library as a bulk operation.
    After deletion, the scene is updated.
    If display_library is not provided, it is obtained from the first valid pad's view.
    Additionally, if deletion completely removes a component, the BOM is updated.
    """
    if not _ensure_selection("Delete Pads", pad_items):
        return

    valid_pad_items = _get_valid_pads("Delete Pads", pad_items)
    if not valid_pad_items:
        return

    if display_library is None:
        board_view = valid_pad_items[0].scene().views()[0]
        try:
            display_library = board_view.display_library
        except AttributeError:
            QMessageBox.warning(None, "Delete Pads", "Display library not available.")
            return

    channels = [
        pad.board_object.channel
        for pad in valid_pad_items
        if pad.board_object.channel is not None
    ]

    reply = QMessageBox.question(
        None,
        "Delete Pads",
        f"Are you sure you want to delete the following pads?\n\n{channels}",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )

    if reply == QMessageBox.Yes:
        object_library.bulk_delete(channels)

        # Update BOM: remove components that no longer exist in the object library.
        if hasattr(object_library, "bom_handler"):
            current_components = {
                obj.component_name for obj in object_library.get_all_objects()
            }
            # Iterate over a copy of the BOM keys to allow safe deletion.
            for comp in list(object_library.bom_handler.bom.keys()):
                if comp not in current_components:
                    object_library.bom_handler.remove_component(comp)
                    display_library.log.log(
                        "info",
                        f"Removed component '{comp}' from BOM because it no longer exists.",
                        module="delete_pads",
                        func="delete_pads",
                    )

        display_library.log.log(
            "info",
            f"Deleted pads: {channels}",
            module="delete_pads",
            func="delete_pads",
        )
        QMessageBox.information(None, "Delete", f"Deleted pads: {channels}")
    else:
        display_library.log.log(
            "info", "Pad deletion canceled.", module="delete_pads", func="delete_pads"
        )


def edit_pads(object_library, pad_items):
    """
    Opens the PadEditorDialog to modify the selected pads' properties.
    After any edits, the scene is refreshed by calling board_view.update_scene().
    """
    if not _ensure_selection("Edit Pads", pad_items):
        return

    valid_pad_items = _get_valid_pads("Edit Pads", pad_items)
    if not valid_pad_items:
        return

    selected_channels = [pad.board_object.channel for pad in valid_pad_items]
    board_objects = [
        object_library.objects[ch]
        for ch in selected_channels
        if ch in object_library.objects
    ]

    if not board_objects:
        QMessageBox.warning(None, "Edit Pads", "No valid pads found to edit.")
        return

    log.log(
        "info",
        f"Editing pads with channels: {selected_channels}",
        module="edit_pads",
        func="edit_pads",
    )

    # Retrieve the current board_view from the first pad item.
    # This ensures we have the correct QGraphicsView instance to refresh the scene.
    board_view = valid_pad_items[0].scene().views()[0] if valid_pad_items else None

    from edit_pads.pad_editor_dialog import PadEditorDialog

    dialog = PadEditorDialog(
        selected_pads=board_objects,
        object_library=object_library,
        board_view=board_view,  # <-- Pass the board_view to the dialog
    )
    if dialog.exec_():
        log.log(
            "info", "Pads edited successfully.", module="edit_pads", func="edit_pads"
        )
    else:
        log.log("info", "Pad edit canceled.", module="edit_pads", func="edit_pads")


def cut_pads(object_library, pad_items):
    """
    Copies the selected pads into the clipboard and then deletes them.
    The copied pad data are normalized (and flipped if needed) in the same way as the copy and move operations.
    After deletion, the scene is updated.
    """
    if not _ensure_selection("Cut Pads", pad_items):
        return

    valid_pad_items = _get_valid_pads("Cut Pads", pad_items)
    if not valid_pad_items:
        return

    board_view = valid_pad_items[0].scene().views()[0]
    current_side = board_view.flags.get_flag("side", "top").lower()

    copied_data = []
    for pad in valid_pad_items:
        pad_data = _extract_pad_data(pad, current_side, board_view)
        copied_data.append(pad_data)
    clipboard.copy(copied_data)

    channels = [
        pad.board_object.channel
        for pad in valid_pad_items
        if pad.board_object.channel is not None
    ]
    object_library.bulk_delete(channels)

    QMessageBox.information(None, "Cut Pads", f"Cut {len(copied_data)} pads.")


def move_pads(object_library, pad_items, component_placer):
    """
    Initiates a move of the selected pads.
    The selected pads are loaded into the ghost component (allowing the user to place them at a new location),
    and the original pads will later be replaced by the new ones in a single bulk operation.
    Uses the same bottom‑side flipping logic as copy‑paste.
    The moved pads will retain the same component name, pin numbers, channel, signal, and also their prefix.
    After activation, the scene is updated.
    """
    if not _ensure_selection("Move Pads", pad_items):
        return

    valid_pad_items = _get_valid_pads("Move Pads", pad_items)
    if not valid_pad_items:
        return

    board_view = valid_pad_items[0].scene().views()[0]
    current_side = board_view.flags.get_flag("side", "top").lower()

    pads_data = []
    for pad in valid_pad_items:
        pad_data = _extract_pad_data(pad, current_side, board_view)
        # Add extra fields needed for move.
        obj = pad.board_object
        pad_data["component_name"] = obj.component_name
        pad_data["channel"] = obj.channel
        pad_data["signal"] = getattr(obj, "signal", None)
        pads_data.append(pad_data)

    if not pads_data:
        QMessageBox.warning(None, "Move Pads", "No valid pad data available.")
        return

    xs = [pad["x_coord_mm"] for pad in pads_data]
    ys = [pad["y_coord_mm"] for pad in pads_data]
    footprint = {
        "pads": pads_data,
        "center_x": (min(xs) + max(xs)) / 2.0,
        "center_y": (min(ys) + max(ys)) / 2.0,
    }

    if component_placer.ghost_component is None:
        from component_placer.ghost import GhostComponent

        component_placer.ghost_component = GhostComponent(component_placer.board_view)
        board_view.log.log("info", "Ghost component created for moving.")

    component_placer.load_footprint_from_clipboard(pads_data)
    component_placer.activate_placement()
    component_placer._move_channels = [
        pad.board_object.channel for pad in valid_pad_items
    ]


def align_selected_pads(object_library, selected_pads, component_placer):
    """
    Initiates an align operation based on the selected pads.

    Builds a ghost footprint from the selected pads (using their original coordinates).
    If the current board side is 'bottom', the x‑coordinate is flipped (as in move mode).
    Computes the average center and assigns the footprint to the ComponentPlacer.
    Sets the align_mode flag so that no component name is prompted and rotation/side switching are disabled.

    After the user moves the ghost to the desired location, the ghost’s final center (in mm)
    will be used to call align_pads() to update all pads.
    """
    if not _ensure_selection("Align Pads", selected_pads):
        return

    valid_pad_items = _get_valid_pads("Align Pads", selected_pads)
    if not valid_pad_items:
        return

    board_view = valid_pad_items[0].scene().views()[0]
    current_side = board_view.flags.get_flag("side", "top").lower()
    board_width_mm = None
    if current_side == "bottom":
        board_width_mm = (
            board_view.converter.image_width * board_view.converter.mm_per_pixels_bot
        )

    pads_data = []
    for pad in valid_pad_items:
        obj = pad.board_object
        x = getattr(obj, "x_coord_mm_original", obj.x_coord_mm)
        if current_side == "bottom" and board_width_mm is not None:
            x = board_width_mm - x
        y = getattr(obj, "y_coord_mm_original", obj.y_coord_mm)
        pad_data = {
            "pin": obj.pin,
            "component_name": obj.component_name,
            "x_coord_mm": x,
            "y_coord_mm": y,
            "shape_type": obj.shape_type,
            "width_mm": obj.width_mm,
            "height_mm": obj.height_mm,
            "hole_mm": obj.hole_mm,
            "angle_deg": obj.angle_deg,  # Keep the existing angle.
            "testability": obj.testability,
            "technology": obj.technology,
        }
        pads_data.append(pad_data)

    if not pads_data:
        QMessageBox.warning(None, "Align Pads", "No valid pad data found.")
        return

    center_x = mean([pad["x_coord_mm"] for pad in pads_data])
    center_y = mean([pad["y_coord_mm"] for pad in pads_data])

    footprint = {"pads": pads_data, "center_x": center_x, "center_y": center_y}
    component_placer.footprint = footprint
    component_placer.align_mode = True
    component_placer.activate_placement()
    log.log(
        "info",
        "Align mode activated (flipping applied if on bottom; rotation and side switching disabled). "
        "Please move the ghost to the correct alignment position.",
    )


# ------------------------------------------------------------------
# Flip ghost helper (called from BoardView shortcut)
# ------------------------------------------------------------------
def flip_ghost_horizontal(component_placer):
    """
    Toggles horizontal mirroring on the active ghost component.
    Safe no-op if placement mode isn't active.
    """
    if component_placer:
        component_placer.flip_current_ghost()
