# GIMP 3 Python-Fu Scripting Reference

## MTG-Specific Findings

This document captures GIMP 3 Python-Fu patterns discovered during the development of this project. It covers the GObject Introspection API, text layer management, Pango markup, font resolution, and the specific workarounds required for this codebase.

---

## 1. Import Pattern (Mandatory)

All `gi.repository` imports in `src/` use `getattr()` rather than direct `from gi.repository import X`. This is intentional — GI bindings have no type stubs, and pyright false-positives on direct imports.

**Correct (used in `helpers.py` and most modules):**

```python
import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
import gi.repository as gir

Gimp = getattr(gir, "Gimp")
Gio = getattr(gir, "Gio")
Gegl = getattr(gir, "Gegl")
GObject = getattr(gir, "GObject")
```

**Incorrect (causes pyright errors, do not use):**

```python
from gi.repository import Gimp, Gio, Gegl  # ❌
```

> Note: `src/text_layers.py` and `src/format_text.py` use the direct import form — this is pre-existing code and is not changed. The `getattr()` pattern is the project standard for all other files.

---

## 2. GIMP 3 Invocation

### Batch Mode Command

```bash
gimp -id --batch-interpreter=python-fu-eval -b 'python_code_here'
```

Flags:
- `-i` — no GUI (batch mode)
- `-d` — no default image (skip splash screen)
- `-id` — **NOT `-idf`**. The `-f` flag skips font loading, causing immediate crashes at any `Gimp.Font.get_by_name()` call.

### Quitting from Batch Script

In GIMP 3.0.4, `Gimp.quit()` takes 0 arguments but exits without force. Use the PDB procedure instead:

```python
pdb = Gimp.get_pdb()
proc = pdb.lookup_procedure("gimp-quit")
cfg = proc.create_config()
cfg.set_property("force", True)
proc.run(cfg)
```

---

## 3. Image and File Operations

### Loading an XCF Template

```python
gfile = Gio.File.new_for_path("/path/to/template.xcf")
image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, gfile)
```

All file paths must be wrapped in `Gio.File.new_for_path()`. Raw strings are not accepted.

### Loading an External Image as a Layer

```python
gfile = Gio.File.new_for_path(art_path)
layer = Gimp.file_load_layer(Gimp.RunMode.NONINTERACTIVE, image, gfile)
image.insert_layer(layer, parent_group, position)
```

### Exporting JPEG with Size Cap

The export pipeline steps JPEG quality from 95 down in increments of 5 to stay under the 1MB limit:

```python
import os
from gi.repository import Gio

def export_jpeg(image, filepath, max_kb=1000):
    flat = image.duplicate()
    flat.flatten()
    drawable = flat.get_active_drawable()
    quality = 95
    while quality >= 5:
        gfile = Gio.File.new_for_path(filepath)
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure("file-jpeg-save")
        cfg = proc.create_config()
        cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
        cfg.set_property("image", flat)
        cfg.set_property("drawable", drawable)
        cfg.set_property("file", gfile)
        cfg.set_property("quality", quality / 100.0)
        proc.run(cfg)
        size_kb = os.path.getsize(filepath) / 1024
        if size_kb <= max_kb:
            break
        quality -= 5
    flat.delete()
```

---

## 4. Layer Traversal

### Root vs All Layers

`image.get_layers()` returns **only root-level** layers. To find a layer anywhere in the tree:

```python
def find_layer_by_name(image_or_group, name):
    """Recursively search the full layer tree for a layer by name."""
    if hasattr(image_or_group, 'get_layers'):
        children = image_or_group.get_layers()
    elif hasattr(image_or_group, 'get_children'):
        children = image_or_group.get_children()
    else:
        return None
    for layer in children:
        if layer.get_name() == name:
            return layer
        if hasattr(layer, 'is_group') and layer.is_group():
            result = find_layer_by_name(layer, name)
            if result:
                return result
    return None
```

### `#N` Suffix Stripping (Critical)

When GIMP imports a PSD file with duplicate layer names, it appends `#1`, `#2`, etc. to disambiguate. All layer lookups must strip this suffix before comparing:

