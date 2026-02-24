# pyright: reportMissingImports=false, reportAttributeAccessIssue=false

import re
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, Gegl  # type: ignore[attr-defined]
from src.constants import (
    SYMBOLS, ABILITY_WORDS,
    FONT_NAME_MPLANTIN, FONT_NAME_MPLANTIN_ITALIC, FONT_NAME_NDPMTG,
    MODAL_INDENT, LINE_BREAK_LEAD, FLAVOUR_TEXT_LEAD,
    RGB_C, RGB_W, RGB_U, RGB_B, RGB_R, RGB_G, RGB_BLACK, RGB_WHITE,
)

# ---------------------------------------------------------------------------
# Pango font family resolution
# ---------------------------------------------------------------------------
# TextLayer.set_markup() renders text via the SYSTEM Pango font map
# (PangoCairo.font_map_get_default()), which uses fontconfig family names
# like 'Plantin MT Pro', 'NDPMTG', 'Beleren2016'.  GIMP's internal
# gimpfontNNN IDs do NOT exist in this font map.  We resolve GIMP font
# names (e.g. 'Plantin MT Pro Regular') to fontconfig families on first use.
# ---------------------------------------------------------------------------
_pango_fonts_resolved = False
# Fontconfig family names (resolved from GIMP font names)
_pango_mplantin_family = FONT_NAME_MPLANTIN        # fallback: full GIMP name
_pango_mplantin_italic_family = FONT_NAME_MPLANTIN_ITALIC
_pango_ndpmtg_family = FONT_NAME_NDPMTG


def _resolve_pango_fonts():
    """Lazy-resolve GIMP font names to fontconfig family names."""
    global _pango_fonts_resolved
    global _pango_mplantin_family, _pango_mplantin_italic_family, _pango_ndpmtg_family
    if _pango_fonts_resolved:
        return
    _pango_fonts_resolved = True
    try:
        from src.helpers import get_pango_family
        _pango_mplantin_family = get_pango_family(FONT_NAME_MPLANTIN)
        _pango_mplantin_italic_family = get_pango_family(FONT_NAME_MPLANTIN_ITALIC)
        _pango_ndpmtg_family = get_pango_family(FONT_NAME_NDPMTG)
    except Exception:
        pass  # keep human-readable fallbacks

def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])


def escape_pango(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;')
            .replace("'", '&apos;'))


def locate_symbols(input_string):
    symbol_regex = re.compile(r'(\{.*?\})')
    symbol_indices = []
    while True:
        match = symbol_regex.search(input_string)
        if match is None:
            break

        symbol = match.group(1)
        symbol_index = match.start()
        symbol_chars = SYMBOLS.get(symbol)
        if symbol_chars is None:
            raise ValueError(
                "Encountered a formatted character in braces that doesn't map to "
                f"characters: {symbol}"
            )

        input_string = input_string.replace(symbol, symbol_chars, 1)
        symbol_indices.append({
            "index": symbol_index,
            "colours": determine_symbol_colours(symbol, len(symbol_chars)),
        })

    return {
        "input_string": input_string,
        "symbol_indices": symbol_indices,
    }


def escape_regex(value):
    return re.sub(r'[\-\[\]{}()*+?.,\\\^$|#\s]', lambda m: "\\" + m.group(0), value)


def locate_italics(input_string, italics_strings):
    italics_indices = []
    for italics in italics_strings:
        start_index = 0
        end_index = 0

        if "}" in italics:
            for symbol in SYMBOLS:
                regex = re.compile(escape_regex(symbol))
                italics = regex.sub(SYMBOLS[symbol], italics)

        while True:
            start_index = input_string.find(italics, end_index)
            end_index = start_index + len(italics)
            if start_index < 0:
                break

            italics_indices.append({
                "start_index": start_index,
                "end_index": end_index,
            })

    return italics_indices


def determine_symbol_colours(symbol, symbol_length):
    symbol_colour_map = {
        "W": RGB_W,
        "U": RGB_U,
        "B": RGB_C,
        "R": RGB_R,
        "G": RGB_G,
        "C": RGB_C,
        "2": RGB_C,
    }

    hybrid_symbol_colour_map = {
        "W": RGB_W,
        "U": RGB_U,
        "B": RGB_B,
        "R": RGB_R,
        "G": RGB_G,
        "2": RGB_C,
        "C": RGB_C,
    }

    if symbol in ("{E}", "{CHAOS}", "{P}"):
        return [RGB_BLACK]
    if symbol == "{S}":
        return [RGB_C, RGB_BLACK, RGB_WHITE]
    if symbol == "{Q}":
        return [RGB_BLACK, RGB_WHITE]

    phyrexian_regex = re.compile(r'^\{([W,U,B,R,G])/P\}$')
    phyrexian_match = phyrexian_regex.match(symbol)
    if phyrexian_match is not None:
        return [hybrid_symbol_colour_map[phyrexian_match.group(1)], RGB_BLACK]

    hybrid_regex = re.compile(r'^\{([2,W,U,B,R,G,C])/([W,U,B,R,G])\}$')
    hybrid_match = hybrid_regex.match(symbol)
    if hybrid_match is not None:
        colour_map = symbol_colour_map
        if hybrid_match.group(1) in ("2", "C"):
            colour_map = hybrid_symbol_colour_map
        return [
            colour_map[hybrid_match.group(2)],
            colour_map[hybrid_match.group(1)],
            RGB_BLACK,
            RGB_BLACK,
        ]

    phyrexian_hybrid_regex = re.compile(r'^\{([W,U,B,R,G])/([W,U,B,R,G])/P\}$')
    phyrexian_hybrid_match = phyrexian_hybrid_regex.match(symbol)
    if phyrexian_hybrid_match is not None:
        return [
            symbol_colour_map[phyrexian_hybrid_match.group(2)],
            symbol_colour_map[phyrexian_hybrid_match.group(1)],
            RGB_BLACK,
        ]

    normal_symbol_regex = re.compile(r'^\{([W,U,B,R,G])\}$')
    normal_symbol_match = normal_symbol_regex.match(symbol)
    if normal_symbol_match is not None:
        return [symbol_colour_map[normal_symbol_match.group(1)], RGB_BLACK]

    if symbol_length == 2:
        return [RGB_C, RGB_BLACK]

    raise ValueError(f"Encountered a symbol that I don't know how to colour: {symbol}")


