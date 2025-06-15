import copy
import time
from typing import List, Dict
from objects.board_object import BoardObject
from logs.log_handler import LogHandler
from constants.constants import Constants

class UndoRedoManager:
    def __init__(self, object_library):
        self.constants = Constants()
        self.max_undo_steps = self.constants.get("max_undo_steps", 10)
        self.object_library = object_library
        self.undo_stack = []
        self.redo_stack = []
        self.log = LogHandler(output="both")
        self.log.log("debug", f"UndoRedoManager initialized with max_undo_steps={self.max_undo_steps}.")

    def push_state(self, extra_state: dict = None):
        start_time = time.perf_counter()
        # Create the composite state with board objects.
        state = {"objects": copy.deepcopy(self.object_library.objects)}
        # If extra state (e.g. BOM) is provided, include it.
        if extra_state is not None:
            state.update(extra_state)
        # Only push if this state is different from the last one.
        if self.undo_stack and state == self.undo_stack[-1]:
            self.log.log("debug", "UndoRedoManager: skipped push. State identical to last undo stack entry.")
            return
        self.undo_stack.append(state)
        self.redo_stack.clear()  # Clear redo stack on new state

        # Enforce max_undo_steps
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
            self.log.log("debug", "UndoRedoManager: removed oldest undo state to maintain max size.")
        
        elapsed = time.perf_counter() - start_time
        self.log.log("info", f"UndoRedoManager: push_state took {elapsed:.4f} seconds. Undo stack size={len(self.undo_stack)}.")

    def undo(self) -> bool:
        if not self.undo_stack:
            self.log.log("debug", "UndoRedoManager: no states in undo stack. Cannot undo.")
            return False

        # Save the current state to the redo stack.
        current_snapshot = {"objects": copy.deepcopy(self.object_library.objects)}
        if hasattr(self.object_library, "bom_handler"):
            current_snapshot["bom"] = copy.deepcopy(self.object_library.bom_handler.bom)
        self.redo_stack.append(current_snapshot)

        # Restore the last undo state.
        old_state = self.undo_stack.pop()
        if "objects" in old_state:
            self.object_library.objects = old_state["objects"]
        if "bom" in old_state and hasattr(self.object_library, "bom_handler"):
            self.object_library.bom_handler.bom = old_state["bom"]

        self.log.log("info", "UndoRedoManager: undo performed. Restored previous state.")
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            self.log.log("debug", "UndoRedoManager: no states in redo stack. Cannot redo.")
            return False

        # Save the current state to the undo stack.
        current_snapshot = {"objects": copy.deepcopy(self.object_library.objects)}
        if hasattr(self.object_library, "bom_handler"):
            current_snapshot["bom"] = copy.deepcopy(self.object_library.bom_handler.bom)
        self.undo_stack.append(current_snapshot)

        # Restore the most recent redo state.
        future_state = self.redo_stack.pop()
        if "objects" in future_state:
            self.object_library.objects = future_state["objects"]
        if "bom" in future_state and hasattr(self.object_library, "bom_handler"):
            self.object_library.bom_handler.bom = future_state["bom"]

        self.log.log("info", "UndoRedoManager: redo performed. Re-applied state from redo stack.")
        return True

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.log.log("debug", "UndoRedoManager: cleared undo and redo stacks.")
