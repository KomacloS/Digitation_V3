# ui/layers_tab.py

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
)
from PyQt5.QtCore import Qt


# Conversion factor for mm to mils (if you want to allow unit conversion later)
MM_TO_MILS = 39.37


class LayersTab(QWidget):
    """
    A tab to control the layers shown in the board view:
      - Toggle the PCB image (JPG) layer and the pads layer.
      - Filter the pads by various criteria. Only pads matching the filter remain visible.
    """

    def __init__(self, board_view, parent=None):
        """
        :param board_view: An instance of BoardView; used to access the image and DisplayLibrary.
        """
        super().__init__(parent)
        self.board_view = board_view
        self.display_library = board_view.display_library
        self.log = board_view.log  # reuse the log handler
        self.constants = board_view.constants

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        # ---- Layer Visibility Group ----
        visibility_group = QGroupBox("Layer Visibility")
        vis_layout = QHBoxLayout()
        visibility_group.setLayout(vis_layout)

        self.chk_show_image = QCheckBox("Show PCB Image")
        self.chk_show_image.setChecked(True)
        self.chk_show_image.stateChanged.connect(self.toggle_image_visibility)

        self.chk_show_pads = QCheckBox("Show Pads")
        self.chk_show_pads.setChecked(True)
        self.chk_show_pads.stateChanged.connect(self.toggle_pads_visibility)

        vis_layout.addWidget(self.chk_show_image)
        vis_layout.addWidget(self.chk_show_pads)
        layout.addWidget(visibility_group)

        # ---- Pad Filter Group ----
        filter_group = QGroupBox("Pad Filter")
        filter_layout = QFormLayout()
        filter_group.setLayout(filter_layout)

        # Create filter controls – using similar controls as in your PadEditor filter:
        self.pin_filter = QLineEdit()
        self.channel_filter = QLineEdit()
        self.signal_filter = QLineEdit()
        self.component_filter = QLineEdit()

        self.testpos_filter = QComboBox()
        self.testpos_filter.addItems(["", "Top", "Bottom", "Both"])

        self.tech_filter = QComboBox()
        self.tech_filter.addItems(["", "SMD", "Through Hole", "Mechanical"])

        self.shape_filter = QComboBox()
        self.shape_filter.addItems(
            [
                "",
                "Round",
                "Square/rectangle",
                "Square/rectangle with Hole",
                "Ellipse",
                "Hole",
            ]
        )

        self.width_filter = QLineEdit()
        self.height_filter = QLineEdit()
        self.hole_filter = QLineEdit()

        filter_layout.addRow("Pin:", self.pin_filter)
        filter_layout.addRow("Channel:", self.channel_filter)
        filter_layout.addRow("Signal:", self.signal_filter)
        filter_layout.addRow("Component:", self.component_filter)
        filter_layout.addRow("Test Pos:", self.testpos_filter)
        filter_layout.addRow("Tech:", self.tech_filter)
        filter_layout.addRow("Shape:", self.shape_filter)
        filter_layout.addRow("Width:", self.width_filter)
        filter_layout.addRow("Height:", self.height_filter)
        filter_layout.addRow("Hole:", self.hole_filter)

        # Add filter buttons in a horizontal layout.
        btn_layout = QHBoxLayout()
        self.btn_apply_filter = QPushButton("Apply Filter")
        self.btn_reset_filter = QPushButton("Reset Filter")
        self.btn_apply_filter.clicked.connect(self.apply_filter)
        self.btn_reset_filter.clicked.connect(self.reset_filter)
        btn_layout.addWidget(self.btn_apply_filter)
        btn_layout.addWidget(self.btn_reset_filter)
        filter_layout.addRow(btn_layout)

        layout.addWidget(filter_group)
        layout.addStretch()

    # ----- Layer Visibility Methods -----

    def toggle_image_visibility(self, state):
        """
        When the 'Show PCB Image' checkbox is toggled:
        - If checked (visible=True), ensure that only the current side's image is visible.
        - If unchecked (visible=False), hide both top and bottom images and add a contour.
        This function does not switch sides.
        """
        visible = state == Qt.Checked
        # Update the flag on the board view.
        self.board_view.image_hidden_by_filter = not visible

        # Log the intended state along with the current side.
        current_side = self.board_view.flags.get_flag("side", "top")
        self.log.log(
            "debug",
            f"toggle_image_visibility: state={state} (visible={visible}), current_side={current_side}",
        )

        if visible:
            # Ensure that only the current side's image is visible.
            if current_side == "top":
                if self.board_view.top_pixmap_item:
                    self.log.log(
                        "debug", "toggle_image_visibility: Showing top_pixmap_item."
                    )
                    self.board_view.top_pixmap_item.setVisible(True)
                if self.board_view.bottom_pixmap_item:
                    self.log.log(
                        "debug", "toggle_image_visibility: Hiding bottom_pixmap_item."
                    )
                    self.board_view.bottom_pixmap_item.setVisible(False)
            else:  # current_side == "bottom"
                if self.board_view.bottom_pixmap_item:
                    self.log.log(
                        "debug", "toggle_image_visibility: Showing bottom_pixmap_item."
                    )
                    self.board_view.bottom_pixmap_item.setVisible(True)
                if self.board_view.top_pixmap_item:
                    self.log.log(
                        "debug", "toggle_image_visibility: Hiding top_pixmap_item."
                    )
                    self.board_view.top_pixmap_item.setVisible(False)
            # Remove any existing board contour.
            if (
                hasattr(self.board_view, "board_contour_item")
                and self.board_view.board_contour_item
            ):
                self.log.log(
                    "debug", "toggle_image_visibility: Removing existing board contour."
                )
                self.board_view.scene.removeItem(self.board_view.board_contour_item)
                self.board_view.board_contour_item = None
            self.log.log("debug", "PCB Image set to visible.")
        else:
            # Force both images to be hidden.
            if self.board_view.top_pixmap_item:
                self.log.log(
                    "debug", "toggle_image_visibility: Hiding top_pixmap_item."
                )
                self.board_view.top_pixmap_item.setVisible(False)
            if self.board_view.bottom_pixmap_item:
                self.log.log(
                    "debug", "toggle_image_visibility: Hiding bottom_pixmap_item."
                )
                self.board_view.bottom_pixmap_item.setVisible(False)
            # Add a board contour if not already present.
            if (
                not hasattr(self.board_view, "board_contour_item")
                or self.board_view.board_contour_item is None
            ):
                self.log.log("debug", "toggle_image_visibility: Adding board contour.")
                self.board_view.add_board_contour()
            else:
                self.log.log(
                    "debug", "toggle_image_visibility: Board contour already exists."
                )
            self.log.log("debug", "PCB Image set to hidden; board contour displayed.")

    def toggle_pads_visibility(self, state):
        visible = state == Qt.Checked
        # Iterate over all pad items stored in DisplayLibrary.
        for item in self.display_library.displayed_objects.values():
            # Check that the item is a pad item (it is created as a SelectablePadItem).
            try:
                # Optionally, you could check with isinstance(item, SelectablePadItem)
                item.setVisible(visible)
            except Exception as e:
                self.log.log("error", f"Error toggling pad visibility: {e}")
        self.log.log("debug", f"Pads visibility set to {visible}.")

    # ----- Pad Filter Methods -----

    def apply_filter(self):
        """
        Iterate over all pads in the object library and update each pad's 'visible'
        attribute based on the filter criteria. Then, re-render the display so that only
        pads with visible == True are shown.
        """
        # Read filter criteria from UI.
        pin_txt = self.pin_filter.text().strip().lower()
        channel_txt = self.channel_filter.text().strip().lower()
        signal_txt = self.signal_filter.text().strip().lower()
        component_txt = self.component_filter.text().strip().lower()
        testpos_val = self.testpos_filter.currentText().strip().lower()
        tech_val = self.tech_filter.currentText().strip().lower()
        shape_val = self.shape_filter.currentText().strip().lower()
        width_txt = self.width_filter.text().strip()
        height_txt = self.height_filter.text().strip()
        hole_txt = self.hole_filter.text().strip()

        def matches_filter(pad_obj):
            # Assume pad_obj is a BoardObject.
            if pin_txt and pin_txt not in str(pad_obj.pin).lower():
                return False
            if channel_txt and channel_txt not in str(pad_obj.channel):
                return False
            if signal_txt and signal_txt not in pad_obj.signal.lower():
                return False
            if component_txt and component_txt not in pad_obj.component_name.lower():
                return False
            if testpos_val and testpos_val not in pad_obj.test_position.lower():
                return False
            if tech_val and tech_val not in pad_obj.technology.lower():
                return False
            if shape_val and shape_val not in pad_obj.shape_type.lower():
                return False
            # For numeric filters, we compare if the pad’s dimension is at least the entered value.
            if width_txt:
                try:
                    if pad_obj.width_mm < float(width_txt):
                        return False
                except ValueError:
                    pass
            if height_txt:
                try:
                    if pad_obj.height_mm < float(height_txt):
                        return False
                except ValueError:
                    pass
            if hole_txt:
                try:
                    if pad_obj.hole_mm < float(hole_txt):
                        return False
                except ValueError:
                    pass
            return True

        count_total = 0
        count_matched = 0

        # Iterate over all pads using the object library from the BoardView.
        for pad_obj in self.board_view.object_library.get_all_objects():
            count_total += 1
            if matches_filter(pad_obj):
                pad_obj.visible = True
                count_matched += 1
            else:
                pad_obj.visible = False

        self.log.log(
            "debug",
            f"Filter applied: {count_matched} out of {count_total} pads are visible.",
        )

        # Clear and re-render the display so that only pads with visible == True are drawn.
        self.board_view.display_library.clear_all_rendered_objects()
        self.board_view.display_library.render_initial_objects()

    def reset_filter(self):
        """
        Clears all filter UI fields and sets all pads to be visible.
        Then re-renders the display so that all pads are shown.
        """
        # Clear filter input boxes.
        self.pin_filter.clear()
        self.channel_filter.clear()
        self.signal_filter.clear()
        self.component_filter.clear()
        self.testpos_filter.setCurrentIndex(0)
        self.tech_filter.setCurrentIndex(0)
        self.shape_filter.setCurrentIndex(0)
        self.width_filter.clear()
        self.height_filter.clear()
        self.hole_filter.clear()

        # Mark all pads as visible using the object library from BoardView.
        for pad_obj in self.board_view.object_library.get_all_objects():
            pad_obj.visible = True

        self.log.log("debug", "Filter reset: all pads are now visible.")

        # Clear and re-render the display so that all pads are drawn.
        self.board_view.display_library.clear_all_rendered_objects()
        self.board_view.display_library.render_initial_objects()

    def reapply_filter(self):
        """
        If any filter field is nonempty, reapply the filter.
        This should be called after the board's side has been switched
        and the pad items have been re-rendered.
        """
        # Check if any filter field is set (you might check a few key fields).
        if (
            self.pin_filter.text().strip()
            or self.channel_filter.text().strip()
            or self.signal_filter.text().strip()
            or self.component_filter.text().strip()
            or self.testpos_filter.currentText().strip()
            or self.tech_filter.currentText().strip()
            or self.shape_filter.currentText().strip()
            or self.width_filter.text().strip()
            or self.height_filter.text().strip()
            or self.hole_filter.text().strip()
        ):
            self.apply_filter()  # Reapply the filter if any field is not empty.
