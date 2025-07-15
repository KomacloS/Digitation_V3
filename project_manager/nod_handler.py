# project_manager/nod_handler.py

from typing import Optional, TYPE_CHECKING
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from logs.log_handler import LogHandler
from objects.nod_file import BoardNodFile
from io import StringIO
from objects.nod_file import obj_to_nod_line 
from utils.file_ops import safe_write, rotate_backups

if TYPE_CHECKING:
    from project_manager.project_manager import ProjectManager  # Only for type hints


class NODHandler:
    def __init__(self, project_manager: 'ProjectManager'):
        self.project_manager = project_manager
        self.main_window = project_manager.main_window
        self.object_library = project_manager.object_library
        self.log = project_manager.log

    def load_nod_file(self, file_path: Optional[str] = None):
        """
        Loads a NOD file from the specified path or prompts the user to select one.
        After loading the objects, the undo/redo history is cleared and the loaded state is pushed
        as the baseline so that future operations (e.g. moving pads) are undoable.
        """
        if file_path is None:
            file_dialog_opts = QFileDialog.Options()
            file_path, _ = QFileDialog.getOpenFileName(
                self.main_window,
                "Load NOD File",
                "",
                "NOD Files (*.nod);;All Files (*)",
                options=file_dialog_opts
            )

        if not file_path:
            self.log.log("warning", "Load NOD File action canceled by the user.")
            return  # User canceled the dialog

        self.log.log("info", f"Selected NOD file: {file_path}")

        try:
            # Create the NOD file handler and load directly into the current object_library.
            nod_file = BoardNodFile(nod_path=file_path, object_library=self.object_library)
            nod_file.load(skip_undo=True)

            # After loading, check for components that have duplicate pin numbers.
            dups = self._find_components_with_duplicate_pins()
            if dups:
                names = ", ".join(sorted(dups))
                QMessageBox.critical(
                    self.main_window,
                    "Invalid Components",
                    (
                        "Duplicate pins detected for component(s): "
                        f"{names}. All pads for these components will be removed."
                    ),
                )
                channels = [
                    obj.channel
                    for obj in self.object_library.get_all_objects()
                    if obj.component_name.lower() in dups
                ]
                if channels:
                    self.object_library.bulk_delete(channels)
                self.log.warning(
                    f"Removed components with duplicate pins: {names}",
                    module="NODHandler",
                    func="load_nod_file",
                )

            # Reset the undo/redo history so that the loaded state is now the baseline.
            self.object_library.undo_redo_manager.clear()
            self.object_library.undo_redo_manager.push_state()

            QMessageBox.information(
                self.main_window,
                "Load NOD File",
                f"Successfully loaded NOD file:\n{file_path}"
            )
            self.log.log("info", f"Successfully loaded NOD file: {file_path}")

        except Exception as e:
            self.log.log("error", f"Failed to load NOD file: {e}")
            QMessageBox.critical(
                self.main_window,
                "Load NOD File Error",
                f"An error occurred while loading the NOD file:\n{e}"
            )

    def _find_components_with_duplicate_pins(self) -> set[str]:
        """Return a set of component names that have duplicate pin numbers."""
        seen = {}
        duplicates = set()
        for obj in self.object_library.get_all_objects():
            key = (obj.component_name.lower(), str(obj.pin))
            if key in seen:
                duplicates.add(obj.component_name.lower())
            else:
                seen[key] = True
        return duplicates

    def save_project_nod(self, file_path: Optional[str] = None) -> bool:
        """
        Invoked by 'Save Project' button.
        Always performs a backup rotation before saving.
        """
        file_path = file_path or self.project_manager.project_nod_path
        nod_file = BoardNodFile(nod_path=file_path,
                                object_library=self.object_library)
        ok = nod_file.save(backup=True, logger=self.log)
        if not ok:
            QMessageBox.critical(self.main_window, "Save Error",
                                 f"Failed to save NOD file:\n{file_path}")
        return ok


    def save_nod_file(self, file_path: Optional[str] = None) -> bool:
        """
        Atomically save all BoardObjects to *file_path* (.nod) and
        keep a timestamped backup copy.
        If *file_path* is not given, open a QFileDialog to choose one.
        Returns True on success, False otherwise.
        """
        if file_path is None:
            file_dialog_opts = QFileDialog.Options()
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                "Save NOD File",
                "",
                "NOD Files (*.nod);;All Files (*)",
                options=file_dialog_opts
            )
            if not file_path:
                self.log.log("warning", "Save NOD canceled by user.")
                return False

        try:
            # 1) build the file in memory
            buf = StringIO()
            buf.write('* SIGNAL COMPONENT PIN X Y PAD POS TECN TEST CHANNEL USER\n')
            for obj in self.object_library.get_all_objects():
                buf.write(obj_to_nod_line(obj.to_dict()) + '\n')
            payload = buf.getvalue()

            # 2) backup current file (if any)
            rotate_backups(file_path)

            # 3) atomic write
            if safe_write(file_path, payload):
                self.log.log("info", f"NOD saved safely to '{file_path}'.")
                return True
            else:
                raise RuntimeError("safe_write failed")

        except Exception as e:
            self.log.log("error", f"Failed to save NOD file: {e}")
            QMessageBox.critical(
                self.main_window,
                "Save NOD File Error",
                f"An error occurred while saving the NOD file:\n{e}"
            )
            return False