# objects/nod_file.py

import re
import os
from typing import List, Optional
from objects.board_object import BoardObject
from objects.object_library import ObjectLibrary
from logs.log_handler import LogHandler
from PyQt5.QtWidgets import QMessageBox
from io import StringIO
from utils.file_ops import safe_write, rotate_backups

# Helper functions are included here for parsing and formatting

def parse_component_nod_file(nod_file_path):
    """
    Parses a .nod file and extracts components into a structured format.

    Parameters:
        nod_file_path (str): Path to the .nod file.

    Returns:
        dict: A dictionary containing the component name and a list of parsed pads.
    """
    if not os.path.exists(nod_file_path):
        LogHandler().log("error", f"File not found: {nod_file_path}")
        return None

    pads = []
    component_name = None  # Initialize the component name

    with open(nod_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines or lines starting with an asterisk (comments)
            if not line or line.startswith('*'):
                continue

            import shlex
            tokens = shlex.split(line)
            # Skip header row if detected (e.g., first token is 'signal')
            if tokens and tokens[0].lower() == "signal":
                continue

            if len(tokens) < 10:
                LogHandler().log("warning", f"Invalid line in {nod_file_path}: {line}")
                continue

            # Extract fields from tokens
            signal = tokens[0]
            comp = tokens[1]  # COMPONENT name
            pin = int(tokens[2])
            x_mm = float(tokens[3])  # Already in mm
            y_mm = float(tokens[4])  # Already in mm
            pad_str = tokens[5]
            pos = tokens[6]
            tecn = tokens[7]
            test = tokens[8]

            # Ensure 'component_name' is set once
            if component_name is None:
                component_name = comp

            test_position = {"T": "Top", "B": "Bottom", "O": "Both"}.get(pos, "Top")
            technology = {"S": "SMD", "T": "Through Hole", "M": "Mechanical"}.get(tecn, "SMD")
            testability = {"F": "Forced", "T": "Testable", "N": "Not Testable", "E": "Terminal"}.get(test, "Not Testable")

            shape_type, width_mils, height_mils, hole_mils, angle_deg = parse_pad(pad_str)

            width_mm = mils_to_mm(width_mils)
            height_mm = mils_to_mm(height_mils)
            hole_mm = mils_to_mm(hole_mils)

            pad_info = {
                "component_name": comp,  # Explicitly include component name
                "signal": signal,
                "pin": pin,
                "x_coord_mm": x_mm,  # Changed key to match BoardObject expectation
                "y_coord_mm": y_mm,  # Changed key to match BoardObject expectation
                "shape_type": shape_type,
                "width_mm": width_mm,
                "height_mm": height_mm,
                "hole_mm": hole_mm,
                "angle_deg": angle_deg,
                "testability": testability,
                "technology": technology,
                "test_position": test_position,
                "channel": int(tokens[9])
            }

            pads.append(pad_info)

    return {
        "component_name": component_name,
        "pads": pads
    }



def parse_pad(pad_str: str):
    """
    Parses the pad string from a .nod file to extract shape parameters.
    The pad string is expected to contain letter-number groups (X, Y, R, H, A)
    in any order. In addition, if only X (or only Y) is present, it is assumed
    to be a square, i.e. Y is set equal to X.
    
    Returns:
        tuple: (shape_type, width_mils, height_mils, hole_mils, angle_deg)
    
    Examples:
      - "X79Y59A270H35" returns:
            shape_type = "Square/rectangle with Hole"
            width_mils = 79, height_mils = 59, hole_mils = 35, angle_deg = 270
      - "R55H28" returns:
            shape_type = "Round with Hole"
            width_mils = 55, height_mils = 55, hole_mils = 28, angle_deg = 0
      - "X55" returns:
            shape_type = "Square/rectangle"
            width_mils = 55, height_mils = 55, hole_mils = 0, angle_deg = 0
      - "X34H12" returns:
            shape_type = "Square/rectangle with Hole"
            width_mils = 34, height_mils = 34, hole_mils = 12, angle_deg = 0
    """
    # Normalize the pad string to uppercase.
    pad_str = pad_str.upper()

    # Use a regex to find all letter-number groups.
    pattern = re.compile(r'([XYRAH])([\d\.]+)')
    matches = pattern.findall(pad_str)

    # Build a dictionary from the found groups.
    data = {}
    for letter, number in matches:
        try:
            value = float(number)
        except ValueError:
            value = 0.0
        data[letter] = value

    # Additional logic: if only X is present (or only Y), set the missing value equal.
    if 'X' in data and 'Y' not in data:
        data['Y'] = data['X']
    if 'Y' in data and 'X' not in data:
        data['X'] = data['Y']

    # Get the angle (if present) and hole size.
    angle_deg = data.get('A', 0.0)
    hole_mils = data.get('H', 0.0)

    # Determine the shape and dimensions.
    # If X and Y are provided, treat it as a square/rectangle.
    if 'X' in data and 'Y' in data:
        width_mils = data['X']
        height_mils = data['Y']
        shape_type = "Square/rectangle with Hole" if hole_mils > 0 else "Square/rectangle"
    # If R is provided, treat it as a round pad.
    elif 'R' in data:
        width_mils = data['R']
        height_mils = width_mils
        shape_type = "Round with Hole" if hole_mils > 0 else "Round"
    else:
        # Fallback default values.
        width_mils = 20.0
        height_mils = 20.0
        shape_type = "Square/rectangle"

    return shape_type, width_mils, height_mils, hole_mils, angle_deg




def get_footprint_for_placer(nod_file_path):
    """
    Loads a .nod file using parse_component_nod_file, then augments
    the data with center_x and center_y for use by ComponentPlacer.

    :param nod_file_path: Path to the .nod file.
    :return: A dict suitable for the ComponentPlacer, or None if parsing fails.
             Format:
             {
               "component_name": <str>,
               "pads": [ <pad_info_dict>, ... ],
               "center_x": <float>,
               "center_y": <float>
             }
    """
    log = LogHandler()
    log.log("debug", f"get_footprint_for_placer called with path: {nod_file_path}")

    footprint_data = parse_component_nod_file(nod_file_path)
    if not footprint_data:
        log.log("warning", f"Failed to parse .nod file or file not found: {nod_file_path}")
        return None

    pads = footprint_data.get("pads", [])
    if not pads:
        log.log("warning", f"No pads found in the parsed data for {nod_file_path}")
        return None

    xs = [pad["x_coord_mm"] for pad in pads]
    ys = [pad["y_coord_mm"] for pad in pads]
    center_x = (min(xs) + max(xs)) / 2.0
    center_y = (min(ys) + max(ys)) / 2.0

    footprint_data["center_x"] = center_x
    footprint_data["center_y"] = center_y

    comp_name = footprint_data.get("component_name", "Unknown")
    log.log(
        "info",
        f"Loaded footprint '{comp_name}' with {len(pads)} pad(s). "
        f"Center at ({center_x:.2f}, {center_y:.2f}) mm."
    )

    return footprint_data


def mils_to_mm(mils: float) -> float:
    """
    Converts mils to millimeters.

    Parameters:
        mils (float): Value in mils.

    Returns:
        float: Value in millimeters.
    """
    return mils / 39.37


def mm_to_mils(mm: float) -> float:
    """
    Converts millimeters to mils.

    Parameters:
        mm (float): Value in millimeters.

    Returns:
        float: Value in mils.
    """
    return mm * 39.37


def obj_to_nod_line(obj: dict, logger: Optional[LogHandler] = None) -> str:
    """
    Converts a BoardObject dictionary to a .nod file line format.
    Parameters:
        obj (dict): A dictionary representation of the BoardObject.
        logger (Optional[LogHandler]): Logger for recording debug information.
    Returns:
        str: The .nod file line.
    """
    # Generate signal as "S" + channel if not provided.
    signal = obj.get("signal", f"S{obj['channel']}")
    component_name = obj["component_name"]
    pin = obj["pin"]
    x_mm = obj["x_coord_mm"]
    y_mm = obj["y_coord_mm"]
    # IMPORTANT: Get hole_mm from obj if available, otherwise default to 0.0
    hole_mm = obj.get("hole_mm", 0.0)
    # Convert dimensions from mm to mils.
    width_mils = mm_to_mils(obj["width_mm"])
    height_mils = mm_to_mils(obj["height_mm"])
    hole_mils = mm_to_mils(hole_mm)
    # Get pad code. (get_pad_code() already checks shape type and includes an 'H' value if hole_mils > 0.)
    pad = get_pad_code(obj["shape_type"], width_mils, height_mils, hole_mils, obj["angle_deg"])
    
    # Map test position (case–insensitive)
    test_position_lower = obj["test_position"].lower()
    pos_map = {"top": "T", "bottom": "B", "both": "O"}
    pos = pos_map.get(test_position_lower, "T")
    
    # Map technology and testability.
    tecn = {"SMD": "S", "Through Hole": "T", "Mechanical": "M"}.get(obj["technology"], "S")
    test = {"Forced": "F", "Testable": "T", "Not Testable": "N", "Terminal": "E"}.get(obj["testability"], "N")
    
    # Construct and return the line.
    return f"\"{signal}\" \"{component_name}\" {pin} {x_mm:.3f} {y_mm:.3f} {pad} {pos} {tecn} {test} {obj['channel']}"


def get_pad_code(shape_type: str, width_mils: float, height_mils: float, hole_mils: float, angle_deg: float) -> str:
    """
    Generates a pad code for a .nod file based on the shape parameters.
    
    - If shape_type == "Round", ignore the hole and include angle only if non-zero.
    - If shape_type == "Round with Hole" or "Hole", include the hole if > 0, but ignore the angle.
    - If shape_type includes "square/rectangle":
        * If shape_type says "with Hole," include the hole code as well.
        * Otherwise, omit hole code.
        * Append angle if non-zero.
    - If shape_type == "Ellipse":
        * Use X{w}Y{h}, optionally with angle.
        * (Hole is typically ignored for elliptical pads, but you can adapt if needed.)
    - Fallback to "Round" if none match.
    """
    w = round(width_mils)
    h = round(height_mils)
    hole = round(hole_mils)

    angle_str = f"A{int(angle_deg)}" if angle_deg != 0 else ""
    lower_shape = shape_type.lower()

    # 1) Strict "Round": ignore hole
    if lower_shape == "round":
        return f"R{w}"

    # 2) "Round with Hole" or "Hole": include hole if > 0, ignore angle
    elif lower_shape in ("round with hole", "hole"):
        if hole > 0:
            return f"R{w}H{hole}"
        else:
            return f"R{w}"

    # 3) Square/rectangle with hole
    elif "square/rectangle with hole" in lower_shape:
        return f"X{w}Y{h}H{hole}{angle_str}"

    # 4) Square/rectangle (no hole)
    elif "square/rectangle" in lower_shape:
        return f"X{w}Y{h}{angle_str}"

    # 5) Ellipse
    elif "ellipse" in lower_shape:
        # If you want to support elliptical holes, add "H{hole}" here:
        return f"R{w}Y{h}{angle_str}"

    # 6) Otherwise => fallback to round
    else:
        return f"R{w}"







class BoardNodFile:
    def __init__(self, nod_path: str, object_library: Optional[ObjectLibrary] = None):
        self.nod_path = nod_path
        self.object_library = object_library if object_library else ObjectLibrary()
        self.log = LogHandler(output="both")
        self.changed = False
        # Remove auto-save counters and thresholds completely:
        # self.change_counter = 0
        # self.auto_save_threshold = auto_save_threshold
        self.next_channel = 1  # Starting channel number set to 1
        self.log.log("debug", f"NOD file writer initialized with path: {self.nod_path}")

    def add_object(self, board_obj: BoardObject):
        """
        Add a single BoardObject in an undoable way.
        """
        # If channel is unassigned, let ObjectLibrary do it
        if board_obj.channel is None:
            board_obj.channel = self.object_library.get_next_channel()
        else:
            # Also keep track in self.next_channel
            self.next_channel = max(self.next_channel, board_obj.channel + 1)

        # Now add to the library
        added = self.object_library.add_object(board_obj)
        if added:
            self.changed = True
            # Removed auto-save trigger from here.
            self.log.log(
                "debug",
                f"add_object: Added {board_obj.component_name}, pin={board_obj.pin}, "
                f"channel={board_obj.channel}, total_objs={len(self.object_library.get_all_objects())}"
            )
        else:
            self.log.log("warning", f"add_object: Failed to add {board_obj.component_name}, channel already exists.")

    def add_objects_batch(
        self,
        objects_list: List[BoardObject],
        skip_auto_save: bool = False,
        skip_undo: bool = False
    ):
        """
        Adds multiple BoardObjects to the library in one shot.
        If skip_undo=True, we do NOT push a new state for this batch addition.
        """
        for obj in objects_list:
            if obj.channel is None:
                obj.channel = self.object_library.get_next_channel()
            else:
                self.next_channel = max(self.next_channel, obj.channel + 1)

        # Pass skip_undo to ObjectLibrary.bulk_add
        self.object_library.bulk_add(objects_list, skip_undo=skip_undo)
        self.changed = True
        # Removed auto-save check after batch addition.
        self.log.log("debug", f"add_objects_batch: Added {len(objects_list)} objects.")

    def remove_object(self, board_obj: BoardObject):
        if board_obj.channel is None:
            self.log.log("warning", "remove_object: Cannot remove object without a channel.")
            return

        # Remove the object using ObjectLibrary
        removed = self.object_library.remove_object(board_obj.channel)
        if removed:
            self.changed = True
            self.log.log("debug", f"remove_object: Removed {board_obj.component_name}, channel={board_obj.channel}")
        else:
            self.log.log("warning", f"remove_object: Failed to remove {board_obj.component_name}, channel not found.")

    def remove_objects_batch(self, objects_to_remove: List[BoardObject]):
        """Remove multiple BoardObjects WITHOUT pushing a new state (since done externally)."""
        channels_to_remove = [obj.channel for obj in objects_to_remove if obj.channel is not None]
        if not channels_to_remove:
            self.log.log("warning", "remove_objects_batch: No valid channels to remove.")
            return

        self.object_library.bulk_delete(channels_to_remove)
        self.changed = True
        self.log.log("debug", f"remove_objects_batch: Removed {len(channels_to_remove)} objects.")
        # Removed automatic save after deletion.
        self.log.log("debug", "remove_objects_batch: Removed objects; manual save is required if needed.")

        # Remove objects in bulk using ObjectLibrary
        self.object_library.bulk_delete(channels_to_remove)
        self.changed = True
        self.change_counter += len(channels_to_remove)
        self.log.log("debug", f"remove_objects_batch: Removed {len(channels_to_remove)} objects.")

        # Save changes immediately after bulk removal
        self.save()
        self.log.log("debug", "remove_objects_batch: Removed objects and saved NOD file.")

    def load(self, skip_undo: bool = False):
        """
        Loads BoardObjects from the .nod file into ObjectLibrary.
        If skip_undo=True, we do NOT push an undo state for this load operation.
        """
        if not self.nod_path or not os.path.exists(self.nod_path):
            self.log.log("warning", f"No NOD file found at {self.nod_path}. Nothing loaded.")
            return

        parsed_data = parse_component_nod_file(self.nod_path)
        if not parsed_data:
            return

        loaded_objects = []
        for pad in parsed_data["pads"]:
            obj = BoardObject(
                component_name=pad["component_name"],
                pin=pad["pin"],
                channel=pad["channel"],
                x_coord_mm=pad["x_coord_mm"],
                y_coord_mm=pad["y_coord_mm"],
                shape_type=pad["shape_type"],
                width_mm=pad["width_mm"],
                height_mm=pad["height_mm"],
                hole_mm=pad["hole_mm"],
                angle_deg=pad["angle_deg"],
                testability=pad["testability"],
                technology=pad["technology"],
                test_position=pad["test_position"]
            )
            # Keep the original coords for saving
            obj.x_coord_mm_original = pad["x_coord_mm"]
            obj.y_coord_mm_original = pad["y_coord_mm"]
            loaded_objects.append(obj)

        # Add all loaded objects in one batch, skipping undo if skip_undo=True
        self.add_objects_batch(loaded_objects, skip_undo=skip_undo)

        # Ensure ObjectLibrary's next_channel is at least one higher than any loaded channel
        self.object_library.refresh_channel_counter()

        if loaded_objects:
            highest_loaded = max(obj.channel for obj in loaded_objects)
            self.next_channel = max(self.next_channel, highest_loaded + 1)
        else:
            self.next_channel = 1

        self.log.log(
            "info",
            f"Loaded {len(loaded_objects)} objects from NOD file. Next channel set to {self.next_channel}."
        )

    def _build_payload(self) -> str:
        """
        Return the complete .nod file as a single string.
        Converts each BoardObject to a dict, then through obj_to_nod_line().
        """
        buf = StringIO()
        buf.write("* SIGNAL COMPONENT PIN X Y PAD POS TECN TEST CHANNEL USER\n")

        for obj in self.object_library.get_all_objects():
            # BoardObject → dict (assumes the class has .to_dict())
            d = obj.to_dict()

            # Ensure original coords & hole are present; fall back if missing
            d["x_coord_mm"] = getattr(obj, "x_coord_mm_original", d.get("x_coord_mm", 0.0))
            d["y_coord_mm"] = getattr(obj, "y_coord_mm_original", d.get("y_coord_mm", 0.0))
            d["hole_mm"]    = getattr(obj, "hole_mm", 0.0)

            buf.write(obj_to_nod_line(d) + "\n")

        return buf.getvalue()


    def save(self, backup: bool = False, logger=None, fixed_ts: str | None = None):
        """
        Atomically write the NOD file.
        Set *backup=True* to create a timestamped .bak copy first.
        Returns True on success, False otherwise.
        """
        log = logger or self.log
        try:
            payload = self._build_payload()
            if backup:
                rotate_backups(self.nod_path, fixed_ts=fixed_ts)
            if not safe_write(self.nod_path, payload):
                raise RuntimeError("safe_write failed")
            self.changed = False
            log.log("info",
                    f"NOD file saved safely to '{self.nod_path}' "
                    f"{'(with backup)' if backup else '(soft)'}")
            return True
        except Exception as e:
            log.log("error", f"Failed to save NOD file: {e}")
            return False


    def update_objects_batch(self, updates: List[BoardObject], changes: dict):
        """
        Update multiple BoardObjects in one undoable step.
        :param updates: List of BoardObjects to be updated.
        :param changes: Dictionary specifying the changes to apply (e.g., {"test_position": "Top"}).
        """
        self.object_library.undo_redo_manager.push_state()

        for obj in updates:
            for key, value in changes.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
                    self.log.log("debug", f"Updated {key} for {obj.component_name}, Pin: {obj.pin} to {value}")
                else:
                    self.log.log("warning", f"{key} is not a valid attribute for {obj}")

        self.changed = True
        # Removed auto-save call; manual save is now required.
        self.log.log("debug", f"Batch updated {len(updates)} objects with changes: {changes}.")

    def delete_objects_batch(self, objects_to_remove: List[BoardObject]):
        """
        Delete multiple BoardObjects in one undoable step.
        """
        self.remove_objects_batch(objects_to_remove)

    def debug_print_objects(self, title="BoardNodFile.objects"):
        self.log.log("debug", f"{title}: We have {len(self.object_library.get_all_objects())} objects in memory.")
        for idx, obj in enumerate(self.object_library.get_all_objects()):
            self.log.log("debug",
                         f"  [{idx}] '{obj.component_name}' pin={obj.pin}, channel={obj.channel}, "
                         f"x={obj.x_coord_mm:.3f}, y={obj.y_coord_mm:.3f}")

