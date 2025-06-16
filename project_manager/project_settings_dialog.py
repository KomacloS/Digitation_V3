from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator


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

        self.mm_top_edit = QLineEdit()
        mm_top_validator = QDoubleValidator(1e-9, 1e6, 10, self.mm_top_edit)
        mm_top_validator.setNotation(QDoubleValidator.ScientificNotation)
        self.mm_top_edit.setValidator(mm_top_validator)
        self.mm_top_edit.setText(str(self.constants.get("mm_per_pixels_top", 0.0333)))
        form.addRow(QLabel("mm_per_pixels_top"), self.mm_top_edit)

        self.mm_bot_edit = QLineEdit()
        mm_bot_validator = QDoubleValidator(1e-9, 1e6, 10, self.mm_bot_edit)
        mm_bot_validator.setNotation(QDoubleValidator.ScientificNotation)
        self.mm_bot_edit.setValidator(mm_bot_validator)
        self.mm_bot_edit.setText(str(self.constants.get("mm_per_pixels_bot", 0.0333)))
        form.addRow(QLabel("mm_per_pixels_bot"), self.mm_bot_edit)

        self.bottom_x_edit = QLineEdit()
        bottom_x_validator = QDoubleValidator(-1e6, 1e6, 8, self.bottom_x_edit)
        self.bottom_x_edit.setValidator(bottom_x_validator)
        self.bottom_x_edit.setText(str(self.constants.get("BottomImageXCoord", 0.0)))
        form.addRow(QLabel("BottomImageXCoord"), self.bottom_x_edit)

        self.bottom_y_edit = QLineEdit()
        bottom_y_validator = QDoubleValidator(-1e6, 1e6, 8, self.bottom_y_edit)
        self.bottom_y_edit.setValidator(bottom_y_validator)
        self.bottom_y_edit.setText(str(self.constants.get("BottomImageYCoord", 0.0)))
        form.addRow(QLabel("BottomImageYCoord"), self.bottom_y_edit)

        self.top_x_edit = QLineEdit()
        top_x_validator = QDoubleValidator(-1e6, 1e6, 8, self.top_x_edit)
        self.top_x_edit.setValidator(top_x_validator)
        self.top_x_edit.setText(str(self.constants.get("TopImageXCoord", 0.0)))
        form.addRow(QLabel("TopImageXCoord"), self.top_x_edit)

        self.top_y_edit = QLineEdit()
        top_y_validator = QDoubleValidator(-1e6, 1e6, 8, self.top_y_edit)
        self.top_y_edit.setValidator(top_y_validator)
        self.top_y_edit.setText(str(self.constants.get("TopImageYCoord", 0.0)))
        form.addRow(QLabel("TopImageYCoord"), self.top_y_edit)

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
            "mm_per_pixels_top": float(self.mm_top_edit.text() or 0.0),
            "mm_per_pixels_bot": float(self.mm_bot_edit.text() or 0.0),
            "BottomImageXCoord": float(self.bottom_x_edit.text() or 0.0),
            "BottomImageYCoord": float(self.bottom_y_edit.text() or 0.0),
            "TopImageXCoord": float(self.top_x_edit.text() or 0.0),
            "TopImageYCoord": float(self.top_y_edit.text() or 0.0),
        }
