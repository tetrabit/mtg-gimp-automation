# GIMP 3 Text Layer API — Research Findings

**Task:** td-57b6c9  
**Status:** Research complete

## Summary

GIMP 3's text layer system supports **Pango markup**, enabling per-character mixed formatting (fonts, sizes, colors, bold/italic) within a single text layer. This is the critical capability that makes the conversion viable — the original `format_text.jsx` (545 lines) applies per-character Photoshop `textItem` formatting, and Pango markup provides an equivalent mechanism.

---

## Text Layer Creation

```python
# Method 1: Create with initial text
font = Gimp.fonts_get_list("Beleren2016-Bold")[0]  # Returns GimpFont object
layer = Gimp.TextLayer.new(image, "Serra Angel", font, 36.0, Gimp.Unit.pixel())
image.insert_layer(layer, parent_group, position)

# Method 2: Create empty and set text later
layer = Gimp.TextLayer.new(image, "", font, 36.0, Gimp.Unit.pixel())
image.insert_layer(layer, parent_group, position)
layer.set_text("Serra Angel")
```

---

## Text Properties

| Property | Method | Notes |
|---|---|---|
| Text content | `layer.set_text(str)` | Plain text, no formatting |
| Formatted text | `layer.set_markup(pango_str)` | Pango markup for mixed formatting |
| Font | `layer.set_font(font_obj)` | Base font for the layer |
| Font size | `layer.set_font_size(size, Gimp.Unit.pixel())` | Base size |
| Color | `layer.set_color(Gegl.Color.new("#000"))` | Base text color |
| Line spacing | `layer.set_line_spacing(float)` | Extra spacing between lines |
| Letter spacing | `layer.set_letter_spacing(float)` | Extra spacing between characters |
| Justification | `layer.set_justification(Gimp.TextJustification.LEFT)` | LEFT, RIGHT, CENTER, FILL |
| Indentation | `layer.set_indent(float)` | First line indent |

---

## Pango Markup Reference

Pango markup is XML-like, similar to HTML. Supported tags for MTG card rendering:

### Basic Formatting
```xml
<b>Bold text</b>
<i>Italic text</i>
<b><i>Bold italic</i></b>
<u>Underline</u>
<s>Strikethrough</s>
```

### Font Switching (Critical for Mana Symbols)
```xml
<!-- Switch to NDPMTG font for mana symbols -->
<span font="NDPMTG">o</span>

<!-- Specific font with size -->
<span font="PlantinMTPro-Regular" size="12000">Rules text here</span>

<!-- Note: Pango size is in 1/1024ths of a point, or use "12pt" -->
<span size="12pt">12 point text</span>
```

### Color
```xml
<span foreground="#FF0000">Red text</span>
<span foreground="red">Named color</span>
<span background="#FFFF00">Yellow background</span>
```

### Size
```xml
<span size="larger">Bigger</span>
<span size="smaller">Smaller</span>
<span size="x-large">Extra large</span>
<span size="14336">14pt in Pango units (14 * 1024)</span>
```

### Position (Superscript/Subscript)
```xml
<span rise="5000">Superscript</span>
<span rise="-5000">Subscript</span>
```

### Letter Spacing
```xml
<span letter_spacing="2048">Wider spacing</span>
```

### Combined Example (MTG Rules Text)
```xml
<span font="PlantinMTPro-Bold">Flying</span>
<span font="PlantinMTPro-Regular">
When this creature enters, you may pay </span><span font="NDPMTG">oWoW</span><span font="PlantinMTPro-Regular">. If you do, create a 4/4 white Angel creature token with flying.</span>
<span font="PlantinMTPro-Italic">"The light of the angels is not a metaphor."</span>
```

---

## Font Management

### Finding Installed Fonts
```python
# Search for fonts by name pattern
fonts = Gimp.fonts_get_list("Beleren")
# Returns: [GimpFont("Beleren2016-Bold-Asterisk"), ...]

fonts = Gimp.fonts_get_list("NDPMTG")
# Returns: [GimpFont("NDPMTG"), ...]

fonts = Gimp.fonts_get_list("PlantinMTPro")
# Returns: [GimpFont("PlantinMTPro-Regular"), GimpFont("PlantinMTPro-Italic"), ...]
```

