# component_placer/quick_creation_controller.py
from PyQt5.QtCore import QObject, QEvent, Qt
from PyQt5.QtWidgets import QMenu
from component_placer.component_input_dialog import ComponentInputDialog
from logs.log_handler import LogHandler

log = LogHandler()


class QuickCreationController(QObject):
    """
    Two-anchor Quick Creation workflow.

    Anchors A/B define a rectangle; dialog parameters define a pad grid.
    Arrow keys nudge anchors (Δx auto-flipped on bottom side).
    """

    def __init__(
        self,
        board_view,
        input_handler,
        component_placer,
        marker_manager,
        coord_converter,
    ):
        super().__init__(board_view)

        # --- core references ------------------------------------------------
        self.log = LogHandler()
        self.board_view = board_view
        self.flags = board_view.flags  # FlagManager
        self.input_handler = input_handler
        self.placer = component_placer
        self.marker_manager = marker_manager
        self.coord_converter = coord_converter
        self.constants = getattr(board_view, "constants", None)

        # --- state ----------------------------------------------------------
        self.active = False
        self.state = 0  # 0=idle, 1=A, 2=B, 3=drag
        self.anchors = {"A": None, "B": None}
        self.selected_anchor = None
        self.quick_anchors = self.anchors  # alias used by ComponentPlacer
        self.last_params = None

        # --- connect signals -----------------------------------------------
        self.input_handler.mouse_clicked.connect(self._on_click)

        # install event-filter AFTER anchors are defined
        self.board_view.installEventFilter(self)

        # arrow keys (nudge step from constants)
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

        # track anchor selection
        scene = (
            board_view.scene()
            if callable(getattr(board_view, "scene", None))
            else getattr(board_view, "scene", None)
        )
        if scene:
            scene.selectionChanged.connect(self._on_anchor_selection_changed)

    # ───────────────────────────────────────────────────────── helpers ─────
    def _flip_dx(self, dx: float) -> float:
        """Invert horizontal Δ on bottom side."""
        return -dx if self.flags.get_flag("side", "top").lower() == "bottom" else dx

    def _current_params(self):
        return getattr(self.placer, "quick_params", {}) or {}

    def _get_step(self) -> float:
        if self.constants:
            try:
                return float(self.constants.get("anchor_nudge_step_mm", 0.2))
            except Exception:
                return 0.2
        return 0.2

    # ───────────────────────────────────────── selection bookkeeping ──────
    def _on_anchor_selection_changed(self):
        for aid, item in self.marker_manager.anchor_items.items():
            if item.isSelected():
                self.selected_anchor = aid
                return
        self.selected_anchor = None

    # ───────────────────────────────────────── mode control ───────────────
    def activate(self):
        self.active = True
        self.state = 0
        self.anchors = {"A": None, "B": None}
        self.quick_anchors = self.anchors
        self.selected_anchor = None
        self.board_view.setCursor(Qt.CrossCursor)

    def deactivate(self):
        self._cleanup()
        self.active = False
        self.board_view.unsetCursor()

    # ───────────────────────────────────────── mouse clicks ───────────────
    def _on_click(self, x_scene: float, y_scene: float, button: str):
        if not self.active or button != "left":
            return

        x_mm, y_mm = self.coord_converter.pixels_to_mm(x_scene, y_scene)

        # --- first anchor ---------------------------------------------------
        if self.state == 0:
            self.anchors["A"] = (x_mm, y_mm)
            self.quick_anchors = self.anchors
            self.marker_manager.place_anchor("A", x_mm, y_mm)
            self.state = 1
            return

        # --- second anchor --------------------------------------------------
        if self.state == 1:
            self.anchors["B"] = (x_mm, y_mm)
            self.quick_anchors = self.anchors
            self.marker_manager.place_anchor("B", x_mm, y_mm)
            self.state = 2
            self._refresh_ghost()
            self._open_dialog()
            return

        # --- relocate anchor in drag mode ----------------------------------
        if self.state == 3 and self.selected_anchor:
            self._nudge_selected(
                x_mm - self.anchors[self.selected_anchor][0],
                y_mm - self.anchors[self.selected_anchor][1],
            )
            self.state = 2
            self.selected_anchor = None

    # ───────────────────────────────────────── eventFilter ────────────────
    def eventFilter(self, obj, event):
        if not self.active:
            return super().eventFilter(obj, event)

        # context menu on anchor
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            pos = event.pos()
            pt = self.board_view.mapToScene(pos)
            for aid in ("A", "B"):
                if self._hit_test(aid, pt.x(), pt.y()):
                    menu = QMenu(self.board_view)
                    if menu.exec_(self.board_view.mapToGlobal(pos)):
                        self.state = 3
                        self.selected_anchor = aid
                    return True

        # ESC / ENTER / direct-arrow fallback
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                self.deactivate()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter) and self.state == 2:
                self._open_dialog()
                return True
            if self.state in (2, 3) and self.selected_anchor:
                step = self._get_step()
                dx = -step if key == Qt.Key_Left else step if key == Qt.Key_Right else 0
                dy = step if key == Qt.Key_Up else -step if key == Qt.Key_Down else 0
                if dx or dy:
                    self._nudge_selected(self._flip_dx(dx), dy)
                    return True

        return super().eventFilter(obj, event)

    # ─────────────────────────── ghost refresh ────────────────────────────
    def _refresh_ghost(self):
        """Rebuild preview and push anchors into the placer."""
        log.debug(
            f"[QC] _refresh_ghost -> anchors={self.anchors} "
            f"params={self._current_params()}",
            module="QuickCreate",
            func="_refresh_ghost",
        )

        if None in self.anchors.values():
            return
        # store live data in the placer
        self.placer.quick_anchors = self.anchors
        self.placer.update_quick_footprint(self.anchors, self._current_params())

    # ───────────────────────────────────────── nudging --------------------
    def _nudge_selected(self, dx_mm: float, dy_mm: float):
        if not self.active or self.selected_anchor is None:
            return

        aid = self.selected_anchor
        x0, y0 = self.anchors[aid]
        x1, y1 = x0 + dx_mm, y0 + dy_mm
        self.anchors[aid] = (x1, y1)
        self.quick_anchors = self.anchors

        self.marker_manager.move_anchor(aid, x1, y1)
        self._refresh_ghost()

    # ───────────────────────────────────────── dialog ---------------------
    def _open_dialog(self):
        dlg = ComponentInputDialog(parent=self.board_view.window(), quick=True)
        dlg.setWindowModality(Qt.NonModal)
        if self.last_params:
            prm = dict(self.last_params)
            prm["test_side"] = self.flags.get_flag("side", "top")
            dlg.set_quick_params(prm)
        else:
            dlg.side_combo.setCurrentText(
                self.flags.get_flag("side", "top").capitalize()
            )
        dlg.quick_params_changed.connect(self._live_params)
        dlg.component_data_ready.connect(self._final_params)
        dlg.rejected.connect(self.deactivate)
        dlg.show()
        self.dialog = dlg
        # Immediately refresh ghost using current dialog parameters
        self._live_params(dlg.get_quick_params())

    # ─────────────── dialog slots ───────────────────────────────────
    def _live_params(self, prm: dict):
        """
        Emitted on every widget change inside ComponentInputDialog.
        Besides keeping a local copy, push the params into the
        ComponentPlacer so _current_params() returns something useful.
        """
        self.params = prm
        self.placer.quick_params = prm  # <-- NEW – keep in sync
        self.last_params = prm
        self._refresh_ghost()  # rebuild ghost immediately

    def _final_params(self, _classic_data: dict):
        """
        Dialog OK pressed.
        Ignore classic data – pull the full quick-params directly so the grid
        dimensions & pad sizes are preserved.
        """
        qp = self.dialog.get_quick_params()  # full set
        log.debug(
            f"[QC] final_params -> {qp}", module="QuickCreate", func="_final_params"
        )

        self.placer.quick_params = qp
        self.last_params = qp
        self.placer.quick_anchors = self.anchors
        self.placer.update_quick_footprint(self.anchors, qp)
        self.placer.place_quick()

        self.deactivate()

    # ───────────────────────────────────────── helpers -------------------
    def _cleanup(self):
        self.placer.cancel_quick()
        self.marker_manager.clear_quick_anchors()
        self.state = 0
        self.anchors = {"A": None, "B": None}
        self.quick_anchors = self.anchors
        self.selected_anchor = None

    def _hit_test(self, aid: str, x_scene: float, y_scene: float) -> bool:
        ax_mm, ay_mm = self.anchors.get(aid) or (None, None)
        if ax_mm is None:
            return False
        a_px, a_py = self.coord_converter.mm_to_pixels(ax_mm, ay_mm)
        c_px, c_py = self.coord_converter.mm_to_pixels(x_scene, y_scene)
        return abs(c_px - a_px) < 5 and abs(c_py - a_py) < 5