```python
import re
_GIMP_SUFFIX_RE = re.compile(r' #\d+$')

def get_layer(image, name):
    """Find a layer by name, stripping GIMP's deduplication suffix."""
    def _strip(n):
        return _GIMP_SUFFIX_RE.sub('', n)

    def _search(group):
        children = group.get_layers() if hasattr(group, 'get_layers') else group.get_children()
        for layer in children:
            if _strip(layer.get_name()) == name:
                return layer
            if hasattr(layer, 'is_group') and layer.is_group():
                result = _search(layer)
                if result:
                    return result
        return None

    return _search(image)
```

**Never** use raw `image.list_layers()` name matching — it will miss any layer with a `#N` suffix.

---

## 5. Text Layers

### The PSD Import Problem

When GIMP imports a PSD file, text layers are usually **rasterized** into normal pixel layers. This means they have no text content, no font information, and cannot be edited via the text API. Before any text operation, you must convert them to native GIMP TextLayers.

### `ensure_text_layer()` — Mandatory Pre-condition

```python
def ensure_text_layer(image, layer, default_text='', fixed_width=None, font_size=None):
    """Convert a rasterized placeholder layer to a native Gimp.TextLayer.

    If the layer is already a TextLayer, returns it unchanged.
    Otherwise: captures position/size/name, creates a new TextLayer at the
    same location, removes the old layer, and returns the new TextLayer.
    """
    # Fast path: already a text layer
    tl = Gimp.TextLayer.get_by_id(layer.get_id())
    if tl is not None:
        return tl

    offsets = layer.get_offsets()
    old_x, old_y = offsets[1], offsets[2]
    old_name = layer.get_name()
    old_visible = layer.get_visible()
    parent = layer.get_parent() if hasattr(layer, 'get_parent') else None
    old_position = image.get_item_position(layer)

    initial_font_size = float(font_size) if font_size is not None else 40.0

    font_obj = Gimp.Font.get_by_name('Plantin MT Pro Regular')  # or any valid font
    new_tl = Gimp.TextLayer.new(image, default_text, font_obj, initial_font_size, Gimp.Unit.pixel())
    new_tl.set_name(old_name)
    new_tl.set_visible(old_visible)
    image.insert_layer(new_tl, parent, old_position)
    image.remove_layer(layer)
    new_tl.set_offsets(old_x, old_y)

    if fixed_width is not None:
        # Fixed-box mode: text wraps at fixed_width pixels
        new_tl.resize(float(fixed_width), max(initial_font_size * 12.0, 2500.0))

    return new_tl
```

Always call this before `set_text()`, `set_markup()`, `set_font()`, or `set_font_size()`.

### Setting Text Content

```python
# Plain text
text_layer.set_text("Lightning Bolt")

# Formatted text (Pango markup)
text_layer.set_markup('<span font_family="Beleren2016">Lightning Bolt</span>')
```

### Text Layer Properties

```python
text_layer.set_font(Gimp.Font.get_by_name("Beleren2016-Bold-Asterisk"))
text_layer.set_font_size(140.0, Gimp.Unit.pixel())
text_layer.set_color(Gegl.Color.new("rgb(0,0,0)"))
text_layer.set_justification(Gimp.TextJustification.LEFT)
text_layer.set_line_spacing(0.0)
text_layer.set_letter_spacing(0.0)
```

### Font Lookup

```python
# GIMP 3 preferred method
font = Gimp.Font.get_by_name("Plantin MT Pro Regular")
# Returns None if font not installed
```

Note: Font names in GIMP are the "Full Name" from the font file's metadata. The name `"Plantin MT Pro Regular"` corresponds to the font file's full PostScript name, not necessarily the family name.

---

## 6. Font Resolution for Pango Markup

This is a subtle but critical distinction. **GIMP font names** and **fontconfig family names** are different things:

| GIMP Font Name | Pango/fontconfig Family |
|---|---|
| `Plantin MT Pro Regular` | `Plantin MT Pro` |
| `NDPMTG Regular` | `NDPMTG` |
| `Beleren2016 Bold` | `Beleren2016` |
| `Keyrune Regular` | `Keyrune` |

When you use `<span font_family="...">` in Pango markup, you must use the **fontconfig family name**, not the GIMP font full name. Using the wrong name silently falls back to the default font.

The `get_pango_family()` function in `helpers.py` resolves GIMP font names to fontconfig families by querying PangoCairo's font map:

