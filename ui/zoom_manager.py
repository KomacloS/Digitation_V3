# zoom_manager.py

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QGraphicsView
from logs.log_handler import LogHandler
from constants.constants import Constants


class ZoomManager(QObject):
    """
    A simpler ZoomManager that performs single-step ("jump") zooms
    around the chosen anchor. Doesn't reset the transform or call fitInView
    after each zoom, so the anchor remains stable.
    """

    scale_factor_changed = pyqtSignal(float)

    def __init__(self, board_view, constants: Constants, log: LogHandler):
        super().__init__()
        self.board_view = board_view
        self.constants = constants
        self.log = log

        # user_scale = how much user has zoomed from the initial fit
        self.user_scale = 1.0
        self.min_user_scale = 1.0
        self.max_user_scale = float(self.constants.get("max_zoom", 10.0))

    def zoom_in(self, factor: float = 1.15):
        self._apply_zoom(factor)

    def zoom_out(self, factor: float = 0.85):
        self._apply_zoom(factor)

    def _apply_zoom(self, factor: float):
        """
        Applies the zoom factor by:
          1. Marking that the user has zoomed (so automatic fit on resize stops)
          2. Recalculating the new scale (clipped to the allowed limits)
          3. Always recalculating the current mouse scene position using QCursor.pos()
             so that the zoom is re-centered on the current cursor position even if the ghost is active.
        """
        self.board_view.user_has_zoomed_yet = True  # Mark that the user has zoomed

        # Determine zoom mode. In your configuration, treat "cursor" and "mouse" the same.
        zoom_mode = self.constants.get("zoom_center_mode", "cursor").lower()
        if zoom_mode in ("cursor", "mouse"):
            self.board_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        elif zoom_mode == "marker":
            self.board_view.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        else:
            self.board_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            zoom_mode = "cursor"

        # Compute the new scale, clipping to min/max limits.
        new_scale = self.user_scale * factor
        if new_scale < self.min_user_scale:
            new_scale = self.min_user_scale
        elif new_scale > self.max_user_scale:
            new_scale = self.max_user_scale
        old_scale = self.user_scale
        actual_factor = new_scale / old_scale
        self.user_scale = new_scale

        # Always recalc the current mouse scene position using QCursor.pos()
        mouse_global = QCursor.pos()
        mouse_scene = self.board_view.mapToScene(
            self.board_view.mapFromGlobal(mouse_global)
        )
        self.log.log(
            "debug",
            f"Zoom mode: CURSOR. Current cursor scene position: ({mouse_scene.x():.2f}, {mouse_scene.y():.2f}).",
        )

        # Apply scaling.
        self.board_view.scale(actual_factor, actual_factor)

        # Re-center the view according to zoom mode.
        if zoom_mode in ("cursor", "mouse"):
            self.board_view.centerOn(mouse_scene)
            self.log.log(
                "debug",
                f"View recentered on cursor scene position: ({mouse_scene.x():.2f}, {mouse_scene.y():.2f}).",
            )
        elif zoom_mode == "marker":
            marker_coords = self.board_view.marker_manager.get_marker_board_coords()
            if marker_coords:
                x_px, y_px = self.board_view.converter.mm_to_pixels(*marker_coords)
                self.board_view.centerOn(x_px, y_px)
                self.log.log(
                    "debug",
                    f"View recentered on marker at scene: ({x_px:.2f}, {y_px:.2f}).",
                )
            else:
                self.log.log(
                    "warning", "Zoom mode 'marker' active but no marker available."
                )

        self.log.log(
            "debug",
            f"Zoom applied: old scale={old_scale:.3f}, new scale={self.user_scale:.3f}, "
            f"factor applied={actual_factor:.3f}, mode={zoom_mode}.",
        )
        self.scale_factor_changed.emit(self.user_scale)

    def update_zoom_limits(self):
        """
        Clamp user_scale if needed.
        """
        if self.user_scale < self.min_user_scale:
            self.user_scale = self.min_user_scale
        elif self.user_scale > self.max_user_scale:
            self.user_scale = self.max_user_scale

        self.log.log("debug", f"update_zoom_limits => user_scale={self.user_scale:.3f}")
