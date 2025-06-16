from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QVBoxLayout, QHBoxLayout,
    QDoubleSpinBox, QPushButton, QLabel
)
from PyQt5.QtCore import Qt

class ProjectSettingsDialog(QDialog):
    """Dialog to edit project specific constants."""

    def __init__(self, constants, parent=None):
        super().__init__(parent)
        self.constants = constants
        self.setWindowTitle("Project Settings")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.mm_top_spin = QDoubleSpinBox()
        self.mm_top_spin.setDecimals(6)
        self.mm_top_spin.setRange(1e-9, 1e6)
        self.mm_top_spin.setValue(self.constants.get("mm_per_pixels_top", 0.0333))
        form.addRow(QLabel("mm_per_pixels_top"), self.mm_top_spin)

        self.mm_bot_spin = QDoubleSpinBox()
        self.mm_bot_spin.setDecimals(6)
        self.mm_bot_spin.setRange(1e-9, 1e6)
        self.mm_bot_spin.setValue(self.constants.get("mm_per_pixels_bot", 0.0333))
        form.addRow(QLabel("mm_per_pixels_bot"), self.mm_bot_spin)

        self.origin_x_spin = QDoubleSpinBox()
        self.origin_x_spin.setDecimals(3)
        self.origin_x_spin.setRange(-1e6, 1e6)
        self.origin_x_spin.setValue(self.constants.get("origin_x_mm", 0.0))
        form.addRow(QLabel("origin_x_mm"), self.origin_x_spin)

        self.origin_y_spin = QDoubleSpinBox()
        self.origin_y_spin.setDecimals(3)
        self.origin_y_spin.setRange(-1e6, 1e6)
        self.origin_y_spin.setValue(self.constants.get("origin_y_mm", 0.0))
        form.addRow(QLabel("origin_y_mm"), self.origin_y_spin)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def get_settings(self):
        return {
            "mm_per_pixels_top": self.mm_top_spin.value(),
            "mm_per_pixels_bot": self.mm_bot_spin.value(),
            "origin_x_mm": self.origin_x_spin.value(),
            "origin_y_mm": self.origin_y_spin.value(),
        }