```python
def get_pango_family(gimp_font_name):
    """Resolve GIMP font name to fontconfig family name for Pango markup.

    Example: 'Plantin MT Pro Regular' → 'Plantin MT Pro'
    """
    import gi as _gi
    _gi.require_version('PangoCairo', '1.0')
    PangoCairo = getattr(__import__('gi.repository', fromlist=['PangoCairo']), 'PangoCairo')
    fontmap = PangoCairo.font_map_get_default()

    best_match = None
    best_len = 0
    for fam in fontmap.list_families():
        fam_name = fam.get_name()
        if gimp_font_name == fam_name or gimp_font_name.startswith(fam_name + ' '):
            if len(fam_name) > best_len:
                best_match = fam_name
                best_len = len(fam_name)

    return best_match if best_match is not None else gimp_font_name
```

---

## 7. Pango Markup

Pango markup is XML-like. It is the mechanism for mixed-font, mixed-color text within a single GIMP text layer.

### Basic Tags

```xml
<b>Bold text</b>
<i>Italic text</i>
<b><i>Bold italic</i></b>
```

### Font Family Switching (Used for Mana Symbols)

```xml
<span font_family="NDPMTG">o</span>
<span font_family="Plantin MT Pro">When this creature enters...</span>
```

### Combined MTG Rules Text Example

```python
markup = (
    '<span font_family="Plantin MT Pro"><b>Flying</b>\n'
    'When Serra Angel enters, you gain 3 life.\n'
    '<i>"The angel came not with sword drawn but with mercy given."</i></span>'
)
text_layer.set_markup(markup)
```

### Mana Symbol Substitution

Mana symbols `{W}`, `{U}`, `{B}`, `{R}`, `{G}`, `{T}`, `{X}`, etc. are substituted with characters from the NDPMTG font:

```python
def format_mana_symbols(text, symbols_map):
    import re
    def replace(match):
        sym = match.group(0)
        char = symbols_map.get(sym, sym)
        ndpmtg_family = get_pango_family("NDPMTG Regular")
        return f'<span font_family="{ndpmtg_family}">{char}</span>'
    return re.sub(r'\{[WUBRGCXST0-9/]+\}', replace, text)
```

### XML Escaping (Mandatory)

Any `&`, `<`, or `>` in card text will break Pango markup parsing. Escape before inserting into markup:

```python
def escape_pango(text):
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;'))
```

Forgetting this causes silent markup failures or a `GLib.Error: unexpected end of markup` crash.

---

## 8. Expansion Symbol — Keyrune Font

The Keyrune font provides unicode Private Use Area (PUA) glyphs for every MTG set symbol. Each set code maps to a specific unicode codepoint.

### Font Installation

Keyrune.ttf must be installed at `~/.config/GIMP/3.0/fonts/` or `~/.local/share/fonts/`.

### Set Code Lookup

```python
import json, os

def get_expansion_symbol_character(set_code):
    mapping_path = os.path.join(os.path.dirname(__file__), "keyrune_mapping.json")
    with open(mapping_path) as f:
        mapping = json.load(f)
    entry = mapping.get(set_code.lower())
    if entry and "codepoint" in entry:
        return chr(int(entry["codepoint"], 16))
    return chr(0xE684)  # Fallback: generic Magic 'M' symbol
```

`keyrune_mapping.json` covers 412 sets (as of Feb 2026).

### Rendering the Symbol

The expansion symbol is rendered as a text character using the Keyrune font, then gets a colored stroke applied matching the card's rarity:

```python
# Place symbol character as text layer using Keyrune font
sym_char = get_expansion_symbol_character(set_code)
keyrune_family = get_pango_family("Keyrune Regular")
sym_layer.set_markup(f'<span font_family="{keyrune_family}">{sym_char}</span>')
sym_layer.set_font_size(130.0, Gimp.Unit.pixel())

# Apply rarity-colored stroke (white, silver, gold, or orange)
rarity_color = get_rarity_color(rarity)
apply_stroke(image, sym_layer, rarity_color, stroke_width=8)
```

### Clipping Symbol to Rarity Mask

Symbols can be clipped to a rarity-colored background using alpha masking:

