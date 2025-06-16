from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel


class StartDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select an option:"))
        self.open_button = QPushButton("Open Existing Project")
        self.create_button = QPushButton("Create New Project")
        layout.addWidget(self.open_button)
        layout.addWidget(self.create_button)
