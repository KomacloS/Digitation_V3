import math
from PyQt5.QtCore import Qt, QPointF, QLineF
from PyQt5.QtGui import QPen, QBrush, QColor, QCursor, QPainterPath
from PyQt5.QtWidgets import QGraphicsItemGroup, QGraphicsPathItem
from logs.log_handler import LogHandler
from objects.board_object import BoardObject
from display.pad_shapes import build_pad_path  # Import our helper

class GhostComponent:
    def __init__(self, board_view):
        self.board_view = board_view
        self.scene = board_view.scene
        self.log = LogHandler()
        self.log.log("info", "GhostComponent initialized.")
        self.ghost_item_group = None
        self.footprint = None
        self.rotation_deg = 0.0
        self.flipped = False
        self.is_active = False

# ─────────── GhostComponent.show_ghost ────────────────────────────────────
    def show_ghost(
        self,
        footprint: dict,
        rotation_deg: float = 0.0,
        flipped: bool | None = None,
        follow_mouse: bool = True           # ← already exists
    ) -> None:
        """
        Draw (or redraw) the translucent footprint.

        • If *follow_mouse* == True  → ghost tracks cursor, **no arrows**
        • If *follow_mouse* == False → fixed preview, arrows are drawn
        """
        self.is_active    = True
        self.footprint    = footprint
        self.rotation_deg = rotation_deg
        self._draw_arrows = not follow_mouse      # ← store once

        if flipped is not None:
            self.flipped = flipped

        self._remove_existing_ghost()
        self._create_ghost_item_group()

        if follow_mouse:
            self.move_ghost_to_mouse()
        else:
            conv = getattr(self.board_view, "coord_converter",
                            getattr(self.board_view, "converter", None))
            if conv and self.footprint:
                cx_px, cy_px = conv.mm_to_pixels(
                    self.footprint["center_x"], self.footprint["center_y"])
                self.ghost_item_group.setPos(cx_px, cy_px)



    def _create_ghost_item_group(self):
        """
        Build the translucent footprint (pads + number-order arrows).

        • Pads are drawn exactly as before (red pin-1, grey/blue others)
        • Between successive pads (as defined by the *order already present*
          in ``footprint["pads"]``) we draw a thin arrow that starts at the
          pad-centre and ends a little before the next pad-centre.
        • Arrow thickness = 0.1 × pad-width; arrow-head length = the same.
        • Everything (pads + arrows) is pushed into one QGraphicsItemGroup
          whose Z-value comes from constants (default = 3).
        """
        if not self.footprint or "pads" not in self.footprint:
            return

        # ---------- helper -------------------------------------------------
        def pin_int(p):          # smallest numeric label = “Pin-1”
            try:
                return int(str(p.get("pin", "9999")))
            except Exception:
                return 9999

        # ---------- pre-compute -------------------------------------------
        lowest_pin = pin_int(min(self.footprint["pads"], key=pin_int))
        z_ghost    = self.board_view.constants.get("z_value_ghost", 3)

        # current side & conversion ------------------------------------------------
        side      = self.board_view.flags.get_flag("side", "top").lower()
        mm_per_px = (self.board_view.converter.mm_per_pixels_top
                     if side == "top"
                     else self.board_view.converter.mm_per_pixels_bot)

        cx, cy    = self.footprint["center_x"], self.footprint["center_y"]
        rad       = math.radians(self.rotation_deg)

        # ---------- container ----------------------------------------------------
        self.ghost_item_group = QGraphicsItemGroup()
        self.ghost_item_group.setZValue(z_ghost)
        self.scene.addItem(self.ghost_item_group)

        # ---------- draw pads & cache their centres in scene-pixel -------------
        centres_px: list[QPointF] = []

        for pad in self.footprint["pads"]:
            # local coordinates → rotated / flipped → scene-px
            dx, dy = pad["x_coord_mm"] - cx, pad["y_coord_mm"] - cy
            rx = dx * math.cos(rad) - dy * math.sin(rad)
            ry = dx * math.sin(rad) + dy * math.cos(rad)

            # For bottom-side quick creation, mirror X only when the ghost
            # is fixed (arrows visible). Regular follow-mouse ghosts should
            # retain the same orientation as placed pads.
            if side == "bottom" and self._draw_arrows:
                rx = -rx

            # optional user flip (changes colour)
            if self.flipped:
                rx = -rx

            px = rx / mm_per_px
            py = -ry / mm_per_px
            centres_px.append(QPointF(px, py))

            # path and graphics item -----------------------------------------
            path = self._build_ghost_pad_path(
                pad["width_mm"], pad["height_mm"],
                pad.get("hole_mm", 0.0),
                pad.get("shape_type", "round")
            )
            item = QGraphicsPathItem(path)
            item.setPos(px, py)
            # Rotate counter-clockwise when angle increases
            total_angle = pad.get("angle_deg", 0.0) + self.rotation_deg
            item.setRotation((-total_angle) % 360)

            # colour logic ---------------------------------------------------
            if pin_int(pad) == lowest_pin:
                pen   = QPen(QColor("#FF0000"), 1)
                brush = QBrush(QColor(255,  85,  85, 160))
            else:
                if self.flipped:         # blue palette
                    pen   = QPen(QColor("#1E88E5"), 1)
                    brush = QBrush(QColor( 85, 170, 255, 120))
                else:                    # grey palette
                    pen   = QPen(QColor("#888888"), 1)
                    brush = QBrush(QColor(204, 204, 204, 120))
            item.setPen(pen)
            item.setBrush(brush)
            self.ghost_item_group.addToGroup(item)

        # ---------- draw numbering arrows (only for fixed ghost) -------------
        if self._draw_arrows and len(centres_px) >= 2:
            base_pad_w_mm = self.footprint["pads"][0]["width_mm"]
            pen_thick_px  = max(0.1, base_pad_w_mm / mm_per_px * 0.10)
            arrow_pen     = QPen(QColor("#555555"), pen_thick_px,
                                 Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

            head_len_px   = base_pad_w_mm / mm_per_px * 0.60

            for i in range(len(centres_px) - 1):
                p1, p2 = centres_px[i], centres_px[i + 1]
                line   = QLineF(p1, p2)

                # shorten line so it stops just before pad edge
                if line.length() > 2 * head_len_px:
                    line.setLength(line.length() - head_len_px)

                # main shaft
                arrow_path = QPainterPath()
                arrow_path.moveTo(line.p1())
                arrow_path.lineTo(line.p2())

                # arrow-head
                a = math.radians(line.angle())
                left_h  = line.p2() + QPointF(-head_len_px * math.cos(a + math.pi/6),
                                               head_len_px * math.sin(a + math.pi/6))
                right_h = line.p2() + QPointF(-head_len_px * math.cos(a - math.pi/6),
                                               head_len_px * math.sin(a - math.pi/6))
                arrow_path.moveTo(line.p2()); arrow_path.lineTo(left_h)
                arrow_path.moveTo(line.p2()); arrow_path.lineTo(right_h)

                arrow_item = QGraphicsPathItem(arrow_path)
                arrow_item.setPen(arrow_pen)
                self.ghost_item_group.addToGroup(arrow_item)

        # ---------- debug bounding rect --------------------------------------
        br = self.ghost_item_group.boundingRect()
        self.log.log("info", f"Ghost built (flipped={self.flipped}) "
                             f"- pads={len(self.footprint['pads'])}, "
                             f"arrows={self._draw_arrows}, rect={br}")



    def move_ghost_to_mouse(self):
        """
        Place ghost_item_group at the current mouse scene position.
        """
        if not self.is_active or not self.ghost_item_group:
            return
        mouse_scene = self.board_view.mapToScene(self.board_view.mapFromGlobal(QCursor.pos()))
        self.ghost_item_group.setPos(mouse_scene.x(), mouse_scene.y())
        self.log.log("info", f"Ghost moved to mouse position: ({mouse_scene.x():.2f}, {mouse_scene.y():.2f})")

    def move_ghost_to(self, scene_x: float, scene_y: float):
        """
        Called on mouseMoveEvent to keep ghost under cursor.
        """
        if self.is_active and self.ghost_item_group:
            self.ghost_item_group.setPos(scene_x, scene_y)

    def rotate_footprint(self, deg: float = 90.0):
        """
        Rotates the ghost by `deg` degrees and re-draws it.
        """
        if not self.is_active:
            return
        self.rotation_deg = (self.rotation_deg + deg) % 360
        self.log.log("info", f"GhostComponent.rotate_footprint => now {self.rotation_deg:.1f}°")
        self._remove_existing_ghost()
        self._create_ghost_item_group()
        self.move_ghost_to_mouse()

    def _remove_existing_ghost(self):
        if self.ghost_item_group:
            self.scene.removeItem(self.ghost_item_group)
            self.ghost_item_group = None

    def remove_ghost(self):
        """
        External method to remove the ghost (deactivate_placement in ComponentPlacer).
        """
        self._remove_existing_ghost()
        self.is_active = False
        self.footprint = None
        self.rotation_deg = 0.0
        self.log.log("info", "GhostComponent: removed ghost from scene.")

    def _build_ghost_pad_path(self, width_mm, height_mm, hole_mm, shape_type):
        """
        Uses the board_view's converter to pick the correct mm_per_pixel
        factor for top or bottom, then calls build_pad_path.
        """
        current_side = self.board_view.flags.get_flag("side", "top").lower()
        if current_side == "top":
            mm_per_pixel = self.board_view.converter.mm_per_pixels_top
        else:
            mm_per_pixel = self.board_view.converter.mm_per_pixels_bot

        # Now build the path
        return build_pad_path(
            width_mm,
            height_mm,
            hole_mm,
            shape_type,
            mm_per_pixel
        )


    def flip_horizontal(self):
        """Mirror the ghost around its Y-axis and recolor pads."""
        if not self.is_active:
            return
        self.flipped = not self.flipped
        self._remove_existing_ghost()
        self._create_ghost_item_group()
        self.move_ghost_to_mouse()