```python
def clip_layer_to_alpha(image, layer, ref_layer):
    """Clip layer's alpha to match ref_layer's alpha channel."""
    pdb = Gimp.get_pdb()
    # Copy alpha from ref_layer
    proc = pdb.lookup_procedure("gimp-layer-create-mask")
    cfg = proc.create_config()
    cfg.set_property("layer", ref_layer)
    cfg.set_property("mask-type", Gimp.AddMaskType.ALPHA)
    result = proc.run(cfg)
    mask = result.index(0)
    layer.add_mask(mask)
    layer.remove_mask(Gimp.MaskApplyMode.APPLY)
```

---

## 9. Stroke Effect

GIMP 3 does not have a direct `layer-effects` stroke API equivalent to Photoshop. The implementation uses alpha-to-selection + grow + fill:

```python
def apply_stroke(image, layer, color, width=6):
    """Apply an outline stroke to a layer using its alpha channel.

    Method:
    1. Select by alpha (alpha-to-selection)
    2. Grow selection by stroke width
    3. Create new layer below, fill with stroke color
    4. Deselect
    """
    # Alpha to selection on the source layer
    image.set_active_layer(layer)
    pdb = Gimp.get_pdb()

    proc = pdb.lookup_procedure("gimp-by-color-select")
    # ... (see helpers.py for full implementation)

    # Simpler approach actually used:
    # 1. gimp-image-select-item (select by alpha)
    proc = pdb.lookup_procedure("gimp-image-select-item")
    cfg = proc.create_config()
    cfg.set_property("image", image)
    cfg.set_property("operation", Gimp.ChannelOps.REPLACE)
    cfg.set_property("item", layer)
    proc.run(cfg)

    # 2. Grow selection
    proc = pdb.lookup_procedure("gimp-selection-grow")
    cfg = proc.create_config()
    cfg.set_property("image", image)
    cfg.set_property("steps", width)
    proc.run(cfg)

    # 3. New layer + fill
    stroke_layer = Gimp.Layer.new(image, layer.get_name() + " stroke",
                                   image.get_width(), image.get_height(),
                                   Gimp.ImageType.RGBA_IMAGE, 100.0,
                                   Gimp.LayerMode.NORMAL)
    parent = layer.get_parent()
    pos = image.get_item_position(layer)
    image.insert_layer(stroke_layer, parent, pos + 1)
    Gimp.context_set_foreground(color)
    stroke_layer.fill(Gimp.FillType.FOREGROUND)
    stroke_layer.resize_to_image_size()

    # 4. Deselect
    image.select_none()
```

---

## 10. Text Box Sizing (Fixed-Box Mode)

GIMP text layers default to **dynamic mode** where the layer resizes to fit the text content. For MTG card rendering, rules text needs **fixed-box mode** with a defined width so text wraps automatically.

### Setting Fixed-Box Mode

```python
# After creating a TextLayer, switch to fixed-box:
text_layer.resize(width, height)
# width:  pixel width of the text box (e.g. 2500px for rules text)
# height: must be generous enough to not clip — use 2500px or more
```

### Text Box Width Rule

The actual usable width should be slightly less than the reference layer width to account for font metrics and avoid edge clipping:

```python
# In FormattedTextField.execute():
box_width = int(self.reference_layer.get_width() * 0.95)
```

Using 100% of the reference layer width causes the last character on each line to be partially cut off by the layer boundary.

---

## 11. Layer Position and Offsets

`layer.get_offsets()` returns a **tuple** `(success_bool, x, y)` in GIMP 3:

```python
offsets = layer.get_offsets()
x = offsets[1]  # index 1, not 0
y = offsets[2]  # index 2, not 1
```

This is a common source of off-by-one bugs for developers coming from older GIMP 2.x where the return value had a different structure.

### Setting Position

```python
layer.set_offsets(x, y)  # absolute position in pixels
```

There is no relative `translate()` — always compute absolute target coordinates:

```python
# Move layer 50px right
offsets = layer.get_offsets()
layer.set_offsets(offsets[1] + 50, offsets[2])
```

---

## 12. Colors

### Creating a Color

```python
# By hex string
black = Gegl.Color.new("#000000")
white = Gegl.Color.new("#FFFFFF")

# By RGB function string
red = Gegl.Color.new("rgb(255,0,0)")

# By named color
gold = Gegl.Color.new("gold")
```

Note: `Gegl.Color`, not `Gimp.Color`. Color creation uses the GEGL namespace.

