# pyright: reportMissingImports=false
import os
import sys

import gi
gi.require_version('Gimp', '3.0')
import gi.repository as gir

Gimp = getattr(gir, "Gimp")
Gio = getattr(gir, "Gio")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.render import render, retrieve_card_name_and_artist
from src.constants import BASIC_LAND_NAMES


FIXTURE_ART_DIR = os.path.join(PROJECT_ROOT, "art")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "out")

TEST_CARD_NAME = "Lightning Bolt"
TEST_CARD_ARTIST = "Christopher Rush"
TEST_ART_FILENAME = f"{TEST_CARD_NAME} ({TEST_CARD_ARTIST}).jpg"


def setup_test_fixtures():
    os.makedirs(FIXTURE_ART_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    art_path = os.path.join(FIXTURE_ART_DIR, TEST_ART_FILENAME)
    if not os.path.exists(art_path):
        print(f"SKIP: Test art file not found: {art_path}")
        print(f"Place a card art file named '{TEST_ART_FILENAME}' in {FIXTURE_ART_DIR}")
        return None
    return art_path


def test_filename_parsing():
    result = retrieve_card_name_and_artist(TEST_ART_FILENAME)
    assert result["card_name"] == TEST_CARD_NAME, (
        f"Expected card name '{TEST_CARD_NAME}', got '{result['card_name']}'"
    )
    assert result["artist"] == TEST_CARD_ARTIST, (
        f"Expected artist '{TEST_CARD_ARTIST}', got '{result['artist']}'"
    )
    print("PASS: test_filename_parsing")


def test_filename_parsing_no_artist():
    result = retrieve_card_name_and_artist("CardName.jpg")
    assert result["card_name"] == "CardName", (
        f"Expected 'CardName', got '{result['card_name']}'"
    )
    assert result["artist"] == "", (
        f"Expected empty artist, got '{result['artist']}'"
    )
    print("PASS: test_filename_parsing_no_artist")


def test_basic_land_detection():
    for land_name in ["Plains", "Island", "Swamp", "Mountain", "Forest"]:
        assert land_name in BASIC_LAND_NAMES, f"{land_name} not in BASIC_LAND_NAMES"
    print("PASS: test_basic_land_detection")


def test_render_normal_card():
    art_path = setup_test_fixtures()
    if art_path is None:
        return

    try:
        render(art_path, PROJECT_ROOT)
    except Exception as e:
        print(f"FAIL: test_render_normal_card — {e}")
        raise

    expected_output = os.path.join(OUTPUT_DIR, TEST_ART_FILENAME.replace(".jpg", ".png"))
    alt_output = os.path.join(OUTPUT_DIR, f"{TEST_CARD_NAME}.png")

    found = os.path.exists(expected_output) or os.path.exists(alt_output)
    assert found, (
        f"No output file found at {expected_output} or {alt_output}"
    )
    print("PASS: test_render_normal_card")


def run_all():
    print("=" * 60)
    print("TEST SUITE: Normal Card End-to-End")
    print("=" * 60)

    passed = 0
    failed = 0
    skipped = 0

    tests = [
        test_filename_parsing,
        test_filename_parsing_no_artist,
        test_basic_land_detection,
        test_render_normal_card,
    ]

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test_fn.__name__} — {e}")
            failed += 1
        except Exception as e:
            if "SKIP" in str(e):
                skipped += 1
            else:
                print(f"ERROR: {test_fn.__name__} — {e}")
                failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    if not success:
        sys.exit(1)
