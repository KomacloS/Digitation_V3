from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
import os


class HelpDialog(QDialog):
    """Simple dialog to display the project README as help text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Guide")
        layout = QVBoxLayout(self)
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.text_browser)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def load_help_content(self, path: str):
        """Load markdown or plain text from `path` into the text browser."""
        if not os.path.isfile(path):
            self.text_browser.setPlainText(f"Help file not found: {path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # QTextBrowser can render basic Markdown via setMarkdown
            try:
                self.text_browser.setMarkdown(content)
            except Exception:
                # Fallback to plain text
                self.text_browser.setPlainText(content)
        except Exception as exc:
            self.text_browser.setPlainText(f"Failed to load help file: {exc}")
