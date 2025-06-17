from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from ttkbootstrap import Style

from objects.board_object import BoardObject
from objects.search_library import SearchLibrary
from ui.selected_pins_info import update_properties_tab

from .base_dialog import BaseDialog
from .form_helpers import labeled_validated_combo


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

        self.comp_box = labeled_validated_combo(
            frm,
            "Component:",
            0,
            self.component_var,
            [],
            lambda v: v in getattr(self, "comp_list", []),
        )

        self.pin_box = labeled_validated_combo(
            frm,
            "Pin:",
            1,
            self.pin_var,
            [],
            lambda v: not getattr(self, "pin_list", []) or v in self.pin_list,
            state="disabled",
        )

        self.signal_box = labeled_validated_combo(
            frm,
            "Signal:",
            2,
            self.signal_var,
            [],
            lambda v: not getattr(self, "signal_list", []) or v in self.signal_list,
        )

        self.channel_box = labeled_validated_combo(
            frm,
            "Channel:",
            3,
            self.channel_var,
            [],
            lambda v: not getattr(self, "channel_list", []) or v in self.channel_list,
        )

        self.component_var.trace_add("write", lambda *_: self._on_component_change())
        self.pin_var.trace_add("write", lambda *_: self._on_pin_change())
        self.signal_var.trace_add("write", lambda *_: self._on_signal_change())
        self.channel_var.trace_add("write", lambda *_: self.validate_all())

    # ------------------------------------------------------------------
    def _populate_initial_lists(self) -> None:
        self.comp_list = self.search_library.get_components()
        self.comp_box.configure(values=self.comp_list)
        self.comp_box._on_change()

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
        self.pin_box._on_change()
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
        self.signal_box._on_change()
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
        self.channel_box._on_change()
        self.validate_all()

    # ------------------------------------------------------------------
    def validate_all(self) -> bool:
        valid = (
            self.comp_box.is_valid()
            and self.pin_box.is_valid()
            and self.signal_box.is_valid()
            and self.channel_box.is_valid()
        )
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
