from PyQt5.QtCore import QObject, QEvent, Qt
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtWidgets import QGraphicsLineItem


class MeasureTool(QObject):
    """Simple two-anchor measurement tool.

    When activated the user can place two anchors that define a right
    triangle.  The tool draws three coloured lines (red = ΔX, blue = ΔY,
    green = direct distance) and writes the measured distances to the
    pad_info_label.  ESC exits the mode.
    """

    def __init__(
        self,
        board_view,
        input_handler,
        marker_manager,
        coord_converter,
        pad_info_label,
        properties_dock=None,
    ):
        super().__init__(board_view)
        self.board_view = board_view
        self.flags = board_view.flags
        self.input_handler = input_handler
        self.marker_manager = marker_manager
        self.converter = coord_converter
        self.pad_info_label = pad_info_label
        self.properties_dock = properties_dock

        self.active = False
        self.state = 0  # 0=idle, 1=have A, 2=have A+B
        self.anchors = {"A": None, "B": None}
        self.lines = []
        self._prev_label_html = ""

        self.input_handler.mouse_clicked.connect(self._on_click)
        self.board_view.installEventFilter(self)

        # arrow key nudging similar to QuickCreation
        self.input_handler.arrow_left.connect(
            lambda: self._nudge_selected(self._flip_dx(-self._get_step()), 0.0)
        )
        self.input_handler.arrow_right.connect(
            lambda: self._nudge_selected(self._flip_dx(self._get_step()), 0.0)
        )
        self.input_handler.arrow_up.connect(
            lambda: self._nudge_selected(0.0, self._get_step())
        )
        self.input_handler.arrow_down.connect(
            lambda: self._nudge_selected(0.0, -self._get_step())
        )

    # ------------------------------------------------------------------
    def _flip_dx(self, dx: float) -> float:
        return -dx if self.flags.get_flag("side", "top").lower() == "bottom" else dx

    def _get_step(self) -> float:
        try:
            return float(
                getattr(self.board_view, "constants", None).get(
                    "anchor_nudge_step_mm", 0.2
                )
            )
        except Exception:
            return 0.2

    # ------------------------------------------------------------------
    def activate(self):
        if self.active:
            return
        if self.properties_dock is not None:
            self._prev_label_html = self.properties_dock.selected_pins_info_tab.toHtml()
        else:
            self._prev_label_html = self.pad_info_label.text()
        self.active = True
        self.state = 0
        self.anchors = {"A": None, "B": None}
        self.marker_manager.clear_quick_anchors()
        self._clear_lines()
        self.board_view.setCursor(Qt.CrossCursor)
        self._update_labels(self.tr("Measurement: place first anchor"))

    def deactivate(self):
        if not self.active:
            return
        self.active = False
        self.marker_manager.clear_quick_anchors()
        self._clear_lines()
        self.board_view.unsetCursor()
        if self._prev_label_html:
            self._update_labels(self._prev_label_html)
        else:
            self._update_labels(self.tr("No pad selected"))
        self._prev_label_html = ""

    # ------------------------------------------------------------------
    def _clear_lines(self):
        scene = self.board_view.scene
        for ln in self.lines:
            scene.removeItem(ln)
        self.lines = []

    def _update_labels(self, html: str):
        """Update both status bar and properties dock displays."""
        self.pad_info_label.setText(html)
        if self.properties_dock is not None:
            self.properties_dock.update_selected_pins_info(html)

    # ------------------------------------------------------------------
    def _on_click(self, x_scene: float, y_scene: float, button: str):
        if not self.active or button != "left":
            return
        x_mm, y_mm = self.converter.pixels_to_mm(x_scene, y_scene)

        if self.state == 0:
            self.anchors["A"] = (x_mm, y_mm)
            self.marker_manager.place_anchor("A", x_mm, y_mm)
            self.state = 1
            self._update_labels(self.tr("Measurement: place second anchor"))
            return

        if self.state == 1:
            self.anchors["B"] = (x_mm, y_mm)
            self.marker_manager.place_anchor("B", x_mm, y_mm)
            self.state = 2
            self._draw_lines()
            return

        # start a new measurement on subsequent clicks
        self.marker_manager.clear_quick_anchors()
        self._clear_lines()
        self.anchors = {"A": (x_mm, y_mm), "B": None}
        self.marker_manager.place_anchor("A", x_mm, y_mm)
        self.state = 1
        self._update_labels(self.tr("Measurement: place second anchor"))

    # ------------------------------------------------------------------
    def _draw_lines(self):
        self._clear_lines()
        A = self.anchors["A"]
        B = self.anchors["B"]
        if None in (A, B):
            return

        ax, ay = self.converter.mm_to_pixels(*A)
        bx, by = self.converter.mm_to_pixels(*B)

        pen_r = QPen(QColor("red"))
        pen_b = QPen(QColor("blue"))
        pen_g = QPen(QColor("green"))
        for pen in (pen_r, pen_b, pen_g):
            pen.setWidth(2)
            pen.setCosmetic(True)

        line_r = QGraphicsLineItem(ax, ay, bx, ay)
        line_r.setPen(pen_r)
        line_b = QGraphicsLineItem(bx, ay, bx, by)
        line_b.setPen(pen_b)
        line_g = QGraphicsLineItem(ax, ay, bx, by)
        line_g.setPen(pen_g)

        z = getattr(self.marker_manager, "z_value_marker", 2)
        for ln in (line_r, line_b, line_g):
            ln.setZValue(z)
            self.board_view.scene.addItem(ln)

        self.lines = [line_r, line_b, line_g]

        dx = abs(B[0] - A[0])
        dy = abs(B[1] - A[1])
        dist = (dx**2 + dy**2) ** 0.5
        constants = getattr(self.board_view, "constants", None)
        fs = constants.get("pins_font_size", 14) if constants else 14
        html = (
            f"<span style='color:red; font-size:{fs}px'>ΔX: {dx:.2f} mm</span>&nbsp;&nbsp;"
            f"<span style='color:blue; font-size:{fs}px'>ΔY: {dy:.2f} mm</span>&nbsp;&nbsp;"
            f"<span style='color:green; font-size:{fs}px'>Dist: {dist:.2f} mm</span>"
        )
        self._update_labels(html)

    # ------------------------------------------------------------------
    def _nudge_selected(self, dx_mm: float, dy_mm: float):
        if not self.active or self.state == 0:
            return
        selected_id = None
        for aid, item in self.marker_manager.anchor_items.items():
            if item.isSelected():
                selected_id = aid
                break
        if not selected_id:
            return
        x, y = self.anchors[selected_id]
        newx, newy = x + dx_mm, y + dy_mm
        self.anchors[selected_id] = (newx, newy)
        self.marker_manager.move_anchor(selected_id, newx, newy)
        if self.state == 2:
            self._draw_lines()

    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if not self.active:
            return super().eventFilter(obj, event)
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.deactivate()
            return True
        return super().eventFilter(obj, event)
