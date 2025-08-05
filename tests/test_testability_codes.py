import shlex
from objects.nod_file import obj_to_nod_line, parse_component_nod_file


def test_testability_letter_roundtrip(tmp_path):
    cases = {
        "Forced": "F",
        "Testable": "Y",
        "Not Testable": "N",
        "Terminal": "T",
        "Testable Alternative": "A",
    }

    lines = ["* SIGNAL COMPONENT PIN X Y PAD POS TECN TEST CHANNEL"]
    for idx, (testability, code) in enumerate(cases.items(), start=1):
        obj = {
            "component_name": "C1",
            "pin": idx,
            "channel": idx,
            "signal": f"S{idx}",
            "x_coord_mm": 0.0,
            "y_coord_mm": 0.0,
            "shape_type": "Round",
            "width_mm": 1.0,
            "height_mm": 1.0,
            "hole_mm": 0.0,
            "angle_deg": 0.0,
            "testability": testability,
            "technology": "SMD",
            "test_position": "Top",
        }
        line = obj_to_nod_line(obj)
        tokens = shlex.split(line)
        assert tokens[8] == code
        lines.append(line)

    nod_path = tmp_path / "sample.nod"
    nod_path.write_text("\n".join(lines))
    parsed = parse_component_nod_file(str(nod_path))
    parsed_testabilities = [pad["testability"] for pad in parsed["pads"]]
    assert parsed_testabilities == list(cases.keys())


def test_legacy_e_treated_as_not_testable(tmp_path):
    lines = [
        "* SIGNAL COMPONENT PIN X Y PAD POS TECN TEST CHANNEL",
        '"S1" "C1" 1 0 0 X1 T S E 1',
    ]
    nod_path = tmp_path / "legacy.nod"
    nod_path.write_text("\n".join(lines))
    parsed = parse_component_nod_file(str(nod_path))
    assert parsed["pads"][0]["testability"] == "Not Testable"
