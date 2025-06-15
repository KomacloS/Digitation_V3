# main.py

import sys
import os
from logs.log_handler import LogHandler  # Ensure LogHandler is imported

# === Step 1: Add Project Root to sys.path ===
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# === Step 2: Import Remaining Modules After Modifying sys.path ===
from PyQt5.QtWidgets import QApplication
from ui.main_menu import MainWindow



def main():
    """
    Entry point for the application. Initializes the QApplication and displays the main window.
    """
    # Setup basic logging to catch uncaught exceptions
    # logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    # Consider removing the above line to prevent configuring the root logger

    try:
        app = QApplication(sys.argv)

        # Initialize LogHandler
        logger = LogHandler(output="both")
        logger.log("info", "Application started.", module="main", func="main")
        
        window = MainWindow()
        window.show()
        logger.log("info", "MainWindow displayed.", module="main", func="main")

        sys.exit(app.exec_())
    except Exception as e:
        logger.log("error", f"Unhandled exception occurred: {e}", module="main", func="main")
        sys.exit(1)

if __name__ == "__main__":
    main()
