import time
import copy
from typing import List
from PyQt5.QtWidgets import (
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QHeaderView,
    QMessageBox,
    QSizePolicy,
    QFileDialog,
)
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal
import pandas as pd  # New import for Excel export

from objects.board_object import BoardObject
from logs.log_handler import LogHandler

# Conversion factor for mm to mils.
MM_TO_MILS = 39.37


class PadEditorDialog(QDialog):
    """
    A dialog to view and edit multiple pads at once.
    (Features include filtering, bulk editing, temporary removal of rows, toggling units,
     and exporting the currently visible table to an Excel file.)
    """

    pads_updated = pyqtSignal()  # Emitted when changes are applied

    def __init__(
        self,
        selected_pads: List[BoardObject],
        object_library=None,
        board_view=None,  # <-- NEW: pass in BoardView here
        parent=None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Pad Editor")
        self.log = LogHandler(output="both")
        self.object_library = object_library

        # Store the selected pads in local structures
        self.selected_pads = selected_pads[:]  # Copy so as not to modify original list
        self.filtered_pads = list(self.selected_pads)

        # Current unit for display and editing ("mm" or "mils")
        self.current_unit = "mm"

        # Define table columns (11 columns)
        self.COL_PIN = 0
        self.COL_COMPONENT = 1
        self.COL_CHANNEL = 2
        self.COL_SIGNAL = 3
        self.COL_TESTPOS = 4
        self.COL_TESTABILITY = 5
        self.COL_TECH = 6
        self.COL_SHAPE = 7
        self.COL_WIDTH = 8
        self.COL_HEIGHT = 9
        self.COL_HOLE = 10

        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # ---------------------------------------------------------
        # 1. FILTER BOX / UI
        # ---------------------------------------------------------
        self.filter_box = QGroupBox("Filter Pads")
        self.filter_layout = QFormLayout(self.filter_box)
        self.pin_filter = QLineEdit()
        self.pin_filter.setFixedWidth(80)
        self.channel_filter = QLineEdit()
        self.channel_filter.setFixedWidth(80)
        self.signal_filter = QLineEdit()
        self.signal_filter.setFixedWidth(100)
        self.component_filter = QLineEdit()
        self.component_filter.setFixedWidth(100)
        self.testpos_filter = QComboBox()
        self.testpos_filter.addItems(["", "Top", "Bottom", "Both"])
        self.testpos_filter.setFixedWidth(100)
        self.tech_filter = QComboBox()
        self.tech_filter.addItems(["", "SMD", "Through Hole", "Mechanical"])
        self.tech_filter.setFixedWidth(100)
        self.shape_filter = QComboBox()
        self.shape_filter.addItems(
            [
                "",
                "Round",
                "Square/rectangle",
                "Square/rectangle with Hole",
                "Ellipse",
                "Hole",
            ]
        )
        self.shape_filter.setFixedWidth(150)
        self.width_filter = QLineEdit()
        self.width_filter.setFixedWidth(80)
        self.height_filter = QLineEdit()
        self.height_filter.setFixedWidth(80)
        self.hole_filter = QLineEdit()
        self.hole_filter.setFixedWidth(80)

        # Add filter controls to the layout
        self.filter_layout.addRow("Pin:", self.pin_filter)
        self.filter_layout.addRow("Channel:", self.channel_filter)
        self.filter_layout.addRow("Signal:", self.signal_filter)
        self.filter_layout.addRow("Component:", self.component_filter)
        self.filter_layout.addRow("Test Pos:", self.testpos_filter)
        self.filter_layout.addRow("Tech:", self.tech_filter)
        self.filter_layout.addRow("Shape:", self.shape_filter)
        self.filter_layout.addRow("Width:", self.width_filter)
        self.filter_layout.addRow("Height:", self.height_filter)
        self.filter_layout.addRow("Hole:", self.hole_filter)

        # Filter box buttons
        self.btn_apply_filter = QPushButton("Apply Filter")
        self.btn_clear_filter = QPushButton("Clear Filter")
        self.btn_select_all = QPushButton("Select All")
        self.btn_remove_selected = QPushButton("Remove Selected")
        filter_btn_layout = QHBoxLayout()
        filter_btn_layout.addWidget(self.btn_apply_filter)
        filter_btn_layout.addWidget(self.btn_clear_filter)
        filter_btn_layout.addWidget(self.btn_select_all)
        filter_btn_layout.addWidget(self.btn_remove_selected)
        self.filter_layout.addRow(filter_btn_layout)

        # ---------------------------------------------------------
        # 2. TABLE FOR DISPLAYING PAD DATA
        # ---------------------------------------------------------
        self.pad_table = QTableWidget()
        self.pad_table.setColumnCount(12)
        self.pad_table.setHorizontalHeaderLabels(
            [
                "Pin",
                "Component",
                "Channel",
                "Signal",
                "Test Pos",
                "Testability",
                "Tech",
                "Shape",
                "Width",
                "Height",
                "Hole",
                "Angle",
            ]
        )
        header = self.pad_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.pad_table.setMinimumHeight(350)
        self.pad_table.setMinimumWidth(600)
        table_size_policy = self.pad_table.sizePolicy()
        table_size_policy.setHorizontalPolicy(QSizePolicy.Expanding)
        table_size_policy.setVerticalPolicy(QSizePolicy.Expanding)
        self.pad_table.setSizePolicy(table_size_policy)
        self.pad_table.itemChanged.connect(self.on_item_changed)

        self.populate_table(self.filtered_pads)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.pad_table, stretch=3)
        top_layout.addWidget(self.filter_box, stretch=1)
        main_layout.addLayout(top_layout)

        # ---------------------------------------------------------
        # 3. BULK EDIT SECTION
        # ---------------------------------------------------------
        self.bulk_edit_box = QGroupBox("Bulk Edit")
        self.bulk_edit_layout = QFormLayout(self.bulk_edit_box)
        bulk_font = self.bulk_edit_box.font()
        bulk_font.setPointSize(11)
        bulk_font.setBold(True)
        self.bulk_edit_box.setFont(bulk_font)
        combo_width = 230

        self.combo_test_position = QComboBox()
        self.combo_test_position.addItems(["No change", "Top", "Bottom", "Both"])
        self.combo_test_position.setFixedWidth(combo_width)
        self.combo_testability = QComboBox()
        self.combo_testability.addItems(
            ["No change", "Testable", "Not Testable", "Forced", "Terminal"]
        )
        self.combo_testability.setFixedWidth(combo_width)
        self.combo_tech = QComboBox()
        self.combo_tech.addItems(["No change", "SMD", "Through Hole", "Mechanical"])
        self.combo_tech.setFixedWidth(combo_width)
        self.combo_shape = QComboBox()
        self.combo_shape.addItems(
            [
                "No change",
                "Round",
                "Square/rectangle",
                "Square/rectangle with Hole",
                "Ellipse",
                "Hole",
            ]
        )
        self.combo_shape.setFixedWidth(combo_width)
        self.combo_shape.currentTextChanged.connect(self.update_bulk_edit_fields)

        self.width_label = QLabel("Width (mm):")
        self.height_label = QLabel("Height (mm):")
        self.hole_label = QLabel("Hole (mm):")
        self.angle_label = QLabel("Angle (deg):")  # Example for angle

        self.width_edit = QLineEdit()
        self.width_edit.setPlaceholderText("No change")
        self.width_edit.setFixedWidth(combo_width)

        self.height_edit = QLineEdit()
        self.height_edit.setPlaceholderText("No change")
        self.height_edit.setFixedWidth(combo_width)

        self.hole_edit = QLineEdit()
        self.hole_edit.setPlaceholderText("No change")
        self.hole_edit.setFixedWidth(combo_width)

        self.angle_edit = QLineEdit("No change")
        self.angle_edit.setPlaceholderText("No change")
        self.angle_edit.setFixedWidth(combo_width)

        self.bulk_edit_layout.addRow("Test Position:", self.combo_test_position)
        self.bulk_edit_layout.addRow("Testability:", self.combo_testability)
        self.bulk_edit_layout.addRow("Technology:", self.combo_tech)
        self.bulk_edit_layout.addRow("Shape:", self.combo_shape)
        self.bulk_edit_layout.addRow(self.width_label, self.width_edit)
        self.bulk_edit_layout.addRow(self.height_label, self.height_edit)
        self.bulk_edit_layout.addRow(self.hole_label, self.hole_edit)
        self.bulk_edit_layout.addRow(self.angle_label, self.angle_edit)

        main_layout.addWidget(self.bulk_edit_box)

        # ---------------------------------------------------------
        # 4. LOWER BAR BUTTONS
        # ---------------------------------------------------------
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Apply Edits")
        self.btn_delete = QPushButton("Delete Pads")
        self.btn_toggle_units = QPushButton("Units: mm")
        self.btn_export = QPushButton("Export to Excel")
        self.btn_close = QPushButton("Close")
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_toggle_units)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

        # Connect signals
        self.btn_apply_filter.clicked.connect(self.apply_filter)
        self.btn_clear_filter.clicked.connect(self.clear_filter)
        self.btn_select_all.clicked.connect(self.select_all_rows)
        self.btn_remove_selected.clicked.connect(self.remove_selected_rows)
        self.btn_toggle_units.clicked.connect(self.toggle_units)
        self.btn_export.clicked.connect(self.export_to_excel)
        self.btn_save.clicked.connect(self.apply_edits)
        self.btn_delete.clicked.connect(self.delete_selected_pads)
        self.btn_close.clicked.connect(self.close)

        self.resize(900, 550)

    # --------------------------------------------------------------------------
    # New slot: toggle_units (also update bulk edit labels)
    # --------------------------------------------------------------------------
    def toggle_units(self):
        if self.current_unit == "mm":
            self.current_unit = "mils"
        else:
            self.current_unit = "mm"
        self.btn_toggle_units.setText(f"Units: {self.current_unit}")
        # Update the bulk edit labels accordingly.
        self.width_label.setText(f"Width ({self.current_unit}):")
        self.height_label.setText(f"Height ({self.current_unit}):")
        self.hole_label.setText(f"Hole ({self.current_unit}):")
        self.populate_table(self.filtered_pads)
        self.log.log("info", f"Units toggled to {self.current_unit}. Table refreshed.")

    # --------------------------------------------------------------------------
    # New method: select_all_rows for table selection
    # --------------------------------------------------------------------------
    def select_all_rows(self):
        self.pad_table.selectAll()
        self.log.log("info", "All rows selected in the table.")

    # --------------------------------------------------------------------------
    # New method: remove_selected_rows (only from the table)
    # --------------------------------------------------------------------------
    def remove_selected_rows(self):
        selected_ranges = self.pad_table.selectedRanges()
        if not selected_ranges:
            QMessageBox.information(
                self, "No Rows Selected", "Select at least one row to remove."
            )
            return
        rows_to_remove = set()
        for sel in selected_ranges:
            for row in range(sel.topRow(), sel.bottomRow() + 1):
                rows_to_remove.add(row)
        new_filtered = [
            pad
            for idx, pad in enumerate(self.filtered_pads)
            if idx not in rows_to_remove
        ]
        removed_count = len(self.filtered_pads) - len(new_filtered)
        self.filtered_pads = new_filtered
        self.populate_table(self.filtered_pads)
        self.log.log(
            "info", f"Removed {removed_count} rows from the table (temporary removal)."
        )

    # --------------------------------------------------------------------------
    # Updated populate_table with timing instrumentation, unit conversion, and read-only cells
    # --------------------------------------------------------------------------
    def populate_table(self, pads: List[BoardObject]) -> None:
        start_time = time.perf_counter()
        # Sort the pads by component name and then by numeric pin value.
        self.filtered_pads = sorted(
            pads, key=lambda p: (p.component_name.lower(), int(p.pin))
        )
        self.pad_table.setSortingEnabled(False)
        self.pad_table.setUpdatesEnabled(False)
        self.pad_table.blockSignals(True)
        self.pad_table.setRowCount(0)
        row_count = len(self.filtered_pads)
        self.pad_table.setRowCount(row_count)
        for row_idx, pad in enumerate(self.filtered_pads):
            # Convert dimensions if units are in mils.
            if self.current_unit == "mils":
                width = pad.width_mm * MM_TO_MILS
                height = pad.height_mm * MM_TO_MILS
                hole = pad.hole_mm * MM_TO_MILS
            else:
                width = pad.width_mm
                height = pad.height_mm
                hole = pad.hole_mm

            # Use pad.signal if it exists; otherwise, default to an empty string.
            signal_text = pad.signal if hasattr(pad, "signal") else ""

            # Prepare the list of table items.
            angle_val = pad.angle_deg
            if pad.test_position.lower() == "bottom":
                angle_val = (180 - angle_val) % 360

            items = [
                QTableWidgetItem(str(pad.pin)),
                QTableWidgetItem(pad.component_name),
                QTableWidgetItem(str(pad.channel)),
                QTableWidgetItem(signal_text),
                QTableWidgetItem(pad.test_position),
                QTableWidgetItem(pad.testability),
                QTableWidgetItem(pad.technology),
                QTableWidgetItem(pad.shape_type),
                QTableWidgetItem(f"{width:.2f}"),
                QTableWidgetItem(f"{height:.2f}"),
                QTableWidgetItem(f"{hole:.2f}"),
                QTableWidgetItem(f"{angle_val:.2f}"),
            ]
            # Set each cell as read-only and insert into the table.
            for col_idx, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.pad_table.setItem(row_idx, col_idx, item)
        self.pad_table.blockSignals(False)
        self.pad_table.setUpdatesEnabled(True)
        self.pad_table.setSortingEnabled(True)
        elapsed = time.perf_counter() - start_time
        self.log.log(
            "info",
            f"Table refresh: populated {row_count} rows in {elapsed:.4f} seconds.",
        )

    # --------------------------------------------------------------------------
    # Updated on_item_changed remains unchanged (if needed)...
    # --------------------------------------------------------------------------
    def on_item_changed(self, item: QTableWidgetItem) -> None:
        # This method would be used if you need to capture changes from within the table.
        # Since the cells are read-only now, this may not be used.
        pass

    def get_column_attr(self, col_idx):
        mapping = [
            "pin",
            "component_name",
            "channel",
            "signal",
            "test_position",
            "testability",
            "technology",
            "shape_type",
            "width_mm",
            "height_mm",
            "hole_mm",
            "angle_deg",
        ]
        return mapping[col_idx]

    def get_pad_for_row(self, row_idx: int) -> BoardObject:
        if 0 <= row_idx < len(self.filtered_pads):
            pad = self.filtered_pads[row_idx]
            self.log.log(
                "debug",
                f"get_pad_for_row: Table row {row_idx} -> Pad {pad.channel} (Component {pad.component_name}, Pin {pad.pin})",
            )
            return pad
        self.log.log(
            "warning",
            f"get_pad_for_row: Invalid row index {row_idx}. Filtered pads count = {len(self.filtered_pads)}",
        )
        return None

    # --------------------------------------------------------------------------
    # Updated apply_filter to include new filters
    # --------------------------------------------------------------------------
    def apply_filter(self):
        self.log.log("debug", "Applying filter to pad table.")
        pin_txt = self.pin_filter.text().strip().lower()
        channel_txt = self.channel_filter.text().strip().lower()
        signal_txt = self.signal_filter.text().strip().lower()
        component_txt = self.component_filter.text().strip().lower()
        testpos_val = self.testpos_filter.currentText().strip().lower()
        tech_val = self.tech_filter.currentText().strip().lower()
        shape_val = self.shape_filter.currentText().strip().lower()
        width_txt = self.width_filter.text().strip()
        height_txt = self.height_filter.text().strip()
        hole_txt = self.hole_filter.text().strip()

        def matches_filter(p: BoardObject):
            if pin_txt and pin_txt not in str(p.pin).lower():
                return False
            if channel_txt and channel_txt not in str(p.channel):
                return False
            if signal_txt and signal_txt not in p.signal.lower():
                return False
            if component_txt and component_txt not in p.component_name.lower():
                return False
            if testpos_val and testpos_val not in p.test_position.lower():
                return False
            if tech_val and tech_val not in p.technology.lower():
                return False
            if shape_val and shape_val not in p.shape_type.lower():
                return False
            conv = MM_TO_MILS if self.current_unit == "mils" else 1.0
            if width_txt:
                try:
                    if conv * p.width_mm < float(width_txt):
                        return False
                except ValueError:
                    pass
            if height_txt:
                try:
                    if conv * p.height_mm < float(height_txt):
                        return False
                except ValueError:
                    pass
            if hole_txt:
                try:
                    if conv * p.hole_mm < float(hole_txt):
                        return False
                except ValueError:
                    pass
            return True

        self.filtered_pads = [p for p in self.selected_pads if matches_filter(p)]
        self.populate_table(self.filtered_pads)
        self.log.log("debug", f"Filtered pads: {len(self.filtered_pads)} remaining.")

    def clear_filter(self):
        self.log.log("debug", "Clearing all filters.")
        self.pin_filter.clear()
        self.channel_filter.clear()
        self.signal_filter.clear()
        self.component_filter.clear()
        self.testpos_filter.setCurrentIndex(0)
        self.tech_filter.setCurrentIndex(0)
        self.shape_filter.setCurrentIndex(0)
        self.width_filter.clear()
        self.height_filter.clear()
        self.hole_filter.clear()
        self.filtered_pads = list(self.selected_pads)
        self.populate_table(self.filtered_pads)
        self.log.log(
            "debug", f"Filter cleared. Showing {len(self.filtered_pads)} pads."
        )

    # --------------------------------------------------------------------------
    # Updated bulk edit: disable/enable dimension edit boxes based on shape selection.
    # --------------------------------------------------------------------------
    def update_bulk_edit_fields(self, new_shape: str):
        # Enable dimension fields only for shapes that need them.
        self.width_edit.setEnabled(False)
        self.height_edit.setEnabled(False)
        self.hole_edit.setEnabled(False)
        # Always enable the angle edit.
        self.angle_edit.setEnabled(True)

        shape = new_shape.lower()
        if shape == "no change":
            pass
        elif shape == "round":
            self.width_edit.setEnabled(True)
        elif shape == "square/rectangle":
            self.width_edit.setEnabled(True)
            self.height_edit.setEnabled(True)
        elif shape == "square/rectangle with hole":
            self.width_edit.setEnabled(True)
            self.height_edit.setEnabled(True)
            self.hole_edit.setEnabled(True)
        elif shape == "ellipse":
            self.width_edit.setEnabled(True)
            self.height_edit.setEnabled(True)
        elif shape == "hole":
            self.width_edit.setEnabled(True)
            self.hole_edit.setEnabled(True)
        self.log.log("debug", f"Bulk edit fields updated for shape '{new_shape}'.")

    # --------------------------------------------------------------------------
    # Updated apply_edits with timing instrumentation
    # --------------------------------------------------------------------------
    def apply_edits(self):
        overall_start = time.perf_counter()

        # ------------------------------------------------------------------
        # STEP 0  – capture which pads are currently selected
        # ------------------------------------------------------------------
        selected_ranges = self.pad_table.selectedRanges()
        if not selected_ranges:
            QMessageBox.information(
                self, "No Rows Selected", "Select at least one row."
            )
            return

        selected_channels = set()
        for sel in selected_ranges:
            for row in range(sel.topRow(), sel.bottomRow() + 1):
                pad = self.get_pad_for_row(row)
                if pad:
                    selected_channels.add(pad.channel)

        self.log.log(
            "debug", f"Selected rows capture: channels={sorted(selected_channels)}"
        )

        # ------------------------------------------------------------------
        # STEP 1  – collect requested changes from the bulk-edit widgets
        # ------------------------------------------------------------------
        shape = self.combo_shape.currentText()
        test_pos = self.combo_test_position.currentText()
        testab = self.combo_testability.currentText()
        tech = self.combo_tech.currentText()
        width_txt = self.width_edit.text().strip()
        height_txt = self.height_edit.text().strip()
        hole_txt = self.hole_edit.text().strip()
        angle_txt = self.angle_edit.text().strip()

        changes = {}
        if shape != "No change":
            changes["shape_type"] = shape
        if test_pos != "No change":
            changes["test_position"] = test_pos
        if testab != "No change":
            changes["testability"] = testab
        if tech != "No change":
            changes["technology"] = tech

        def _f(x):
            try:
                return float(x)
            except ValueError:
                return None

        if (v := _f(width_txt)) is not None:
            changes["width_mm"] = v
        if (v := _f(height_txt)) is not None:
            changes["height_mm"] = v
        if (v := _f(hole_txt)) is not None:
            changes["hole_mm"] = v
        if angle_txt and angle_txt.lower() != "no change":
            if (v := _f(angle_txt)) is not None:
                changes["angle_deg"] = v

        self.log.log("debug", f"Bulk edit changes: {changes}")

        # ------------------------------------------------------------------
        # STEP 2  – build list of pads to update
        # ------------------------------------------------------------------
        updated_pads = []
        for row in range(self.pad_table.rowCount()):
            pad = self.get_pad_for_row(row)
            if pad and pad.channel in selected_channels:
                pad_copy = copy.deepcopy(pad)
                modified = False
                for attr, val in changes.items():
                    if getattr(pad_copy, attr, None) != val:
                        setattr(pad_copy, attr, val)
                        modified = True
                if modified:
                    updated_pads.append(pad_copy)

        if not updated_pads:
            QMessageBox.information(self, "No Changes", "No attributes changed.")
            return

        # ------------------------------------------------------------------
        # STEP 3  – commit changes to ObjectLibrary (with partial re-render)
        # ------------------------------------------------------------------
        if self.object_library:
            self.object_library.bulk_update_objects(updated_pads, changes)
            channel_map = {obj.channel: obj for obj in updated_pads}
            self.selected_pads = [
                channel_map.get(p.channel, p) for p in self.selected_pads
            ]
            self.filtered_pads = [
                channel_map.get(p.channel, p) for p in self.filtered_pads
            ]

        # ------------------------------------------------------------------
        # STEP 4 – refresh table *and* restore multi-row selection
        # ------------------------------------------------------------------
        self.populate_table(self.filtered_pads)

        # re-select the same rows without clearing previous ones
        sel_model = self.pad_table.selectionModel()
        for row_idx, pad in enumerate(self.filtered_pads):
            if pad.channel in selected_channels:
                first = self.pad_table.model().index(row_idx, 0)
                last = self.pad_table.model().index(
                    row_idx, self.pad_table.columnCount() - 1
                )
                sel_range = QtCore.QItemSelection(first, last)
                sel_model.select(
                    sel_range,
                    QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows,
                )

        # ------------------------------------------------------------------
        # STEP 5  – wrap-up
        # ------------------------------------------------------------------
        self.pads_updated.emit()
        QMessageBox.information(self, "Edits Applied", "Bulk edits have been applied.")

        elapsed = time.perf_counter() - overall_start
        self.log.log(
            "info",
            f"apply_edits completed in {elapsed:.4f}s – "
            f"updated {len(updated_pads)} pad(s).",
        )

    def delete_selected_pads(self):
        selected_ranges = self.pad_table.selectedRanges()
        if not selected_ranges:
            QMessageBox.information(
                self, "No Rows Selected", "Select at least one row."
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Remove selected pads from the ObjectLibrary?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        to_delete = []
        for sel in selected_ranges:
            for row in range(sel.topRow(), sel.bottomRow() + 1):
                pad_obj = self.get_pad_for_row(row)
                if pad_obj and pad_obj not in to_delete:
                    to_delete.append(pad_obj)

        if to_delete:
            self.object_library.modify_objects(deleted=to_delete)
            self.selected_pads = [p for p in self.selected_pads if p not in to_delete]
            self.filtered_pads = [p for p in self.filtered_pads if p not in to_delete]
            self.populate_table(self.filtered_pads)
            self.pads_updated.emit()
            QMessageBox.information(
                self, "Pads Removed", f"Removed {len(to_delete)} pad(s)."
            )
            self.log.log("debug", f"Deleted {len(to_delete)} pads and updated UI.")

    # --------------------------------------------------------------------------
    # New method: export_to_excel to export the current visible table
    # --------------------------------------------------------------------------
    def export_to_excel(self):
        # Prepare a list of dictionaries from the filtered pads.
        data = []
        for pad in self.filtered_pads:
            # Convert dimensions based on current unit.
            if self.current_unit == "mils":
                width = pad.width_mm * MM_TO_MILS
                height = pad.height_mm * MM_TO_MILS
                hole = pad.hole_mm * MM_TO_MILS
            else:
                width = pad.width_mm
                height = pad.height_mm
                hole = pad.hole_mm
            angle_val = pad.angle_deg
            if pad.test_position.lower() == "bottom":
                angle_val = (180 - angle_val) % 360

            data.append(
                {
                    "Pin": pad.pin,
                    "Component": pad.component_name,
                    "Channel": pad.channel,
                    "Signal": pad.signal,
                    "Test Pos": pad.test_position,
                    "Testability": pad.testability,
                    "Tech": pad.technology,
                    "Shape": pad.shape_type,
                    "Width": f"{width:.2f}",
                    "Height": f"{height:.2f}",
                    "Hole": f"{hole:.2f}",
                    "Angle": f"{angle_val:.2f}",
                    "Units": self.current_unit,
                }
            )
        if not data:
            QMessageBox.information(self, "No Data", "There are no pads to export.")
            return
        df = pd.DataFrame(data)
        # Ask the user where to save the file.
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save as Excel File", "", "Excel Files (*.xlsx)"
        )
        if filename:
            try:
                df.to_excel(filename, index=False, engine="openpyxl")
                self.log.log("info", f"Exported table to Excel file: {filename}")
                QMessageBox.information(
                    self, "Export Successful", f"Table exported to {filename}"
                )
            except Exception as e:
                self.log.log("error", f"Failed to export table: {e}")
                QMessageBox.critical(
                    self, "Export Failed", f"Failed to export table:\n{e}"
                )

    def closeEvent(self, event):
        """
        When the dialog is closed, re-select the pads in the board view that were originally selected.

        if self.board_view and self.selected_pads:
            # Iterate over the originally selected pads.
            for pad in self.selected_pads:
                # Assume the DisplayLibrary stores rendered items keyed by the pad's channel.
                item = self.board_view.display_library.displayed_objects.get(pad.channel)
                if item:
                    item.setSelected(True)
                    # Optionally, if you want to force a visual refresh:
                    item.update()
        """
        super().closeEvent(event)
