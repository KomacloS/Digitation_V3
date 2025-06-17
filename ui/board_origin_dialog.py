from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
)
from PyQt5.QtGui import QDoubleValidator


class BoardOriginDialog(QDialog):
    """Dialog to edit board origin coordinates for top and bottom images."""

    def __init__(self, constants, parent=None):
        super().__init__(parent)
        self.constants = constants
        self.setWindowTitle("Set Board Origin")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.top_x_edit = QLineEdit()
        validator = QDoubleValidator(-1e6, 1e6, 8, self.top_x_edit)
        self.top_x_edit.setValidator(validator)
        self.top_x_edit.setText(str(self.constants.get("TopImageXCoord", 0.0)))
        form.addRow(QLabel("TopImageXCoord"), self.top_x_edit)

        self.top_y_edit = QLineEdit()
        validator = QDoubleValidator(-1e6, 1e6, 8, self.top_y_edit)
        self.top_y_edit.setValidator(validator)
        self.top_y_edit.setText(str(self.constants.get("TopImageYCoord", 0.0)))
        form.addRow(QLabel("TopImageYCoord"), self.top_y_edit)

        self.bottom_x_edit = QLineEdit()
        validator = QDoubleValidator(-1e6, 1e6, 8, self.bottom_x_edit)
        self.bottom_x_edit.setValidator(validator)
        self.bottom_x_edit.setText(str(self.constants.get("BottomImageXCoord", 0.0)))
        form.addRow(QLabel("BottomImageXCoord"), self.bottom_x_edit)

        self.bottom_y_edit = QLineEdit()
        validator = QDoubleValidator(-1e6, 1e6, 8, self.bottom_y_edit)
        self.bottom_y_edit.setValidator(validator)
        self.bottom_y_edit.setText(str(self.constants.get("BottomImageYCoord", 0.0)))
        form.addRow(QLabel("BottomImageYCoord"), self.bottom_y_edit)

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

    def get_values(self):
        return {
            "TopImageXCoord": float(self.top_x_edit.text() or 0.0),
            "TopImageYCoord": float(self.top_y_edit.text() or 0.0),
            "BottomImageXCoord": float(self.bottom_x_edit.text() or 0.0),
            "BottomImageYCoord": float(self.bottom_y_edit.text() or 0.0),
        }
