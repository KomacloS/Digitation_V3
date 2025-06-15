# ui/main_menu.py

from typing import List 
import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QKeySequence, QFont, QColor, QDoubleValidator
from PyQt5.QtWidgets import (
    QMainWindow, QStatusBar, QLabel, QToolBar, QAction, QComboBox,
    QFileDialog, QDockWidget, QTreeWidget, QTreeWidgetItem, QMessageBox,
    QDialog, QMenu, QToolButton, QInputDialog, QTabWidget, QVBoxLayout, QWidget, QLabel, QTextBrowser,
    QTableWidget, QTableWidgetItem, QHBoxLayout, QLineEdit,QStyle
)
from logs.log_handler import LogHandler
from constants.constants import Constants
from ui.board_view.board_view import BoardView
from objects.nod_file import get_footprint_for_placer
from component_placer.component_placer import ComponentPlacer
from inputs.input_handler import InputHandler
from component_placer.ghost import GhostComponent
from project_manager.project_manager import ProjectManager
from ui.search_dialog import SearchDialog
from objects.object_library import ObjectLibrary
from display.display_library import SelectablePadItem
from ui.selected_pins_info import generate_selected_pins_html
from ui.ui_customization_dialog import UICustomizationDialog
from ui.properties_dock import PropertiesDock
import edit_pads.actions as actions
from ui.layers_tab import LayersTab
from component_placer.bom_handler.bom_handler import BOMHandler
from component_placer.quick_creation_controller import QuickCreationController


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Board Digitization Tool")
        self.log = LogHandler()

        # ─── Constants & State ─────────────────────────────────────────────
        self.constants = Constants()
        self.current_project_path = self.constants.get("current_project_path", None)
        self.project_loaded      = self.constants.get("project_loaded", False)
        self.pixels_per_mm       = self.constants.get("pixels_per_mm", 30.0)

        # ─── Status Bar ────────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.project_name_label = QLabel("Project: [None]")
        self.status_bar.addPermanentWidget(self.project_name_label)
        self.pad_info_label     = QLabel("No pad selected")
        self.status_bar.addPermanentWidget(self.pad_info_label)

        # ─── Core Models ───────────────────────────────────────────────────
        self.object_library = ObjectLibrary()
        self.bom_handler    = BOMHandler()
        # Link BOM ↔ undo/redo
        self.bom_handler.undo_redo_manager  = self.object_library.undo_redo_manager
        self.object_library.bom_handler     = self.bom_handler

        # ─── Project Manager ───────────────────────────────────────────────
        # Must exist before wiring up input_handler, etc.
        self.project_manager = ProjectManager(self, bom_handler=self.bom_handler)

        # ─── Placer & View ─────────────────────────────────────────────────
        self.component_placer = ComponentPlacer(
            board_view=None,
            object_library=self.object_library,
            bom_handler=self.bom_handler
        )

        self.board_view = BoardView(
            parent=self,
            pad_info_label=self.pad_info_label,
            component_placer=self.component_placer,
            object_library=self.object_library,
            constants=self.constants
        )
        self.component_placer.board_view = self.board_view
        self.setCentralWidget(self.board_view)

        # ─── Wire up Ghost, InputHandler, etc. ──────────────────────────
        self.wire_everything()

        # ─── Quick Creation Controller ──────────────────────────────────
        self.quick_creation_controller = QuickCreationController(
            board_view       = self.board_view,
            input_handler    = self.input_handler,
            component_placer = self.component_placer,
            marker_manager   = self.board_view.marker_manager,
            coord_converter  = self.board_view.converter
        )

        # ─── Link DisplayLibrary ─────────────────────────────────────────
        self.object_library.display_library = self.board_view.display_library

        # ─── Docks & UI setup ────────────────────────────────────────────
        self.layers_dock = QDockWidget("Layers", self)
        self.layers_tab  = LayersTab(self.board_view, parent=self)
        self.layers_dock.setWidget(self.layers_tab)
        self.layers_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layers_dock)

        self.create_properties_dock()

        # ─── Toolbar, Menus, Fonts ───────────────────────────────────────
        self.create_components_bar()
        self.create_tool_bar()
        self.create_menus()
        self.apply_individual_fonts()

        # ─── Show window ────────────────────────────────────────────────
        self.show()



    # --------------------------------------------------------------------------
    #  Toolbar (zoom, search, switch-side …) – UX-upgraded
    # --------------------------------------------------------------------------
    def create_tool_bar(self):
        """
        Builds a tidy main toolbar and improves UX:
            • Search-pad and Switch-side icons are 4 × larger (80 px)  
            • All combo / label widgets have a fixed width so the bar
            never jiggles when their text changes.  
            • Icon-only buttons keep the bar compact and clear.
        """
        from PyQt5.QtCore    import QSize
        from PyQt5.QtWidgets import QStyle, QToolButton

        LARGE   = QSize(80, 80)      # 4 × bigger than default 20 px
        SMALL   = QSize(20, 20)

        tb = QToolBar(self.tr("Main Toolbar"))
        tb.setMovable(False)
        tb.setIconSize(SMALL)        # default for *all* actions
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(tb)

        # ── Zoom-centre selector ───────────────────────────────────────────────
        tb.addWidget(QLabel(self.tr("Zoom centre:")))
        self.zoom_center_mode_combo = QComboBox()
        self.zoom_center_mode_combo.addItems(["Mouse", "Marker"])
        self.zoom_center_mode_combo.setFixedWidth(90)
        tb.addWidget(self.zoom_center_mode_combo)
        self.zoom_center_mode_combo.currentIndexChanged.connect(
            self.update_zoom_center_mode
        )
        init_idx = 0 if self.constants.get("zoom_center_mode", "mouse") == "mouse" else 1
        self.zoom_center_mode_combo.setCurrentIndex(init_idx)

        tb.addSeparator()

        # ── Working-side label ─────────────────────────────────────────────────
        self.working_side_label = QLabel(self.tr("Side: Top"))
        font = self.working_side_label.font()
        font.setPointSize(13)
        self.working_side_label.setFont(font)
        self.working_side_label.setFixedWidth(120)
        tb.addWidget(self.working_side_label)

        tb.addSeparator()

        # ── Zoom-level label ───────────────────────────────────────────────────
        self.zoom_level_label = QLabel("Zoom 100 %")
        self.zoom_level_label.setFixedWidth(90)
        tb.addWidget(self.zoom_level_label)
        self.board_view.zoom_manager.scale_factor_changed.connect(
            self.update_zoom_level_label
        )

        tb.addSeparator()

        # ── Search-pad action  (big icon) ──────────────────────────────────────
        search_pad_action = QAction(
            self.style().standardIcon(QStyle.SP_FileDialogContentsView),
            self.tr("Search pad …"),
            self
        )
        search_pad_action.setToolTip(self.tr("Open pad search dialog"))
        search_pad_action.triggered.connect(self.open_search_dialog)
        tb.addAction(search_pad_action)

        # make this action’s tool-button big:
        btn = tb.widgetForAction(search_pad_action)       # QToolButton
        if isinstance(btn, QToolButton):
            btn.setIconSize(LARGE)
            btn.setFixedSize(LARGE)                       # keeps layout stable

        # ── Switch-side action  (big icon) ─────────────────────────────────────
        switch_side_action = QAction(
            self.style().standardIcon(QStyle.SP_BrowserReload),
            self.tr("Flip side"),
            self
        )
        switch_side_action.setToolTip(self.tr("Switch between top ↔ bottom"))
        switch_side_action.triggered.connect(self.on_switch_side)
        tb.addAction(switch_side_action)

        btn2 = tb.widgetForAction(switch_side_action)
        if isinstance(btn2, QToolButton):
            btn2.setIconSize(LARGE)
            btn2.setFixedSize(LARGE)

        # ── Quick Creation action (big icon) ───────────────────────────
        quick_action = QAction(
            self.style().standardIcon(QStyle.SP_FileDialogNewFolder),
            self.tr("Quick Creation"),
            self
        )
        quick_action.setToolTip(self.tr("Activate Quick Creation mode (N)"))
        quick_action.triggered.connect(self.quick_creation_controller.activate)
        tb.addAction(quick_action)

        btn_qc = tb.widgetForAction(quick_action)
        if isinstance(btn_qc, QToolButton):
            btn_qc.setIconSize(LARGE)
            btn_qc.setFixedSize(LARGE)

        # final stretch so items stay left-aligned
        tb.addSeparator()
        tb.addWidget(QWidget())  # empty stretch




    # --------------------------------------------------------------------------
    #  Enhanced "Load NOD" method
    # --------------------------------------------------------------------------

    def load_jpg_file(self, side: str):
        """
        Opens a typical file dialog for .jpg/.jpeg/.png, then calls project_manager.load_image().
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Load {side.capitalize()} Image",
            "",
            "Images (*.jpg *.jpeg *.png)"
        )
        if file_path:
            self.project_manager.load_image(file_path=file_path, side=side)

    def _perform_nod_load(self):
        """
        Actually calls ProjectManager.load_nod_file() to load the new objects.
        If successful, updates the project_name_label with the folder name of the nod file.
        """
        old_count = len(self.object_library.get_all_objects())
        self.project_manager.load_nod_file()  # triggers a file dialog if no path

        new_count = len(self.object_library.get_all_objects())
        if new_count > old_count:
            # The load likely succeeded
            # Retrieve the path from project_manager if available
            nod_path = None
            if getattr(self.project_manager.nod_handler, "last_loaded_nod_path", None):
                nod_path = self.project_manager.nod_handler.last_loaded_nod_path

            if nod_path:
                # Extract the folder name from the nod file path
                folder_path = os.path.dirname(nod_path)
                folder_name = os.path.basename(folder_path)
                self.update_project_name(folder_name)

    # --------------------------------------------------------------------------
    #  Update the label in the status bar for current project folder name
    # --------------------------------------------------------------------------
    def update_project_name(self, folder_name: str):
        if folder_name:
            self.project_name_label.setText(f"Project: {folder_name}")
            self.log.log("info", f"Project name label set to: '{folder_name}'")
            # enable Restore‑Backup once a project is open
            if hasattr(self, "restore_backup_action"):
                self.restore_backup_action.setEnabled(True)
        else:
            self.project_name_label.setText("Project: [None]")
            self.log.log("info", "Project name label set to: '[None]'")
            if hasattr(self, "restore_backup_action"):
                self.restore_backup_action.setEnabled(False)

    # --------------------------------------------------------------------------
    #  Wire everything (Ghost, InputHandler, etc.)
    # --------------------------------------------------------------------------

    def wire_everything(self):
        self.log.log("debug", "=== Wiring up all core objects ===")
        # Create the ghost component and link it to the existing component_placer.
        self.ghost_component = GhostComponent(self.board_view)
        self.component_placer.ghost_component = self.ghost_component

        # Also link the project_manager to the existing component_placer.
        self.component_placer.project_manager = self.project_manager

        self.log.log("debug", "ComponentPlacer updated with ghost component and project_manager.")

        # Create the InputHandler with references to existing objects.
        self.input_handler = InputHandler(
            board_view=self.board_view,
            component_placer=self.component_placer,
            ghost_component=self.ghost_component
        )
        self.log.log("debug", "Created InputHandler for BoardView, ComponentPlacer, GhostComponent.")

        # Install the input handler as an event filter for the board view.
        self.board_view.viewport().setMouseTracking(True)
        self.board_view.viewport().installEventFilter(self.input_handler)
        self.board_view.setFocusPolicy(Qt.StrongFocus)
        self.board_view.setFocus()
        self.board_view.installEventFilter(self.input_handler)

        self.input_handler.mouse_clicked.connect(self.board_view.marker_manager.place_marker_from_scene)
        self.input_handler.wheel_moved.connect(self.board_view.wheelEvent)
        self.log.log("info", "All wiring completed successfully.")

    # --------------------------------------------------------------------------
    #  Menus: "File" (Open, Save, SaveAs, Create Project), "Project" (Load Top, etc.)
    # --------------------------------------------------------------------------
    def create_menus(self):
        menubar = self.menuBar()

        # -------------------- FILE Menu --------------------
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.project_manager.open_project_dialog)
        file_menu.addAction(open_action)
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.project_manager.save_project_dialog)
        file_menu.addAction(save_action)
        save_as_action = QAction("Save As", self)
        save_as_action.triggered.connect(self.project_manager.save_project_as_dialog)
        file_menu.addAction(save_as_action)
        create_project_action = QAction("Create Project", self)
        create_project_action.triggered.connect(self.project_manager.create_project_dialog)
        file_menu.addAction(create_project_action)

        # ── NEW: Restore Backup … ───────────────────────────────────────────
        restore_action = QAction("Restore Backup…", self)
        restore_action.setToolTip("Browse timestamped .bak files and restore")
        restore_action.triggered.connect(self.project_manager.restore_backup_dialog)
        file_menu.addAction(restore_action)
        # Disabled until a project is loaded
        self.restore_backup_action = restore_action
        self.restore_backup_action.setEnabled(False)

        # ------------------- EDIT Menu ------------------
        edit_menu = menubar.addMenu("Edit")
        undo_action = QAction("Undo", self)
        undo_action.triggered.connect(self.board_view.perform_undo)
        edit_menu.addAction(undo_action)
        redo_action = QAction("Redo", self)
        redo_action.triggered.connect(self.board_view.perform_redo)
        edit_menu.addAction(redo_action)
        align_action = QAction("Align Pads", self)
        align_action.triggered.connect(self.align_pads_action)
        edit_menu.addAction(align_action)
        # New BOM action:
        bom_action = QAction("BOM", self)
        bom_action.triggered.connect(self.open_bom_editor)
        edit_menu.addAction(bom_action)

        # ------------------- PROJECT Menu ------------------
        project_menu = menubar.addMenu("Project")
        load_top_action = QAction("Load Top JPG", self)
        load_top_action.triggered.connect(lambda: self.project_manager.image_handler.load_image(side='top'))
        project_menu.addAction(load_top_action)
        load_bottom_action = QAction("Load Bottom JPG", self)
        load_bottom_action.triggered.connect(lambda: self.project_manager.image_handler.load_image(side='bottom'))
        project_menu.addAction(load_bottom_action)
        load_nod_action = QAction("Load NOD", self)
        load_nod_action.triggered.connect(self.project_manager.load_nod_advanced)
        project_menu.addAction(load_nod_action)

        # ------------------- VIEW Menu ------------------
        view_menu = menubar.addMenu("View")
        
        # Toggle action for Components dock (if you have one)
        components_toggle = self.components_dock.toggleViewAction()
        components_toggle.setText("Components")
        view_menu.addAction(components_toggle)

        # Toggle action for Properties dock
        properties_toggle = self.properties_dock.toggleViewAction()
        properties_toggle.setText("Properties")
        view_menu.addAction(properties_toggle)
        
        # Toggle action for Layers dock
        layers_toggle = self.layers_dock.toggleViewAction()
        layers_toggle.setText("Layers")
        view_menu.addAction(layers_toggle)

        # ------------------- PROPERTIES Menu ------------------
        properties_menu = menubar.addMenu("Properties")
        ui_custom_action = QAction("UI Customization", self)
        ui_custom_action.triggered.connect(self.open_ui_customization_dialog)
        properties_menu.addAction(ui_custom_action)

        autosave_action = QAction("Set Auto-Save Threshold", self)
        autosave_action.triggered.connect(self.set_auto_save_threshold)
        properties_menu.addAction(autosave_action)

        set_pixels_ratio_action = QAction("Set Pixels Per MM (Legacy)", self)
        set_pixels_ratio_action.triggered.connect(self.set_pixels_per_mm)
        properties_menu.addAction(set_pixels_ratio_action)

        # -- NEW: Add two separate menu actions for top & bottom mm-per-pixels
        set_mm_per_pixels_top_action = QAction("Set mm_per_pixels_top", self)
        set_mm_per_pixels_top_action.triggered.connect(self.set_mm_per_pixels_top)
        properties_menu.addAction(set_mm_per_pixels_top_action)

        set_mm_per_pixels_bot_action = QAction("Set mm_per_pixels_bot", self)
        set_mm_per_pixels_bot_action.triggered.connect(self.set_mm_per_pixels_bot)
        properties_menu.addAction(set_mm_per_pixels_bot_action)

        # --- Board Origin ---
        set_origin_action = QAction("Set Board Origin (mm)", self)
        set_origin_action.triggered.connect(self.set_board_origin)
        edit_menu.addAction(set_origin_action)

    # ------------------------------------------------------------------
    #  Board Origin Setter
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    #  Board Origin Setter  (full replacement)
    # ------------------------------------------------------------------
    def set_board_origin(self):
        """
        Lets the user pick a new X₀ / Y₀ origin (mm).  
        • May optionally shift every pad by ΔX, ΔY  
        • Re-positions the marker so it stays visually correct.
        """
        ox_old = self.constants.get("origin_x_mm", 0.0)
        oy_old = self.constants.get("origin_y_mm", 0.0)

        # -- get two doubles -------------------------------------------------
        x0, ok1 = QInputDialog.getDouble(self, "Board Origin",
                                         "New X-origin (mm):", ox_old,
                                         -1e6, 1e6, 3)
        if not ok1:
            return
        y0, ok2 = QInputDialog.getDouble(self, "Board Origin",
                                         "New Y-origin (mm):", oy_old,
                                         -1e6, 1e6, 3)
        if not ok2:
            return

        dx = x0 - ox_old
        dy = y0 - oy_old

        # -- current marker position *before* anything changes ---------------
        old_marker_mm = self.board_view.marker_manager.get_marker_board_coords()

        # -- ask whether to shift every pad ----------------------------------
        shift_pads = False
        if abs(dx) > 1e-9 or abs(dy) > 1e-9:
            resp = QMessageBox.question(
                self, "Shift Pads?",
                f"Origin moves by ΔX={dx:.3f} mm, ΔY={dy:.3f} mm.\n"
                "Shift all existing pads by the same amount?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            shift_pads = (resp == QMessageBox.Yes)

        # -- save new constants & tell converter -----------------------------
        self.constants.set("origin_x_mm", x0)
        self.constants.set("origin_y_mm", y0)
        self.constants.save()
        self.board_view.converter.set_origin_mm(x0, y0)

        # -- shift pads if requested -----------------------------------------
        if shift_pads and (abs(dx) > 1e-9 or abs(dy) > 1e-9):
            self._shift_all_pads(dx, dy)

        # -- restore / move the marker ---------------------------------------
        if old_marker_mm:
            if shift_pads:
                new_marker_mm = (old_marker_mm[0] + dx, old_marker_mm[1] + dy)
            else:
                new_marker_mm = old_marker_mm            # same board coords
            self.board_view.marker_manager.place_marker(*new_marker_mm)

        # -- redraw -----------------------------------------------------------
        self.board_view.update_scene()
        self.log.log("info",
            f"Origin set to ({x0:.3f}, {y0:.3f}) mm ; pads shifted={shift_pads}.")

        
    def _shift_all_pads(self, dx: float, dy: float):
        """Bulk-translate every BoardObject by dx,dy millimetres."""
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return
        updates = []
        for obj in self.object_library.get_all_objects():
            obj.x_coord_mm += dx
            obj.y_coord_mm += dy
            # keep “original” coords too, if they exist
            if hasattr(obj, "x_coord_mm_original"):
                obj.x_coord_mm_original += dx
            if hasattr(obj, "y_coord_mm_original"):
                obj.y_coord_mm_original += dy
            updates.append(obj)
        self.object_library.bulk_update_objects(updates, {})



    # --------------------------------------------------------------------------
    #  "Components" Dock  – now with refresh button **and** live filter
    # --------------------------------------------------------------------------
    def create_components_bar(self):
        """
        Builds the dock that lists footprints found under ./component_libraries.
        Adds:
            •   a ⟳ refresh button (rescans the folder)
            •   a small filter field to quickly narrow down the list
        """
        from PyQt5.QtWidgets import QHBoxLayout, QLineEdit, QToolButton, QStyle

        # ---------- dock & tree -------------------------------------------------
        self.components_dock = QDockWidget(self.tr("Components"), self)
        self.components_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )

        self.component_tree = QTreeWidget()
        self.component_tree.setHeaderHidden(True)
        self.components_dock.setWidget(self.component_tree)
        self.addDockWidget(Qt.RightDockWidgetArea, self.components_dock)

        self.component_tree.itemDoubleClicked.connect(
            self.on_component_tree_item_double_clicked
        )

        # ---------- locate / create folder -------------------------------------
        script_dir   = os.path.dirname(os.path.abspath(__file__))
        root_dir     = os.path.dirname(script_dir)
        self.libraries_dir = os.path.join(root_dir, "component_libraries")
        os.makedirs(self.libraries_dir, exist_ok=True)

        # ---------- helper: filtering ------------------------------------------
        def _apply_filter(pattern: str):
            pat = pattern.lower()

            def recurse(item):
                txt_match   = pat in item.text(0).lower()
                child_match = False
                for i in range(item.childCount()):
                    if recurse(item.child(i)):
                        child_match = True
                item.setHidden(not (txt_match or child_match))
                return txt_match or child_match

            for i in range(self.component_tree.topLevelItemCount()):
                recurse(self.component_tree.topLevelItem(i))

        # ---------- custom title-bar (label | filter | refresh) ----------------
        title = QWidget()
        hl    = QHBoxLayout(title)
        hl.setContentsMargins(6, 0, 6, 0)
        hl.setSpacing(4)

        lbl = QLabel(self.tr("Components"))
        hl.addWidget(lbl)

        self.components_filter = QLineEdit()
        self.components_filter.setPlaceholderText(self.tr("Filter…"))
        self.components_filter.textChanged.connect(_apply_filter)
        self.components_filter.setFixedWidth(110)
        hl.addWidget(self.components_filter)

        btn_refresh = QToolButton()
        btn_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        btn_refresh.setToolTip(self.tr("Rescan component_libraries"))
        btn_refresh.clicked.connect(self.refresh_component_tree)
        hl.addWidget(btn_refresh)

        self.components_dock.setTitleBarWidget(title)

        # ---------- initial populate -------------------------------------------
        self.refresh_component_tree()



    def refresh_component_tree(self):
        """
        Clears and re-populates the component tree, so newly exported footprints show up immediately.
        """
        self.component_tree.clear()
        if not self.libraries_dir or not os.path.exists(self.libraries_dir):
            return

        root_item = QTreeWidgetItem(self.component_tree, ["component_libraries"])
        root_item.setData(0, Qt.UserRole, self.libraries_dir)
        self.populate_component_tree(root_item, self.libraries_dir)



    def on_component_tree_item_double_clicked(self, item, column):
        path = item.data(0, Qt.UserRole)
        if not path or not os.path.isfile(path):
            return
        if not path.lower().endswith(".nod"):
            QMessageBox.information(self, "Info", f"'{path}' is not a .nod file.")
            return

        self.log.log("info", f"Double-clicked .nod file: {path}")
        footprint = get_footprint_for_placer(path)
        if footprint and "pads" in footprint:
            self.component_placer.footprint = footprint
            # Set the nod_file property on the ComponentPlacer so its base name is used
            from objects.nod_file import BoardNodFile
            self.component_placer.nod_file = BoardNodFile(nod_path=path)
            self.component_placer.activate_placement()
        else:
            QMessageBox.warning(self, "Error", f"Failed to parse .nod file from {path}.")


    def on_component_placed(self, component_name: str):
        QMessageBox.information(
            self,
            "Component Placed",
            f"The component '{component_name}' was placed successfully."
        )


    def populate_component_tree(self, parent_item, directory: str):
        try:
            entries = sorted(os.listdir(directory))
        except FileNotFoundError:
            return

        for entry in entries:
            full_path = os.path.join(directory, entry)
            if os.path.isdir(full_path):
                folder_item = QTreeWidgetItem([entry])
                folder_item.setData(0, Qt.UserRole, full_path)
                parent_item.addChild(folder_item)
                self.populate_component_tree(folder_item, full_path)
            elif entry.lower().endswith(".nod"):
                file_item = QTreeWidgetItem([entry])
                file_item.setData(0, Qt.UserRole, full_path)
                parent_item.addChild(file_item)
        parent_item.setExpanded(True)



    # --------------------------------------------------------------------------
    #  Zoom updates and side-switch logic
    # --------------------------------------------------------------------------
    def update_zoom_center_mode(self, index):
        mode = "mouse" if index == 0 else "marker"
        self.constants.set("zoom_center_mode", mode)
        self.constants.save()
        self.log.log("info", f"Zoom center mode changed to {mode}.")

    def update_zoom_level_label(self):
        if not self.board_view or not self.board_view.zoom_manager:
            self.zoom_level_label.setText("Zoom: N/A")
            self.log.log("debug", "ZoomManager not available. Zoom level label set to N/A.")
            return

        min_scale = self.board_view.zoom_manager.min_user_scale
        current_scale = self.board_view.zoom_manager.user_scale
        max_scale = self.board_view.zoom_manager.max_user_scale
        zoom_percentage = current_scale * 100

        self.zoom_level_label.setText(f"Zoom: {zoom_percentage:.0f}%")
        self.log.log("debug", f"Zoom Levels - Min: {min_scale}, Current: {current_scale}, Max: {max_scale}")

    def on_switch_side(self):
        self.log.log("info", "Switch Side button clicked.")
        self.board_view.switch_side()
        # After switching, update the working side label.
        current_side = self.board_view.flags.get_flag("side", "top").capitalize()
        self.working_side_label.setText(f"Working Side: {current_side}")

    def open_search_dialog(self):
        self.log.log("info", "Opening Search Dialog.")
        # Pass the QTextBrowser widget from the PropertiesDock that displays selected pins info.
        search_dialog = SearchDialog(
            board_view=self.board_view,
            selected_pins_widget=self.properties_dock.selected_pins_info_tab,
            parent=self
        )
        if search_dialog.exec_() == QDialog.Accepted:
            self.log.log("info", "Search Dialog completed successfully.")
        else:
            self.log.log("info", "Search Dialog was canceled.")



    # --------------------------------------------------------------------------
    #  Create the Properties Dock (for selected pins info)
    # --------------------------------------------------------------------------
    def create_properties_dock(self):
        """
        Creates a bottom dock widget with a tab for 'Selected Pins'
        that displays info (as HTML) about the currently selected pads.
        When no pads are selected, it shows the last clicked coordinates and side.
        """
        from PyQt5.QtWidgets import QTextBrowser  # Ensure QTextBrowser is imported

        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.properties_tabs = QTabWidget()
        self.properties_dock.setWidget(self.properties_tabs)

        # Create a single tab named "Selected Pins" with a QTextBrowser.
        self.selected_pins_tab = QWidget()
        layout = QVBoxLayout()
        
        self.selected_pins_info_tab = QTextBrowser()
        self.selected_pins_info_tab.setMinimumHeight(20)  # Set reduced height
        self.selected_pins_info_tab.setMaximumHeight(50)  # Prevent it from being too large
        layout.addWidget(self.selected_pins_info_tab)
        
        self.selected_pins_tab.setLayout(layout)
        self.properties_tabs.addTab(self.selected_pins_tab, "Selected Pins")
        
        # Add dock widget to the bottom area
        self.addDockWidget(Qt.BottomDockWidgetArea, self.properties_dock)

        # Reduce the initial size of the dock
        self.properties_dock.setFixedHeight(80)  # Adjust to make the tab half the previous size

    def update_selected_pins_info(self, selected_pads):
        """
        Updates the 'Selected Pins' tab in the Properties dock with information
        about the currently selected pads. This function uses the BoardView’s
        last clicked coordinate and current side.
        """
        from ui.selected_pins_info import generate_selected_pins_html
        html = generate_selected_pins_html(
            selected_pads,
            self.board_view.last_clicked_mm,
            self.board_view.flags.get_flag("side", "top")
        )
        # Forward to the dock:
        self.properties_dock.update_selected_pins_info(html)


    def create_font_controls(self):
        """
        Creates two actions (A+ and A-) to increase or decrease the font size
        used in the Selected Pins tab. These actions are added to the View menu.
        The selected font size is stored in the constants.
        """
        increase_font_action = QAction("A+", self)
        decrease_font_action = QAction("A-", self)
        increase_font_action.triggered.connect(self.on_increase_pins_font_size)
        decrease_font_action.triggered.connect(self.on_decrease_pins_font_size)
        
        # Find or create the View menu
        view_menu = self.menuBar().findChild(QMenu, "View")
        if view_menu is None:
            view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(increase_font_action)
        view_menu.addAction(decrease_font_action)

    def on_increase_pins_font_size(self):
        fs = self.constants.get("pins_font_size", 14)
        if fs < 72:  # maximum font size limit
            fs += 1
        self.constants.set("pins_font_size", fs)
        self.constants.save()
        # Refresh display using the stored selection (or empty list if none)
        self.update_selected_pins_info(self.current_selected_pads if hasattr(self, 'current_selected_pads') else [])

    def on_decrease_pins_font_size(self):
        fs = self.constants.get("pins_font_size", 14)
        if fs > 6:  # minimum font size limit
            fs -= 1
        self.constants.set("pins_font_size", fs)
        self.constants.save()
        # Refresh display using the stored selection (or empty list if none)
        self.update_selected_pins_info(self.current_selected_pads if hasattr(self, 'current_selected_pads') else [])


    def closeEvent(self, event):
        """
        Checks if undo/redo stack is non-empty before closing.
        Asks user whether to save changes, discard changes, or cancel quit.
        """
        # 1) Check if the ObjectLibrary's undo stack has any entries
        undo_manager = self.object_library.undo_redo_manager
        if undo_manager.undo_stack or undo_manager.redo_stack:
            response = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Would you like to save before quitting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )

            if response == QMessageBox.Yes:
                # Call the existing save flow
                self.project_manager.save_project_dialog()
                # If user cancels inside save_project_dialog, you can decide whether to close anyway
                # For now, assume user’s acceptance = proceed with close
                event.accept()
            elif response == QMessageBox.No:
                event.accept()  # user discards changes
            else:
                # response == QMessageBox.Cancel
                event.ignore()  # Do not close the app
        else:
            # Undo stack is empty => no unsaved changes
            event.accept()


    def open_ui_customization_dialog(self):
        dialog = UICustomizationDialog(self.constants, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            # User clicked OK => retrieve the chosen sizes
            new_toolbar_size = dialog.get_toolbar_font_size()
            new_statusbar_size = dialog.get_statusbar_font_size()
            new_tab_size = dialog.get_tab_font_size()

            # Save to constants
            self.constants.set("toolbar_font_size", new_toolbar_size)
            self.constants.set("statusbar_font_size", new_statusbar_size)
            self.constants.set("tab_font_size", new_tab_size)
            self.constants.save()

            # Apply them immediately
            self.apply_individual_fonts()

    def apply_individual_fonts(self):
        """
        Applies each stored font size to its respective widget,
        using the values from the constants.
        """
        # Retrieve the font sizes from constants
        toolbar_font_size = self.constants.get("toolbar_font_size", 10)
        statusbar_font_size = self.constants.get("statusbar_font_size", 10)
        tab_font_size = self.constants.get("tab_font_size", 10)

        from PyQt5.QtGui import QFont

        # Toolbar font
        toolbar_font = QFont()
        toolbar_font.setPointSize(toolbar_font_size)
        for tb in self.findChildren(QToolBar):
            tb.setFont(toolbar_font)

        # Status bar font
        statusbar_font = QFont()
        statusbar_font.setPointSize(statusbar_font_size)
        self.status_bar.setFont(statusbar_font)
        self.project_name_label.setFont(statusbar_font)
        self.pad_info_label.setFont(statusbar_font)

        # Tab widget font - note we changed this line to reference the dock's tab widget:
        tab_font = QFont()
        tab_font.setPointSize(tab_font_size)
        self.properties_dock.properties_tabs.setFont(tab_font)

        self.log.log("info",
                    f"Applied fonts => Toolbar: {toolbar_font_size}, "
                    f"Statusbar: {statusbar_font_size}, Tabs: {tab_font_size}.")
        self.updateGeometry()

    def create_properties_dock(self):
        """
        Just instantiate your custom PropertiesDock and add it to the bottom area.
        """
        self.properties_dock = PropertiesDock(
            constants=self.constants,
            log=self.log,
            parent=self
        )
        self.addDockWidget(Qt.BottomDockWidgetArea, self.properties_dock)

    def showEvent(self, event):
        super().showEvent(event)
        self.restore_properties_dock_size()

    def restore_properties_dock_size(self):
        """
        Attempt to give the PropertiesDock the saved height from constants
        by calling QMainWindow.resizeDocks().
        """
        saved_height = self.constants.get("properties_dock_height", 104)
        # Note that 'resizeDocks' wants a list of docks and a list of sizes:
        self.resizeDocks([self.properties_dock], [saved_height], Qt.Vertical)
        self.log.debug(f"[restore_properties_dock_size] Applied saved height={saved_height}")

    def set_auto_save_threshold(self):
        # Retrieve the current value from constants; default to 20 if not set.
        current_value = self.constants.get("auto_save_threshold", 20)
        # Open a dialog for the user to input an integer between 1 and 100.
        value, ok = QInputDialog.getInt(
            self,
            "Auto-Save Threshold",
            "Enter new auto-save threshold (number of bulk actions before auto-saving):",
            current_value,
            1,
            100
        )
        if ok:
            self.constants.set("auto_save_threshold", value)
            self.constants.save()
            self.log.log("info", f"Auto-Save Threshold changed to {value}")
            # (Optionally, update any local thresholds in your ProjectManager if needed.)

    def align_pads_action(self):
        """
        Called when the user selects "Align Pads" from the Edit menu.
        It retrieves the selected pads from the BoardView and calls align_selected_pads.
        """
        selected_pads = self.board_view._get_selected_pads()
        if not selected_pads:
            QMessageBox.information(self, "Align Pads", "No pads selected for alignment.")
            return
        try:
            actions.align_selected_pads(self.object_library, selected_pads, self.component_placer)
        except Exception as e:
            self.log.log("error", f"Error during Align Pads action: {e}")

    def set_pixels_per_mm(self):
        """
        Prompts the user to set a new pixels-to-mm conversion ratio.
        Updates the constants and refreshes related UI components in real time.
        """
        current_value = self.constants.get("pixels_per_mm", 30.0)
        # Using QInputDialog.getDouble to allow decimal input.
        new_value, ok = QInputDialog.getDouble(
            self,
            "Set Pixels Per MM",
            "Enter new pixels per mm ratio:",
            value=current_value,
            min=0.00001,  # minimum acceptable ratio (adjust as needed)
            max=10000000.0,
            decimals=10
        )
        if ok:
            # Update constants
            self.constants.set("pixels_per_mm", new_value)
            self.constants.save()
            self.pixels_per_mm = new_value

            # Update BoardView’s local copy
            self.board_view.pixels_per_mm = new_value

            # Update the DisplayLibrary instance that uses the conversion ratio.
            self.board_view.display_library.pixels_per_mm = new_value

            # If your CoordinateConverter needs to know about the ratio, update it.
            # (Assuming you add a setter method in your CoordinateConverter.)
            if hasattr(self.board_view.converter, "set_pixels_per_mm"):
                self.board_view.converter.set_pixels_per_mm(new_value)

            self.log.log("info", f"Pixels per mm ratio updated to {new_value}.")

            # Optionally trigger a refresh of the scene if necessary.
            self.board_view.fit_in_view()

    def open_bom_editor(self):
        """
        Opens the BOM editor dialog to allow manual editing of the BOM.
        It retrieves the board's component names from the ObjectLibrary and
        determines an official BOM CSV path (using the current project folder if set).
        If the BOM editor dialog is accepted, the BOM is saved to disk.
        """
        # Determine official CSV path: if a project is loaded, use its BOM file; otherwise prompt for one.
        if self.current_project_path and self.current_project_path.strip().lower() != "[none]":
            bom_path = os.path.join(self.current_project_path, "project_bom.csv")
        else:
            bom_path, _ = QFileDialog.getSaveFileName(
                self, "Select BOM CSV File", "", "CSV Files (*.csv)"
            )
            if not bom_path:
                self.log.log("info", "BOM editing canceled: No CSV file selected.", module="MainWindow", func="open_bom_editor")
                return

        # Retrieve the current board component names from the ObjectLibrary.
        board_set = set([obj.component_name for obj in self.object_library.get_all_objects()])

        # Open the BOMEditorDialog directly, regardless of mismatches.
        from component_placer.bom_handler.bom_editor_dialog import BOMEditorDialog
        dialog = BOMEditorDialog(
            bom_handler=self.bom_handler,
            board_component_names=board_set,
            parent=self
        )
        if dialog.exec_() == dialog.Accepted:
            # If accepted, save the updated BOM.
            if self.bom_handler.save_bom(bom_path):
                self.log.log("info", f"BOM updated and saved to {bom_path}.", module="MainWindow", func="open_bom_editor")
                QMessageBox.information(self, "BOM Updated", f"BOM saved successfully to:\n{bom_path}")
            else:
                self.log.log("warning", "Failed to save updated BOM after editing.", module="MainWindow", func="open_bom_editor")
                QMessageBox.warning(self, "BOM Update Failed", "BOM editing completed but saving failed.")
        else:
            self.log.log("info", "User canceled BOM editing. BOM remains unchanged.", module="MainWindow", func="open_bom_editor")


    def set_mm_per_pixels_top(self):
        """
        Prompts the user to set a new mm_per_pixels_top value using a custom QInputDialog
        in text mode with a QDoubleValidator set to ScientificNotation.
        """
        current_value = self.constants.get("mm_per_pixels_top", 0.0333)
        
        # Create a QInputDialog in text input mode
        dialog = QInputDialog(self)
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setWindowTitle("Set mm_per_pixels_top")
        dialog.setLabelText("Enter new mm_per_pixels_top (mm per pixel):")
        dialog.setTextValue(str(current_value))
        
        # Retrieve the embedded QLineEdit to set a validator and enable context menu
        line_edit = dialog.findChild(QLineEdit)
        if line_edit:
            validator = QDoubleValidator(1e-9, 1e6, 10, line_edit)
            # Set notation to ScientificNotation to accept inputs like 2.486912492e-002
            validator.setNotation(QDoubleValidator.ScientificNotation)
            line_edit.setValidator(validator)
            # Enable right-click context menu (for paste, etc.)
            line_edit.setContextMenuPolicy(Qt.DefaultContextMenu)
        
        # Execute the dialog and process input
        if dialog.exec_() == QDialog.Accepted:
            new_value_str = dialog.textValue().strip()
            try:
                new_value = float(new_value_str)
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", f"'{new_value_str}' is not a valid float.")
                return
            # Update the constants and save changes
            self.constants.set("mm_per_pixels_top", new_value)
            self.constants.save()
            if hasattr(self.board_view.converter, "set_mm_per_pixels_top"):
                self.board_view.converter.set_mm_per_pixels_top(new_value)
            # Refresh the scene so the new scale is visible
            self.board_view.update_scene()
            self.log.log("info", f"mm_per_pixels_top updated to {new_value:.10g} (user input).")


    def set_mm_per_pixels_bot(self):
        """
        Prompts the user to set a new mm_per_pixels_bot value using a custom QInputDialog
        in text mode with a QDoubleValidator set to ScientificNotation.
        """
        current_value = self.constants.get("mm_per_pixels_bot", 0.0333)
        
        dialog = QInputDialog(self)
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setWindowTitle("Set mm_per_pixels_bot")
        dialog.setLabelText("Enter new mm_per_pixels_bot (mm per pixel):")
        dialog.setTextValue(str(current_value))
        
        line_edit = dialog.findChild(QLineEdit)
        if line_edit:
            from PyQt5.QtGui import QDoubleValidator
            validator = QDoubleValidator(1e-9, 1e6, 10, line_edit)
            validator.setNotation(QDoubleValidator.ScientificNotation)
            line_edit.setValidator(validator)
            line_edit.setContextMenuPolicy(Qt.DefaultContextMenu)
        
        if dialog.exec_() == QDialog.Accepted:
            new_value_str = dialog.textValue().strip()
            try:
                new_value = float(new_value_str)
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", f"'{new_value_str}' is not a valid float.")
                return
            self.constants.set("mm_per_pixels_bot", new_value)
            self.constants.save()
            if hasattr(self.board_view.converter, "set_mm_per_pixels_bot"):
                self.board_view.converter.set_mm_per_pixels_bot(new_value)
            self.board_view.update_scene()
            self.log.log("info", f"mm_per_pixels_bot updated to {new_value:.10g} (user input).")

    def update_working_side_label(self):
        """Refreshes the fixed-width label that shows the current board side."""
        current_side = self.board_view.flags.get_flag("side", "top").capitalize()
        # pad text to constant width (5 chars = 'Top  ' / 'Bottom')
        txt = f"Side: {current_side:<6}"
        self.working_side_label.setText(txt)
