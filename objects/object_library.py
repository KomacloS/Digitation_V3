# objects/object_library.py

import copy
from typing import List, Dict, Optional
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
from objects.board_object import BoardObject
from logs.log_handler import LogHandler
from objects.undo_redo_manager import UndoRedoManager
from utils.flag_manager import FlagManager

class ObjectLibrary(QObject):
    object_added = pyqtSignal(BoardObject)
    object_removed = pyqtSignal(BoardObject)
    object_updated = pyqtSignal(BoardObject)
    bulk_operation_completed = pyqtSignal(str)

    _instance = None  # Singleton instance

    def __new__(cls, *args, **kwargs):
        """
        Implements the Singleton pattern.
        Ensures only one instance of ObjectLibrary is created.
        """
        if not cls._instance:
            cls._instance = super(ObjectLibrary, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__()

        # Check if already initialized
        if hasattr(self, "_initialized") and self._initialized:
            return

        # Initialize the object
        self.objects: Dict[int, BoardObject] = {}
        self.log = LogHandler()
        self.log.log("debug", f"ObjectLibrary initialized. Singleton id={id(self)}")

        # Initialize mutex for thread safety
        self._mutex = QMutex()

        # Initialize UndoRedoManager
        self.undo_redo_manager = UndoRedoManager(self)
        self.log.log("debug", "UndoRedoManager initialized within ObjectLibrary.")

        # A simple counter to generate unique channel IDs
        self._next_channel_id = 1

        # --- Auto-save state removed ---
        # self.change_counter = 0
        # self.auto_save_threshold = 20  # No longer used

        self._initialized = True

    def get_next_channel(self) -> int:
        """
        Retrieves a new unique channel ID and increments the internal counter.
        Logs the current counter for debugging collisions.
        """
        self.log.log(
            "debug",
            f"get_next_channel() called. Current _next_channel_id = {self._next_channel_id}"
        )
        ch = self._next_channel_id
        self._next_channel_id += 1
        return ch

    def refresh_channel_counter(self):
        """
        Ensures _next_channel_id is at least one higher than any channel currently stored in self.objects.
        Call this after loading objects from a .nod file.
        """
        with QMutexLocker(self._mutex):
            if self.objects:
                highest_channel = max(self.objects.keys())
                if highest_channel >= self._next_channel_id:
                    self._next_channel_id = highest_channel + 1
                self.log.log(
                    "debug",
                    f"refresh_channel_counter: highest_channel={highest_channel}, "
                    f"next_channel_id set to {self._next_channel_id}"
                )
            else:
                self.log.log("debug", "refresh_channel_counter called, but no objects exist yet.")

    def add_object(self, board_object: BoardObject) -> bool:
        with QMutexLocker(self._mutex):
            self.undo_redo_manager.push_state()

            # If channel is None OR already in use, assign a new unique channel
            if board_object.channel is None or board_object.channel in self.objects:
                assigned_channel = self.get_next_channel()
                self.log.log(
                    "debug",
                    f"add_object: Reassigning channel from {board_object.channel} to {assigned_channel}."
                )
                board_object.channel = assigned_channel

            # Store the object
            self.objects[board_object.channel] = board_object

            self.log.log(
                "info",
                f"Added object: {board_object.component_name}, "
                f"Channel: {board_object.channel}, "
                f"Test Position: {board_object.test_position}"
            )
            self.log.log(
                "debug",
                f"Emitting object_added signal for Channel {board_object.channel}"
            )
            self.object_added.emit(board_object)
            return True

    def remove_object(self, channel: int) -> bool:
        with QMutexLocker(self._mutex):
            self.undo_redo_manager.push_state()
            if channel not in self.objects:
                self.log.log("warning", f"Channel {channel} does not exist.")
                return False
            removed_object = self.objects.pop(channel)
            self.log.log(
                "info",
                f"Removed object: {removed_object.component_name}, "
                f"Channel: {removed_object.channel}, "
                f"Test Position: {removed_object.test_position}"
            )
            self.log.log(
                "debug",
                f"Emitting object_removed signal for Channel {removed_object.channel}"
            )
            self.object_removed.emit(removed_object)
            return True

    def update_object(self, board_object: BoardObject) -> bool:
        with QMutexLocker(self._mutex):
            self.undo_redo_manager.push_state()
            if board_object.channel not in self.objects:
                self.log.log(
                    "warning",
                    f"Attempted to update non-existent object with channel {board_object.channel}."
                )
                return False
            self.objects[board_object.channel] = board_object
            self.log.log(
                "info",
                f"Updated BoardObject: {board_object.component_name}, "
                f"Channel: {board_object.channel}, "
                f"Test Position: {board_object.test_position}"
            )
            self.log.log(
                "debug",
                f"Emitting object_updated signal for Channel {board_object.channel}"
            )
            if self.display_library:
                self.display_library.update_rendered_objects_for_updates([board_object])
            return True

    def bulk_add(
            self,
            board_objects: List[BoardObject],
            preserve_channels: bool = False,
            skip_undo: bool = False,
            skip_auto_save: bool = False,
            skip_render: bool = False
    ) -> None:
        with QMutexLocker(self._mutex):

            if not board_objects:
                self.log.log("warning", "bulk_add called with an empty list.")
                return

            if not skip_undo:
                self.undo_redo_manager.push_state()

            if skip_render:
                FlagManager().set_flag("bulk_in_progress", True)

            added_objects: list[BoardObject] = []
            for obj in board_objects:
                # assign a free channel if needed
                if (obj.channel is None) or (obj.channel in self.objects):
                    obj.channel = self.get_next_channel()

                self.objects[obj.channel] = obj
                added_objects.append(obj)

                # ⬅️  NO per‑object signal here
                # self.object_added.emit(obj)

            # one shot partial render
            if not skip_render and hasattr(self, "display_library") and self.display_library:
                self.display_library.add_rendered_objects(added_objects)

            self.log.log("info", f"bulk_add: Added {len(added_objects)} objects.")




    # Remove or leave a no-op save() method since auto-save is not desired.
    def save(self):
        self.log.log("debug", "[ObjectLibrary.save] Auto-save has been removed.")

    def get_all_objects(self) -> List[BoardObject]:
        """Retrieves all BoardObject instances."""
        return list(self.objects.values())

    def get_objects_by_test_position(self, test_position: str) -> List[BoardObject]:
        """Retrieves all BoardObject instances for a specific test position."""
        with QMutexLocker(self._mutex):
            filtered_objects = [
                obj for obj in self.objects.values()
                if obj.test_position.lower() == test_position.lower()
            ]
        self.log.log(
            "debug",
            f"ObjectLibrary: Retrieved {len(filtered_objects)} objects for test position '{test_position.lower()}'."
        )
        return filtered_objects

    def undo(self) -> bool:
        """Undoes the last operation."""
        with QMutexLocker(self._mutex):
            return self.undo_redo_manager.undo()

    def redo(self) -> bool:
        """Redoes the last undone operation."""
        with QMutexLocker(self._mutex):
            return self.undo_redo_manager.redo()

    def clear_all(self) -> None:
        with QMutexLocker(self._mutex):
            self.undo_redo_manager.push_state()
            self.objects.clear()
            self.log.log("info", "Cleared all BoardObjects from ObjectLibrary.")

    def clear(self):
        """Clears all BoardObjects from the library (alias for clear_all())."""
        self.clear_all()

    def find_pad(self, component: str, pin: str, signal: str, channel: int) -> Optional[BoardObject]:
        """
        Finds and returns the BoardObject matching the specified criteria.
        """
        all_objs = self.get_all_objects()
        for obj in all_objs:
            if (obj.component_name.lower() == component.lower() and
                str(obj.pin) == pin and
                getattr(obj, 'signal', "").lower() == signal.lower() and
                obj.channel == channel):
                self.log.log("info", f"Pad found: {obj}")
                return obj

        self.log.log(
            "warning",
            f"No pad found for Component='{component}', Pin='{pin}', "
            f"Signal='{signal}', Channel={channel}"
        )
        return None

    def modify_objects(self, added=None, updated=None, deleted=None):
        """
        A unified bulk operation that adds, updates, or deletes objects
        without emitting single-object signals. Instead, we do partial
        updates in the DisplayLibrary all at once.
        """
        with QMutexLocker(self._mutex):
            self.undo_redo_manager.push_state()

            added = added or []
            updated = updated or []
            deleted = deleted or []

            # 1) Add
            for obj in added:
                if obj.channel is None or obj.channel in self.objects:
                    obj.channel = self.get_next_channel()
                self.objects[obj.channel] = obj

            # 2) Update
            for obj in updated:
                if obj.channel in self.objects:
                    self.objects[obj.channel] = obj

            # 3) Delete
            deleted_channels = []
            for obj in deleted:
                if obj.channel in self.objects:
                    del self.objects[obj.channel]
                    deleted_channels.append(obj.channel)

            # 4) Partial rendering calls
            if self.display_library:
                if added:
                    self.display_library.add_rendered_objects(added)
                if updated:
                    self.display_library.update_rendered_objects_for_updates(updated)
                if deleted_channels:
                    self.display_library.remove_rendered_objects(deleted_channels)

            # Optionally remove or comment out this signal if not needed
            # self.bulk_operation_completed.emit("Bulk Modify")

            self.log.log(
                "info",
                f"modify_objects => Added={len(added)}, Updated={len(updated)}, "
                f"Deleted={len(deleted)}"
            )


    def bulk_delete(self, channels_to_remove: List[int]) -> None:
        """
        Deletes multiple BoardObjects in one bulk operation.
        Then removes them from the display in a partial update.
        """
        with QMutexLocker(self._mutex):
            self.undo_redo_manager.push_state()

            removed_channels = []
            for ch in channels_to_remove:
                if ch in self.objects:
                    self.objects.pop(ch)
                    removed_channels.append(ch)

            # Partially remove from display
            if self.display_library:
                self.display_library.remove_rendered_objects(removed_channels)

            self.log.log("info", f"bulk_delete: Deleted {len(removed_channels)} objects.")
            # self.bulk_operation_completed.emit("Bulk Delete")  # <-- remove/comment out

    def bulk_update_objects(self, updates: List[BoardObject], changes: dict) -> None:
        """
        Updates multiple BoardObjects in one undoable step, then does a partial re-render.
        """
        with QMutexLocker(self._mutex):
            self.undo_redo_manager.push_state()

            for obj in updates:
                for key, value in changes.items():
                    if hasattr(obj, key):
                        setattr(obj, key, value)
                self.objects[obj.channel] = obj

            # Partial update display for only these objects
            if self.display_library:
                self.display_library.update_rendered_objects_for_updates(updates)

            self.log.log("info", f"bulk_update_objects: Updated {len(updates)} objects.")