from __future__ import annotations

from ttkbootstrap import ttk
from ttkbootstrap.tooltip import ToolTip


class ValidatedEntry(ttk.Entry):
    def __init__(self, parent, textvariable=None, validate_func=None, **kwargs):
        super().__init__(parent, textvariable=textvariable, **kwargs)
        self.validate_func = validate_func
        self._tooltip = ToolTip(self, text="")
        self.bind("<KeyRelease>", self._on_change)
        self.bind("<FocusOut>", self._on_change)

    def _on_change(self, _event=None):
        if self.validate_func is None:
            return
        valid = self.validate_func(self.get())
        if valid:
            self.configure(bootstyle="")
            self._tooltip.hide()
        else:
            self.configure(bootstyle="danger")
            self._tooltip.text = "Invalid value"
            self._tooltip.show()

    def is_valid(self) -> bool:
        if self.validate_func is None:
            return True
        return self.validate_func(self.get())


class ValidatedCombobox(ttk.Combobox):
    """Combobox that highlights invalid input."""

    def __init__(self, parent, textvariable=None, validate_func=None, **kwargs):
        super().__init__(parent, textvariable=textvariable, **kwargs)
        self.validate_func = validate_func
        self._tooltip = ToolTip(self, text="")
        self.bind("<<ComboboxSelected>>", self._on_change)
        self.bind("<KeyRelease>", self._on_change)
        self.bind("<FocusOut>", self._on_change)

    def _on_change(self, _event=None):
        if self.validate_func is None:
            return
        valid = self.validate_func(self.get())
        if valid:
            self.configure(bootstyle="")
            self._tooltip.hide()
        else:
            self.configure(bootstyle="danger")
            self._tooltip.text = "Invalid value"
            self._tooltip.show()

    def is_valid(self) -> bool:
        if self.validate_func is None:
            return True
        return self.validate_func(self.get())


def labeled_validated_entry(parent, label, row, variable, validator):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=5, pady=3)
    entry = ValidatedEntry(parent, textvariable=variable, validate_func=validator)
    entry.grid(row=row, column=1, sticky="we", padx=5, pady=3)
    parent.grid_rowconfigure(row, weight=0)
    parent.grid_columnconfigure(1, weight=1)
    return entry


def labeled_validated_combo(parent, label, row, variable, values, validator, **kwargs):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=5, pady=3)
    combo = ValidatedCombobox(
        parent,
        textvariable=variable,
        validate_func=validator,
        values=values,
        **kwargs,
    )
    combo.grid(row=row, column=1, sticky="we", padx=5, pady=3)
    parent.grid_rowconfigure(row, weight=0)
    parent.grid_columnconfigure(1, weight=1)
    return combo
