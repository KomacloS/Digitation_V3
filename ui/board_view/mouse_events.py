# ui/board_view/mouse_events.py
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QGraphicsView

def handle_mouse_press(view, event):
    # 'view' is the BoardView instance.
    if not view:
        view.log.warning("handle_mouse_press: board_view is not set.")
        return False

    # Map the mouse position to scene coordinates.
    scene_pos = view.mapToScene(event.pos())
    # Always update last_clicked_mm using the converter.
    view.last_clicked_mm = view.converter.pixels_to_mm(scene_pos.x(), scene_pos.y())
    
    btn = event.button()
    btn_str = ("left" if btn == Qt.LeftButton
               else "middle" if btn == Qt.MiddleButton
               else "right" if btn == Qt.RightButton
               else "unknown")
    
    view.log.debug(f"Detected {btn_str}-click at scene=({scene_pos.x():.2f}, {scene_pos.y():.2f}).")
    
    # Emit the custom mouse_clicked signal.
    view.mouse_clicked.emit(scene_pos.x(), scene_pos.y(), btn_str)
    
    # Immediately update the info display with the current selection (even if empty)
    main_win = view.window()
    if hasattr(main_win, "update_selected_pins_info"):
        main_win.update_selected_pins_info(view._get_selected_pads())
    
    placer_active = (view.component_placer and view.component_placer.is_active)
    
    if btn == Qt.LeftButton:
        if placer_active:
            view.log.info("Left-click while placer active: finalizing component placement.")
            view.component_placer.on_user_left_click(scene_pos.x(), scene_pos.y())
            return True
        else:
            view.setDragMode(view.RubberBandDrag)
            return False

    elif btn == Qt.MiddleButton:
        view._panning = True
        view._pan_start = event.pos()
        view.setCursor(Qt.ClosedHandCursor)
        return True

    elif btn == Qt.RightButton:
        # If nothing is selected, try to select the topmost item at the click point.
        selected_pads = view._get_selected_pads()
        if not selected_pads:
            item = view.scene.itemAt(scene_pos, view.transform())
            if item and hasattr(item, 'setSelected'):
                item.setSelected(True)
                selected_pads = [item]
        view.show_context_menu(selected_pads, event.globalPos())
        # Update selection info again after showing the menu.
        if hasattr(main_win, "update_selected_pins_info"):
            main_win.update_selected_pins_info(view._get_selected_pads())
        event.accept()
        return True

    return False



def handle_mouse_move(board_view, event):
    # Handle panning if in panning mode.
    if board_view._panning:
        delta = event.pos() - board_view._pan_start
        board_view._pan_start = event.pos()
        board_view.horizontalScrollBar().setValue(
            board_view.horizontalScrollBar().value() - delta.x()
        )
        board_view.verticalScrollBar().setValue(
            board_view.verticalScrollBar().value() - delta.y()
        )
        return True

    # If component placer is active, update the ghost position.
    if board_view.component_placer and board_view.component_placer.is_active:
        ghost = board_view.component_placer.ghost_component
        if ghost and ghost.is_active:
            scene_pos = board_view.mapToScene(event.pos())
            ghost.move_ghost_to(scene_pos.x(), scene_pos.y())
            return True

    return False

def handle_mouse_release(board_view, event):
    if event.button() == Qt.MiddleButton:
        board_view._panning = False
        board_view._pan_start = QPoint()
        board_view.setCursor(Qt.ArrowCursor)
        return True
    return False

def handle_wheel(board_view, event):
    """
    Always zoom on mouse wheel, ignoring default QGraphicsView scrolling.
    """
    delta = event.angleDelta().y()
    if delta > 0:
        board_view.zoom_manager.zoom_in()
    else:
        board_view.zoom_manager.zoom_out()
    # The event has been handled.
    return True
