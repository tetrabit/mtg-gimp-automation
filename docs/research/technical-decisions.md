# Technical Decisions

## TD-1: Scripting Language — Python-Fu (Python 3)

**Task:** td-f6c02e  
**Decision:** Python-Fu (Python 3 + GObject Introspection)  
**Confidence:** High — unanimous recommendation from all research

### Rationale

| Factor | Python-Fu | Script-Fu |
|---|---|---|
| OOP support | Native classes, inheritance | None — requires manual simulation |
| String/regex | Full Python stdlib | Basic substring only |
| Existing code reuse | Direct import of `get_card_info.py`, `get_card_scan.py` | Impossible — different language |
| Community/docs | Extensive Python ecosystem | Niche Scheme dialect |
| GIMP 3 investment | GObject Introspection (modern API) | Legacy compatibility layer |
| Code complexity | 1x baseline | 3-5x for equivalent OOP patterns |

### API Pattern

```python
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, Gio, Gegl, GObject

# Plugin registration pattern
class MyPlugin(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["my-procedure-name"]
    
    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        # configure procedure...
        return procedure
    
    def run(self, procedure, run_mode, image, n_drawables, drawables, config, data):
        # implementation
        pass
```

### Rejected Alternative
Script-Fu was rejected because:
- The original codebase uses `es-class.js` for OOP inheritance (25+ template classes)
- Mana symbol formatting requires complex string manipulation (545 lines in `format_text.jsx`)
- No path to reuse existing Python helpers

---

## TD-2: Invocation Method — GIMP Batch Mode

**Task:** td-f14d39  
**Decision:** `gimp-console-3.0` batch mode with `python-fu-eval`  
**Confidence:** High

### Architecture

```
render_all.py (controller, pure Python)
  └─ subprocess.run("gimp-console-3.0 -i --batch-interpreter python-fu-eval -b '...'")
       └─ batch_renderer.py (runs inside GIMP process)
            ├─ Reads JSON manifest of cards to render
            ├─ For each card: open template → set layers → export PNG
            └─ pdb.gimp_quit(0) on completion
```

### Key Constraints
- **Standalone Python CANNOT call GIMP API** — PDB lives inside GIMP process
- **Start GIMP once, process all cards in loop** — not per-card restart (performance)
- **Pass config via environment variables** — not sys.argv (GIMP intercepts args)
- **Use `Gio.File.new_for_path()`** for all file operations

### Command Line

```bash
# Single card
gimp-console-3.0 -i --batch-interpreter python-fu-eval \
  -b "import sys; sys.path.append('.'); import render_target; render_target.run()" \
  -b "pdb.gimp_quit(0)"

# All cards
gimp-console-3.0 -i --batch-interpreter python-fu-eval \
  -b "import sys; sys.path.append('.'); import render_all; render_all.run()" \
  -b "pdb.gimp_quit(0)"
```

### Error Handling
- Wrap all operations in `try/except`
- On failure: `pdb.gimp_quit(1)` for non-zero exit code
- Controller script checks subprocess return code

### Rejected Alternatives
- **GUI Script-Fu console**: Not automatable for batch rendering
- **Standalone Python**: Cannot access GIMP PDB — API is process-internal only
- **GIMP as library**: Not supported in GIMP 3 architecture

---

## TD-3: Template File Strategy — Convert PSD to XCF

**Task:** td-250f2a  
**Decision:** One-time batch conversion from PSD to XCF with manual verification  
**Confidence:** High

### Rationale
- **XCF is GIMP's native format** — loads as memory dump (instant), no parsing overhead
- **PSD import has known fidelity issues** — text layers often rasterized, layer effects lost
- **Batch process stability** — runtime PSD loading risks silent failures across hundreds of renders
- **One-time effort** — convert once, use forever

### Conversion Workflow

1. **Batch convert** all PSDs using GIMP Python script
2. **Manual audit** each XCF:
   - Verify all 120+ layer names match constants
   - Re-create text layers that were rasterized during import
   - Re-apply any lost layer effects
