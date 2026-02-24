#!/usr/bin/env python3
"""
Verify converted XCF template files have all required layers.

Usage:
    gimp-console-3.0 -i --batch-interpreter python-fu-eval \
        -b "import sys; sys.path.insert(0, '/home/nullvoid/projects/mtg-gimp-automation'); exec(open('/home/nullvoid/projects/mtg-gimp-automation/verify_templates.py').read())" --quit

Cross-references layer names from src/constants.py against
actual layers in each XCF file.
"""

import os
import sys

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, Gio

# ── Configuration ──────────────────────────────────────────────────────────────

def _find_script_dir():
    for candidate in [os.getcwd(), os.path.expanduser('~/projects/mtg-gimp-automation')]:
        if os.path.exists(os.path.join(candidate, 'verify_templates.py')):
            return candidate
    return os.getcwd()

SCRIPT_DIR = _find_script_dir()
XCF_DIR = os.path.join(SCRIPT_DIR, "templates")

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from src.constants import LayerNames

# Map convenient short names to LayerNames class attributes
CARD_NAME = LayerNames.NAME
MANA_COST = LayerNames.MANA_COST
TYPE_LINE = LayerNames.TYPE_LINE
RULES_TEXT = LayerNames.RULES_TEXT
RULES_TEXT_NONCREATURE = LayerNames.RULES_TEXT_NONCREATURE
POWER_TOUGHNESS = LayerNames.POWER_TOUGHNESS
EXPANSION_SYMBOL = LayerNames.EXPANSION_SYMBOL
ART_LAYER = LayerNames.ART_FRAME
ARTIST = LayerNames.ARTIST

# Layers that MUST exist in every standard template
COMMON_REQUIRED_LAYERS = [
    CARD_NAME,
    MANA_COST,
    TYPE_LINE,
    ART_LAYER,
]

# Layers that SHOULD exist in creature templates
CREATURE_LAYERS = [
    POWER_TOUGHNESS,
    RULES_TEXT,
]

# Layers that SHOULD exist in noncreature templates
NONCREATURE_LAYERS = [
    RULES_TEXT_NONCREATURE,
]

# Text layers that must be editable (not rasterized)
TEXT_LAYERS_MUST_BE_EDITABLE = [
    CARD_NAME,
    MANA_COST,
    TYPE_LINE,
    RULES_TEXT,
    RULES_TEXT_NONCREATURE,
    POWER_TOUGHNESS,
]


# ── Verification Logic ────────────────────────────────────────────────────────


def collect_layer_names(image_or_group):
    """Recursively collect all layer names from an image or group."""
    names = set()
    text_layer_names = set()

    if hasattr(image_or_group, 'get_layers'):
        layers = image_or_group.get_layers()
    elif hasattr(image_or_group, 'get_children'):
        layers = image_or_group.get_children()
    else:
        return names, text_layer_names

    for layer in layers:
        name = layer.get_name()
        names.add(name)

        if hasattr(layer, 'is_text_layer') and layer.is_text_layer():
            text_layer_names.add(name)

        if hasattr(layer, 'is_group') and layer.is_group():
            child_names, child_text = collect_layer_names(layer)
            names.update(child_names)
            text_layer_names.update(child_text)

    return names, text_layer_names


def dump_layer_tree(image_or_group, indent=0):
    """Recursively print layer tree for debugging."""
    if hasattr(image_or_group, 'get_layers'):
        layers = image_or_group.get_layers()
    elif hasattr(image_or_group, 'get_children'):
        layers = image_or_group.get_children()
    else:
        return

    for layer in layers:
        layer_type = "GROUP" if (hasattr(layer, 'is_group') and layer.is_group()) else (
            "TEXT" if (hasattr(layer, 'is_text_layer') and layer.is_text_layer()) else "LAYER"
        )
        visible = "V" if layer.get_visible() else "H"
        prefix = "  " * indent
        print(f"{prefix}[{layer_type}][{visible}] {layer.get_name()}")

        if hasattr(layer, 'is_group') and layer.is_group():
            dump_layer_tree(layer, indent + 1)


