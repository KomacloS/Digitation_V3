# project_manager/project_manager.py
import time
import os
from PyQt5.QtCore import QObject, pyqtSignal, QSettings
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QInputDialog
from project_manager.project_settings_dialog import ProjectSettingsDialog
from objects.nod_file import BoardNodFile
from project_manager.nod_handler import NODHandler
from project_manager.image_handler import ImageHandler
from constants.constants import Constants  # Import your constants
from project_manager.alf_handler import save_alf_file
from project_manager.project_settings import load_settings, save_settings
from component_placer.bom_handler.bom_handler import BOMHandler
from project_manager.backup_browser_dialog import BackupBrowserDialog


class ProjectManager(QObject):
    project_loaded_signal = pyqtSignal()

    def __init__(self, main_window, bom_handler: BOMHandler):
        super().__init__()
        self.main_window = main_window
        self.log = main_window.log
        self.object_library = main_window.object_library
        self.nod_handler = NODHandler(self)
        self.image_handler = ImageHandler(self)
        self.auto_save_counter = 0
        constants = Constants()
        self.auto_save_threshold = constants.get("auto_save_threshold", 20)
        self.project_loaded = False  # Set to True after project load
        self.object_library.bulk_operation_completed.connect(
            self.handle_bulk_operation_completed
        )

        # Use the shared BOMHandler instance provided from MainWindow.
        self.bom_handler = bom_handler
        self.log.info(
            f"ProjectManager: Using shared BOMHandler instance at {hex(id(self.bom_handler))}",
            module="ProjectManager",
            func="__init__",
        )

    def save_project_settings(self, folder: str | None = None):
        """Save mm/px and origin settings to the project folder if possible."""
        folder = folder or self.main_window.current_project_path
        if not folder or folder.strip().lower().endswith("[none]"):
            return
        consts = Constants()
        save_settings(folder, consts, logger=self.log)

    def handle_bulk_operation_completed(self, operation: str):
        if not self.project_loaded:
            return
        self.auto_save_counter += 1
        self.log.log(
            "debug",
            f"Auto-save counter increased to {self.auto_save_counter} after operation: {operation}",
        )
        if self.auto_save_counter >= self.auto_save_threshold:
            self.auto_save()

    def auto_save(self):
        folder = self.main_window.current_project_path
        if folder and folder.strip() and not folder.strip().lower().endswith("[none]"):
            nod_path = os.path.join(folder, "project.nod")
            self.log.log(
                "info",
                f"Auto-saving project to {nod_path} after {self.auto_save_counter} bulk actions.",
            )
            nod_file = BoardNodFile(nod_path, object_library=self.object_library)
            nod_file.save_with_logging(logger=self.log)
            self.auto_save_counter = 0
        else:
            self.log.log("warning", "Auto-save skipped: No valid project folder.")

    def open_project_dialog(self):
        try:
            folder = QFileDialog.getExistingDirectory(
                self.main_window,
                "Select Existing Project Folder",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
            )
            if not folder:
                self.log.log("info", "User canceled project folder selection.")
                return

            self.log.log("info", f"User selected project folder: {folder}")
            self.main_window.current_project_path = folder
            self.log.log("debug", f"current_project_path set to: {folder}")

            # Actually load the project from 'folder'
            self.load_existing_project(folder)

        except Exception as e:
            self.log.log("error", f"Failed in open_project_dialog: {e}")
            QMessageBox.critical(
                self.main_window,
                "Open Project Failed",
                f"An error occurred while opening the project:\n{e}",
            )

    def load_existing_project(self, project_dir: str):
        try:
            self.log.log("info", f"Loading existing project from: {project_dir}")

            top_img = os.path.join(project_dir, "top_image.png")
            bottom_img = os.path.join(project_dir, "bottom_image.png")
            nod_path = os.path.join(project_dir, "project.nod")
            bom_path = os.path.join(project_dir, "project_bom.csv")

            missing = []
            for f in [top_img, bottom_img, nod_path]:
                if not os.path.exists(f):
                    missing.append(os.path.basename(f))

            if missing:
                self.log.log("warning", f"Missing files: {missing}")
                QMessageBox.warning(
                    self.main_window,
                    "Missing Files",
                    f"The following files are missing:\n{', '.join(missing)}",
                )
                return

            # Load any project-specific settings before manipulating the view
            consts = Constants()
            load_settings(project_dir, consts, logger=self.log)

            mm_top = consts.get("mm_per_pixels_top", 0.0333)
            mm_bot = consts.get("mm_per_pixels_bot", 0.0333)
            ox = consts.get("origin_x_mm", 0.0)
            oy = consts.get("origin_y_mm", 0.0)
            self.main_window.board_view.converter.set_mm_per_pixels_top(mm_top)
            self.main_window.board_view.converter.set_mm_per_pixels_bot(mm_bot)
            self.main_window.board_view.converter.set_origin_mm(ox, oy)

            self.log.log("info", "Clearing previous project objects.")
            self.object_library.clear()
            if hasattr(self.main_window, "board_view") and hasattr(
                self.main_window.board_view, "display_library"
            ):
                self.main_window.board_view.display_library.clear_all_rendered_objects()
                self.log.log("info", "Cleared rendered objects from display.")

            QSettings("MyCompany", "PCB Digitization Tool").setValue(
                "last_numbers", "{}"
            )
            self.log.log("debug", "Auto numbering reset (last_numbers cleared).")

            # Load images
            self.image_handler.load_image(file_path=top_img, side="top")
            self.image_handler.load_image(file_path=bottom_img, side="bottom")

            # Load the NOD file (populates ObjectLibrary)
            self.nod_handler.load_nod_file(file_path=nod_path)

            # Load BOM from CSV
            if self.bom_handler.load_bom(bom_path):
                self.log.log("info", f"BOM loaded from: {bom_path}")
            else:
                self.log.log(
                    "info",
                    "No BOM file found or BOM empty; starting with an empty BOM.",
                )

            # Now delegate mismatch checking and fixing to BOMHandler
            board_comps = [
                obj.component_name for obj in self.object_library.get_all_objects()
            ]
            self.bom_handler.check_and_fix_mismatch(
                board_comps, self.main_window, bom_path
            )

            from project_manager.alf_handler import load_project_alf

            load_project_alf(project_dir, self.object_library, logger=self.log)

            folder_name = os.path.basename(project_dir)
            self.main_window.update_project_name(folder_name)

            self.project_loaded = True
            self.auto_save_counter = 0

            # Update working side label based on the BoardView's flag.
            self.main_window.update_working_side_label()

            QMessageBox.information(
                self.main_window,
                "Project Loaded",
                f"Project loaded successfully from {project_dir}.",
            )
            self.log.log("info", f"Project loaded successfully from {project_dir}.")
            self.project_loaded_signal.emit()

        except Exception as e:
            self.log.log("error", f"Failed to load project from {project_dir}: {e}")
            QMessageBox.critical(
                self.main_window,
                "Load Project Error",
                f"An error occurred while loading the project:\n{e}",
            )

    def create_project_dialog(self):
        self.log.log(
            "info", "[create_project_dialog] User requested 'Create Project' dialog."
        )
        self.main_window.current_project_path = None
        self.main_window.update_project_name("[None]")
        self.log.log(
            "debug", "[create_project_dialog] current_project_path set to None."
        )
        self.object_library.clear()
        self.log.log(
            "debug",
            "[create_project_dialog] ObjectLibrary cleared => board is now blank.",
        )
        self.log.log("debug", "[create_project_dialog] Loading top image.")
        self.image_handler.load_image(side="top")
        self.log.log("debug", "[create_project_dialog] Top image loaded.")
        self.log.log("debug", "[create_project_dialog] Loading bottom image.")
        self.image_handler.load_image(side="bottom")
        self.log.log("debug", "[create_project_dialog] Bottom image loaded.")

        # ── Ask for project settings immediately ─────────────────────
        dlg = ProjectSettingsDialog(self.main_window.constants, parent=self.main_window)
        if dlg.exec_() == dlg.Accepted:
            settings = dlg.get_settings()
            consts = self.main_window.constants
            for k, v in settings.items():
                consts.set(k, v)
            consts.save()
            self.main_window.board_view.converter.set_mm_per_pixels_top(
                settings["mm_per_pixels_top"]
            )
            self.main_window.board_view.converter.set_mm_per_pixels_bot(
                settings["mm_per_pixels_bot"]
            )
            self.main_window.board_view.converter.set_origin_mm(
                settings["origin_x_mm"], settings["origin_y_mm"]
            )
            self.save_project_settings()

        QSettings("MyCompany", "PCB Digitization Tool").setValue("last_numbers", "{}")
        self.log.log(
            "debug", "Auto numbering reset for new project (last_numbers cleared)."
        )

        reply = QMessageBox.question(
            self.main_window,
            "Load .nod?",
            "Would you like to load an existing .nod file now?\n(Choose 'No' to start with a blank project.)",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.log.log(
                "debug", "[create_project_dialog] User chose YES => load_nod_advanced."
            )
            self.load_nod_advanced()
        else:
            self.log.log(
                "info",
                "[create_project_dialog] User chose NO => staying blank (empty project).",
            )
            self.project_loaded = True
            self.auto_save_counter = 0
            self.project_loaded_signal.emit()

        # Update working side label based on the BoardView's flag.
        self.main_window.update_working_side_label()

        # Prompt user to select a location to save the new project
        self.save_project_as_dialog()

    def save_project_dialog(self):
        folder = self.main_window.current_project_path
        if not folder or folder.strip().lower().endswith("[none]"):
            self.save_project_as_dialog()
            return

        try:
            overall_start = time.perf_counter()
            self.log.log("info", f"Saving existing project to folder: {folder}")

            # ── ONE shared timestamp for this hard save ───────────
            ts_stamp = time.strftime("%Y%m%d_%H%M%S")

            nod_path = os.path.join(folder, "project.nod")
            bom_path = os.path.join(folder, "project_bom.csv")

            self.log.log("info", "Skipping image check; images already up‑to‑date.")

            # NOD ----------------------------------------------------------------
            t0 = time.perf_counter()
            nod_file = BoardNodFile(nod_path, object_library=self.object_library)
            nod_file.save(backup=True, logger=self.log, fixed_ts=ts_stamp)
            nod_time = time.perf_counter() - t0
            self.log.log("info", f"NOD file saved in {nod_time:.4f} seconds.")

            # BOM ----------------------------------------------------------------
            t0 = time.perf_counter()
            bom_saved = self.bom_handler.save_bom(bom_path, fixed_ts=ts_stamp)
            bom_time = time.perf_counter() - t0
            if bom_saved:
                self.log.log(
                    "info", f"BOM saved to: {bom_path} in {bom_time:.4f} seconds."
                )
            else:
                self.log.log("warning", "Failed to save BOM.")

            # mismatch check unchanged …
            board_comps = [
                obj.component_name for obj in self.object_library.get_all_objects()
            ]
            self.bom_handler.check_and_fix_mismatch(
                board_comps, self.main_window, bom_path
            )

            # ALF ----------------------------------------------------------------
            t0 = time.perf_counter()
            save_alf_file(
                folder, self.object_library, logger=self.log, fixed_ts=ts_stamp
            )
            alf_time = time.perf_counter() - t0
            self.log.log("info", f"ALF file saved in {alf_time:.4f} seconds.")

            total_time = time.perf_counter() - overall_start
            report = (
                "--- Save Project Report ---\n"
                f"NOD file save time: {nod_time:.4f} sec\n"
                f"BOM save time: {bom_time:.4f} sec\n"
                f"ALF file save time: {alf_time:.4f} sec\n"
                f"Total save time: {total_time:.4f} sec\n"
                "----------------------------"
            )
            self.log.log("info", report)

            self.object_library.undo_redo_manager.clear()
            self.auto_save_counter = 0

            # Save project specific settings
            self.save_project_settings(folder)

            QMessageBox.information(
                self.main_window,
                "Project Saved",
                f"Project saved to {folder}\nTotal save time: {total_time:.4f} seconds.",
            )
            self.log.log(
                "info", f"Project saved to {folder} in {total_time:.4f} seconds."
            )

        except Exception as e:
            import traceback
            import sys

            traceback.print_exc(file=sys.stdout)  # ← add this
            self.log.log("error", f"Failed to save project: {e}")
            QMessageBox.critical(
                self.main_window,
                "Save Project Error",
                f"An error occurred while saving:\n{e}",
            )

    def save_project_as_dialog(self):
        self.log.log("info", "User triggered Save As dialog.")

        # ── 1. ask for project name ───────────────────────────────
        while True:
            project_name, ok = QInputDialog.getText(
                self.main_window, "Project Name", "Enter a name for this project:"
            )
            if not ok or not project_name.strip():
                self.log.log("info", "User canceled or provided empty project name.")
                return
            project_name = project_name.strip()
            if project_name.lower() == "[none]":
                QMessageBox.warning(
                    self.main_window,
                    "Invalid Name",
                    "You cannot use '[None]' as a project name. Please choose another name.",
                )
                continue
            break

        # ── 2. choose parent directory ────────────────────────────
        parent_dir = QFileDialog.getExistingDirectory(
            self.main_window,
            "Select Folder for Project",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not parent_dir:
            self.log.log("info", "User canceled selecting the folder to save.")
            return

        # ── 3. create / reuse project folder ──────────────────────
        new_proj_dir = os.path.join(parent_dir, project_name)
        if not os.path.exists(new_proj_dir):
            try:
                os.mkdir(new_proj_dir)
                self.log.log("info", f"Created new project folder: {new_proj_dir}")
            except OSError as e:
                self.log.log(
                    "error", f"Failed to create directory '{new_proj_dir}': {e}"
                )
                QMessageBox.critical(
                    self.main_window,
                    "Save As Error",
                    f"Cannot create '{new_proj_dir}':\n{e}",
                )
                return
        else:
            self.log.log(
                "warning",
                f"Folder '{new_proj_dir}' already exists. Will overwrite contents if needed.",
            )

        # ── 4. define paths ───────────────────────────────────────
        top_image_path = os.path.join(new_proj_dir, "top_image.png")
        bottom_image_path = os.path.join(new_proj_dir, "bottom_image.png")
        nod_path = os.path.join(new_proj_dir, "project.nod")
        bom_path = os.path.join(new_proj_dir, "project_bom.csv")

        self.log.log("info", f"Saving project to new folder: {new_proj_dir}")

        # ── 5. save images (same as before) ───────────────────────
        self.image_handler.save_image(top_image_path, "top")
        self.image_handler.save_image(bottom_image_path, "bottom")

        # ── 6. HARD‑save NOD (atomic + backup) ────────────────────
        nod_file = BoardNodFile(nod_path, object_library=self.object_library)
        if not nod_file.save(backup=True, logger=self.log):  # ← NEW
            return  # error already logged + message box shown inside

        # ── 7. HARD‑save BOM (already atomic + backup inside) ─────
        if self.bom_handler.save_bom(bom_path):
            self.log.log("info", f"BOM saved to: {bom_path}")
        else:
            self.log.log("warning", "Failed to save BOM in the new project folder.")
            # optional: QMessageBox.warning(...)

        # ── 8. HARD‑save ALF (if prefixes exist) ──────────────────
        from project_manager.alf_handler import save_alf_file

        save_alf_file(new_proj_dir, self.object_library, logger=self.log)

        # save project specific settings
        self.save_project_settings(new_proj_dir)

        # ── 9. wrap‑up UI / state  ────────────────────────────────
        QMessageBox.information(
            self.main_window,
            "Project Saved As",
            f"Project '{project_name}' saved successfully to:\n{new_proj_dir}",
        )
        self.log.log("info", f"Project '{project_name}' saved to {new_proj_dir}.")

        self.main_window.current_project_path = new_proj_dir
        self.main_window.update_project_name(project_name)
        self.auto_save_counter = 0
        self.project_loaded = True

    def load_nod_advanced(self):
        existing = self.object_library.get_all_objects()
        if existing:
            msg_box = QMessageBox(self.main_window)
            msg_box.setWindowTitle("Load NOD - Overwrite?")
            msg_box.setText(
                "Objects already exist in the current project.\n"
                "Do you want to overwrite (clear) the existing objects and load the new NOD file?"
            )
            overwrite_button = msg_box.addButton(
                "Overwrite",
                QMessageBox.DestructiveRole,
            )
            msg_box.addButton("Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(overwrite_button)
            msg_box.exec_()

            clicked = msg_box.clickedButton()
            if clicked == overwrite_button:
                self.log.log(
                    "info",
                    "[load_nod_advanced] Overwrite chosen => clearing existing and loading NOD.",
                )
                self.overwrite_load_nod()
            else:
                self.log.log(
                    "info", "[load_nod_advanced] User canceled => doing nothing."
                )
                return
        else:
            self.log.log(
                "info",
                "[load_nod_advanced] No existing objects => direct load of NOD file.",
            )
            self.nod_handler.load_nod_file()

    def overwrite_load_nod(self, file_path: str = None):
        if file_path is None:
            file_dialog_opts = QFileDialog.Options()
            file_path, _ = QFileDialog.getOpenFileName(
                self.main_window,
                "Load NOD File (Overwrite)",
                "",
                "NOD Files (*.nod);;All Files (*)",
                options=file_dialog_opts,
            )
        if not file_path:
            self.log.log(
                "warning", "Overwrite load NOD: No file selected. Operation canceled."
            )
            return

        self.log.log("info", f"Overwrite load NOD: Selected file: {file_path}")
        self.object_library.clear()
        self.log.log(
            "info",
            "Overwrite load NOD: Cleared all existing BoardObjects from ObjectLibrary.",
        )
        if hasattr(self.main_window, "board_view") and hasattr(
            self.main_window.board_view, "display_library"
        ):
            self.main_window.board_view.display_library.clear_all_rendered_objects()
            self.log.log(
                "info", "Overwrite load NOD: Cleared rendered objects from display."
            )

        try:
            nod_file = BoardNodFile(
                nod_path=file_path, object_library=self.object_library
            )
            nod_file.load(skip_undo=True)
            QMessageBox.information(
                self.main_window, "Load NOD", f"Successfully loaded:\n{file_path}"
            )
            self.log.log(
                "info", f"Overwrite load NOD: Successfully loaded NOD file: {file_path}"
            )

            project_folder = os.path.dirname(file_path)
            project_name = os.path.basename(project_folder)
            self.main_window.update_project_name(project_name)
            self.auto_save_counter = 0
            self.project_loaded = True

            # Update working side label after loading NOD file.
            self.main_window.update_working_side_label()

        except Exception as e:
            self.log.log("error", f"Overwrite load NOD: Failed to load NOD file: {e}")
            QMessageBox.critical(
                self.main_window,
                "Load NOD Error",
                f"An error occurred while loading the NOD file:\n{e}",
            )

    # --------------------------------------------------------------------------
    #                           MISMATCH HELPER
    # --------------------------------------------------------------------------
    def _check_and_handle_bom_mismatch(self, bom_path: str):
        """
        Retrieves the list of board component names from the ObjectLibrary,
        calls BOMHandler.check_mismatch(...),
        and if there's a mismatch, calls handle_mismatch(...)
        letting the user fix it (via BOMEditorDialog or whatever approach you prefer).
        """
        board_comps = [
            obj.component_name for obj in self.object_library.get_all_objects()
        ]
        missing, extra = self.bom_handler.check_mismatch(board_comps)
        if missing or extra:
            self.bom_handler.handle_mismatch(missing, extra, self.main_window, bom_path)

    def reimport_bom_fixes(self):
        """
        If the user wants to manually re-import the BOM from CSV or mismatch .xlsx,
        we still rely on BOMHandler for loading. Then optionally rewrite project_bom.csv
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Select Updated BOM or Mismatch Spreadsheet",
            "",
            "Excel Spreadsheet (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            self.log.log("info", "User canceled reimport of BOM fixes.")
            return

        extension = os.path.splitext(file_path)[1].lower()
        success = False
        if extension in [".xlsx", ".xls"]:
            success = self.bom_handler.import_from_mismatch_xlsx(file_path)
        else:
            success = self.bom_handler.load_bom(file_path)

        if success:
            self.log.log("info", f"Successfully re-imported BOM from {file_path}.")
            folder = self.main_window.current_project_path
            if (
                folder
                and folder.strip()
                and not folder.strip().lower().endswith("[none]")
            ):
                official_csv = os.path.join(folder, "project_bom.csv")
                self.bom_handler.save_bom(official_csv)
                self.log.log("info", f"Rewrote BOM to {official_csv} after import.")
            else:
                self.log.log(
                    "warning", "No valid project folder => not overwriting BOM on disk."
                )
            QMessageBox.information(
                self.main_window,
                "BOM Re-Imported",
                "The BOM changes have been applied.",
            )
        else:
            self.log.log("warning", f"Re-import of BOM from {file_path} failed.")
            QMessageBox.warning(
                self.main_window,
                "Import Failed",
                "Could not parse or load the updated BOM file.",
            )

    def restore_backup_dialog(self):
        """
        Opens the BackupBrowserDialog for the current project.
        Disabled in the menu when no project is open, but we still
        check here for safety.
        """
        proj_dir = getattr(self.main_window, "current_project_path", None)
        if not proj_dir:
            QMessageBox.information(
                self.main_window,
                "No Project",
                "Open a project first, then choose Restore Backup.",
            )
            return

        project_name = os.path.basename(proj_dir.rstrip(os.sep))

        const_root = Constants().get("central_backup_dir")
        backup_root = str(const_root).strip() if const_root else ""
        if not backup_root:
            backup_root = os.path.join(proj_dir, "backups")

        b_dir = os.path.join(backup_root, project_name)
        if not os.path.isdir(b_dir):
            QMessageBox.information(
                self.main_window,
                "No Backups",
                "No backup files were found for this project.",
            )
            return

        dlg = BackupBrowserDialog(proj_dir, b_dir, parent=self.main_window)
        if dlg.exec_() == dlg.Accepted:
            # re‑load to reflect restored files
            self.load_existing_project(self.main_window.current_project_path)
