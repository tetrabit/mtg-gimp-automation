#!/usr/bin/env python3
"""
Batch convert PSD template files to XCF format for GIMP 3.

Usage:
    cd ~/projects/mtg-gimp-automation
    gimp-console-3.0 -i --batch-interpreter python-fu-eval \
        -b "import sys; sys.path.insert(0, '/home/nullvoid/projects/mtg-gimp-automation'); exec(open('/home/nullvoid/projects/mtg-gimp-automation/convert_templates.py').read())" --quit
"""

import os
import sys

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, Gio


# When exec'd via -b, __file__ is not defined and GIMP may change cwd.
# Resolve SCRIPT_DIR by checking multiple strategies.
def _find_script_dir():
    # Strategy 1: Check if convert_templates.py exists relative to cwd
    for candidate in [os.getcwd(), os.path.expanduser('~/projects/mtg-gimp-automation')]:
        if os.path.exists(os.path.join(candidate, 'convert_templates.py')):
            return candidate
    # Strategy 2: If _SCRIPT_DIR was injected by the caller, use it
    if '_SCRIPT_DIR' in dir():
        return _SCRIPT_DIR
    # Fallback: cwd
    return os.getcwd()

SCRIPT_DIR = _find_script_dir()
PSD_SOURCE_DIR = os.path.join(SCRIPT_DIR, "mtg-photoshop-automation", "templates")
XCF_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "templates")


def convert_psd_to_xcf(psd_path, xcf_path):
    result = {
        "psd": os.path.basename(psd_path),
        "xcf": os.path.basename(xcf_path),
        "layers": 0,
        "groups": 0,
        "text_layers": 0,
        "issues": [],
    }

    gfile = Gio.File.new_for_path(psd_path)
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, gfile)

    if image is None:
        result["issues"].append("FATAL: Failed to load PSD file")
        return result

    _audit_layers(image, result)

    out_gfile = Gio.File.new_for_path(xcf_path)
    try:
        success = Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, out_gfile)
        if not success:
            result["issues"].append("FATAL: Gimp.file_save returned False")
    except Exception as e:
        result["issues"].append(f"FATAL: Failed to save XCF: {e}")

    image.delete()
    return result


def _audit_layers(image_or_group, result, depth=0):
    if hasattr(image_or_group, 'get_layers'):
        layers = image_or_group.get_layers()
    elif hasattr(image_or_group, 'get_children'):
        layers = image_or_group.get_children()
    else:
        return

    for layer in layers:
        is_group = hasattr(layer, 'is_group') and layer.is_group()
        is_text = hasattr(layer, 'is_text_layer') and layer.is_text_layer()

        if is_group:
            result["groups"] += 1
            _audit_layers(layer, result, depth + 1)
        else:
            result["layers"] += 1
            if is_text:
                result["text_layers"] += 1


def convert_all(psd_dir=None, xcf_dir=None):
    psd_dir = psd_dir or PSD_SOURCE_DIR
    xcf_dir = xcf_dir or XCF_OUTPUT_DIR

    if not os.path.isdir(psd_dir):
        print(f"ERROR: PSD source directory not found: {psd_dir}")
        print("Make sure the mtg-photoshop-automation/templates/ directory exists with .psd files.")
        return

    os.makedirs(xcf_dir, exist_ok=True)

    # Search for PSD files in psd_dir and immediate subdirectories
    # (Google Drive download may place files in 'Automated Templates/' subfolder)
    psd_files = []
    for entry in sorted(os.listdir(psd_dir)):
        full = os.path.join(psd_dir, entry)
        if entry.lower().endswith('.psd') and os.path.isfile(full):
            psd_files.append(full)
        elif os.path.isdir(full):
            for sub in sorted(os.listdir(full)):
                if sub.lower().endswith('.psd') and os.path.isfile(os.path.join(full, sub)):
                    psd_files.append(os.path.join(full, sub))

    if not psd_files:
        print(f"No .psd files found in {psd_dir} (or subdirectories)")
        return

    print(f"Found {len(psd_files)} PSD files to convert")
    print(f"Output directory: {xcf_dir}")
    print("=" * 60)

    results = []
    for psd_path in psd_files:
        filename = os.path.basename(psd_path)
        xcf_name = filename.rsplit('.', 1)[0] + '.xcf'
        xcf_path = os.path.join(xcf_dir, xcf_name)

        print(f"\nConverting: {filename} -> {xcf_name}")
        result = convert_psd_to_xcf(psd_path, xcf_path)
        results.append(result)

        print(f"  Layers: {result['layers']}, Groups: {result['groups']}, "
              f"Text: {result['text_layers']}")
        if result["issues"]:
            for issue in result["issues"]:
                print(f"  ⚠ {issue}")

    print("\n" + "=" * 60)
    print("CONVERSION SUMMARY")
    print("=" * 60)

    total_issues = 0
    for r in results:
        status = "OK" if not r["issues"] else "ISSUES"
        print(f"  [{status}] {r['psd']} -> {r['xcf']} "
              f"({r['layers']} layers, {r['groups']} groups, {r['text_layers']} text)")
        total_issues += len(r["issues"])

    print(f"\nTotal: {len(results)} files converted, {total_issues} issues")

    if total_issues > 0:
        print("\nSome templates had issues. Review the output above.")
        print("Text layers from PSD import are typically rasterized.")
        print("Run verify_templates.py to check layer structure,")
        print("then manually recreate text layers in GIMP GUI.")


# When exec'd via GIMP batch mode, __name__ is "__main__" but sys.argv
# contains GIMP internal args (e.g. '-gimp', '277', ...), not our arguments.
# Always call convert_all() with defaults; override via env vars if needed.
_psd_override = os.environ.get('MTG_PSD_DIR')
_xcf_override = os.environ.get('MTG_XCF_DIR')
convert_all(_psd_override, _xcf_override)
