# objects/alf_file.py

import os
from typing import List, Dict, Optional
from logs.log_handler import LogHandler


def parse_alf_file(alf_file_path: str) -> Optional[List[Dict[str, str]]]:
    """
    Parses a .alf file and extracts relationships between the component's prefix and its pin.
    
    Each line in the file is expected to be in the format:
        [component_name].[prefix]    [component_name].[pin]
    
    Example:
        COMP_0.A1     COMP_0.1
    
    Returns:
        A list of dictionaries, each containing:
          - "component_name": str
          - "prefix": str
          - "pin": str
        Returns None if the file is not found.
    """
    logger = LogHandler()
    
    if not os.path.exists(alf_file_path):
        logger.log("error", f"File not found: {alf_file_path}")
        return None

    relationships = []
    
    with open(alf_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and lines starting with a comment character.
            if not line or line.startswith(('*', '#')):
                continue

            # Split line on whitespace
            tokens = line.split()
            if len(tokens) < 2:
                logger.log("warning", f"Invalid line in {alf_file_path}: {line}")
                continue

            left_token, right_token = tokens[0], tokens[1]
            
            # Each token should contain exactly one dot.
            if left_token.count('.') != 1 or right_token.count('.') != 1:
                logger.log("warning", f"Token format error in line: {line}")
                continue
            
            comp_name_left, prefix = left_token.split('.', 1)
            comp_name_right, pin = right_token.split('.', 1)
            
            # Verify both tokens refer to the same component name.
            if comp_name_left != comp_name_right:
                logger.log("warning", 
                           f"Mismatched component names in line: {line} "
                           f"({comp_name_left} != {comp_name_right})")
                continue
            
            relationship = {
                "component_name": comp_name_left,
                "prefix": prefix,
                "pin": pin
            }
            relationships.append(relationship)
    
    logger.log("info", f"Parsed {len(relationships)} relationships from {alf_file_path}.")
    return relationships


def export_alf_file(relationships: List[Dict[str, str]], alf_file_path: str) -> bool:
    """
    Exports the given relationships to a .alf file.
    
    Each relationship in the list should be a dictionary with keys:
        - "component_name"
        - "prefix"
        - "pin"
    
    The output file will have one relationship per line in the format:
        [component_name].[prefix]    [component_name].[pin]
    
    Returns:
        True if the file was written successfully, False otherwise.
    """
    logger = LogHandler()
    
    try:
        with open(alf_file_path, 'w') as f:
            for rel in relationships:
                # Ensure the required keys exist
                if not all(k in rel for k in ("component_name", "prefix", "pin")):
                    logger.log("warning", f"Skipping incomplete relationship: {rel}")
                    continue
                line = f"{rel['component_name']}.{rel['prefix']}\t{rel['component_name']}.{rel['pin']}\n"
                f.write(line)
                logger.log("debug", f"Wrote line to ALF file: {line.strip()}")
        logger.log("info", f"ALF file saved successfully to {alf_file_path}.")
        return True
    except Exception as e:
        logger.log("error", f"Failed to save ALF file: {e}")
        return False
