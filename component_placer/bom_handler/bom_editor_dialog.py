from typing import List, Dict
import os
from constants import FUNCTIONS_REF_PATH
from PyQt5.QtWidgets import (
    QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import time

class NoWheelComboBox(QComboBox):
    """A QComboBox that ignores mouse‐wheel scrolling."""
    def wheelEvent(self, event):
        # simply ignore all wheel events
        event.ignore()

class BOMEditorDialog(QDialog):
    """
    A dialog to display and fix BOM mismatches:
      - Shows all BOM components (normal rows) along with missing components.
      - Extra components (present in BOM but not on board) are highlighted in red.
      - Missing components (present on board but not in BOM) appear as blank rows highlighted in yellow.
      - A filter combobox lets the user switch between viewing All, Extra, Missing, or Errors.
      - The user can edit the function/value/package/part_number fields inline.
      - When the user clicks "Apply", the in‑memory BOM is updated accordingly.
    """

    def __init__(self, bom_handler, board_component_names, parent=None):
        super().__init__(parent)
        self.bom_handler = bom_handler
        self.board_set = board_component_names  # a set of board component names
        self.setWindowTitle("BOM Editor - Mismatch Fix")
        # Make the dialog larger by default
        self.resize(800, 600)
        
        # Compute mismatch sets (missing: on board not in BOM, extra: in BOM not on board)
        self.missing_set, self.extra_set = self._compute_mismatch()
        
        # Load function reference (options and mapping) from external file.
        self.FUNCTION_OPTIONS, _ = self._load_function_reference()

        # Build a list of all rows from the current BOM plus missing rows.
        self.all_rows = []
        self._build_all_rows()
        
        # --- UI Layout ---
        main_layout = QVBoxLayout()
        
        # Add a filter combobox at the top.
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Extra", "Missing", "Errors"])
        self.filter_combo.currentIndexChanged.connect(self.populate_table)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        main_layout.addLayout(filter_layout)
        
        # Create the table (6 columns)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Component", "Function", "Value", "Package", "Part Number", "Status/Action"
        ])
        main_layout.addWidget(self.table)
        
        # Buttons at the bottom
        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Apply")
        self.btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
        
        # Connect button signals.
        self.btn_apply.clicked.connect(self.on_apply)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Initially populate the table.
        self.populate_table()
    
    def _load_function_reference(self):
        """
        Loads function options and their prefixes from the reference text file.
        The file ``constants/functions_ref.txt`` should have one line per entry
        in the format:
            FUNCTION_NAME,PREFIX
        Blank lines or lines starting with '#' are ignored.
        Returns a tuple: (list of function options, dict mapping function option to prefix)
        """
        ref_file = FUNCTIONS_REF_PATH
        function_options = []
        prefix_mapping = {}
        try:
            with open(ref_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(",")
                    if len(parts) >= 2:
                        func = parts[0].strip()
                        prefix = parts[1].strip()
                        function_options.append(func)
                        prefix_mapping[func] = prefix
            # (Optionally log how many were loaded)
        except Exception as e:
            # If there is an error, log it (if self.log is available)
            if hasattr(self, "log"):
                self.log.error(f"Failed to load function reference from {ref_file}: {e}",
                               module="BOMEditorDialog", func="_load_function_reference")
        return function_options, prefix_mapping


    def _compute_mismatch(self):
        """
        Computes missing and extra sets.
        missing: components on board but not in BOM.
        extra: components in BOM but not on board.
        """
        bom_set = set(self.bom_handler.bom.keys())
        missing = self.board_set - bom_set
        extra = bom_set - self.board_set
        return missing, extra

    def _build_all_rows(self):
        """
        Build the complete list of rows.
        For each BOM entry, record its data and mark its type as "normal" or "extra".
        Then for each missing component, add a row with blank fields and type "missing".
        """
        self.all_rows = []
        for comp_name, attrs in self.bom_handler.bom.items():
            row_type = "extra" if comp_name in self.extra_set else "normal"
            self.all_rows.append({
                "component_name": comp_name,
                "function": attrs.get("function", ""),
                "value": attrs.get("value", ""),
                "package": attrs.get("package", ""),
                "part_number": attrs.get("part_number", ""),
                "type": row_type
            })
        for comp_name in self.missing_set:
            self.all_rows.append({
                "component_name": comp_name,
                "function": "",
                "value": "",
                "package": "",
                "part_number": "",
                "type": "missing"
            })

    def populate_table(self):
        """
        Repopulate the table based on the current filter selection.
        """
        filter_option = self.filter_combo.currentText().strip().lower()
        if filter_option == "all":
            rows_to_show = self.all_rows
        elif filter_option == "extra":
            rows_to_show = [r for r in self.all_rows if r["type"] == "extra"]
        elif filter_option == "missing":
            rows_to_show = [r for r in self.all_rows if r["type"] == "missing"]
        elif filter_option == "errors":
            rows_to_show = [r for r in self.all_rows if r["type"] in ("extra", "missing")]
        else:
            rows_to_show = self.all_rows

        self.table.setRowCount(0)
        row_index = 0
        for row_data in rows_to_show:
            self.table.insertRow(row_index)
            comp_name = row_data["component_name"]
            # Column 0: Component (make it editable and store the original name)
            item_comp = QTableWidgetItem(comp_name)
            item_comp.setFlags(item_comp.flags() | Qt.ItemIsEditable)
            item_comp.setData(Qt.UserRole, comp_name)  # store original name
            self.table.setItem(row_index, 0, item_comp)
            # Column 1: For Function, use a QComboBox with the reference options.
            combo_func = NoWheelComboBox()
            combo_func.addItems(self.FUNCTION_OPTIONS)
            current_func = row_data["function"]
            if current_func and current_func in self.FUNCTION_OPTIONS:
                combo_func.setCurrentText(current_func)
            else:
                combo_func.setCurrentIndex(-1)
            self.table.setCellWidget(row_index, 1, combo_func)
            # Columns 2-4: Value, Package, Part Number as editable items.
            item_value = QTableWidgetItem(row_data["value"])
            item_packg = QTableWidgetItem(row_data["package"])
            item_partn = QTableWidgetItem(row_data["part_number"])
            self.table.setItem(row_index, 2, item_value)
            self.table.setItem(row_index, 3, item_packg)
            self.table.setItem(row_index, 4, item_partn)
            # Column 5: Status/Action
            combo_status = NoWheelComboBox()
            if row_data["type"] == "extra":
                combo_status.addItems(["EXTRA - Remove", "Keep"])
                for col in range(0, 5):
                    cell = self.table.item(row_index, col)
                    if cell:
                        cell.setBackground(QColor("#FFBBBB"))
            elif row_data["type"] == "missing":
                combo_status.addItems(["MISSING - Add", "Remove"])
                for col in range(0, 5):
                    cell = self.table.item(row_index, col)
                    if cell:
                        cell.setBackground(QColor("#FFFFBB"))
            else:
                combo_status.addItems(["OK", "Remove"])
            self.table.setCellWidget(row_index, 5, combo_status)
            row_index += 1


    def on_apply(self):
        """
        Reads the table rows and updates the BOM as follows:
          - For rows with "EXTRA": remove them immediately.
          - For rows with "MISSING": add them only if a non‑empty function is provided.
          - For normal rows, update their values.
          Additionally, if a component name is changed (renamed), the change is
          propagated to all board objects (pads) whose component_name equals the old name.
          Duplicate names (i.e. renaming to an already-existing component) are blocked.
        """
        # Reset background colors
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setBackground(QColor("white"))

        collected = []
        row_count = self.table.rowCount()
        for row_idx in range(row_count):
            comp_item = self.table.item(row_idx, 0)
            if not comp_item:
                continue
            original_name = comp_item.data(Qt.UserRole)
            new_name = comp_item.text().strip()
            combo_func = self.table.cellWidget(row_idx, 1)
            fn_str = combo_func.currentText().strip() if combo_func else ""
            val_item = self.table.item(row_idx, 2)
            pkg_item = self.table.item(row_idx, 3)
            pn_item = self.table.item(row_idx, 4)
            value = val_item.text().strip() if val_item else ""
            package = pkg_item.text().strip() if pkg_item else ""
            part_number = pn_item.text().strip() if pn_item else ""
            status_widget = self.table.cellWidget(row_idx, 5)
            status_text = status_widget.currentText().strip() if status_widget else "OK"

            collected.append(
                {
                    "row": row_idx,
                    "original": original_name,
                    "new": new_name,
                    "function": fn_str,
                    "value": value,
                    "package": package,
                    "part_number": part_number,
                    "status": status_text,
                }
            )

        # ---- duplicate check (case-insensitive) ----
        name_map = {}
        for entry in collected:
            lname = entry["new"].lower()
            name_map.setdefault(lname, []).append(entry["row"])
        dup_rows = [rows for rows in name_map.values() if len(rows) > 1]
        if any(dup_rows):
            for rows in dup_rows:
                for r in rows:
                    item = self.table.item(r, 0)
                    if item:
                        item.setBackground(QColor("#FF8888"))
            QMessageBox.warning(
                self,
                "Duplicate Component",
                "Duplicate component names detected. Please ensure all names are unique.",
            )
            return

        new_bom = {}
        removed_comps = set()
        added_comps = set()
        renamed_components = {}

        for entry in collected:
            new_name = entry["new"].strip()
            if not new_name:
                QMessageBox.warning(self, "Invalid Name", "Component name cannot be blank.")
                return
            fn_str = entry["function"]
            value = entry["value"]
            package = entry["package"]
            part_number = entry["part_number"]
            status_text = entry["status"]

            if "EXTRA" in status_text:
                removed_comps.add(entry["original"])
                continue
            elif "MISSING" in status_text:
                if fn_str == "":
                    QMessageBox.warning(
                        self,
                        "Missing Function",
                        f"Component '{new_name}' is marked as missing and must have a function specified.",
                    )
                    return
                added_comps.add(new_name)
            new_bom[new_name] = {
                "function": fn_str,
                "value": value,
                "package": package,
                "part_number": part_number,
            }

            if entry["original"] != new_name:
                renamed_components[entry["original"]] = new_name

        messages = []
        if removed_comps:
            messages.append(f"Removed: {', '.join(sorted(removed_comps))}")
        if added_comps:
            messages.append(f"Added: {', '.join(sorted(added_comps))}")
        if renamed_components:
            renamed_msg = ", ".join([f"{o}->{n}" for o, n in renamed_components.items()])
            messages.append(f"Renamed: {renamed_msg}")
        summary = "\n".join(messages) if messages else "BOM updated with no new additions, removals, or renames."
        reply = QMessageBox.question(
            self,
            "Apply BOM Changes",
            summary + "\n\nApply these changes?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Update BOMHandler's BOM
        self.bom_handler.bom = new_bom

        if self.parent() and hasattr(self.parent(), "object_library"):
            object_library = self.parent().object_library
            rename_lookup = {old.lower(): new for old, new in renamed_components.items()}
            for obj in object_library.get_all_objects():
                original = obj.component_name
                new_name = rename_lookup.get(original.lower())
                if new_name:
                    obj.component_name = new_name
            for old_name, new_name in renamed_components.items():
                self.bom_handler.log.info(
                    f"Renamed component '{old_name}' to '{new_name}' in ObjectLibrary.",
                    module="BOMEditorDialog",
                    func="on_apply",
                )

        QMessageBox.information(self, "Edits Applied", summary)
        self.accept()


