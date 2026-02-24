# pyright: reportMissingImports=false
import os
import sys
import json

import gi
gi.require_version('Gimp', '3.0')
import gi.repository as gir

Gimp = getattr(gir, "Gimp")
Gio = getattr(gir, "Gio")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.render import render
from src.constants import (
    NORMAL_CLASS, TRANSFORM_FRONT_CLASS, TRANSFORM_BACK_CLASS,
    MDFC_FRONT_CLASS, MDFC_BACK_CLASS, PLANESWALKER_CLASS,
    SAGA_CLASS, ADVENTURE_CLASS, LEVELER_CLASS, TOKEN_CLASS,
    BASIC_CLASS, SNOW_CLASS, MIRACLE_CLASS, MUTATE_CLASS,
    PLANAR_CLASS,
)

FIXTURE_ART_DIR = os.path.join(PROJECT_ROOT, "art")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "out")

TEMPLATE_TEST_CARDS = {
    NORMAL_CLASS: "Lightning Bolt",
    TRANSFORM_FRONT_CLASS: "Delver of Secrets",
    TRANSFORM_BACK_CLASS: "Insectile Aberration",
    MDFC_FRONT_CLASS: "Agadeem's Awakening",
    MDFC_BACK_CLASS: "Agadeem, the Undercrypt",
    PLANESWALKER_CLASS: "Liliana of the Veil",
    SAGA_CLASS: "The Eldest Reborn",
    ADVENTURE_CLASS: "Bonecrusher Giant",
    LEVELER_CLASS: "Figure of Destiny",
    TOKEN_CLASS: "Angel",
    BASIC_CLASS: "Island",
    SNOW_CLASS: "Marit Lage's Slumber",
    MIRACLE_CLASS: "Terminus",
    MUTATE_CLASS: "Gemrazer",
    PLANAR_CLASS: "Academy at Tolaria West",
}


def find_art_file(card_name):
    if not os.path.isdir(FIXTURE_ART_DIR):
        return None
    for f in os.listdir(FIXTURE_ART_DIR):
        if f.lower().startswith(card_name.lower()):
            return os.path.join(FIXTURE_ART_DIR, f)
    return None


def test_template_type(card_class, card_name):
    art_path = find_art_file(card_name)
    if art_path is None:
        print(f"SKIP: {card_class} — no art file for '{card_name}' in {FIXTURE_ART_DIR}")
        return "skip"

    try:
        render(art_path, PROJECT_ROOT)
        print(f"PASS: {card_class} ({card_name})")
        return "pass"
    except Exception as e:
        print(f"FAIL: {card_class} ({card_name}) — {e}")
        return "fail"


def run_all():
    print("=" * 60)
    print("TEST SUITE: Per-Template-Type Rendering")
    print("=" * 60)

    os.makedirs(FIXTURE_ART_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    passed = 0
    failed = 0
    skipped = 0

    for card_class, card_name in TEMPLATE_TEST_CARDS.items():
        result = test_template_type(card_class, card_name)
        if result == "pass":
            passed += 1
        elif result == "fail":
            failed += 1
        else:
            skipped += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    if skipped > 0:
        print(f"\nTo run skipped tests, place art files in {FIXTURE_ART_DIR}")
        print("Expected filenames: 'CardName (Artist).jpg'")
        print("\nRequired cards:")
        for card_class, card_name in TEMPLATE_TEST_CARDS.items():
            if find_art_file(card_name) is None:
                print(f"  - {card_name}")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    if not success:
        sys.exit(1)