def verify_template(xcf_path, required_layers=None, verbose=False):
    """Verify a single XCF template has required layers.

    Args:
        xcf_path: Path to XCF file
        required_layers: List of required layer names (defaults to COMMON_REQUIRED_LAYERS)
        verbose: Print full layer tree

    Returns:
        dict with verification results
    """
    if required_layers is None:
        required_layers = COMMON_REQUIRED_LAYERS

    result = {
        "file": os.path.basename(xcf_path),
        "missing_layers": [],
        "rasterized_text_layers": [],
        "total_layers": 0,
        "total_groups": 0,
        "total_text_layers": 0,
        "ok": True,
    }

    gfile = Gio.File.new_for_path(xcf_path)
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, gfile)

    if image is None:
        result["ok"] = False
        result["missing_layers"] = ["FATAL: Could not load file"]
        return result

    if verbose:
        print(f"\n--- Layer Tree: {result['file']} ---")
        dump_layer_tree(image)

    all_names, text_names = collect_layer_names(image)
    result["total_layers"] = len(all_names)
    result["total_text_layers"] = len(text_names)

    for name in required_layers:
        if name not in all_names:
            result["missing_layers"].append(name)

    for name in TEXT_LAYERS_MUST_BE_EDITABLE:
        if name in all_names and name not in text_names:
            result["rasterized_text_layers"].append(name)

    result["ok"] = len(result["missing_layers"]) == 0

    image.delete()
    return result


def verify_all(xcf_dir=None, verbose=False):
    """Verify all XCF templates in directory.

    Args:
        xcf_dir: Directory containing XCF files (defaults to XCF_DIR)
        verbose: Print full layer trees
    """
    xcf_dir = xcf_dir or XCF_DIR

    if not os.path.isdir(xcf_dir):
        print(f"ERROR: XCF directory not found: {xcf_dir}")
        print("Run convert_templates.py first to create XCF files.")
        return

    xcf_files = sorted([f for f in os.listdir(xcf_dir) if f.lower().endswith('.xcf')])

    if not xcf_files:
        print(f"No .xcf files found in {xcf_dir}")
        return

    print(f"Verifying {len(xcf_files)} XCF templates")
    print("=" * 60)

    results = []
    for filename in xcf_files:
        xcf_path = os.path.join(xcf_dir, filename)
        result = verify_template(xcf_path, verbose=verbose)
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    passed = 0
    warned = 0
    failed = 0

    for r in results:
        if not r["ok"]:
            status = "FAIL"
            failed += 1
        elif r["rasterized_text_layers"]:
            status = "WARN"
            warned += 1
        else:
            status = "OK"
            passed += 1

        print(f"  [{status}] {r['file']} "
              f"({r['total_layers']} layers, {r['total_text_layers']} text)")

        if r["missing_layers"]:
            for name in r["missing_layers"]:
                print(f"    MISSING: {name}")

        if r["rasterized_text_layers"]:
            for name in r["rasterized_text_layers"]:
                print(f"    RASTERIZED (needs recreation): {name}")

    print(f"\nTotal: {passed} OK, {warned} warnings, {failed} failed")

    if warned > 0 or failed > 0:
        print("\nNext steps:")
        if failed > 0:
            print("  1. Re-run convert_templates.py for failed files")
        if warned > 0:
            print("  2. Open warned templates in GIMP GUI")
            print("     - Delete rasterized text layers")
            print("     - Recreate as native Text layers with correct fonts:")
            print(f"       Card Name: Beleren2016-Bold-Asterisk")
            print(f"       Mana Cost: NDPMTG")
            print(f"       Type Line: PlantinMTPro-Bold")
            print(f"       Rules Text: PlantinMTPro-Regular")
            print(f"       Power/Toughness: Beleren2016-Bold-Asterisk")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    xcf_dir = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            xcf_dir = arg
            break
    verify_all(xcf_dir, verbose=verbose)
else:
    verify_all()
