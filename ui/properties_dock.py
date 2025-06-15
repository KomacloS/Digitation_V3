# ui/properties_dock.py

from PyQt5.QtWidgets import QDockWidget, QTabWidget, QWidget, QVBoxLayout, QTextBrowser
from PyQt5.QtCore import Qt, QEvent, QTimer

class PropertiesDock(QDockWidget):
    """
    A custom QDockWidget that:
      - Contains a QTabWidget with a 'Selected Pins' tab.
      - DEBOUNCES saving of its height (writes to constants after user stops resizing).
      - Does NOT forcibly set its own height (that is handled in MainWindow.showEvent via resizeDocks).
    """
    def __init__(self, constants, log, parent=None):
        super().__init__("Properties", parent)
        self.constants = constants
        self.log = log

        # Debounce timer for saving user-resized height
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(500)  # 500 ms
        self.debounce_timer.timeout.connect(self._save_height_debounced)

        self._init_ui()

        # Optional: Let the dock be placed on top or bottom
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

    def _init_ui(self):
        """ Create the QTabWidget, plus a text browser for 'Selected Pins'. """
        self.properties_tabs = QTabWidget()
        self.setWidget(self.properties_tabs)

        self.selected_pins_tab = QWidget()
        layout = QVBoxLayout(self.selected_pins_tab)

        self.selected_pins_info_tab = QTextBrowser()
        self.selected_pins_info_tab.setMinimumHeight(20)
        # remove maxHeight if you want truly free resizing
        self.selected_pins_info_tab.setMaximumHeight(999999)
        layout.addWidget(self.selected_pins_info_tab)

        self.properties_tabs.addTab(self.selected_pins_tab, "Selected Pins")

    def resizeEvent(self, event):
        """
        Called whenever the user (or layout) changes the dock's size.
        We'll capture the new height but won't write to constants until 500ms passes.
        """
        super().resizeEvent(event)

        new_height = self.height()
        if new_height > 0:
            self.debounce_timer.stop()
            self._pending_height = new_height
            self.debounce_timer.start()

    def _save_height_debounced(self):
        """
        Actually writes the stored height to constants.
        Called ~500ms after user stops dragging the dock's splitter or floating resize.
        """
        final_height = getattr(self, '_pending_height', None)
        if final_height is not None and final_height > 0:
            self.constants.set("properties_dock_height", final_height)
            self.constants.save()
            self.log.debug(f"PropertiesDock => Debounced height saved => {final_height}")

    def update_selected_pins_info(self, html_content: str):
        """
        Called by MainWindow to show 'Selected Pins' info as HTML.
        """
        self.selected_pins_info_tab.setHtml(html_content)
