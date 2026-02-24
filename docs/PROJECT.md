# MTG GIMP Automation — Project Documentation

## Overview

MTG GIMP Automation is a GIMP 3 Python-Fu system for rendering Magic: The Gathering proxy cards. It is a full port of an existing Photoshop ExtendScript system (`mtg-photoshop-automation/`) into GIMP 3's Python API, using XCF templates, Pango markup text rendering, and Scryfall card data.

Given a card name and a piece of card artwork, the system produces a print-quality 3288×4488px proxy card image in under 5 seconds.

---

## Directory Structure

```
mtg-gimp-automation/
├── src/                          # Active GIMP 3 Python-Fu port (14 modules)
│   ├── render.py                 # Core render pipeline + template dispatch
│   ├── render_all.py             # Batch entry point — iterates art/ folder
│   ├── render_target.py          # Single-card entry point
│   ├── templates.py              # 25+ template classes (1280 lines)
│   ├── text_layers.py            # Text field class hierarchy
│   ├── helpers.py                # GIMP PDB abstraction layer (1025 lines)
│   ├── format_text.py            # Pango markup builder for mana symbols
│   ├── frame_logic.py            # Frame color selection (pure logic)
│   ├── layouts.py                # Scryfall JSON → Layout data objects
│   ├── constants.py              # 120+ layer names, symbol maps, colors
│   ├── config.py                 # User configuration (paths, output settings)
│   ├── keyrune_mapping.json      # MTG set code → Keyrune font codepoint map (412 sets)
│   ├── borderify.py              # Black border post-processing utility
│   └── extend_art.py             # Content-aware art extension
├── templates/                    # 27 XCF template files (converted from PSD)
│   └── normal.xcf                # Main 3288×4488 card template
├── tests/
│   ├── test_normal_card.py       # Single NormalTemplate render test
│   ├── test_batch.py             # Batch render test
│   └── test_all_types.py         # Multi-template-type coverage
├── docs/
│   ├── research/                 # Technical research docs
│   ├── PROJECT.md                # This file
│   ├── AGENTIC_WORKFLOW.md       # AI image-generation + verification workflow
│   └── GIMP3_SCRIPTING.md        # GIMP 3 Python-Fu scripting reference
├── fonts/                        # Required MTG fonts (see Fonts section)
├── art/                          # (gitignored) Input card artwork JPEGs
├── out/                          # (gitignored) Rendered card output
├── convert_templates.py          # PSD → XCF batch converter (root-level tool)
├── verify_templates.py           # XCF layer structure validator
├── render_card.sh                # Convenience shell wrapper
└── mtg-photoshop-automation/     # Original Photoshop reference implementation
```

---

## Data Flow

```
1. User places card art in art/
   Filename format: "CardName (Artist).jpg"
   Example: "Lightning Bolt (Christopher Moeller).jpg"

2. render_all.py / render_target.py
   └── Parse filename → extract card_name, artist

3. render.py: render_card(art_path, project_root)
   ├── get_card_info.py → Scryfall API → card JSON
   ├── card JSON → Layout object (NormalLayout, TransformLayout, etc.)
   └── Layout.template → Template class name

4. Template class (templates.py)
   ├── load_template()       → xcf_load via Gio.File
   ├── load_artwork()        → place_image() into art layer group
   ├── set_text_fields()     → name, type, mana cost, rules, P/T via Pango markup
   ├── set_frame_colors()    → frame_logic → visibility toggles
   ├── set_expansion_symbol()→ Keyrune font glyph placed + clipped
   └── export()              → flatten + JPEG export

5. out/CardName.jpg  (≤1MB, 3288×4488px)
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Runtime | GIMP 3.0+ with Python-Fu (GObject Introspection) |
| Python API | `gi.repository` → `Gimp`, `Gegl`, `Gio`, `GLib`, `Pango`, `PangoCairo` |
| Text rendering | Pango markup (replaces Photoshop per-character `textItem` styling) |
| Templates | `.xcf` files (native GIMP format, converted from `.psd` via `convert_templates.py`) |
| External card data | Scryfall API via `get_card_info.py` (pure Python, unchanged from PS version) |
| Expansion symbols | Keyrune font (unicode symbols for all MTG sets) |
| Invocation | `gimp -id --batch-interpreter=python-fu-eval -b '...'` |

---

## Running

### Single Card

```bash
gimp -id --batch-interpreter=python-fu-eval -b '
import sys, traceback
sys.path.insert(0, "/path/to/mtg-gimp-automation")
try:
    from src.render import render_card
    render_card("/path/to/mtg-gimp-automation/art/Lightning Bolt (Christopher Moeller).jpg",
                "/path/to/mtg-gimp-automation")
