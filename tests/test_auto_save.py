import builtins
from types import SimpleNamespace
import os

from logs.log_handler import LogHandler
from objects.object_library import ObjectLibrary
from project_manager.project_manager import ProjectManager
from component_placer.bom_handler.bom_handler import BOMHandler
from objects.nod_file import BoardNodFile


def test_auto_save_trigger(tmp_path, monkeypatch):
    log = LogHandler()
    obj_lib = ObjectLibrary()
    constants = SimpleNamespace(
        get=lambda k, d=None: d, set=lambda k, v: None, save=lambda: None
    )
    main_window = SimpleNamespace(
        log=log,
        object_library=obj_lib,
        current_project_path=str(tmp_path),
        constants=constants,
    )
    pm = ProjectManager(main_window, bom_handler=BOMHandler())
    pm.project_loaded = True
    pm.auto_save_threshold = 2

    saved = {"count": 0}

    def fake_save(self, backup=False, logger=None, fixed_ts=None):
        saved["count"] += 1
        return True

    monkeypatch.setattr(BoardNodFile, "save", fake_save)
    monkeypatch.setattr(BoardNodFile, "save_with_logging", fake_save, raising=False)

    pm.handle_bulk_operation_completed("Bulk Add")
    assert saved["count"] == 0
    pm.handle_bulk_operation_completed("Bulk Add")
    assert saved["count"] == 1
    assert pm.auto_save_counter == 0


def test_auto_save_via_object_library(tmp_path, monkeypatch):
    log = LogHandler()
    obj_lib = ObjectLibrary()
    constants = SimpleNamespace(
        get=lambda k, d=None: d, set=lambda k, v: None, save=lambda: None
    )
    main_window = SimpleNamespace(
        log=log,
        object_library=obj_lib,
        current_project_path=str(tmp_path),
        constants=constants,
    )
    pm = ProjectManager(main_window, bom_handler=BOMHandler())
    pm.project_loaded = True
    pm.auto_save_threshold = 2

    saved = {"count": 0}

    def fake_save(self, backup=False, logger=None, fixed_ts=None):
        saved["count"] += 1
        return True

    monkeypatch.setattr(BoardNodFile, "save", fake_save)

    from objects.board_object import BoardObject

    obj = BoardObject("C1", 1)

    obj_lib.bulk_add([obj], skip_render=True)
    assert saved["count"] == 0
    obj_lib.bulk_add([obj], skip_render=True)
    assert saved["count"] == 1
    assert pm.auto_save_counter == 0