def _extract_layer_rgb(layer):
    color = None
    if hasattr(layer, "get_color"):
        color = layer.get_color()

    if color is None:
        return RGB_BLACK

    if isinstance(color, tuple) and len(color) >= 3:
        return (int(color[0]), int(color[1]), int(color[2]))

    color_any = color
    if hasattr(color_any, "get_rgba"):
        rgba = color_any.get_rgba()
        if isinstance(rgba, tuple) and len(rgba) >= 3:
            r, g, b = rgba[0], rgba[1], rgba[2]
            if max(r, g, b) <= 1.0:
                return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
            return (int(round(r)), int(round(g)), int(round(b)))

    if isinstance(color_any, Gegl.Color):
        as_string = color_any.to_string()
        match = re.search(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', as_string)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

    return RGB_BLACK


def build_pango_markup(input_string, symbol_indices, italics_indices, flavour_index, default_rgb):
    _resolve_pango_fonts()
    input_string = input_string.replace("\r", "\n")

    symbol_map = {}
    for symbol_data in symbol_indices:
        base_index = symbol_data["index"]
        colours = symbol_data["colours"]
        for i, colour in enumerate(colours):
            symbol_map[base_index + i] = colour

    italic_mask = [False] * len(input_string)
    for italic_range in italics_indices:
        start = max(0, italic_range["start_index"])
        end = min(len(input_string), italic_range["end_index"])
        for i in range(start, end):
            italic_mask[i] = True

    def style_at(index):
        """Return (font_family, font_style, rgb_tuple) for the character at index."""
        if index in symbol_map:
            return (_pango_ndpmtg_family, 'normal', symbol_map[index])
        if flavour_index >= 0 and index >= flavour_index:
            return (_pango_mplantin_italic_family, 'italic', default_rgb)
        if italic_mask[index]:
            return (_pango_mplantin_italic_family, 'italic', default_rgb)
        return (_pango_mplantin_family, 'normal', default_rgb)
    if not input_string:
        return f'<span font_family="{_pango_mplantin_family}"></span>'
    spans = []
    current_style = style_at(0)
    current_text = [input_string[0]]
    for i in range(1, len(input_string)):
        style = style_at(i)
        if style == current_style:
            current_text.append(input_string[i])
            continue
        text_fragment = escape_pango("".join(current_text))
        colour_attr = f' foreground="{rgb_to_hex(current_style[2])}"'
        spans.append(f'<span font_family="{current_style[0]}" font_style="{current_style[1]}"{colour_attr}>{text_fragment}</span>')
        current_style = style
        current_text = [input_string[i]]
    text_fragment = escape_pango("".join(current_text))
    colour_attr = f' foreground="{rgb_to_hex(current_style[2])}"'
    spans.append(f'<span font_family="{current_style[0]}" font_style="{current_style[1]}"{colour_attr}>{text_fragment}</span>')
    return "".join(spans)


def format_text(layer, input_string, italics_strings, flavour_index, is_centred):
    ret = locate_symbols(input_string)
    input_string = ret["input_string"]
    symbol_indices = ret["symbol_indices"]

    italics_indices = locate_italics(input_string, italics_strings)
    default_rgb = _extract_layer_rgb(layer)

    markup = build_pango_markup(
        input_string,
        symbol_indices,
        italics_indices,
        flavour_index,
        default_rgb,
    )
    layer.set_color(Gegl.Color.new("rgb(255,255,255)"))
    layer.set_markup(markup)

    if is_centred:
        layer.set_justification(Gimp.TextJustification.CENTER)
        line_spacing = 0.0
    else:
        layer.set_justification(Gimp.TextJustification.LEFT)
        line_spacing = LINE_BREAK_LEAD

    if flavour_index > 0:
        line_spacing = max(line_spacing, FLAVOUR_TEXT_LEAD)
    layer.set_line_spacing(line_spacing)

    if "\u2022" in input_string:
        layer.set_indent(MODAL_INDENT)


def generate_italics(card_text):
    reminder_text = True
    italic_text = []
    end_index = 0
    while reminder_text:
        start_index = card_text.find("(", end_index)
        if start_index >= 0:
            end_index = card_text.find(")", start_index + 1)
            italic_text.append(card_text[start_index:end_index + 1])
        else:
            reminder_text = False

    for ability_word in ABILITY_WORDS:
        italic_text.append(ability_word + " \u2014")

    return italic_text


def format_text_wrapper(layer):
    card_text = ""
    if hasattr(layer, "get_text"):
        card_text = layer.get_text()
    elif hasattr(layer, "get_markup"):
        card_text = layer.get_markup()

    if isinstance(card_text, tuple):
        card_text = card_text[0]
    if card_text is None:
        card_text = ""

    italic_text = generate_italics(card_text)
    format_text(layer, card_text, italic_text, -1, False)