except Exception as e:
    print("ERROR:", e); traceback.print_exc()
import gi; Gimp = getattr(__import__("gi.repository", fromlist=["Gimp"]), "Gimp")
pdb = Gimp.get_pdb()
proc = pdb.lookup_procedure("gimp-quit")
cfg = proc.create_config(); cfg.set_property("force", True); proc.run(cfg)
'
```

Or use the convenience wrapper:

```bash
./render_card.sh "Lightning Bolt"
```

### Batch (All Art Files)

```bash
gimp -id --batch-interpreter=python-fu-eval -b '
import sys; sys.path.insert(0, "/path/to/mtg-gimp-automation")
from src.render_all import render_all; render_all()
...(quit)
'
```

### Tests

```bash
gimp -id --batch-interpreter=python-fu-eval -b '
import sys; sys.path.insert(0, "/path/to/mtg-gimp-automation")
exec(open("tests/test_normal_card.py").read())
...(quit)
'
```

> **Note**: Use `gimp -id` (NOT `-idf`). The `-f` flag skips font loading, causing crashes.

---

## Module Reference

### `render.py` — Core Pipeline

The orchestrator. `render_card(art_path, project_root)` is the main entry point.

- Parses art filename → extracts `card_name`, `artist`
- Calls `get_card_info.py` subprocess → card JSON
- Constructs `Layout` object from JSON
- Looks up template class from `TEMPLATE_MAP` dict
- Calls `template.execute()`

### `templates.py` — Template Classes

25+ classes representing different MTG card frame types. All inherit from `Template`.

Key base class flow (`Template.execute()`):
1. `load_template()` — XCF file open
2. `load_artwork()` — Place + scale art JPEG into art layer group
3. `set_text_fields()` — All text fields via `text_layers.py`
4. `set_frame_colors()` — Toggle frame layer group visibility via `frame_logic.py`
5. `set_expansion_symbol()` — Keyrune font glyph, stroke, rarity clip
6. `post_processing()` — Optional per-template hooks
7. `export()` — Flatten + JPEG save

### `text_layers.py` — Text Field Classes

Class hierarchy for card text. Each class knows its layer name and font constants.

| Class | Purpose |
|---|---|
| `TextField` | Base class — name, type line, P/T |
| `FormattedTextField` | Rules text with Pango mana symbols + word wrap |
| `ScaledTextField` | Auto-shrink font until text fits bounding box |
| `CreatureTextField` | Rules text offset for creature P/T box |

Font size constants (pixels, calibrated to 3288×4488 canvas):

```python
FONT_SIZE_CARD_NAME      = 140.0   # Name bar
FONT_SIZE_MANA_COST      = 130.0   # NDPMTG mana cost symbols
FONT_SIZE_TYPE_LINE      = 104.0   # Type line bar
FONT_SIZE_RULES_TEXT     = 100.0   # Oracle text box
FONT_SIZE_POWER_TOUGHNESS= 100.0   # P/T box
FONT_SIZE_EXPANSION      = 130.0   # Expansion symbol glyph
FONT_SIZE_ARTIST         = 44.0    # Artist credit line
FONT_SIZE_DEFAULT        = 40.0    # Fallback
```

### `helpers.py` — GIMP Abstraction Layer

All GIMP PDB calls go through here. Critical functions:

| Function | Purpose |
|---|---|
| `get_layer(image, name)` | Layer lookup with automatic `#N` suffix stripping |
| `ensure_text_layer(image, layer, ...)` | Converts rasterized PSD layers → native GIMP TextLayer |
| `place_image(image, filepath, target_layer)` | Load + scale artwork into layer group |
| `apply_stroke(image, layer, color, width)` | Alpha-to-selection + grow + fill stroke effect |
| `clip_layer_to_alpha(image, layer, ref_layer)` | Clip one layer's alpha to another |
| `get_pango_family(gimp_font_name)` | Resolve GIMP font name → fontconfig family for Pango |
| `export_jpeg(image, filepath, max_kb)` | Flatten + JPEG save with quality stepping for size limit |
| `vertically_align_text(layer, ref_layer)` | Align text to vertical center of reference layer |

### `format_text.py` — Pango Markup Builder

Converts raw Scryfall oracle text (with `{W}`, `{U}`, `{B}`, etc. symbols) into Pango markup strings suitable for `layer.set_markup()`.