### Font Installation Locations
```
~/.config/GIMP/3.0/fonts/     # User fonts (recommended)
/usr/share/fonts/              # System fonts
~/.local/share/fonts/          # User system fonts
```

### Required Font Mapping for MTG

| Purpose | Photoshop Font | GIMP Font Name | Pango `font` Attribute |
|---|---|---|---|
| Card name | Beleren2016-Bold-Asterisk | `Beleren2016-Bold-Asterisk` | `font="Beleren2016-Bold-Asterisk"` |
| Mana symbols | NDPMTG | `NDPMTG` | `font="NDPMTG"` |
| Rules text | PlantinMTPro-Regular | `PlantinMTPro-Regular` | `font="PlantinMTPro-Regular"` |
| Flavor text | PlantinMTPro-Italic | `PlantinMTPro-Italic` | `font="PlantinMTPro-Italic"` |
| Type line | PlantinMTPro-Bold | `PlantinMTPro-Bold` | `font="PlantinMTPro-Bold"` |
| Bold italic | PlantinMTPro-BoldItalic | `PlantinMTPro-BoldItalic` | `font="PlantinMTPro-BoldItalic"` |

---

## Text Measurement

```python
# Measure text extents without creating a layer
width, height, ascent, descent = Gimp.text_get_extents_font(
    "Serra Angel",      # text
    36.0,               # font size
    font_obj            # GimpFont
)
# Returns pixel dimensions the text would occupy
```

### Use Cases
- **Pre-check if text fits**: Measure before placing, reduce font size if too wide
- **Dynamic font sizing**: Loop reducing size until text fits within reference bounds
- **Vertical centering**: Use ascent/descent to precisely position text

---

## format_text.jsx → format_text.py Conversion Strategy

### Original Pattern (Photoshop)
The original `format_text.jsx` works by:
1. Setting the full text string on a text layer
2. Iterating character-by-character
3. Setting font, size, color per character range using `textItem.textRange(start, end)`

### New Pattern (GIMP 3)
The new `format_text.py` will:
1. Parse input text (same logic as original)
2. Build a Pango markup string instead of character-by-character formatting
3. Apply the complete markup in a single `layer.set_markup()` call

### Pseudocode

```python
def format_rules_text(text, symbols_map):
    """Convert MTG rules text to Pango markup.
    
    Input:  "Flying\n{W}{U}: Draw a card.\nFlavor text here"
    Output: Pango markup string with font tags for each segment
    """
    result = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        if is_flavor_text(line):
            result.append(f'<span font="PlantinMTPro-Italic">{escape_pango(line)}</span>')
        elif is_ability_word(line):
            word, rest = split_ability_word(line)
            result.append(
                f'<span font="PlantinMTPro-Italic">{escape_pango(word)}</span>'
                f'<span font="PlantinMTPro-Regular">{format_mana_symbols(rest, symbols_map)}</span>'
            )
        else:
            result.append(
                f'<span font="PlantinMTPro-Regular">{format_mana_symbols(line, symbols_map)}</span>'
            )
    
    return '\n'.join(result)

def format_mana_symbols(text, symbols_map):
    """Replace {W}, {U}, {B}, etc. with NDPMTG font spans."""
    import re
    def replace_symbol(match):
        symbol = match.group(0)
        char = symbols_map.get(symbol, symbol)
        return f'<span font="NDPMTG">{char}</span>'
    
    return re.sub(r'\{[WUBRGCXST0-9]+\}', replace_symbol, text)

def escape_pango(text):
    """Escape XML special characters for Pango markup."""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;'))
```

---

## Potential Issues & Mitigations

### 1. Font Name Mismatch
GIMP may register fonts under different names than Photoshop. Verify with `Gimp.fonts_get_list("")` and create a mapping if needed.

### 2. Pango Markup Escaping
Any `&`, `<`, `>` in card text must be XML-escaped or Pango will fail. Rules text frequently contains these characters.

### 3. Text Layer Auto-Resize
GIMP text layers auto-resize to fit content. The original code may expect fixed-size text boxes. You may need to set text, then resize/crop the layer.

### 4. Line Height Differences
Photoshop and Pango compute line heights differently. Expect to fine-tune `set_line_spacing()` values to match the original Photoshop output.

### 5. Kerning/Tracking
Pango handles kerning via font tables (usually fine) but letter-spacing adjustments may differ from Photoshop. Use `<span letter_spacing="...">` for tweaks.
