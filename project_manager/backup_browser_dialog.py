# project_manager/backup_browser_dialog.py

from PyQt5.QtWidgets import (
    QDialog, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt
import re, os, glob, shutil, datetime

class BackupBrowserDialog(QDialog):
    def __init__(self, project_dir, backup_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Backup")
        self.resize(700, 320)

        self.proj_dir   = project_dir
        self.backup_dir = backup_dir

        self.table = QTableWidget(self)
        self.table.setColumnCount(6)                 # 6 columns now
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.restore_btn = QPushButton("Restore", self)
        self.restore_btn.clicked.connect(self._restore_selected)

        lay = QVBoxLayout(self)
        lay.addWidget(self.table)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.restore_btn)
        lay.addLayout(btn_row)

        # -------- build index and fill the table ----------
        self._build_version_index()
        self._populate_table()


# ------------------------------------------------------------------
# 2.  helper: build self.versions + self.sorted_ts
# ------------------------------------------------------------------
    TIMESTAMP_RX = re.compile(r"\.(\d{8}_\d{6})\.bak$")

    def _build_version_index(self):
        """
        Build:
            self.versions  : ts -> {"nod": path, "bom": path, "alf": path,
                                    "pads": int, "comps": int}
            self.sorted_ts : newest‑first list of ts strings
        """
        versions = {}
        for path in glob.glob(os.path.join(self.backup_dir, "*.bak")):
            m = self.TIMESTAMP_RX.search(path)
            if not m:
                continue
            ts = m.group(1)
            bucket = versions.setdefault(ts, {"pads": None, "comps": None})
            fname = os.path.basename(path)
            if fname.startswith("project.nod"):
                bucket["nod"] = path
                bucket["pads"] = self._count_pads(path)
            elif fname.startswith("project_bom.csv"):
                bucket["bom"] = path
                bucket["comps"] = self._count_components(path)
            elif fname.startswith("project.alf"):
                bucket["alf"] = path
        self.versions  = versions
        self.sorted_ts = sorted(versions.keys(), reverse=True)

    # helpers -------------------------------------------------------
    def _count_pads(self, nod_path: str) -> int:
        """Lines (pads) minus the header '* SIGNAL…'."""
        try:
            with open(nod_path, "r", encoding="utf‑8", errors="ignore") as f:
                return max(0, sum(1 for _ in f) - 1)
        except Exception:
            return 0

    def _count_components(self, bom_path: str) -> int:
        """Rows minus the CSV header."""
        try:
            with open(bom_path, "r", encoding="utf‑8", errors="ignore") as f:
                return max(0, sum(1 for _ in f) - 1)
        except Exception:
            return 0


# ------------------------------------------------------------------
# 3.  populate table from self.sorted_ts
# ------------------------------------------------------------------
    def _populate_table(self):
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Timestamp", "NOD", "BOM", "ALF", "Comp", "Pads"]
        )

        self.table.setRowCount(len(self.sorted_ts))
        for row, ts in enumerate(self.sorted_ts):
            dt = datetime.datetime.strptime(ts, "%Y%m%d_%H%M%S")
            self.table.setItem(row, 0, QTableWidgetItem(dt.strftime("%Y‑%m‑%d  %H:%M:%S")))

            v = self.versions[ts]
            self.table.setItem(row, 1, QTableWidgetItem("✓" if "nod" in v else "—"))
            self.table.setItem(row, 2, QTableWidgetItem("✓" if "bom" in v else "—"))
            self.table.setItem(row, 3, QTableWidgetItem("✓" if "alf" in v else "—"))

            comps = str(v.get("comps", "")) if v.get("comps") is not None else ""
            pads  = str(v.get("pads", ""))  if v.get("pads")  is not None else ""
            self.table.setItem(row, 4, QTableWidgetItem(comps))
            self.table.setItem(row, 5, QTableWidgetItem(pads))

            self.table.setRowHeight(row, 22)

        self.table.selectRow(0)

        # ── column widths & resize policy ────────────────────────────
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)      # Timestamp
        for col in (1, 2, 3):                                 # ✓/— columns
            hdr.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, 40)
        for col in (4, 5):                                    # Comp, Pads
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
            self.table.setMinimumWidth(700)                   # keep dialog wide

# ------------------------------------------------------------------
#  Restore every file that belongs to the selected timestamp
# ------------------------------------------------------------------
    def _restore_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return

        ts = self.sorted_ts[row]          # timestamp string
        files = self.versions[ts]         # {"nod": …, "bom": …, "alf": …}

        msg = (f"Restore the project files saved on "
               f"{self.table.item(row, 0).text()}?\n"
               f"The current files will be renamed *.prev‑<timestamp>.")
        if QMessageBox.question(self, "Confirm Restore", msg) != QMessageBox.Yes:
            return

        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        def replace(src_bak, live_name):
            live_path = os.path.join(self.proj_dir, live_name)
            if os.path.exists(live_path):
                shutil.move(live_path, f"{live_path}.prev-{now}")
            shutil.copy2(src_bak, live_path)

        if "nod" in files:
            replace(files["nod"], "project.nod")
        if "bom" in files:
            replace(files["bom"], "project_bom.csv")
        if "alf" in files:
            replace(files["alf"], "project.alf")

        self.accept()               # caller reloads the project