3. **Automated verification** — script to dump layer names from XCF and diff against constants.py

### PSD Import Fidelity Summary

| Feature | Import Status | Action Needed |
|---|---|---|
| Layer names | ✅ Preserved exactly | None |
| Group structure | ✅ Preserved | None |
| Visibility states | ✅ Preserved | None |
| Blend modes | ⚠️ Standard modes OK | Verify non-standard modes |
| Opacity | ✅ Preserved | None |
| Text layers | ❌ Usually rasterized | Re-create as native GIMP text layers |
| Smart objects | ❌ Not supported | Rasterized — use placeholder layers |
| Layer effects | ⚠️ Often rasterized/lost | Re-apply using GIMP effects |
| Layer masks | ✅ Generally preserved | Verify complex masks |
| Clipping masks | ⚠️ Imported as groups | May need code adjustment |

### MTG-Specific Concerns
- **Text layers** (Card Name, Mana Cost, Type Line, Rules Text, P/T): Must be recreated as native GIMP text layers in XCF. The automation code needs editable text, not rasterized bitmaps.
- **Expansion symbols**: If stored as Smart Objects in PSD, they'll be rasterized. Use `Gimp.file_load_layer()` at runtime to insert symbol PNGs.
- **Clipping masks**: May import as layer groups. Frame logic code may need to target groups instead of individual layers.

---

## TD-4: Text Formatting Strategy — Pango Markup

**Task:** td-57b6c9  
**Decision:** Use Pango markup via `layer.set_markup()` for all text formatting  
**Confidence:** High

### Key Discovery
GIMP 3's text layers support **Pango markup**, which enables per-character formatting in a single text layer. This is critical for MTG cards where rules text mixes:
- Regular text (PlantinMTPro-Regular)
- Italic text for flavor text (PlantinMTPro-Italic)
- Bold text for keywords (PlantinMTPro-Bold)
- Mana symbols using NDPMTG font
- Mixed sizes and colors

### Pango Markup Examples

```python
# Simple bold/italic
layer.set_markup('<b>Flying</b>, <i>vigilance</i>')

# Font switching for mana symbols
layer.set_markup('Pay <span font="NDPMTG">o</span> to activate.')

# Mixed formatting for a full rules text box
markup = (
    '<span font="PlantinMTPro-Bold">Flying</span>\n'
    '<span font="PlantinMTPro-Regular">When Serra Angel enters, '
    'you gain 3 life.</span>\n'
    '<span font="PlantinMTPro-Italic">"The angel came not with '
    'sword drawn but with mercy given."</span>'
)
layer.set_markup(markup)
```

### format_text.py Rewrite Strategy
The original `format_text.jsx` (545 lines) parses text and applies per-character formatting via Photoshop's `textItem.contents` manipulation. The GIMP rewrite will:

1. Parse input text (same parsing logic)
2. Replace `{W}`, `{U}`, `{B}`, etc. with `<span font="NDPMTG">symbol_char</span>`
3. Wrap italic text in `<i>...</i>` tags
4. Wrap bold text in `<b>...</b>` tags
5. Build single Pango markup string
6. Apply via `layer.set_markup(result)`

### Text API Quick Reference

| Operation | GIMP 3 API |
|---|---|
| Create text layer | `Gimp.TextLayer.new(image, text, font_obj, size, Gimp.Unit.pixel())` |
| Set plain text | `layer.set_text(text)` |
| Set formatted text | `layer.set_markup(pango_string)` |
| Set font | `layer.set_font(font_obj)` |
| Set font size | `layer.set_font_size(size, Gimp.Unit.pixel())` |
| Set color | `layer.set_color(Gegl.Color.new("#000000"))` |
| Set line spacing | `layer.set_line_spacing(value)` |
| Measure text | `Gimp.text_get_extents_font(text, size, font_obj)` → (w, h, ascent, descent) |
| Find fonts | `Gimp.fonts_get_list("FontName")` → list of GimpFont objects |
