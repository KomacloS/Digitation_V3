# utils/file_ops.py
import os, pathlib, shutil, tempfile
import time
from typing import Optional
from logs.log_handler import LogHandler
from constants.constants import Constants

log = LogHandler()

def safe_write(target_path: str, data: str, encoding: str = "utf-8") -> bool:
    """
    Atomically write *data* to *target_path*.
    Returns True on success, False on failure (and leaves the old file intact).
    """
    target_path = os.path.abspath(target_path)
    dir_ = os.path.dirname(target_path)
    try:
        # 1) write to a tmp file in the same dir
        with tempfile.NamedTemporaryFile("w",
                                         encoding=encoding,
                                         dir=dir_,
                                         delete=False,
                                         prefix=".tmp_",
                                         suffix=".nod") as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())      # force to disk
            temp_name = tmp.name
        # 2) atomic replace
        os.replace(temp_name, target_path)      # atomic on Win / POSIX
        return True
    except Exception as e:
        log.error(f"safe_write() failed for {target_path}: {e}")
        try:
            if os.path.exists(temp_name):
                os.remove(temp_name)
        except Exception:
            pass
        return False


# utils/file_ops.py
def rotate_backups(file_path: str,
                   max_backups: int | None = None,
                   fixed_ts: str | None = None) -> None:
    """
    Copy *file_path* to the backup tree, naming it
        <filename>.<YYYYmmdd_HHMMSS>.bak
    If *fixed_ts* is supplied, that exact stamp is used for the copy; otherwise
    datetime.now() is used.  *max_backups* (defaults to constants["max_backups"]
    or 5) prunes older copies.
    """
    try:
        if not os.path.exists(file_path):
            return                                # nothing to back up

        const = Constants()
        if max_backups is None:
            max_backups = int(const.get("max_backups", 5) or 5)

        central_dir = str(const.get("central_backup_dir") or "").strip()
        if not central_dir:
            central_dir = os.path.join(os.path.dirname(file_path), "backups")

        project_name = pathlib.Path(file_path).parent.name
        b_dir = os.path.join(central_dir, project_name)
        os.makedirs(b_dir, exist_ok=True)

        ts   = fixed_ts or time.strftime("%Y%m%d_%H%M%S")
        base = pathlib.Path(file_path).name
        dst  = os.path.join(b_dir, f"{base}.{ts}.bak")

        shutil.copy2(file_path, dst)

        # prune
        backups = sorted(pathlib.Path(b_dir).glob(f"{base}.*.bak"),
                         key=lambda p: p.stat().st_mtime,
                         reverse=True)
        for old in backups[max_backups:]:
            old.unlink(missing_ok=True)

    except Exception as e:
        log.warning(f"rotate_backups(): could not back up '{file_path}': {e}")
