# ui/selected_pins_info.py

from typing import List, Optional, Tuple
from PyQt5.QtCore import Qt
from display.display_library import SelectablePadItem
from display.pad_shapes import build_pad_path
from constants.constants import Constants

def generate_selected_pins_html(selected_pads: List[SelectablePadItem],
                                last_clicked_mm: Optional[Tuple[float, float]] = None,
                                side: str = "top",
                                font_size: int = 12) -> str:
    """
    Generates an HTML string that displays information about the currently selected pads.
    In all cases, if a last-click coordinate is provided, it is shown.
    
    - If no pads are selected, the board click info (coordinates and side) is shown.
    - For one pad, its details are shown along with the board click info.
    - For multiple pads, a summary is shown along with the board click info.
    """
    def styled_span(text: str, color: str, bold: bool = False) -> str:
        style = f"color:{color}; font-size:{font_size}px; white-space:nowrap;"
        if bold:
            style += " font-weight:bold;"
        return f"<span style='{style}'>{text}</span>"

    def attribute_chunk(label: str, value: str) -> str:
        return f"{styled_span(label, 'blue', True)}: {styled_span(value, 'black')}"

    spacer = "&nbsp;&nbsp;&nbsp;&nbsp;"  # four non-breaking spaces

    # Build board click info using last_clicked_mm.
    board_click_info = ""
    if last_clicked_mm is not None:
        x_mm, y_mm = last_clicked_mm
        board_click_info = (f"{attribute_chunk('Last Click', f'X: {x_mm:.2f} mm, Y: {y_mm:.2f} mm')}"
                              f"{spacer}{attribute_chunk('Side', side.capitalize())}")
    
    # If no pads are selected, return the board click info.
    if not selected_pads:
        return board_click_info

    # If exactly one pad is selected, show its details.
    if len(selected_pads) == 1:
        pad_obj = selected_pads[0].board_object
        attributes = [
            ("Component", pad_obj.component_name),
            ("Pin", str(pad_obj.pin)),
            ("Prefix", pad_obj.prefix if pad_obj.prefix else ""),
            ("Test Pos", pad_obj.test_position),
            ("Testability", pad_obj.testability),
            ("X (mm)", f"{pad_obj.x_coord_mm:.2f}"),
            ("Y (mm)", f"{pad_obj.y_coord_mm:.2f}"),
            ("Shape", pad_obj.shape_type),
            ("Width (mm)", f"{pad_obj.width_mm:.2f}"),
            ("Height (mm)", f"{pad_obj.height_mm:.2f}"),
            ("Hole (mm)", f"{pad_obj.hole_mm:.2f}"),
            ("Angle (deg)", f"{pad_obj.angle_deg:.1f}")
        ]
        pad_info_html = spacer.join([attribute_chunk(key, value) for key, value in attributes])
        # Append board click info.
        return pad_info_html + "<br>" + board_click_info

    # For multiple pads, display a summary.
    else:
        num_pads = len(selected_pads)
        positions = {pad.board_object.test_position for pad in selected_pads}
        common_pos = positions.pop() if len(positions) == 1 else "Mixed"
        summary = f"{attribute_chunk('Selected Pads', str(num_pads))}{spacer}{attribute_chunk('Common Test Pos', common_pos)}"
        return summary + "<br>" + board_click_info


def update_properties_tab(
    found_pad,
    pad_info_label,
    last_clicked_mm: Optional[Tuple[float, float]] = None,
    side: str = "top",
    log_handler=None,
    font_size: int = 12
):
    """
    Wraps the found pad in a SelectablePadItem, generates the HTML,
    and updates the properties tab (via pad_info_label).

    :param found_pad: The BoardObject for the found pad.
    :param pad_info_label: The widget (e.g., a QLabel) that displays pad info.
    :param last_clicked_mm: Optional last-click coords (x_mm, y_mm).
    :param side: Current side ("top" or "bottom").
    :param log_handler: Logger to be passed to the SelectablePadItem (if desired).
    :param font_size: Font size for the generated HTML.
    """

    # 1) Retrieve mm-per-pixel values from constants
    constants = Constants()
    mm_per_pixels_top = constants.get("mm_per_pixels_top")
    mm_per_pixels_bot = constants.get("mm_per_pixels_bot")

    # 2) Determine which scale factor to use based on side
    if side.lower() == "top":
        mm_per_pixel = mm_per_pixels_top
    else:
        mm_per_pixel = mm_per_pixels_bot

    # 3) Build the pad's graphical path
    path = build_pad_path(
        found_pad.width_mm,
        found_pad.height_mm,
        found_pad.hole_mm,
        found_pad.shape_type,
        mm_per_pixel
    )

    # 4) Create the SelectablePadItem (purely for info display, no parent needed)
    selected_item = SelectablePadItem(path, found_pad, log_handler, None)

    # 5) Generate HTML from the existing function
    html = generate_selected_pins_html(
        [selected_item],
        last_clicked_mm=last_clicked_mm,
        side=side,
        font_size=font_size
    )

    # 6) Update the properties tab
    pad_info_label.setText(html)
