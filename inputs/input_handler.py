import logging
from PyQt5.QtCore import QObject, QEvent, Qt, QPoint, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QGraphicsScene


class InputHandler(QObject):
    """
    A single event filter that:
      - Uses QGraphicsView's default rubber-band selection when NOT placing a component.
      - Tracks the ghost continuously when the component placer IS active.
      - Handles middle mouse (panning), right mouse (context menu), Ctrl+Wheel (zoom)
      - Supports ESC, Ctrl+R, and arrow keys.
    """

    mouse_clicked = pyqtSignal(float, float, str)
    wheel_moved = pyqtSignal(int)

    arrow_up = pyqtSignal()
    arrow_down = pyqtSignal()
    arrow_left = pyqtSignal()
    arrow_right = pyqtSignal()

    def __init__(self, board_view=None, component_placer=None, ghost_component=None):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.board_view = board_view
        self.component_placer = component_placer
        self.ghost_component = ghost_component
        self._panning = False
        self._pan_start = QPoint()

    def set_board_view(self, bv):
        self.board_view = bv

    def set_component_placer(self, cp):
        self.component_placer = cp

    def set_ghost_component(self, gc):
        self.ghost_component = gc

    def eventFilter(self, obj, event):
        """
        Intercept only:
          • Mouse events coming from the BoardView's viewport widget
          • KeyPress events coming from the BoardView itself

        Everything else (e.g. QGraphicsScene) passes through.
        """
        # If board_view is missing or has been deleted, do nothing special.
        if getattr(self, "board_view", None) is None:
            return super().eventFilter(obj, event)

        # ------------------------------------------------------------------
        # Safely resolve viewport_widget without ever calling something
        # that’s already a QWidget or QGraphicsScene.
        #   • If board_view.viewport is a QWidget/QGraphicsScene attribute,
        #     use it directly.
        #   • If it’s callable (standard Qt), call it to get the widget.
        #   • If any step fails, viewport_widget = None.
        # ------------------------------------------------------------------
        try:
            vp_attr = getattr(self.board_view, "viewport", None)
            if isinstance(vp_attr, (QWidget, QGraphicsScene)):
                viewport_widget = vp_attr
            elif callable(vp_attr):
                try:
                    viewport_widget = vp_attr()
                except Exception:
                    viewport_widget = None
            else:
                viewport_widget = None
        except Exception:
            viewport_widget = None

        # ── Mouse events from the viewport ────────────────────────────────
        if viewport_widget is not None and obj is viewport_widget:
            t = event.type()
            if t == QEvent.MouseButtonPress:
                return self.handle_mouse_press(event)
            elif t == QEvent.MouseMove:
                return self.handle_mouse_move(event)
            elif t == QEvent.MouseButtonRelease:
                return self.handle_mouse_release(event)
            elif t == QEvent.Wheel:
                return self.handle_wheel(event)

        # ── Key-press events from the BoardView itself ────────────────────
        if obj is self.board_view and event.type() == QEvent.KeyPress:
            return self.handle_key_press(event)

        # Everything else: let Qt handle it
        return super().eventFilter(obj, event)

    def handle_mouse_press(self, event):
        if not self.board_view:
            self.log.warning("handle_mouse_press: board_view is not set.")
            return False

        # Map the mouse position to the scene
        scene_pos = self.board_view.mapToScene(event.pos())
        btn = event.button()
        btn_str = (
            "left"
            if btn == Qt.LeftButton
            else (
                "middle"
                if btn == Qt.MiddleButton
                else "right" if btn == Qt.RightButton else "unknown"
            )
        )
        self.log.debug(
            f"Detected {btn_str}-click at scene=({scene_pos.x():.2f}, {scene_pos.y():.2f})."
        )
        self.mouse_clicked.emit(scene_pos.x(), scene_pos.y(), btn_str)

        placer_active = self.component_placer and getattr(
            self.component_placer, "is_active", False
        )

        if btn == Qt.LeftButton:
            if placer_active:
                self.log.info(
                    "Left-click while placer active: finalizing component placement."
                )
                self.component_placer.on_user_left_click(scene_pos.x(), scene_pos.y())
                return True
            else:
                self.board_view.setDragMode(self.board_view.RubberBandDrag)
                return False

        elif btn == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.board_view.setCursor(Qt.ClosedHandCursor)
            return True

        elif btn == Qt.RightButton:
            # If nothing is selected, try selecting the topmost item
            selected_pads = self.board_view._get_selected_pads()
            if not selected_pads:
                item = self.board_view.scene.itemAt(
                    scene_pos, self.board_view.transform()
                )
                if item and hasattr(item, "setSelected"):
                    item.setSelected(True)
                    selected_pads = [item]
            # Show context menu
            self.board_view.show_context_menu(selected_pads, event.globalPos())
            # Update selection info in main window if available
            main_win = self.board_view.window()
            if hasattr(main_win, "update_selected_pins_info"):
                main_win.update_selected_pins_info(self.board_view._get_selected_pads())
            event.accept()
            return True

        return False

    def handle_mouse_move(self, event):
        if not self.board_view:
            return False

        # Always update last mouse scene position
        scene_pos = self.board_view.mapToScene(event.pos())
        self.last_mouse_scene = scene_pos

        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            h_scroll = self.board_view.horizontalScrollBar()
            v_scroll = self.board_view.verticalScrollBar()
            h_scroll.setValue(h_scroll.value() - delta.x())
            v_scroll.setValue(v_scroll.value() - delta.y())
            return True

        if (
            self.component_placer
            and getattr(self.component_placer, "is_active", False)
            and self.ghost_component
            and getattr(self.ghost_component, "is_active", False)
        ):
            # Update ghost component position
            self.ghost_component.move_ghost_to(scene_pos.x(), scene_pos.y())
            return True

        return False

    def handle_mouse_release(self, event):
        if not self.board_view:
            return False
        if event.button() == Qt.LeftButton:
            if self.board_view.dragMode() == self.board_view.RubberBandDrag:
                self.board_view.setDragMode(self.board_view.NoDrag)
            return False
        elif event.button() == Qt.MiddleButton:
            self._panning = False
            self._pan_start = QPoint()
            self.board_view.setCursor(Qt.ArrowCursor)
            return True
        return False

    def handle_wheel(self, event):
        mods = QApplication.keyboardModifiers()
        delta = event.angleDelta().y()
        if mods & Qt.ControlModifier:
            if (
                self.component_placer
                and getattr(self.component_placer, "is_active", False)
                and self.ghost_component
                and getattr(self.ghost_component, "is_active", False)
                and self.board_view
            ):
                step = int(self.board_view.constants.get("ghost_rotation_step_deg", 15))
                if delta > 0:
                    self.component_placer.rotate_footprint(step)
                elif delta < 0:
                    self.component_placer.rotate_footprint(-step)
            else:
                if delta > 0:
                    if self.board_view and self.board_view.zoom_manager:
                        self.board_view.zoom_manager.zoom_in()
                elif delta < 0:
                    if self.board_view and self.board_view.zoom_manager:
                        self.board_view.zoom_manager.zoom_out()
            return True
        return False

    def handle_key_press(self, event):
        key = event.key()
        mods = event.modifiers()
        self.log.debug(f"Key press: key={key}, modifiers={mods}")

        # ESC cancels placement or ghost
        if key == Qt.Key_Escape:
            if self.component_placer and getattr(
                self.component_placer, "is_active", False
            ):
                self.component_placer.deactivate_placement()
                self.log.info("ESC pressed: deactivated component placement.")
                return True
            if self.ghost_component and getattr(
                self.ghost_component, "is_active", False
            ):
                self.ghost_component.remove_ghost()
                self.log.info("ESC pressed: removed ghost component.")
                return True
            return False

        # Ctrl+R rotates the ghost or placer
        if key == Qt.Key_R and (mods & Qt.ControlModifier):
            self.log.info("Ctrl+R detected.")
            if self.component_placer and getattr(
                self.component_placer, "is_active", False
            ):
                self.log.info("Rotating component placer footprint by 90°.")
                self.component_placer.rotate_footprint(90)
                return True
            elif self.ghost_component and getattr(
                self.ghost_component, "is_active", False
            ):
                self.log.info("Rotating ghost component by 90°.")
                self.ghost_component.rotate_footprint(90)
                return True
            else:
                self.log.warning(
                    "Ctrl+R pressed but no active placer or ghost component."
                )
                return False

        # ── Arrow keys: emit signals and consume the event ─────────────
        if key == Qt.Key_Left:
            self.log.debug("Arrow Left pressed")
            self.arrow_left.emit()
            event.accept()
            return True
        if key == Qt.Key_Right:
            self.log.debug("Arrow Right pressed")
            self.arrow_right.emit()
            event.accept()
            return True
        if key == Qt.Key_Up:
            self.log.debug("Arrow Up pressed")
            self.arrow_up.emit()
            event.accept()
            return True
        if key == Qt.Key_Down:
            self.log.debug("Arrow Down pressed")
            self.arrow_down.emit()
            event.accept()
            return True

        return False
