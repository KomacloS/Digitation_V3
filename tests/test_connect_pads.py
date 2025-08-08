import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import edit_pads.actions as actions  # noqa: E402
from objects.board_object import BoardObject  # noqa: E402


class FakeObjectLibrary:
    def __init__(self, objs=None):
        self.updated = None
        self.objects = {}
        if objs:
            self.objects = {obj.channel: obj for obj in objs}

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


def test_connect_pads_reduces_existing_forced(monkeypatch):
    """Connecting pads to a signal with existing forced pads leaves only one forced."""
    pad1 = FakePadItem(
        BoardObject(
            "C1",
            1,
            channel=1,
            signal="S30",
            width_mm=1,
            height_mm=1,
            testability="Forced",
        )
    )
    pad2 = FakePadItem(
        BoardObject(
            "C1",
            2,
            channel=2,
            signal="S30",
            width_mm=1,
            height_mm=1,
            testability="Terminal",
        )
    )
    pad3 = FakePadItem(
        BoardObject(
            "C1",
            3,
            channel=3,
            signal="S31",
            width_mm=3,
            height_mm=3,
            testability="Forced",
        )
    )
    pad4 = FakePadItem(
        BoardObject(
            "C1",
            4,
            channel=4,
            signal="S31",
            width_mm=2,
            height_mm=2,
            testability="Terminal",
        )
    )

    obj_lib = FakeObjectLibrary(
        [pad1.board_object, pad2.board_object, pad3.board_object, pad4.board_object]
    )

    monkeypatch.setattr(actions, "_update_scene", lambda *args, **kwargs: None)

    # Connect pad2 and pad4 so that all three pads with signal S31 are considered
    actions.connect_pads(obj_lib, [pad2, pad4])

    forced = [o for o in obj_lib.updated if o.testability == "Forced"]
    assert len(forced) == 1
    # Pad3 has the largest area among S31 pads
    assert forced[0].channel == 3
    terminals = [o for o in obj_lib.updated if o.testability == "Terminal"]
    assert len(terminals) == 2
    assert all(o.channel in (2, 4) for o in terminals)


def test_connect_pads_handles_pad_without_scene(monkeypatch):
    """Pads detached from a scene should not cause errors when connecting."""

    class PadWithoutScene(FakePadItem):
        def __init__(self, board_object):
            self.board_object = board_object
            self._scene = None

        def scene(self):
            return self._scene

    obj_lib = FakeObjectLibrary()

    pad1 = PadWithoutScene(
        BoardObject(
            "C1",
            1,
            channel=1,
            signal="S1",
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
            signal="S2",
            width_mm=2,
            height_mm=2,
            testability="Forced",
        )
    )

    seen_view = {}

    def fake_update_scene(view):
        seen_view["view"] = view

    monkeypatch.setattr(actions, "_update_scene", fake_update_scene)

    actions.connect_pads(obj_lib, [pad1, pad2])

    assert seen_view["view"] is pad2.scene().views()[0]
