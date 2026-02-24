"""Configuration for MTG GIMP Automation.
Converted from settings.jsx.
"""

import json
import os
import shutil

# Expansion symbol - characters from Keyrune cheatsheet
EXPANSION_SYMBOL_CHARACTER = "\uE684"  # Planeswalker/Magic symbol (Keyrune) - fallback


def get_expansion_symbol_character(set_code):
    """Look up the Keyrune font character for a given MTG set code.

    Falls back to the generic Magic 'M' symbol (U+E684) if the set code
    is not found in the mapping.
    """
    if not set_code:
        return EXPANSION_SYMBOL_CHARACTER
    mapping_path = os.path.join(os.path.dirname(__file__), "keyrune_mapping.json")
    try:
        with open(mapping_path, "r") as f:
            mapping = json.load(f)
        entry = mapping.get(set_code.lower())
        if entry and "codepoint" in entry:
            return chr(int(entry["codepoint"], 16))
    except Exception:
        pass
    return EXPANSION_SYMBOL_CHARACTER

# Specify a template class to use (if the card's layout is compatible)
# Set to None for auto-detection, or a template class for override
SPECIFIED_TEMPLATE = None

# Specify whether to stop after the first card is formatted (for debugging)
EXIT_EARLY = False

# Target card file for render_target.py
FILE_TARGET = "CardName (Artist).jpg"

# Python command - auto-detect
PYTHON_COMMAND = shutil.which("python3") or shutil.which("python") or "python3"


# Output file settings
# Format: 'jpeg' or 'png'
OUTPUT_FORMAT = "jpeg"

# Maximum output file size in KB (only applies to JPEG)
# JPEG quality will be stepped down to stay under this limit
# Set to None to disable size limit
OUTPUT_MAX_SIZE_KB = 1000