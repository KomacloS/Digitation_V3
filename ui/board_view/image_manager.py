# board_view/image_manager.py
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMessageBox, QGraphicsPixmapItem

def load_image(board_view, file_path: str, side: str):
    board_view.log.info(f"Loading image for {side} from {file_path}.")
    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        board_view.log.error(f"Failed to load image from {file_path}.")
        QMessageBox.critical(board_view, "Image Load Error", f"Failed to load image from {file_path}.")
        return

    image_z_value = board_view.constants.get("z_value_image", 0)
    if side.lower() == "top":
        board_view.converter.set_image_size((pixmap.width(), pixmap.height()))
        board_view.flags.set_flag("side", "top")
        if board_view.top_pixmap_item:
            board_view.top_pixmap_item.setPixmap(pixmap)
        else:
            board_view.top_pixmap_item = QGraphicsPixmapItem(pixmap)
            board_view.scene.addItem(board_view.top_pixmap_item)
            board_view.top_pixmap_item.setZValue(image_z_value)
        board_view.top_image_size = (pixmap.width(), pixmap.height())
        board_view.current_pixmap_item = board_view.top_pixmap_item

    elif side.lower() == "bottom":
        board_view.converter.set_image_size((pixmap.width(), pixmap.height()))
        board_view.flags.set_flag("side", "bottom")
        if board_view.bottom_pixmap_item:
            board_view.bottom_pixmap_item.setPixmap(pixmap)
        else:
            board_view.bottom_pixmap_item = QGraphicsPixmapItem(pixmap)
            board_view.scene.addItem(board_view.bottom_pixmap_item)
            board_view.bottom_pixmap_item.setZValue(image_z_value)
        board_view.bottom_image_size = (pixmap.width(), pixmap.height())
        board_view.current_pixmap_item = board_view.bottom_pixmap_item

    else:
        board_view.log.error(f"Unknown side '{side}' specified for load_image.")
        QMessageBox.warning(board_view, "Load Image", f"Unknown side '{side}'. Must be 'top' or 'bottom'.")
        return

    board_view.display_library.current_side = side.lower()
    board_view.display_library.update_display_side()
    board_view.zoom_manager.update_zoom_limits()
    board_view.fit_in_view()
    board_view.log.info(f"Image loaded for {side} and display updated.")
