from __future__ import annotations

import tkinter as tk
from ttkbootstrap import ttk


class BaseDialog(tk.Toplevel):
    """Common OK/Cancel dialog with modal behavior."""

    def __init__(self, parent: tk.Misc | None = None, title: str = "") -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.result = False

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.main = ttk.Frame(self)
        self.main.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=1, column=0, sticky="e", padx=10, pady=(0, 10))
        self.ok_button = ttk.Button(btn_frame, text="OK", command=self.on_ok)
        self.ok_button.grid(row=0, column=0, padx=5)
        self.cancel_button = ttk.Button(
            btn_frame, text="Cancel", command=self.on_cancel
        )
        self.cancel_button.grid(row=0, column=1)

        self.bind("<Return>", lambda _e: self.on_ok())
        self.bind("<Escape>", lambda _e: self.on_cancel())

    # ------------------------------------------------------------------
    def show(self) -> bool:
        """Displays the dialog modally and returns True if OK was pressed."""
        self.wait_window()
        return self.result

    # ------------------------------------------------------------------
    def on_ok(self) -> None:
        self.result = True
        self.destroy()

    def on_cancel(self) -> None:
        self.result = False
        self.destroy()
