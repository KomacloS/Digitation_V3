# component_input_dialog.py

import os
import re
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import Qt, QSettings, pyqtSlot, pyqtSignal
from logs.log_handler import LogHandler
from component_placer.bom_handler.bom_handler import BOMHandler

class ComponentInputDialog(QDialog):
    """
    Dialog for both standard component entry and Quick Creation.
    Original functionality is fully preserved; Quick Creation fields
    are added at the end.
    """
    component_data_ready = pyqtSignal(dict)
    quick_params_changed  = pyqtSignal(dict)

    # Loaded once from functions_ref.txt
    FUNCTION_OPTIONS = []  
    PREFIX_MAPPING    = {}
    last_numbers      = {}

    def __init__(self, parent=None, logger=None, bom_handler: BOMHandler = None,
                 quick: bool = False):
        super().__init__(parent)
        self.quick_mode = quick
        self.setWindowTitle("New Component Details")
        self.setModal(True)

        # Logging & settings
        self.log = logger if logger is not None else LogHandler()
        self.settings = QSettings("MyCompany", "PCB Digitization Tool")
        self.bom_handler = bom_handler

        # Load the function→prefix mapping
        self.FUNCTION_OPTIONS, self.PREFIX_MAPPING = self._load_function_reference()

        # Build UI, restore values, then hide/show Quick fields
        self.setup_ui()
        self.load_settings()
        self._toggle_quick_fields(self.quick_mode)

        # ── Connect every Quick widget to live emitter ───────────────
        for w in self._quick_widgets:
            if hasattr(w, "valueChanged"):
                w.valueChanged.connect(self._emit_live)
            elif hasattr(w, "currentIndexChanged"):
                w.currentIndexChanged.connect(self._emit_live)
            elif hasattr(w, "toggled"):
                w.toggled.connect(self._emit_live)


    def _load_function_reference(self):
        """
        Reads component_placer/bom_handler/functions_ref.txt for lines of the form:
            FUNCTION_NAME,PREFIX
        Ignores blank or '#' lines.
        """
        ref_file = os.path.join(os.path.dirname(__file__), "bom_handler", "functions_ref.txt")
        function_options, prefix_mapping = [], {}
        try:
            with open(ref_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(",")
                    if len(parts) >= 2:
                        func   = parts[0].strip()
                        prefix = parts[1].strip()
                        function_options.append(func)
                        prefix_mapping[func] = prefix
            self.log.info(f"Loaded {len(function_options)} functions.", module="ComponentInputDialog", func="_load_function_reference")
        except Exception as e:
            self.log.error(f"Failed to load function reference: {e}", module="ComponentInputDialog", func="_load_function_reference")
        return function_options, prefix_mapping

    def setup_ui(self):
        main_layout      = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        main_layout.addLayout(self.form_layout)

        # ── 1. CORE COMPONENT FIELDS ──────────────────────────────────────
        self.name_edit               = QLineEdit()
        self.auto_prefix_checkbox    = QCheckBox("Auto Prefix");    self.auto_prefix_checkbox.setChecked(True)
        self.auto_numbering_checkbox = QCheckBox("Auto Numbering"); self.auto_numbering_checkbox.setChecked(False)

        self.function_combo = QComboBox()
        self.function_combo.addItems(self.FUNCTION_OPTIONS)

        self.part_number_edit = QLineEdit()
        self.value_edit       = QLineEdit()
        self.package_edit     = QLineEdit()

        self.form_layout.addRow("Component Name*:", self.name_edit)
        cbh = QHBoxLayout()
        cbh.addWidget(self.auto_prefix_checkbox)
        cbh.addWidget(self.auto_numbering_checkbox)
        self.form_layout.addRow("", cbh)
        self.form_layout.addRow("Function*:",   self.function_combo)
        self.form_layout.addRow("Part Number:", self.part_number_edit)
        self.form_layout.addRow("Value:",       self.value_edit)
        self.form_layout.addRow("Package:",     self.package_edit)

        # auto-naming links
        self.function_combo.currentTextChanged.connect(self.update_component_name)
        self.auto_prefix_checkbox.toggled.connect(self.update_component_name)
        self.auto_numbering_checkbox.toggled.connect(self.update_component_name)

        # ── 2. QUICK-CREATION FIELDS ──────────────────────────────────────
        self.x_pins_spin = QSpinBox(); self.x_pins_spin.setRange(1, 100)
        self.y_pins_spin = QSpinBox(); self.y_pins_spin.setRange(1, 100)

        # numbering pattern selector
        self.numbering_combo = QComboBox()
        self.numbering_combo.addItems([
            "Circular / IC-snake",   # 0
            "By long rows",          # 1
            "By long columns"        # 2
        ])

        # other combo boxes
        self.side_combo = QComboBox(); self.side_combo.addItems(["Top", "Bottom", "Both"])
        self.testability_combo = QComboBox(); self.testability_combo.addItems(["Forced", "Testable", "Not Testable"])
        self.tech_combo = QComboBox(); self.tech_combo.addItems(["SMD", "Through Hole"])

        # pad shape & dimensions
        self.shape_combo = QComboBox()
        self.shape_combo.addItems([
            "Round",
            "Square/rectangle",
            "Square/rectangle with Hole",
            "Ellipse",
            "Hole"
        ])

        self.width_spin  = QDoubleSpinBox(); self.width_spin.setDecimals(3);  self.width_spin.setRange(0.10, 10.0)
        self.height_spin = QDoubleSpinBox(); self.height_spin.setDecimals(3); self.height_spin.setRange(0.10, 10.0)
        self.hole_spin   = QDoubleSpinBox(); self.hole_spin.setDecimals(3);   self.hole_spin.setRange(0.00, 10.0)

        # add to form
        self.form_layout.addRow("Pins in X:",          self.x_pins_spin)
        self.form_layout.addRow("Pins in Y:",          self.y_pins_spin)
        self.form_layout.addRow("Pin Numbering:",      self.numbering_combo)
        self.form_layout.addRow("Pad Side:",           self.side_combo)
        self.form_layout.addRow("Testability:",        self.testability_combo)
        self.form_layout.addRow("Technology:",         self.tech_combo)
        self.form_layout.addRow("Pad Shape:",          self.shape_combo)
        self.form_layout.addRow("Pad Width (mm):",     self.width_spin)
        self.form_layout.addRow("Pad Height (mm):",    self.height_spin)
        self.form_layout.addRow("Hole Ø (mm):",        self.hole_spin)

        # enable/disable width/height/hole depending on shape
        self._dim_widgets = [self.width_spin, self.height_spin, self.hole_spin]
        self.shape_combo.currentTextChanged.connect(self._shape_toggle_dims)
        self._shape_toggle_dims(self.shape_combo.currentText())  # initial

        # store quick widgets for hide/show
        self._quick_widgets = [
            self.x_pins_spin, self.y_pins_spin,
            self.numbering_combo,
            self.side_combo,  self.testability_combo,
            self.tech_combo,  self.shape_combo,
            self.width_spin,  self.height_spin, self.hole_spin
        ]

        # ── 3. DIALOG BUTTONS ─────────────────────────────────────────────
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.form_layout.addRow(self.button_box)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)

        # initialise auto-name
        self.update_component_name()


    def _shape_toggle_dims(self, shape_text: str):
        """Enable the right dimension boxes, leave others disabled."""
        for w in self._dim_widgets:
            w.setEnabled(False)

        st = shape_text.lower()
        if st == "round":
            self.width_spin.setEnabled(True)
        elif st == "square/rectangle":
            self.width_spin.setEnabled(True)
            self.height_spin.setEnabled(True)
        elif st == "square/rectangle with hole":
            self.width_spin.setEnabled(True)
            self.height_spin.setEnabled(True)
            self.hole_spin.setEnabled(True)
        elif st == "ellipse":
            self.width_spin.setEnabled(True)
            self.height_spin.setEnabled(True)
        elif st == "hole":
            self.width_spin.setEnabled(True)
            self.hole_spin.setEnabled(True)


    # ── Logging helpers ─────────────────────────────────────────────────────
    def log_prefix_status(self, checked):
        self.log.info(f"Auto Prefix: {checked}", module="ComponentInputDialog", func="log_prefix_status")

    def log_numbering_status(self, checked):
        self.log.info(f"Auto Numbering: {checked}", module="ComponentInputDialog", func="log_numbering_status")

    # ── Settings persistence ─────────────────────────────────────────────────
    def load_settings(self):
        self.function_combo.setCurrentText(self.settings.value("function", self.FUNCTION_OPTIONS[0] if self.FUNCTION_OPTIONS else ""))
        self.part_number_edit.setText(self.settings.value("part_number", ""))
        self.value_edit.setText(self.settings.value("value", ""))
        self.package_edit.setText(self.settings.value("package", ""))
        self.auto_prefix_checkbox.setChecked(self.settings.value("auto_prefix", True, type=bool))
        self.auto_numbering_checkbox.setChecked(self.settings.value("auto_numbering", False, type=bool))
        last_str = self.settings.value("last_numbers", "{}")
        try:
            if self.__class__.last_numbers:
                self.last_numbers = self.__class__.last_numbers
            else:
                self.last_numbers = eval(last_str)
                self.__class__.last_numbers = self.last_numbers
        except:
            self.last_numbers = {}
            self.__class__.last_numbers = {}

    def save_settings(self):
        self.settings.setValue("function",      self.function_combo.currentText())
        self.settings.setValue("part_number",   self.part_number_edit.text())
        self.settings.setValue("value",         self.value_edit.text())
        self.settings.setValue("package",       self.package_edit.text())
        self.settings.setValue("auto_prefix",   self.auto_prefix_checkbox.isChecked())
        self.settings.setValue("auto_numbering",self.auto_numbering_checkbox.isChecked())
        self.settings.setValue("last_numbers",  repr(self.last_numbers))
        self.log.info("Settings saved.", module="ComponentInputDialog", func="save_settings")

    # ── Auto-naming logic ────────────────────────────────────────────────────
    def update_component_name(self):
        auto_pref = self.auto_prefix_checkbox.isChecked()
        auto_num  = self.auto_numbering_checkbox.isChecked()
        text      = self.name_edit.text().strip()
        func      = self.function_combo.currentText()
        from objects.search_library import SearchLibrary
        from objects.object_library import ObjectLibrary
        existing  = SearchLibrary(ObjectLibrary()).get_components()

        if not auto_num:
            if auto_pref:
                pref = self.PREFIX_MAPPING.get(func, "")
                if not re.search(r'\d', text):
                    self.name_edit.setText(pref)
            return

        if auto_pref:
            pref = self.PREFIX_MAPPING.get(func, "")
        else:
            m = re.match(r'([^\d]*)(\d*)$', text)
            pref = m.group(1) if m else ""
        last = self.last_numbers.get(pref, 0)
        cand = pref + str(last + 1)
        while cand in existing:
            last += 1
            cand = pref + str(last + 1)
        self.name_edit.setText(cand)

    @pyqtSlot()
    def reset_auto_numbering(self):
        self.load_settings()
        self.update_component_name()

    # ── Validation & emit ───────────────────────────────────────────────────
    def validate_and_accept(self):
        name     = self.name_edit.text().strip()
        function = self.function_combo.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Component Name is required.")
            return
        if not function:
            QMessageBox.warning(self, "Input Error", "Function is required.")
            return

        if self.auto_numbering_checkbox.isChecked():
            if self.auto_prefix_checkbox.isChecked():
                pref = self.PREFIX_MAPPING.get(function, "")
            else:
                m = re.match(r'([^\d]*)', name)
                pref = m.group(1) if m else ""
            try:
                num = int(name.replace(pref, ""))
            except:
                num = 0
            self.last_numbers[pref] = num
            self.__class__.last_numbers = self.last_numbers

        self.save_settings()
        data = self.get_data()

        if self.bom_handler:
            # Directly update BOM if handler provided
            self.bom_handler.add_component(
                data.get("component_name", ""),
                data.get("function",        ""),
                data.get("value",           ""),
                data.get("package",         ""),
                data.get("part_number",     "")
            )
        else:
            # Normal signal-based flow
            self.component_data_ready.emit(data)

        self.accept()

    def get_data(self) -> dict:
        """
        Returns the classic component data dict (preserves older behavior).
        """
        return {
            "component_name": self.name_edit.text().strip(),
            "function":       self.function_combo.currentText().strip(),
            "part_number":    self.part_number_edit.text().strip(),
            "value":          self.value_edit.text().strip(),
            "package":        self.package_edit.text().strip(),
            "auto_prefix":    self.auto_prefix_checkbox.isChecked(),
            "auto_numbering": self.auto_numbering_checkbox.isChecked()
        }

    def get_quick_params(self) -> dict:
        """
        Collect all Quick-Creation parameters.
        Spin-boxes are forced to interpret their editors first so typed but
        unfocused values are not lost.
        """
        # Flush any un-committed editor text
        for sb in (self.x_pins_spin, self.y_pins_spin,
                self.width_spin,  self.height_spin, self.hole_spin):
            sb.interpretText()

        return {
            "component_name": self.name_edit.text().strip(),
            "function"      : self.function_combo.currentText(),
            "x_pins"        : self.x_pins_spin.value(),
            "y_pins"        : self.y_pins_spin.value(),
            "number_scheme" : self.numbering_combo.currentIndex(),   # 0-circular / 1-rows / 2-cols
            "test_side"     : self.side_combo.currentText().lower(),
            "testability"   : self.testability_combo.currentText(),
            "technology"    : self.tech_combo.currentText(),
            "shape"         : self.shape_combo.currentText(),
            "width"         : self.width_spin.value(),
            "height"        : self.height_spin.value(),
            "hole"          : self.hole_spin.value()
        }





    def _toggle_quick_fields(self, show: bool):
        """
        Hide or show all Quick-Creation widgets (and their labels).
        """
        for w in self._quick_widgets:
            w.setVisible(show)
            lbl = self.form_layout.labelForField(w)
            if lbl:
                lbl.setVisible(show)

    def _emit_live(self, *args):
        """Emit quick_params_changed with the current params."""
        if self.quick_mode:
            self.quick_params_changed.emit(self.get_quick_params())

    def closeEvent(self, event):
        self.log.info("ComponentInputDialog closed.", module="ComponentInputDialog", func="closeEvent")
        super().closeEvent(event)
