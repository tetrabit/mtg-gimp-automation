"""Render pipeline conversion from render.jsx."""

import json
import os
from typing import Any
from types import SimpleNamespace
from urllib.parse import unquote

from .config import (
    EXIT_EARLY,
    EXPANSION_SYMBOL_CHARACTER,
    SPECIFIED_TEMPLATE,
)
from .constants import (
    ADVENTURE_CLASS,
    BASIC_CLASS,
    BASIC_LAND_NAMES,
    IXALAN_CLASS,
    LEVELER_CLASS,
    MDFC_BACK_CLASS,
    MDFC_FRONT_CLASS,
    MIRACLE_CLASS,
    MUTATE_CLASS,
    NORMAL_CLASS,
    PLANAR_CLASS,
    PLANESWALKER_CLASS,
    SAGA_CLASS,
    SNOW_CLASS,
    TOKEN_CLASS,
    TRANSFORM_BACK_CLASS,
    TRANSFORM_FRONT_CLASS,
)
from .helpers import in_array, save_and_close
from .layouts import layout_map

_SCRYFALL_HEADERS = {
    "User-Agent": "MTG-GIMP-Automation/1.0",
    "Accept": "application/json",
}


def _get_template_map():
    """Lazy import to avoid circular imports and allow templates to be defined later."""
    from . import templates

    def t(name):
        return getattr(templates, name)

    return {
        NORMAL_CLASS: {
            "default": t("NormalTemplate"),
            "other": [
                t("NormalClassicTemplate"),
                t("NormalExtendedTemplate"),
                t("WomensDayTemplate"),
                t("StargazingTemplate"),
                t("MasterpieceTemplate"),
                t("ExpeditionTemplate"),
            ],
        },
        TRANSFORM_FRONT_CLASS: {"default": t("TransformFrontTemplate"), "other": []},
        TRANSFORM_BACK_CLASS: {"default": t("TransformBackTemplate"), "other": []},
        IXALAN_CLASS: {"default": t("IxalanTemplate"), "other": []},
        MDFC_FRONT_CLASS: {"default": t("MDFCFrontTemplate"), "other": []},
        MDFC_BACK_CLASS: {"default": t("MDFCBackTemplate"), "other": []},
        MUTATE_CLASS: {"default": t("MutateTemplate"), "other": []},
        ADVENTURE_CLASS: {"default": t("AdventureTemplate"), "other": []},
        LEVELER_CLASS: {"default": t("LevelerTemplate"), "other": []},
        SAGA_CLASS: {"default": t("SagaTemplate"), "other": []},
        MIRACLE_CLASS: {"default": t("MiracleTemplate"), "other": []},
        PLANESWALKER_CLASS: {
            "default": t("PlaneswalkerTemplate"),
            "other": [t("PlaneswalkerExtendedTemplate")],
        },
        SNOW_CLASS: {"default": t("SnowTemplate"), "other": []},
        BASIC_CLASS: {
            "default": t("BasicLandTemplate"),
            "other": [
                t("BasicLandClassicTemplate"),
                t("BasicLandTherosTemplate"),
                t("BasicLandUnstableTemplate"),
            ],
        },
        PLANAR_CLASS: {"default": t("PlanarTemplate"), "other": []},
        TOKEN_CLASS: {"default": t("TokenTemplate"), "other": []},
    }


def retrieve_card_name_and_artist(file_path_str):
    """Retrieve card name and optional artist from file name."""
    filename = unquote(os.path.basename(file_path_str))
    if "." in filename:
        filename_no_ext = filename.rsplit(".", 1)[0]
    else:
        filename_no_ext = filename

    open_index = filename_no_ext.rfind(" (")
    close_index = filename_no_ext.rfind(")")

    card_name = filename_no_ext
    artist = ""

    if open_index > 0 and close_index > open_index:
        artist = filename_no_ext[open_index + 2:close_index]
        card_name = filename_no_ext[:open_index]

    return {
        "card_name": card_name,
        "artist": artist,
    }


def _add_meld_info(card_json):
    """If the card is a meld card, fetch info for each part."""
    import time
    from urllib import request as url_request

    if card_json.get("layout") == "meld":
        for i in range(3):
            time.sleep(0.1)
            uri = card_json["all_parts"][i]["uri"]
            req = url_request.Request(uri, headers=_SCRYFALL_HEADERS)
            part = json.loads(url_request.urlopen(req).read())
            card_json["all_parts"][i]["info"] = part
    return card_json


def call_python(card_name, file_path):
    """Query Scryfall API directly for card data.

    Replaces the original shell-out to get_card_info.py with a direct
    Python implementation that includes proper User-Agent headers
    (required by Scryfall and newer Python versions).
    """
    import time
    from urllib import request as url_request, parse, error as url_error

    time.sleep(0.1)  # Scryfall rate limiting courtesy

    card_set = None
    if "$" in card_name:
        idx = card_name.index("$")
        card_set = card_name[idx + 1:]
        card_name = card_name[:idx]

    if card_set:
        url = (f"https://api.scryfall.com/cards/named"
               f"?fuzzy={parse.quote(card_name)}&set={parse.quote(card_set)}")
    else:
        url = f"https://api.scryfall.com/cards/named?fuzzy={parse.quote(card_name)}"

    print(f"Searching Scryfall for: {card_name}" + (f", set: {card_set}" if card_set else "") + "...",
          end="", flush=True)

    try:
        req = url_request.Request(url, headers=_SCRYFALL_HEADERS)
        data = url_request.urlopen(req).read()
    except url_error.HTTPError as e:
        raise RuntimeError(
            f"\n\nScryfall API error ({e.code}) for card '{card_name}'.\n"
            f"URL: {url}\n"
            "Check the card name spelling and try again."
        ) from e

    print(" done!", flush=True)
    card_json = _add_meld_info(json.loads(data))
    return card_json


def select_template(layout, file_path_str, file_path):
    """Instantiate a template object based on card layout and configuration."""
    class_template_map = _get_template_map()
    template_entry = class_template_map[layout.card_class]

    template_ctor = template_entry["default"]
    if SPECIFIED_TEMPLATE is not None and in_array(template_entry["other"], SPECIFIED_TEMPLATE):
        template_ctor = SPECIFIED_TEMPLATE

    if not callable(template_ctor):
        raise RuntimeError(f"Template for card class '{layout.card_class}' is not callable")
    return template_ctor(layout, file_path_str, file_path)


def render(file_path_str, project_path):
    """Render a single card.

    Args:
        file_path_str: Path to the art file (e.g., "CardName (Artist).jpg")
        project_path: Path to the project root directory
    """
    ret = retrieve_card_name_and_artist(file_path_str)
    card_name = ret["card_name"]
    artist = ret["artist"]

    if in_array(BASIC_LAND_NAMES, card_name):
        layout = SimpleNamespace(
            artist=artist,
            name=card_name,
            card_class=BASIC_CLASS,
        )
    else:
        scryfall = call_python(card_name, project_path)
        layout_name = scryfall["layout"]

        if layout_name in layout_map:
            layout = layout_map[layout_name](scryfall, card_name)
        else:
            raise RuntimeError(f'Layout "{layout_name}" is not supported. Sorry!')

        if artist != "":
            layout.artist = artist

    template: Any = select_template(layout, file_path_str, project_path)
    # expansion_symbol_character is now set in BaseTemplate.__init__ via config import
    template.exit_early = EXIT_EARLY

    file_name = template.execute()
    if EXIT_EARLY:
        raise RuntimeError("Exiting...")
    save_and_close(template.image, file_name, project_path)
