# ui/ui_customization_dialog.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QPushButton
)
from PyQt5.QtCore import Qt

class UICustomizationDialog(QDialog):
    """
    Lets the user pick separate font sizes for various UI areas.
    """

    def __init__(self, constants, parent=None):
        super().__init__(parent)
        self.setWindowTitle("UI Customization")
        self.constants = constants

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Retrieve existing font sizes from constants, defaulting if not found.
        self.toolbar_font_size = self.constants.get("toolbar_font_size", 10)
        self.statusbar_font_size = self.constants.get("statusbar_font_size", 10)
        self.tab_font_size = self.constants.get("tab_font_size", 10)

        # Create spin boxes for each setting
        layout.addLayout(self._create_font_spinbox_row("Main Toolbar Font Size:", "toolbar_font"))
        layout.addLayout(self._create_font_spinbox_row("Status Bar Font Size:", "statusbar_font"))
        layout.addLayout(self._create_font_spinbox_row("Tab Widget Font Size:", "tab_font"))

        # Add OK/Cancel buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _create_font_spinbox_row(self, label_text, setting_key_prefix):
        """
        Helper to build a row with a label + QSpinBox for font size.
        setting_key_prefix is either "toolbar_font", "statusbar_font", or "tab_font".
        """
        row_layout = QHBoxLayout()
        label = QLabel(label_text)
        spin_box = QSpinBox()
        spin_box.setRange(6, 72)

        # Map prefix to the appropriate current size
        if setting_key_prefix == "toolbar_font":
            spin_box.setValue(self.toolbar_font_size)
            self.toolbar_spin = spin_box
        elif setting_key_prefix == "statusbar_font":
            spin_box.setValue(self.statusbar_font_size)
            self.statusbar_spin = spin_box
        elif setting_key_prefix == "tab_font":
            spin_box.setValue(self.tab_font_size)
            self.tab_spin = spin_box

        row_layout.addWidget(label)
        row_layout.addWidget(spin_box)
        return row_layout

    def get_toolbar_font_size(self):
        return self.toolbar_spin.value()

    def get_statusbar_font_size(self):
        return self.statusbar_spin.value()

    def get_tab_font_size(self):
        return self.tab_spin.value()
