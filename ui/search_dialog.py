# ui/search_dialog.py

from typing import Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QCompleter, QStyle
)
from PyQt5.QtCore import Qt, QTimer, QStringListModel
from objects.search_library import SearchLibrary
from objects.board_object import BoardObject
from ui.selected_pins_info import generate_selected_pins_html, update_properties_tab

class SearchDialog(QDialog):
    last_searched_pad: Optional[BoardObject] = None
    """
    Dialog window for searching specific pads on the PCB.
    Each field (Component, Pin, Signal, and Channel) is a QLineEdit with a QCompleter.
    The field that the user last edits (“driver”) is used to update the other fields.
    If a field’s text is not found in its valid list, an error icon (red cross) and a red border appear.
    For the Pin field the valid list comes only from the pins associated with the currently selected component.
    """
    def __init__(self, board_view, selected_pins_widget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search Pad")
        self.board_view = board_view
        self.selected_pins_widget = selected_pins_widget  # Widget for the "Selected Pins" tab

        # Use the shared object_library from board_view.
        self.search_library = SearchLibrary(object_library=self.board_view.object_library)
        self.selected_pad: Optional[BoardObject] = None
        self.last_changed_field = None

        self.init_ui()
        self.populate_fields()  # Populate completer models with full available lists
        self.setup_connections()

        # Restore last search (if available and valid)
        self.restore_last_search()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        error_icon = self.style().standardIcon(QStyle.SP_MessageBoxCritical)

        # --- Component Input ---
        comp_layout = QHBoxLayout()
        comp_label = QLabel("Component:")
        self.component_line_edit = QLineEdit()
        self.component_line_edit.setPlaceholderText("Enter component")
        self.comp_model = QStringListModel([])
        self.comp_completer = QCompleter(self.comp_model, self)
        self.comp_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.component_line_edit.setCompleter(self.comp_completer)
        self.comp_error_action = self.component_line_edit.addAction(error_icon, QLineEdit.TrailingPosition)
        self.comp_error_action.setVisible(False)
        comp_layout.addWidget(comp_label)
        comp_layout.addWidget(self.component_line_edit)
        layout.addLayout(comp_layout)

        # --- Pin Input ---
        pin_layout = QHBoxLayout()
        pin_label = QLabel("Pin:")
        self.pin_line_edit = QLineEdit()
        self.pin_line_edit.setPlaceholderText("Select pin from component")
        self.pin_line_edit.setEnabled(False)
        self.pin_model = QStringListModel([])
        self.pin_completer = QCompleter(self.pin_model, self)
        self.pin_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.pin_line_edit.setCompleter(self.pin_completer)
        self.pin_error_action = self.pin_line_edit.addAction(error_icon, QLineEdit.TrailingPosition)
        self.pin_error_action.setVisible(False)
        pin_layout.addWidget(pin_label)
        pin_layout.addWidget(self.pin_line_edit)
        layout.addLayout(pin_layout)

        # --- Signal Input ---
        signal_layout = QHBoxLayout()
        signal_label = QLabel("Signal:")
        self.signal_line_edit = QLineEdit()
        self.signal_line_edit.setPlaceholderText("Enter signal")
        self.signal_model = QStringListModel([])
        self.signal_completer = QCompleter(self.signal_model, self)
        self.signal_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.signal_line_edit.setCompleter(self.signal_completer)
        self.signal_error_action = self.signal_line_edit.addAction(error_icon, QLineEdit.TrailingPosition)
        self.signal_error_action.setVisible(False)
        signal_layout.addWidget(signal_label)
        signal_layout.addWidget(self.signal_line_edit)
        layout.addLayout(signal_layout)

        # --- Channel Input ---
        channel_layout = QHBoxLayout()
        channel_label = QLabel("Channel:")
        self.channel_line_edit = QLineEdit()
        self.channel_line_edit.setPlaceholderText("Enter channel")
        self.channel_model = QStringListModel([])
        self.channel_completer = QCompleter(self.channel_model, self)
        self.channel_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.channel_line_edit.setCompleter(self.channel_completer)
        self.channel_error_action = self.channel_line_edit.addAction(error_icon, QLineEdit.TrailingPosition)
        self.channel_error_action.setVisible(False)
        channel_layout.addWidget(channel_label)
        channel_layout.addWidget(self.channel_line_edit)
        layout.addLayout(channel_layout)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_button)
        btn_layout.addWidget(self.cancel_button)
        layout.addLayout(btn_layout)

        self.setFixedSize(400, 300)

    def populate_fields(self):
        all_components = set()
        all_pins = set()
        all_signals = set()
        all_channels = set()

        for pad in self.search_library.object_library.get_all_objects():
            all_components.add(pad.component_name)
            all_pins.add(str(pad.pin))
            if pad.signal:
                all_signals.add(pad.signal)
            if pad.channel is not None:
                all_channels.add(str(pad.channel))

        comp_list = sorted(all_components)
        pin_list = sorted(all_pins, key=lambda x: int(x) if x.isdigit() else x)
        signal_list = sorted(all_signals)
        channel_list = sorted(all_channels, key=lambda x: int(x) if x.isdigit() else x)

        self.comp_model.setStringList(comp_list)
        self.pin_model.setStringList(pin_list)
        self.signal_model.setStringList(signal_list)
        self.channel_model.setStringList(channel_list)

    def setup_connections(self):
        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(300)
        self.update_timer.timeout.connect(self.do_live_update)

        self.component_line_edit.textChanged.connect(lambda text: (
            self.set_last_changed("component"),
            self.validate_field("component", text)
        ))
        self.component_line_edit.textChanged.connect(self.update_pin_list)

        self.pin_line_edit.textChanged.connect(lambda text: (
            self.set_last_changed("pin"),
            self.validate_field("pin", text)
        ))
        self.signal_line_edit.textChanged.connect(lambda text: (
            self.set_last_changed("signal"),
            self.validate_field("signal", text)
        ))
        self.channel_line_edit.textChanged.connect(lambda text: (
            self.set_last_changed("channel"),
            self.validate_field("channel", text)
        ))

        self.ok_button.clicked.connect(self.on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def update_pin_list(self, component_text: str):
        comp = component_text.strip()
        if comp:
            pin_list = self.search_library.get_pins(comp)
            self.pin_line_edit.setEnabled(bool(pin_list))
        else:
            pin_list = []
            self.pin_line_edit.setEnabled(False)
        self.pin_model.setStringList(pin_list)

    def set_last_changed(self, field: str):
        self.last_changed_field = field
        # Logging removed here.
        self.update_timer.start()

    def validate_field(self, field: str, text: str) -> bool:
        text = text.strip()
        valid = False
        if field == "component":
            valid_list = self.comp_model.stringList()
            valid = any(item.lower() == text.lower() for item in valid_list)
            self.comp_error_action.setVisible(not valid)
            self.component_line_edit.setStyleSheet("" if valid else "border: 1px solid red;")
        elif field == "pin":
            current_comp = self.component_line_edit.text().strip()
            valid_list = self.search_library.get_pins(current_comp) if current_comp else []
            valid = text in valid_list
            self.pin_error_action.setVisible(not valid)
            self.pin_line_edit.setStyleSheet("" if valid else "border: 1px solid red;")
        elif field == "signal":
            valid_list = self.signal_model.stringList()
            valid = text in valid_list
            self.signal_error_action.setVisible(not valid)
            self.signal_line_edit.setStyleSheet("" if valid else "border: 1px solid red;")
        elif field == "channel":
            valid_list = self.channel_model.stringList()
            valid = text in valid_list
            self.channel_error_action.setVisible(not valid)
            self.channel_line_edit.setStyleSheet("" if valid else "border: 1px solid red;")
        return valid

    def do_live_update(self):
        comp_text = self.component_line_edit.text().strip()
        pin_text = self.pin_line_edit.text().strip()
        signal_text = self.signal_line_edit.text().strip()
        channel_text = self.channel_line_edit.text().strip()

        # Determine the driver field.
        if self.component_line_edit.hasFocus():
            driver = "component"
        elif self.pin_line_edit.hasFocus():
            driver = "pin"
        elif self.signal_line_edit.hasFocus():
            driver = "signal"
        elif self.channel_line_edit.hasFocus():
            driver = "channel"
        else:
            driver = self.last_changed_field or "component"

        # Query candidate pads based on the driver field.
        if driver == "component":
            candidates = [pad for pad in self.search_library.object_library.get_all_objects()
                          if pad.component_name.lower().startswith(comp_text.lower())]
        elif driver == "pin":
            candidates = [] if not comp_text else [pad for pad in self.search_library.object_library.get_all_objects()
                          if pad.component_name.lower() == comp_text.lower() and str(pad.pin).startswith(pin_text)]
        elif driver == "signal":
            candidates = [pad for pad in self.search_library.object_library.get_all_objects()
                          if pad.signal and pad.signal.lower().startswith(signal_text.lower())]
        elif driver == "channel":
            candidates = [pad for pad in self.search_library.object_library.get_all_objects()
                          if pad.channel is not None and str(pad.channel).startswith(channel_text)]
        else:
            candidates = []

        if candidates:
            match_pad = candidates[0]
            if driver != "component":
                self.component_line_edit.blockSignals(True)
                self.component_line_edit.setText(match_pad.component_name)
                self.component_line_edit.blockSignals(False)
            if driver != "pin":
                self.pin_line_edit.blockSignals(True)
                self.pin_line_edit.setText(str(match_pad.pin))
                self.pin_line_edit.setEnabled(True)
                self.pin_line_edit.blockSignals(False)
            if driver != "signal":
                self.signal_line_edit.blockSignals(True)
                self.signal_line_edit.setText(match_pad.signal if match_pad.signal else "")
                self.signal_line_edit.blockSignals(False)
            if driver != "channel":
                self.channel_line_edit.blockSignals(True)
                self.channel_line_edit.setText(str(match_pad.channel))
                self.channel_line_edit.blockSignals(False)
            self.clear_error_icon(driver)
            self.ok_button.setEnabled(True)
        else:
            self.set_error_icon(driver)
            self.ok_button.setEnabled(False)
        # No logging here.

    def set_error_icon(self, field: str):
        if field == "component":
            self.comp_error_action.setVisible(True)
        elif field == "pin":
            self.pin_error_action.setVisible(True)
        elif field == "signal":
            self.signal_error_action.setVisible(True)
        elif field == "channel":
            self.channel_error_action.setVisible(True)

    def clear_error_icon(self, field: str):
        if field == "component":
            self.comp_error_action.setVisible(False)
        elif field == "pin":
            self.pin_error_action.setVisible(False)
        elif field == "signal":
            self.signal_error_action.setVisible(False)
        elif field == "channel":
            self.channel_error_action.setVisible(False)

    def on_ok_clicked(self):
        comp = self.component_line_edit.text().strip()
        pin_str = self.pin_line_edit.text().strip()
        signal_str = self.signal_line_edit.text().strip()
        channel_str = self.channel_line_edit.text().strip()

        criteria = {}
        if comp:
            criteria['component_name'] = comp
        if pin_str:
            criteria['pin'] = pin_str
        if signal_str:
            criteria['signal'] = signal_str
        if channel_str:
            criteria['channel'] = int(channel_str) if channel_str.isdigit() else channel_str

        matched_pad = None
        for pad in self.search_library.object_library.get_all_objects():
            if 'component_name' in criteria and pad.component_name != criteria['component_name']:
                continue
            if 'pin' in criteria and str(pad.pin) != criteria['pin']:
                continue
            if 'signal' in criteria and (not pad.signal or pad.signal.lower() != criteria['signal'].lower()):
                continue
            if 'channel' in criteria:
                if isinstance(criteria['channel'], int):
                    if pad.channel != criteria['channel']:
                        continue
                else:
                    if pad.channel is None or str(pad.channel) != criteria['channel']:
                        continue
            matched_pad = pad
            break

        if not matched_pad:
            QMessageBox.information(self, "No match", "No matching pad found with those fields.")
            return

        self.selected_pad = matched_pad
        self.place_marker(matched_pad)

        from ui.selected_pins_info import update_properties_tab
        update_properties_tab(
            found_pad=matched_pad,
            pad_info_label=self.selected_pins_widget,
            last_clicked_mm=self.board_view.last_clicked_mm,
            side=self.board_view.flags.get_flag("side", "top"),
            log_handler=self.search_library.log
        )

        # Save this pad as the last searched pad.
        SearchDialog.last_searched_pad = matched_pad

        # Log essential info from on_ok_clicked
        self.search_library.log.log("info", f"Search complete: Pad found (component={matched_pad.component_name}, "
                                              f"pin={matched_pad.pin}, signal={matched_pad.signal}, "
                                              f"channel={matched_pad.channel}).")
        self.accept()

    def place_marker(self, pad: BoardObject):
        side = pad.test_position.lower()
        if side not in ["top", "bottom"]:
            self.search_library.log.log("warning", f"Invalid test_position '{pad.test_position}' for pad: {pad}")
            QMessageBox.warning(self, "Invalid Test Position", f"Pad's test position '{pad.test_position}' is invalid.")
            return
        current_side = self.board_view.flags.get_flag("side", "top")
        if current_side != side:
            self.board_view.switch_side()
        try:
            self.board_view.marker_manager.place_marker(pad.x_coord_mm, pad.y_coord_mm)
        except AttributeError as e:
            self.search_library.log.log("error", f"Failed to place marker: {e}")
            QMessageBox.critical(self, "Error", "Failed to place marker on the board.")
            return
        try:
            x_scene, y_scene = self.board_view.converter.mm_to_pixels(pad.x_coord_mm, pad.y_coord_mm)
            self.board_view.center_on(x_scene, y_scene)
            self.search_library.log.log("debug", f"Centered view on pad at ({x_scene}, {y_scene}) pixels.")
        except Exception as e:
            self.search_library.log.log("error", f"Failed to center on pad: {e}")
            QMessageBox.critical(self, "Error", "Failed to center view on pad.")
        self.search_library.log.log("info", f"Marker placed on {side} side at ({pad.x_coord_mm}, {pad.y_coord_mm}) mm.")

    def restore_last_search(self):
        last_pad = SearchDialog.last_searched_pad
        if last_pad is None:
            return

        self.component_line_edit.blockSignals(True)
        self.pin_line_edit.blockSignals(True)
        self.signal_line_edit.blockSignals(True)
        self.channel_line_edit.blockSignals(True)

        exists = False
        for pad in self.search_library.object_library.get_all_objects():
            if pad.channel == last_pad.channel:
                exists = True
                self.component_line_edit.setText(pad.component_name)
                self.pin_line_edit.setText(str(pad.pin))
                self.pin_line_edit.setEnabled(True)
                self.signal_line_edit.setText(pad.signal if pad.signal else "")
                self.channel_line_edit.setText(str(pad.channel))
                self.ok_button.setEnabled(True)
                break

        if not exists:
            self.component_line_edit.clear()
            self.pin_line_edit.clear()
            self.signal_line_edit.clear()
            self.channel_line_edit.clear()
            self.ok_button.setEnabled(False)

        self.component_line_edit.blockSignals(False)
        self.pin_line_edit.blockSignals(False)
        self.signal_line_edit.blockSignals(False)
        self.channel_line_edit.blockSignals(False)

    # --- Helper reset methods ---
    def reset_pin_signal_channel(self):
        self.pin_line_edit.clear()
        self.signal_line_edit.clear()
        self.channel_line_edit.clear()
        self.ok_button.setEnabled(False)

    def reset_component_signal_channel_based_on_pin(self):
        self.component_line_edit.clear()
        self.signal_line_edit.clear()
        self.channel_line_edit.clear()
        self.ok_button.setEnabled(False)

    def reset_component_pin_based_on_signal(self):
        self.component_line_edit.clear()
        self.pin_line_edit.clear()

    def reset_component_pin_based_on_channel(self):
        self.component_line_edit.clear()
        self.pin_line_edit.clear()

    def reset_signal_channel(self):
        self.signal_line_edit.clear()
        self.channel_line_edit.clear()
        self.ok_button.setEnabled(False)

    def reset_channel(self):
        self.channel_line_edit.clear()
        self.ok_button.setEnabled(False)

    def log_error(self, message: str):
        self.search_library.log.log("error", message)
        QMessageBox.warning(self, "Search Error", message)
