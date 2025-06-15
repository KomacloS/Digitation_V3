# For example, in project_manager/alf_handler.py

import os
from collections import defaultdict
from utils.file_ops import safe_write, rotate_backups
from logs.log_handler import LogHandler

print(">>> LOADED patched alf_handler FROM", __file__)

def save_alf_file(project_folder, object_library, logger=None,
                  fixed_ts: str | None = None):
    """
    Writes 'project.alf' atomically with rotating backups.
    Each line: component.prefix<TAB>component.pin
    If no objects have a prefix, writes an empty file (but still atomically).
    """
    if logger is None:
        logger = LogHandler()

    alf_file_path = os.path.join(project_folder, "project.alf")

    # 1) gather entries
    grouped = defaultdict(list)
    for obj in object_library.get_all_objects():
        prefix = (getattr(obj, "prefix", "") or "").strip()
        if prefix:
            try:
                pin_num = int(obj.pin)
            except Exception:
                pin_num = 0
            grouped[obj.component_name].append((pin_num, prefix))

    # 2) build payload
    lines = []
    for comp, entries in grouped.items():
        entries.sort()
        for pin, prefix in entries:
            lines.append(f"{comp}.{prefix}\t{comp}.{pin}")
    payload = "\n".join(lines) + ("\n" if lines else "")

    try:
        rotate_backups(alf_file_path, fixed_ts=fixed_ts)
        if safe_write(alf_file_path, payload, encoding="utf-8"):
            if lines:
                logger.log("info",
                           f"ALF saved safely at {alf_file_path} "
                           f"({len(lines)} entries).")
            else:
                logger.log("info",
                           f"ALF cleared (no prefixes) at {alf_file_path}.")
    except Exception as e:
        logger.log("error",
                   f"ALF handler: Error saving ALF file at {alf_file_path}: {e}")




def load_project_alf(project_folder, object_library, logger=None):
    """
    If an ALF file exists in the project folder, load its contents and update
    any board objects in the object_library that match the ALF mapping.
    
    The ALF file is expected to have lines of the form:
        ComponentName.Prefix<TAB>ComponentName.Pin

    For each line, the function updates the board object's 'prefix' attribute.
    """
    if logger is None:
        logger = LogHandler()
    
    alf_path = os.path.join(project_folder, "project.alf")
    if not os.path.exists(alf_path):
        logger.log("info", f"No ALF file found at {alf_path}. Skipping ALF loading.")
        return

    mapping = {}  # mapping: (component_name, pin) -> prefix
    try:
        with open(alf_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Assume whitespace (or tab) separation:
                parts = line.split()
                if len(parts) < 2:
                    continue
                left, right = parts[0], parts[1]
                # Both left and right should contain a dot.
                if "." not in left or "." not in right:
                    continue
                comp_left, prefix = left.split(".", 1)
                comp_right, pin_str = right.split(".", 1)
                # Optionally, verify that the component names match.
                if comp_left != comp_right:
                    logger.log("warning", f"ALF entry mismatch: {left} vs {right}")
                    continue
                try:
                    pin = int(pin_str)
                except Exception:
                    continue
                mapping[(comp_left, pin)] = prefix
        logger.log("info", f"ALF mapping obtained (total {len(mapping)} entries) from '{alf_path}'.")
    except Exception as e:
        logger.log("error", f"Error reading ALF file '{alf_path}': {e}")
        return

    # Now update BoardObjects in the library.
    all_objs = object_library.get_all_objects()
    updated_count = 0
    for obj in all_objs:
        try:
            pin_num = int(obj.pin)
        except Exception:
            pin_num = 0
        key = (obj.component_name, pin_num)
        if key in mapping:
            obj.prefix = mapping[key]
            updated_count += 1

    logger.log("info", f"Loaded ALF file '{alf_path}', updated {updated_count} board objects with prefix.")