from objects.board_object import BoardObject
from objects.object_library import ObjectLibrary


def _reset_library() -> ObjectLibrary:
    lib = ObjectLibrary()
    # ObjectLibrary is a singleton; ensure a clean state for each test.
    lib.objects.clear()
    lib._next_channel_id = 1  # reset channel counter
    return lib


def test_bulk_add_replaces_library_signal():
    lib = _reset_library()
    obj = BoardObject(
        component_name="C1", pin=1, signal="$FOFE$_t7/1", channel=None
    )
    lib.bulk_add([obj], skip_render=True)
    assert obj.signal == "S1"
    assert obj.channel == 1
    lib.objects.clear()


def test_bulk_add_preserves_existing_signal():
    lib = _reset_library()
    obj = BoardObject(
        component_name="C1", pin=1, signal="SIG_CUSTOM", channel=None
    )
    lib.bulk_add([obj], skip_render=True)
    assert obj.signal == "SIG_CUSTOM"
    assert obj.channel == 1
    lib.objects.clear()
