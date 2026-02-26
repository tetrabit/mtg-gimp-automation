# src/ — GIMP 3 Python-Fu Card Renderer

## Purpose

Active GIMP 3 port of the Photoshop ExtendScript card renderer. 14 modules, ~4500 LOC. Converts Scryfall card data + artwork into rendered proxy card PNGs using XCF templates.

## Module Map

### Entry Points
- `render_all.py` (35 lines) — Batch: iterates `art/` folder, calls `render.render_card()` per file
- `render_target.py` (34 lines) — Single card: takes card name string, renders one card

### Core Pipeline
- `render.py` (220 lines) — Orchestrator. Parses filename → Scryfall lookup → Layout → Template dispatch via `TEMPLATE_MAP` dict. Contains `render_card()` main function.
- `templates.py` (1280 lines) — **Largest file.** 25+ template classes. Base `Template` class defines `execute()` flow: load XCF → place art → set text → set frame → export. Subclasses override for card types (Normal, Transform, Planeswalker, Saga, MDFC, Adventure, Class, Mutate, Leveler, Miracle, Snow, etc.)
- `layouts.py` (328 lines) — Scryfall JSON → Python objects. `NormalLayout`, `TransformLayout`, `SplitLayout`, `AdventureLayout`, `SagaLayout`, `PlaneswalkerLayout`, `ClassLayout`, `MutateLayout`, etc. Each layout exposes `.name`, `.mana_cost`, `.type_line`, `.oracle_text`, `.power`, `.toughness`, `.template`.

### Text System
- `text_layers.py` (318 lines) — Class hierarchy for card text fields. Base `TextField` → subclasses: `FormattedTextField` (rules text with mana symbols), `ScaledTextField` (auto-shrink to fit), `CreatureTextField` (P/T aware positioning). Each class knows how to position itself relative to reference layers.
- `format_text.py` (292 lines) — Converts rules text with mana symbols `{W}`, `{U}`, `{B}`, `{R}`, `{G}`, `{T}`, `{X}` etc. into Pango markup. Replaces Photoshop's per-character `textItem` styling. Key function: `format_rules_text()` → returns Pango markup string with `<span font_family="NDPMTG">` for symbol characters.

### GIMP Abstraction Layer
- `helpers.py` (629 lines) — **Critical file.** All GIMP PDB calls go through here. Key functions:
  - `get_layer(image, name)` — Layer lookup with `#N` suffix stripping
  - `ensure_text_layer(image, layer)` — Converts rasterized PSD layers to native TextLayers
  - `place_image(image, filepath, target_layer)` — Load + scale artwork into layer group
  - `set_text(layer, text, markup=None)` — Set text content with optional Pango markup
  - `frame_layer_toggle(image, colors)` — Batch visibility toggle for frame groups
  - `content_fill(image, layer)` — Content-aware fill via GEGL `heal-clone`
  - `export_png(image, filepath)` — Flatten + file-png-save

### Support
- `frame_logic.py` (253 lines) — Pure logic (no GIMP calls). Maps card color identity → frame layer names. Handles mono, dual, tri, colorless, gold frames. Returns list of layer names to show/hide.
- `constants.py` (437 lines) — All string constants: 120+ layer names (`LAYER_NAME`, `LAYER_TYPE`, `LAYER_MANA_COST`, etc.), mana symbol → NDPMTG character maps, frame group names, file paths.
- `config.py` (21 lines) — Paths: template dir, art dir, output dir, font dir. User-editable.
- `borderify.py` (47 lines) — Adds black border around finished card for printing.
- `extend_art.py` (138 lines) — Content-aware art extension: extends card artwork to fill full-art frame using GEGL `heal-clone`.

## Class Hierarchy

```
Template (templates.py)
├── NormalTemplate          ← Standard creature/spell cards
├── TransformTemplate       ← Double-faced cards (front)
├── TransformBackTemplate   ← Double-faced cards (back)
├── MDFCFrontTemplate       ← Modal DFC front
├── MDFCBackTemplate        ← Modal DFC back
├── PlaneswalkerTemplate    ← Planeswalker cards
├── SagaTemplate            ← Saga enchantments
├── AdventureTemplate       ← Adventure cards
├── ClassTemplate           ← Class enchantments
├── MutateTemplate          ← Mutate cards
├── LevelerTemplate         ← Level Up cards
├── MiracleTemplate         ← Miracle cards
├── SnowTemplate            ← Snow mana frame
├── NyxTemplate             ← Enchantment creature (Nyx)
├── CompanionTemplate       ← Companion frame
├── ExtendedTemplate        ← Extended/borderless art
├── BasicLandTemplate       ← Basic lands
├── TokenTemplate           ← Token cards
├── SplitTemplate           ← Split cards (L/R)
├── PlanarTemplate          ← Planechase cards
├── ExpeditionTemplate      ← Zendikar Expeditions
├── WomensDayTemplate       ← Secret Lair Women's Day
├── StargazingTemplate      ← Theros Stargazing
└── ... (more variants)

TextField (text_layers.py)
├── FormattedTextField      ← Rules text with Pango mana symbols
├── ScaledTextField         ← Auto-shrink text to fit bounding box
└── CreatureTextField       ← Rules text that accounts for P/T box
```

## Critical Patterns

### Layer Lookup Chain
```python
# constants.py defines names
LAYER_NAME = "Card Name"
# helpers.py:get_layer() strips GIMP's #N suffixes before matching
layer = get_layer(image, LAYER_NAME)  # finds "Card Name #2" → matches "Card Name"
```

### Text Layer Lifecycle
```python
# PSD-imported layers are rasterized → must convert before setting text
layer = get_layer(image, LAYER_NAME)
text_layer = ensure_text_layer(image, layer)  # creates native TextLayer, removes raster
set_text(text_layer, card.name)  # now safe to set content
```

### Template Execute Flow
```python
class NormalTemplate(Template):
    def execute(self):
        self.load_template()       # xcf_load via Gio.File
        self.load_artwork()        # place_image into art layer group
        self.set_text_fields()     # name, type, mana cost, rules, P/T
        self.set_frame_colors()    # frame_logic → visibility toggles
        self.set_expansion_symbol()
        self.post_processing()     # optional per-template hooks
        self.export()              # flatten + PNG save
```

### GObject Introspection Import Pattern
```python
import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
gir = __import__('gi.repository', fromlist=['Gimp', 'Gegl', 'Gio'])
Gimp = getattr(gir, 'Gimp')  # Avoids pyright errors — intentional
Gegl = getattr(gir, 'Gegl')
Gio = getattr(gir, 'Gio')
```

## Gotchas

- **No `from gi.repository import X`** — use `getattr()` pattern. GI bindings have no type stubs. Pyright will false-positive on direct imports. Do NOT change this.
- **`ensure_text_layer()` is mandatory** before ANY text operation on PSD-imported layers. Skip → silent failure or crash.
- **Layer name `#N` suffixes** — GIMP deduplicates on PSD import. All lookups must go through `get_layer()`, never raw `image.list_layers()` name matching.
- **Pango markup, not textItem** — PS used per-character textItem styling. GIMP uses Pango markup XML. Mana symbols use `<span font_family="NDPMTG">` wrapping.
- **GEGL for image ops** — Content-aware fill uses `Gegl.Node` pipeline with `gegl:heal-clone`, not PDB.
- **Tests require GIMP runtime** — Cannot run with plain `python`. Must invoke via `gimp -idf --batch-interpreter=python-fu-eval`.
- **`frame_logic.py` is pure Python** — No GIMP imports. Safe to unit test outside GIMP.
- **`config.py` paths are relative** — Assumes CWD is project root.
