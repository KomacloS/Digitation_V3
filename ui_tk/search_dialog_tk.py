from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from ttkbootstrap import Style, ttk

from objects.board_object import BoardObject
from objects.search_library import SearchLibrary
from ui.selected_pins_info import update_properties_tab

from .base_dialog import BaseDialog


class SearchDialogTk(BaseDialog):
    """Tkinter-based replacement for the PyQt5 SearchDialog."""

    last_searched_pad: BoardObject | None = None

    def __init__(self, board_view, selected_pins_widget, parent=None):
        Style(theme="cyborg")
        super().__init__(parent, title="Search Pad")

        self.board_view = board_view
        self.selected_pins_widget = selected_pins_widget
        self.search_library = SearchLibrary(object_library=board_view.object_library)

        self.component_var = tk.StringVar()
        self.pin_var = tk.StringVar()
        self.signal_var = tk.StringVar()
        self.channel_var = tk.StringVar()

        self._build_form()
        self._populate_initial_lists()
        self.validate_all()

    # ------------------------------------------------------------------
    def _build_form(self) -> None:
        frm = self.main
        frm.columnconfigure(1, weight=1)

        self.comp_box = ttk.Combobox(frm, textvariable=self.component_var)
        ttk.Label(frm, text="Component:").grid(
            row=0, column=0, sticky="e", padx=5, pady=3
        )
        self.comp_box.grid(row=0, column=1, sticky="we", padx=5, pady=3)

        self.pin_box = ttk.Combobox(frm, textvariable=self.pin_var, state="disabled")
        ttk.Label(frm, text="Pin:").grid(row=1, column=0, sticky="e", padx=5, pady=3)
        self.pin_box.grid(row=1, column=1, sticky="we", padx=5, pady=3)

        self.signal_box = ttk.Combobox(frm, textvariable=self.signal_var)
        ttk.Label(frm, text="Signal:").grid(row=2, column=0, sticky="e", padx=5, pady=3)
        self.signal_box.grid(row=2, column=1, sticky="we", padx=5, pady=3)

        self.channel_box = ttk.Combobox(frm, textvariable=self.channel_var)
        ttk.Label(frm, text="Channel:").grid(
            row=3, column=0, sticky="e", padx=5, pady=3
        )
        self.channel_box.grid(row=3, column=1, sticky="we", padx=5, pady=3)

        self.component_var.trace_add("write", lambda *_: self._on_component_change())
        self.pin_var.trace_add("write", lambda *_: self._on_pin_change())
        self.signal_var.trace_add("write", lambda *_: self._on_signal_change())
        self.channel_var.trace_add("write", lambda *_: self.validate_all())

    # ------------------------------------------------------------------
    def _populate_initial_lists(self) -> None:
        self.comp_list = self.search_library.get_components()
        self.comp_box.configure(values=self.comp_list)

    # ------------------------------------------------------------------
    def _on_component_change(self) -> None:
        comp = self.component_var.get().strip()
        if comp:
            self.pin_list = self.search_library.get_pins(comp)
            self.pin_box.configure(
                values=self.pin_list, state="normal" if self.pin_list else "disabled"
            )
        else:
            self.pin_list = []
            self.pin_box.configure(values=self.pin_list, state="disabled")
        self.validate_all()

    # ------------------------------------------------------------------
    def _on_pin_change(self) -> None:
        comp = self.component_var.get().strip()
        pin = self.pin_var.get().strip()
        if comp and pin:
            self.signal_list = self.search_library.get_signals(comp, pin)
            self.signal_box.configure(values=self.signal_list)
        else:
            self.signal_list = []
            self.signal_box.configure(values=self.signal_list)
        self.validate_all()

    # ------------------------------------------------------------------
    def _on_signal_change(self) -> None:
        comp = self.component_var.get().strip()
        pin = self.pin_var.get().strip()
        signal = self.signal_var.get().strip()
        if comp and pin and signal:
            self.channel_list = self.search_library.get_channels(comp, pin, signal)
            self.channel_box.configure(values=self.channel_list)
        else:
            self.channel_list = []
            self.channel_box.configure(values=self.channel_list)
        self.validate_all()

    # ------------------------------------------------------------------
    def validate_all(self) -> bool:
        valid = True
        comp = self.component_var.get().strip()
        if comp not in self.comp_list:
            valid = False
        pin = self.pin_var.get().strip()
        if hasattr(self, "pin_list") and self.pin_list and pin not in self.pin_list:
            valid = False
        signal = self.signal_var.get().strip()
        if (
            hasattr(self, "signal_list")
            and self.signal_list
            and signal not in self.signal_list
        ):
            valid = False
        channel = self.channel_var.get().strip()
        if (
            hasattr(self, "channel_list")
            and self.channel_list
            and channel not in self.channel_list
        ):
            valid = False
        self.ok_button.configure(state="normal" if valid else "disabled")
        return valid

    # ------------------------------------------------------------------
    def on_ok(self) -> None:  # type: ignore[override]
        if not self.validate_all():
            messagebox.showinfo(self, "No match", "Please provide valid search values.")
            return

        channel_str = self.channel_var.get().strip()
        channel = int(channel_str) if channel_str.isdigit() else channel_str
        pad = self.search_library.find_pad(
            self.component_var.get().strip(),
            self.pin_var.get().strip(),
            self.signal_var.get().strip(),
            channel,
        )
        if not pad:
            messagebox.showinfo(
                self, "No match", "No matching pad found with those fields."
            )
            return

        self.place_marker(pad)
        update_properties_tab(
            found_pad=pad,
            pad_info_label=self.selected_pins_widget,
            last_clicked_mm=self.board_view.last_clicked_mm,
            side=self.board_view.flags.get_flag("side", "top"),
            log_handler=self.search_library.log,
        )
        SearchDialogTk.last_searched_pad = pad
        super().on_ok()

    # ------------------------------------------------------------------
    def place_marker(self, pad: BoardObject) -> None:
        side = pad.test_position.lower()
        if side not in ["top", "bottom"]:
            messagebox.showwarning(
                self,
                "Invalid Test Position",
                f"Pad's test position '{pad.test_position}' is invalid.",
            )
            return
        current_side = self.board_view.flags.get_flag("side", "top")
        if current_side != side:
            self.board_view.switch_side()
        try:
            self.board_view.marker_manager.place_marker(pad.x_coord_mm, pad.y_coord_mm)
            x_scene, y_scene = self.board_view.converter.mm_to_pixels(
                pad.x_coord_mm, pad.y_coord_mm
            )
            self.board_view.center_on(x_scene, y_scene)
        except Exception:
            messagebox.showerror(self, "Error", "Failed to place marker on the board.")
            return