### Setting Context Foreground (for fills)

```python
Gimp.context_set_foreground(color)  # Sets global foreground color
layer.fill(Gimp.FillType.FOREGROUND)  # Fills layer with current foreground
```

---

## 13. PDB Procedure Pattern

Some operations are only available via the GIMP Procedure Database, not as direct method calls:

```python
pdb = Gimp.get_pdb()
proc = pdb.lookup_procedure("procedure-name")
cfg = proc.create_config()
cfg.set_property("param-name", value)
result = proc.run(cfg)
```

Useful PDB procedures in this project:

| Procedure | Purpose |
|---|---|
| `gimp-quit` | Force quit GIMP from batch script |
| `file-jpeg-save` | Export JPEG with quality parameter |
| `gimp-text-layer-resize` | Set text layer to fixed-box mode (fallback) |
| `gimp-image-select-item` | Select by alpha channel |
| `gimp-selection-grow` | Grow selection (for stroke) |
| `gimp-xcf-save` | Save as XCF |

---

## 14. Blend Modes

| Photoshop | GIMP 3 |
|---|---|
| Normal | `Gimp.LayerMode.NORMAL` |
| Multiply | `Gimp.LayerMode.MULTIPLY` |
| Screen | `Gimp.LayerMode.SCREEN` |
| Overlay | `Gimp.LayerMode.OVERLAY` |
| Soft Light | `Gimp.LayerMode.SOFTLIGHT` |
| Hard Light | `Gimp.LayerMode.HARDLIGHT` |
| Color Dodge | `Gimp.LayerMode.DODGE` |
| Color Burn | `Gimp.LayerMode.BURN` |
| Darken | `Gimp.LayerMode.DARKEN_ONLY` |
| Lighten | `Gimp.LayerMode.LIGHTEN_ONLY` |
| Difference | `Gimp.LayerMode.DIFFERENCE` |
| Pass Through (groups) | `Gimp.LayerMode.PASS_THROUGH` |

---

## 15. Common Pitfalls

### `layer.get_offsets()` tuple indexing

```python
# WRONG — off by one, gets bool and x instead of x and y
x, y = layer.get_offsets()[:2]

# CORRECT — result is (success, x, y)
offsets = layer.get_offsets()
x = offsets[1]
y = offsets[2]
```

### New layers are NOT in the image until inserted

```python
layer = Gimp.Layer.new(image, "Name", w, h, Gimp.ImageType.RGBA_IMAGE, 100.0, Gimp.LayerMode.NORMAL)
# layer exists but is NOT visible yet
image.insert_layer(layer, parent, position)  # now it's in the image
```

### `image.flatten()` removes alpha channel

If you need transparency in the output, use `image.merge_visible_layers()` instead of `image.flatten()`.

### Font not found → silent fallback

`Gimp.Font.get_by_name()` returns `None` if the font isn't installed — it does NOT raise an exception. Always check for `None`:

```python
font = Gimp.Font.get_by_name("Beleren2016-Bold-Asterisk")
if font is None:
    raise RuntimeError("Beleren2016-Bold-Asterisk not installed in GIMP fonts directory")
```

### `set_markup()` silently fails if text has unescaped XML

Any `&`, `<`, `>` in card text must be escaped via `escape_pango()` or the markup is silently discarded and the text layer shows empty or garbled content.

### GIMP 3.0 vs 3.0.4 API differences

- `Gimp.quit()` signature changed between minor versions. Use PDB `gimp-quit` for guaranteed compatibility.
- Some PDB procedures changed parameter names. Always use `create_config()` + `set_property()` rather than positional arguments.

---

## 16. Font Installation

Fonts must be installed where GIMP can find them:

```
~/.config/GIMP/3.0/fonts/    ← GIMP-specific user fonts (preferred)
~/.local/share/fonts/         ← System user fonts (also works)
/usr/share/fonts/             ← System-wide fonts
```

After installing fonts, GIMP will rescan on next launch. In batch mode with `-id`, this happens automatically unless `-f` is also specified (which must be avoided).

Verify fonts are loaded:

```python
# In batch mode, check a required font
font = Gimp.Font.get_by_name("NDPMTG Regular")
if font is None:
    print("ERROR: NDPMTG font not found — check fonts/ directory")
```
