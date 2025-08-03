import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import edit_pads.actions as actions  # noqa: E402
from objects.board_object import BoardObject  # noqa: E402


class FakeObjectLibrary:
    def __init__(self):
        self.updated = None

    def bulk_update_objects(self, updates, _):
        self.updated = updates


class FakeBoardView:
    pass


class FakeScene:
    def __init__(self):
        self._views = [FakeBoardView()]

    def views(self):
        return self._views


class FakePadItem:
    def __init__(self, board_object):
        self.board_object = board_object
        self._scene = FakeScene()

    def scene(self):
        return self._scene


def test_connect_pads_forces_largest_area(monkeypatch):
    obj_lib = FakeObjectLibrary()
    pad1 = FakePadItem(
        BoardObject(
            "C1",
            1,
            channel=1,
            signal="SIG1",
            width_mm=1,
            height_mm=1,
            testability="Terminal",
        )
    )
    pad2 = FakePadItem(
        BoardObject(
            "C1",
            2,
            channel=2,
            signal="SIG2",
            width_mm=2,
            height_mm=2,
            testability="Forced",
        )
    )
    pad3 = FakePadItem(
        BoardObject(
            "C1",
            3,
            channel=3,
            signal="SIG3",
            width_mm=3,
            height_mm=3,
            testability="Terminal",
        )
    )
    pads = [pad1, pad2, pad3]
    monkeypatch.setattr(actions, "_update_scene", lambda *args, **kwargs: None)

    actions.connect_pads(obj_lib, pads)

    forced = [o for o in obj_lib.updated if o.testability == "Forced"]
    assert len(forced) == 1
    assert forced[0].width_mm == 3 and forced[0].height_mm == 3
    assert all(o.signal == "SIG3" for o in obj_lib.updated)

    non_forced = [o for o in obj_lib.updated if o is not forced[0]]
    assert all(o.testability == "Terminal" for o in non_forced)
