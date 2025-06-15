# project_manager/image_handler.py

from typing import Optional, TYPE_CHECKING
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PyQt5.QtCore import QByteArray, QBuffer, QIODevice
from logs.log_handler import LogHandler
import hashlib
import os

log = LogHandler()

if TYPE_CHECKING:
    from project_manager.project_manager import ProjectManager  # Only for type hints

def is_same_file(file_path, pixmap):
    """Checks if the given file is the same as the in-memory pixmap.
    First compares file sizes, then computes MD5 hashes only if needed."""
    if not file_path or not pixmap:
        return False

    try:
        # Get the file size.
        file_size = os.path.getsize(file_path)

        # Convert the pixmap to a PNG byte array.
        buffer = QByteArray()
        io_buffer = QBuffer(buffer)
        io_buffer.open(QIODevice.WriteOnly)
        pixmap.save(io_buffer, "PNG")
        mem_data = buffer.data()
        mem_size = len(mem_data)

        # If sizes differ, no need to calculate MD5.
        if file_size != mem_size:
            return False

        # Compute MD5 hash for file by reading in chunks.
        file_hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                file_hash_md5.update(chunk)
        file_hash = file_hash_md5.hexdigest()

        # Compute MD5 for the in-memory data.
        memory_hash = hashlib.md5(mem_data).hexdigest()

        return file_hash == memory_hash

    except Exception as e:
        log.error(f"Error in is_same_file: {e}")
        return False


def pixmapToBytes(pixmap):
    """Converts QPixmap to byte array for hashing."""
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return byte_array.data()


class ImageHandler:
    def __init__(self, project_manager: 'ProjectManager'):
        self.project_manager = project_manager
        self.main_window = project_manager.main_window
        self.log = project_manager.log

    def load_image(self, file_path: Optional[str] = None, side: str = 'top'):
        """
        Loads an image into the specified side. If file_path is provided, load the image directly.
        Otherwise, prompt the user to select an image via a file dialog.
        
        After successfully loading the image, if a valid project folder is set and the file
        is not already in that folder, the image is automatically saved (copied) into the project's folder.
        """
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(
                self.main_window,
                f"Load {side.capitalize()} Image",
                "",
                "Images (*.jpg *.jpeg *.png)",
                options=QFileDialog.Options()
            )
        
        if not file_path:
            self.log.log("warning", f"No file selected for {side} image.")
            return  # User canceled the dialog or no file selected
        
        self.log.log("info", f"Selected {side} image: {file_path}")
        pixmap = QPixmap(file_path)
        
        if pixmap.isNull():
            self.log.log("error", f"Failed to load {side} image from {file_path}.")
            QMessageBox.critical(self.main_window, "Load Image Failed", f"Failed to load {side} image from {file_path}.")
            return
        
        if side == 'top':
            self.main_window.top_image_pixmap = pixmap
            self.log.log("info", "Top image pixmap updated.")
        elif side == 'bottom':
            self.main_window.bottom_image_pixmap = pixmap
            self.log.log("info", "Bottom image pixmap updated.")
        else:
            self.log.log("error", f"Unknown side '{side}' when loading image.")
            QMessageBox.warning(self.main_window, "Load Image", f"Unknown side '{side}'. Use 'top' or 'bottom'.")
            return
        
        # Update board_view with the loaded image.
        self.main_window.board_view.load_image(file_path, side)
        self.main_window.board_view.display_library.update_display_side()
        self.log.log("info", f"Loaded image for '{side}' and updated the display.")
        
        # --- New Logic: Ensure the image is saved in the project's folder ---
        project_folder = self.main_window.current_project_path
        # Only if a valid project folder is set (and not "[None]")
        if project_folder and project_folder.strip().lower() != "[none]":
            abs_proj = os.path.abspath(project_folder)
            abs_file = os.path.abspath(file_path)
            # If the image is not already in the project folder, save (copy) it.
            if not abs_file.startswith(abs_proj):
                target_file = os.path.join(abs_proj, f"{side}_image.png")
                self.save_image(target_file, side)
                self.log.log("info", f"Copied {side} image to project folder: {target_file}")


    def save_image(self, file_path: str, side: str):
        """
        Saves the specified side's image to the given file path **only if necessary**.

        Parameters:
            file_path (str): The path where the image will be saved.
            side (str): 'top' or 'bottom' indicating which side's image to save.
        """
        if side == 'top':
            pixmap = self.main_window.top_image_pixmap
            side_label = "Top"
        elif side == 'bottom':
            pixmap = self.main_window.bottom_image_pixmap
            side_label = "Bottom"
        else:
            self.log.log("error", f"Invalid side '{side}' specified for saving image.")
            QMessageBox.critical(self.main_window, "Save Image Failed", f"Invalid side '{side}'. Use 'top' or 'bottom'.")
            return

        # 🛑 Check if we should skip saving (file exists and is identical)
        if os.path.exists(file_path) and is_same_file(file_path, pixmap):
            self.log.log("info", f"Skipped saving {side_label} image - no changes detected.")
            return  # 🔹 Skip saving if the file is unchanged

        if pixmap and not pixmap.isNull():
            success = pixmap.save(file_path, 'PNG')
            if success:
                self.log.log("info", f"{side_label} image saved to {file_path}.")
            else:
                self.log.log("error", f"Failed to save {side_label} image to {file_path}.")
                QMessageBox.critical(self.main_window, "Save Image Failed", f"Failed to save {side_label} image to {file_path}.")
        else:
            self.log.log("error", f"No {side_label.lower()} image available to save.")
            QMessageBox.critical(self.main_window, "Save Image Failed", f"No {side_label.lower()} image available to save.")



