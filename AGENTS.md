# MTG GIMP Automation — Project Root
## MANDATORY: Use td for Task Management

Run td usage --new-session at conversation start (or after /clear). This tells you what to work on next.
Sessions are automatic (based on terminal/agent context). Optional:
- td session "name" to label the current session
- td session --new to force a new session in the same context
Use td usage -q after first read.

## Purpose

Render Magic: The Gathering proxy cards via GIMP 3 Python-Fu. Converted from a Photoshop ExtendScript system. The original codebase in `mtg-photoshop-automation/` is the reference implementation; `src/` is the active GIMP 3 port.

## Project Status

**Phase**: Active development. Core conversion complete — 14 Python modules in `src/`, 27 XCF templates converted, 3 test suites written. Text formatting (Pango markup) and multi-face card templates are the primary areas of ongoing work.

## Architecture Overview

```
mtg-gimp-automation/
├── AGENTS.md                         ← This file
├── src/                              ← GIMP 3 Python-Fu conversion (has own AGENTS.md)
│   ├── render.py                     ← Render pipeline + template dispatch
│   ├── render_all.py                 ← Batch entry (iterates art/ folder)
│   ├── render_target.py              ← Single-card entry
│   ├── templates.py                  ← 25+ template classes (1280 lines)
│   ├── text_layers.py                ← Text field class hierarchy
│   ├── helpers.py                    ← GIMP PDB abstraction layer (629 lines)
│   ├── format_text.py                ← Pango markup builder for mana symbols
│   ├── frame_logic.py                ← Frame color selection (algorithmic)
│   ├── layouts.py                    ← Scryfall JSON → Layout objects
│   ├── constants.py                  ← 120+ layer names, symbol maps
│   ├── config.py                     ← User configuration
│   ├── borderify.py                  ← Black border utility
│   └── extend_art.py                 ← Content-aware art extension
├── templates/                        ← 27 converted .xcf template files
├── tests/                            ← GIMP batch-mode test suites
│   ├── test_normal_card.py           ← Single NormalTemplate render test
│   ├── test_batch.py                 ← Batch render test
│   └── test_all_types.py             ← Multi-template-type coverage
├── docs/research/                    ← Technical research (GIMP 3 API, PSD conversion)
├── convert_templates.py              ← PSD → XCF batch converter (root-level tool)
├── verify_templates.py               ← XCF layer structure validator
├── fonts/                            ← Required fonts (Beleren, NDPMTG, PlantinMTPro)
└── mtg-photoshop-automation/         ← Original Photoshop repo (has own AGENTS.md)
    └── scripts/                      ← Original JSX logic (has own AGENTS.md)
```

## Data Flow

```
1. User places card art in art/ folder (filename: "CardName (Artist).jpg")
2. render_all.py iterates art files → for each:
   a. Parse filename → extract card_name, artist
   b. subprocess → get_card_info.py → Scryfall API → card.json
   c. card.json → Layout object (NormalLayout, TransformLayout, etc.)
   d. Layout.template → Template class (NormalTemplate, SagaTemplate, etc.)
   e. Template loads .xcf template in GIMP via Gio.File + xcf_load
   f. Template.execute():
      - Load & scale artwork into art layer group
      - Set text layers via Pango markup (name, mana cost, type, rules, P/T)
      - Toggle frame color visibility via frame_logic
      - Apply expansion symbol
   g. Flatten + export PNG to out/
```

## Technology Stack

- **Runtime**: GIMP 3.0+ with Python-Fu (GObject Introspection)
- **Imports**: `gi.repository` → `Gimp`, `Gegl`, `Gio`, `GLib`, `Pango`, `PangoCairo`
- **Text rendering**: Pango markup (replaces PS per-character textItem styling)
- **Templates**: `.xcf` files (converted from `.psd` via `convert_templates.py`)
- **External data**: Scryfall API via `get_card_info.py` / `get_card_scan.py` (pure Python, unchanged)
- **Invocation**: `gimp -idf --batch-interpreter=python-fu-eval -b 'import sys; sys.path.insert(...); ...'`

## Key Technical Patterns

### GObject Introspection Workaround
All `gi.repository` imports use `getattr()` to satisfy pyright:
```python
Gimp = getattr(gir, "Gimp")  # instead of: from gi.repository import Gimp
```
This is intentional — GI bindings have no type stubs. Do NOT "fix" this.

### PSD-Import Layer Name Deduplication
GIMP appends `#N` suffixes when importing PSD files with duplicate layer names.
`helpers.py:_strip_gimp_suffix()` handles this. Layer lookups must go through `get_layer()` which strips suffixes before matching against `constants.py` names.

### Text Layer Conversion
PSD-imported text layers arrive as rasterized pixel layers. `helpers.py:ensure_text_layer()` creates a new native GIMP TextLayer, copies position/size from the rasterized original, and removes the old layer. This is required before any text content can be set.

## Conversion Status (PS → GIMP)

| Module | PS Original | GIMP Port | Status |
|---|---|---|---|
| Entry points | render_all.jsx, render_target.jsx | render_all.py, render_target.py | ✅ Complete |
| Render pipeline | render.jsx | render.py | ✅ Complete |
| Templates | templates.jsx (1486 lines) | templates.py (1280 lines) | ✅ Complete (25+ classes) |
| Text layers | text_layers.jsx | text_layers.py | ✅ Complete |
| Helpers | helpers.jsx (481 lines) | helpers.py (629 lines) | ✅ Complete |
| Text formatting | format_text.jsx | format_text.py | ✅ Complete (Pango) |
| Frame logic | frame_logic.jsx | frame_logic.py | ✅ Complete |
| Layouts | layouts.jsx | layouts.py | ✅ Complete |
| Constants | constants.jsx | constants.py | ✅ Complete |
| Templates (.psd) | 27 .psd files | 27 .xcf files | ✅ Converted |
| Art extension | extend_art.jsx | extend_art.py | ✅ Complete |
| Borderify | borderify.jsx | borderify.py | ✅ Complete |

## Conventions

- **snake_case** everywhere in `src/` (Python standard)
- Template dispatch: string-to-class dict in `render.py`
- Layer names: string constants centralized in `constants.py`
- All coordinates/sizes in pixels
- Frame colors → layer group visibility via `frame_logic.py`
- Config via `config.py` (paths, preferences)

## Running

```bash
# Single card
gimp -idf --batch-interpreter=python-fu-eval -b \
  'import sys; sys.path.insert(0, "/path/to/mtg-gimp-automation"); from src.render_target import render; render("CardName")'

# Batch (all art/ files)
gimp -idf --batch-interpreter=python-fu-eval -b \
  'import sys; sys.path.insert(0, "/path/to/mtg-gimp-automation"); from src.render_all import render_all; render_all()'

# Tests
gimp -idf --batch-interpreter=python-fu-eval -b \
  'import sys; sys.path.insert(0, "/path/to/mtg-gimp-automation"); exec(open("tests/test_normal_card.py").read())'
```

## Fonts Required

- `Beleren2016-Bold-Asterisk.ttf` — Card name
- `NDPMTG.ttf` — Mana/ability symbols
- `PlantinMTPro-Regular.ttf` — Rules text
- `PlantinMTPro-Italic.ttf` — Flavor text
- `PlantinMTPro-Bold.ttf` — Type line
- `PlantinMTPro-BoldItalic.ttf` — Bold italic rules
- External (not bundled): Beleren Smallcaps, Keyrune, Mana, Relay Medium, Calibri