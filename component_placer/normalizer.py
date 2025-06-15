# component_placer/normalizer.py

"""
This module contains functions to normalize footprint data for the ComponentPlacer.
It is used by both the nod file loading workflow and the copy/paste workflow so that
the data fed into the ComponentPlacer is consistent.
"""

def normalize_footprint(source_data: dict) -> dict:
    """
    Given a source footprint (a dictionary with a 'pads' key containing a list
    of pad dictionaries), this function:
      - Uses the original coordinates if available (keys "x_coord_mm_original" and "y_coord_mm_original"),
        otherwise falls back to "x_coord_mm" and "y_coord_mm".
      - If all pads have an "order" key, the pads are sorted by that key to preserve the original copy order.
      - Computes the center of the footprint from these normalized values.
    
    Parameters:
        source_data (dict): A dictionary that must contain a key "pads", which is a list
            of pad dictionaries. Each pad dictionary is expected to have at least:
                - "x_coord_mm" and optionally "x_coord_mm_original"
                - "y_coord_mm" and optionally "y_coord_mm_original"
            (Other keys are passed through unchanged.)
    
    Returns:
        dict: A normalized footprint dictionary with keys:
            - "pads": A list of pad dictionaries with normalized coordinates (and sorted if applicable).
            - "center_x": The computed center x-coordinate (in mm).
            - "center_y": The computed center y-coordinate (in mm).
    """
    pads = source_data.get("pads", [])
    
    # If all pads have an "order" key, sort by it; otherwise, use the original order.
    if pads and all("order" in pad for pad in pads):
        pads_sorted = sorted(pads, key=lambda p: p["order"])
    else:
        pads_sorted = pads

    normalized_pads = []
    xs = []
    ys = []

    for pad in pads_sorted:
        # Use original coordinates if available; otherwise, use current coordinates.
        x = pad.get("x_coord_mm_original", pad.get("x_coord_mm", 0.0))
        y = pad.get("y_coord_mm_original", pad.get("y_coord_mm", 0.0))
        
        # Build a copy of the pad dictionary with normalized coordinates.
        norm_pad = pad.copy()
        norm_pad["x_coord_mm"] = x
        norm_pad["y_coord_mm"] = y
        
        normalized_pads.append(norm_pad)
        xs.append(x)
        ys.append(y)

    center_x = (min(xs) + max(xs)) / 2.0 if xs else 0.0
    center_y = (min(ys) + max(ys)) / 2.0 if ys else 0.0

    return {
        "pads": normalized_pads,
        "center_x": center_x,
        "center_y": center_y
    }