- Mana symbols → `<span font_family="NDPMTG">char</span>`
- Flavor text → `<span font_family="PlantinMTPro-Italic">...</span>`
- Ability words → leading italic with regular text body
- Bold keywords → `<span font_family="PlantinMTPro-Bold">...</span>`

### `frame_logic.py` — Frame Color Logic (Pure Python)

No GIMP imports. Maps card color identity to frame layer names to show/hide. Handles mono, dual, tri, colorless (artifact), and gold (multicolor) frames. Safe to unit-test outside GIMP.

### `constants.py` — All String Constants

Centralized layer name strings (120+), mana symbol character mappings, RGB color tuples, frame group names, and XCF file paths. Never hardcode layer names inline — always reference from here.

### `config.py` — User Configuration

```python
OUTPUT_FORMAT = "jpeg"        # or "png"
OUTPUT_MAX_SIZE_KB = 1000     # Max JPEG size; quality stepped down to stay under limit
SPECIFIED_TEMPLATE = None     # Override template auto-detection
EXIT_EARLY = False            # Stop after first card (debugging)
FILE_TARGET = "CardName (Artist).jpg"  # Target for render_target.py
```

`get_expansion_symbol_character(set_code)` — looks up the Keyrune unicode character for a given set code using `keyrune_mapping.json`.

---

## Template Files (XCF)

27 XCF files in `templates/`, converted from the original Photoshop `.psd` files.

The main template `templates/normal.xcf` has these key layer/group positions (3288×4488 canvas):

| Layer / Group | Position (x,y) | Size (w×h) |
|---|---|---|
| Card Name | (396, 398) | 836×147 |
| Mana Cost | (2060, 384) | 872×128 |
| Typeline | (392, 2570) | 1291×131 |
| Expansion Symbol | (2766, 2543) | 155×164 |
| Textbox Reference | (352, 2772) | 2584×1249 |
| Rules Text | (393, 2810) | 1297×106 |
| Art Frame | (360, 613) | 2568×1866 |

---

## Required Fonts

These fonts must be installed at `~/.config/GIMP/3.0/fonts/` or `~/.local/share/fonts/`:

| Font File | Purpose | Notes |
|---|---|---|
| `Beleren2016-Bold-Asterisk.ttf` | Card name | Required |
| `NDPMTG.ttf` | Mana/ability symbols | Required |
| `PlantinMTPro-Regular.ttf` | Rules text body | Required |
| `PlantinMTPro-Italic.ttf` | Flavor text | Required |
| `PlantinMTPro-Bold.ttf` | Type line | Required |
| `PlantinMTPro-BoldItalic.ttf` | Bold italic rules | Required |
| `Keyrune.ttf` | Expansion set symbols | Required — unicode PUA glyphs |

Additional fonts (not bundled): Beleren Smallcaps, Keyrune, Relay Medium, Calibri.

---

## Output Settings

- **Format**: JPEG (configurable to PNG in `config.py`)
- **Max size**: 1MB (`OUTPUT_MAX_SIZE_KB = 1000`)
- **Canvas**: 3288×4488 pixels
- **Location**: `out/CardName.jpg`

The 1MB limit exists because AI agents (used for visual verification) cannot analyze images larger than 1MB. JPEG quality is automatically stepped down to stay under the limit.

---

## Known Limitations

- Multi-face card types (Transform, MDFC, Split) have basic template support but are less tested than Normal cards
- Flavor text separator line (thin rule between oracle and flavor text) is not yet rendered
- Mana symbols in the mana cost render as monochrome glyphs, not colored circles (matches original PS behavior)
- `tests/test_all_types.py` covers template dispatch but does not verify visual output

---

## Conversion Status

| Module | Original (JSX) | GIMP Port | Status |
|---|---|---|---|
| Entry points | render_all.jsx, render_target.jsx | render_all.py, render_target.py | Complete |
| Render pipeline | render.jsx | render.py | Complete |
| Templates | templates.jsx (1486 lines) | templates.py (1280 lines) | Complete (25+ classes) |
| Text layers | text_layers.jsx | text_layers.py | Complete |
| Helpers | helpers.jsx (481 lines) | helpers.py (1025 lines) | Complete |
| Text formatting | format_text.jsx | format_text.py | Complete (Pango) |
| Frame logic | frame_logic.jsx | frame_logic.py | Complete |
| Layouts | layouts.jsx | layouts.py | Complete |
| Constants | constants.jsx | constants.py | Complete |
| Templates (.psd) | 27 .psd files | 27 .xcf files | Converted |
| Art extension | extend_art.jsx | extend_art.py | Complete |
| Borderify | borderify.jsx | borderify.py | Complete |
