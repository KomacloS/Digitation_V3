# board_view/shortcuts.py
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt


def setup_board_view_shortcuts(board_view):
    board_view.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), board_view)
    board_view.save_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    # Typically, we want to call project_manager.save_project_dialog()
    # The project_manager is accessible from board_view's parent window if set up:
    board_view.save_shortcut.activated.connect(
        lambda: board_view.parent().project_manager.save_project_dialog()
    )

    board_view.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), board_view)
    board_view.copy_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.copy_shortcut.activated.connect(board_view.copy_selected_pads)

    board_view.paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), board_view)
    board_view.paste_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.paste_shortcut.activated.connect(board_view.paste_selected_pads)

    board_view.delete_shortcut = QShortcut(QKeySequence("Delete"), board_view)
    board_view.delete_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.delete_shortcut.activated.connect(board_view.delete_selected_pads)

    board_view.edit_shortcut = QShortcut(QKeySequence("Ctrl+E"), board_view)
    board_view.edit_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.edit_shortcut.activated.connect(board_view.edit_selected_pads)

    board_view.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), board_view)
    board_view.undo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.undo_shortcut.activated.connect(board_view.perform_undo)

    board_view.redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), board_view)
    board_view.redo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.redo_shortcut.activated.connect(board_view.perform_redo)

    board_view.switch_side_shortcut = QShortcut(
        QKeySequence("Ctrl+Shift+S"), board_view
    )
    board_view.switch_side_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.switch_side_shortcut.activated.connect(board_view.switch_side)

    board_view.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), board_view)
    board_view.search_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    # Assume that MainWindow provides an open_search_dialog() method:
    board_view.search_shortcut.activated.connect(
        lambda: board_view.parent().open_search_dialog()
    )

    board_view.cut_shortcut = QShortcut(QKeySequence("Ctrl+X"), board_view)
    board_view.cut_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.cut_shortcut.activated.connect(board_view.cut_selected_pads)

    board_view.move_shortcut = QShortcut(QKeySequence("Ctrl+M"), board_view)
    board_view.move_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.move_shortcut.activated.connect(board_view.move_selected_pads)

    #  Flip ghost horizontally  (Ctrl+H)
    board_view.flip_shortcut = QShortcut(QKeySequence("Ctrl+H"), board_view)
    board_view.flip_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.flip_shortcut.activated.connect(board_view.flip_ghost_horizontal)

    # ── Quick Creation shortcut (press “N”) ────────────────────────────
    board_view.quick_creation_shortcut = QShortcut(QKeySequence("N"), board_view)
    board_view.quick_creation_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    board_view.quick_creation_shortcut.activated.connect(
        lambda: board_view.parent().quick_creation_controller.activate()
    )
