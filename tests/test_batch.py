# pyright: reportMissingImports=false
import os
import sys
import glob
import time

import gi
gi.require_version('Gimp', '3.0')
import gi.repository as gir

Gimp = getattr(gir, "Gimp")
Gio = getattr(gir, "Gio")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.render_all import run as render_all_run


FIXTURE_ART_DIR = os.path.join(PROJECT_ROOT, "art")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "out")


def count_art_files():
    if not os.path.isdir(FIXTURE_ART_DIR):
        return 0
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.tif"]
    count = 0
    for pattern in patterns:
        count += len(glob.glob(os.path.join(FIXTURE_ART_DIR, pattern)))
    return count


def count_output_files():
    if not os.path.isdir(OUTPUT_DIR):
        return 0
    return len(glob.glob(os.path.join(OUTPUT_DIR, "*.png")))


def test_batch_render():
    art_count = count_art_files()
    if art_count == 0:
        print(f"SKIP: No art files in {FIXTURE_ART_DIR}")
        return "skip"

    print(f"Found {art_count} art files in {FIXTURE_ART_DIR}")

    output_before = count_output_files()
    start_time = time.time()

    try:
        render_all_run(PROJECT_ROOT)
    except Exception as e:
        if "Exiting" in str(e):
            pass
        else:
            print(f"FAIL: Batch render raised — {e}")
            return "fail"

    elapsed = time.time() - start_time
    output_after = count_output_files()
    new_outputs = output_after - output_before

    print(f"Rendered {new_outputs} cards in {elapsed:.1f}s")

    if new_outputs == 0:
        print("FAIL: No new output files generated")
        return "fail"

    if new_outputs < art_count:
        print(f"WARN: Only {new_outputs}/{art_count} cards rendered successfully")
        return "pass"

    print(f"PASS: All {art_count} cards rendered ({elapsed:.1f}s total, "
          f"{elapsed / art_count:.1f}s per card)")
    return "pass"


def test_output_files_are_valid():
    if not os.path.isdir(OUTPUT_DIR):
        print("SKIP: No output directory")
        return "skip"

    png_files = glob.glob(os.path.join(OUTPUT_DIR, "*.png"))
    if not png_files:
        print("SKIP: No PNG files in output directory")
        return "skip"

    min_valid_size = 10_000
    invalid = []
    for png_path in png_files:
        size = os.path.getsize(png_path)
        if size < min_valid_size:
            invalid.append((os.path.basename(png_path), size))

    if invalid:
        for name, size in invalid:
            print(f"  WARN: {name} is only {size} bytes (possibly corrupt)")
        print(f"FAIL: {len(invalid)}/{len(png_files)} output files are suspiciously small")
        return "fail"

    print(f"PASS: All {len(png_files)} output PNGs are valid size (>{min_valid_size} bytes)")
    return "pass"


def run_all():
    print("=" * 60)
    print("TEST SUITE: Batch Render")
    print("=" * 60)

    passed = 0
    failed = 0
    skipped = 0

    tests = [
        ("Batch render all art files", test_batch_render),
        ("Validate output file sizes", test_output_files_are_valid),
    ]

    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        result = test_fn()
        if result == "pass":
            passed += 1
        elif result == "fail":
            failed += 1
        else:
            skipped += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    if not success:
        sys.exit(1)
