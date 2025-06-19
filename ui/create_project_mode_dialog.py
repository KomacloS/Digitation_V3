from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel


class CreateProjectModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Project")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select creation mode:"))
        self.manual_button = QPushButton("Manual")
        self.auto_button = QPushButton("Automatic from MDB")
        layout.addWidget(self.manual_button)
        layout.addWidget(self.auto_button)
