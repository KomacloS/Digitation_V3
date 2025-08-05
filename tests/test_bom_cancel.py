import sys
import types
from component_placer.bom_handler.bom_handler import BOMHandler


class DummyFlags:
    def get_flag(self, key, default):
        return "top"


class DummyBoardView:
    def __init__(self):
        self.flags = DummyFlags()
        self.converter = types.SimpleNamespace(pixels_to_mm=lambda x, y: (x, y))


class DummyObjectLibrary:
    def __init__(self):
        self.objects = {}
        self.added = None

    def bulk_add(self, new_objs, skip_render=False):
        self.added = new_objs

    def get_all_objects(self):
        return []


def test_bom_not_updated_on_cancel(monkeypatch):
    bom = BOMHandler()
    # Existing BOM entry with different data
    bom.add_component("R1", "RES", "1k", "0402", "PN1")

    # Provide a stub for edit_pads.actions to avoid circular imports
    stub_actions = types.ModuleType("actions")
    sys.modules.setdefault("edit_pads", types.ModuleType("edit_pads"))
    sys.modules["edit_pads.actions"] = stub_actions

    from component_placer.component_placer import ComponentPlacer

    placer = ComponentPlacer(
        board_view=DummyBoardView(),
        object_library=DummyObjectLibrary(),
        bom_handler=bom,
        ghost_component=None,
    )

    placer.footprint = {
        "pads": [
            {
                "pin": 1,
                "x_coord_mm": 0,
                "y_coord_mm": 0,
                "shape_type": "Round",
                "width_mm": 1,
                "height_mm": 1,
                "hole_mm": 0,
                "technology": "SMD",
            }
        ],
        "center_x": 0,
        "center_y": 0,
    }

    # Bypass duplicate name dialog and force cancel in BOM mismatch dialog
    monkeypatch.setattr(
        placer,
        "_handle_duplicate_name_or_offset_pins",
        lambda name: (name, False, 0, None),
    )
    monkeypatch.setattr(
        placer,
        "_prompt_bom_update",
        lambda name, existing, new: None,
    )

    input_data = {
        "component_name": "R1",
        "function": "RES",
        "value": "10k",
        "package": "0603",
        "part_number": "PN1",
    }

    assert placer._finalize_footprint_placement(0, 0, input_data) is False
    # BOM should remain unchanged
    assert bom.get_component("R1") == {
        "function": "RES",
        "value": "1k",
        "package": "0402",
        "part_number": "PN1",
    }
