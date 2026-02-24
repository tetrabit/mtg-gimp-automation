# GIMP 3 API Mapping — Photoshop ExtendScript → GIMP 3 Python-Fu

**Task:** td-73c90b  
**Status:** Research complete

## Prerequisites

```python
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, GObject, Gio, Gegl
```

### Critical GIMP 3 Concepts

1. **Namespace**: All GIMP types live under `Gimp.*` (e.g., `Gimp.Image`, `Gimp.Layer`)
2. **Procedure Database**: Some operations still require `Gimp.get_pdb().run_procedure()`, but most are now methods on objects
3. **Items vs Layers**: `Gimp.Layer` inherits from `Gimp.Item`. Transforms are often on `Gimp.Item`
4. **Properties**: Use getters/setters (e.g., `layer.get_opacity()`, `layer.set_visible(True)`)

---

## 1. Document Operations

| Photoshop (JSX) | Purpose | GIMP 3 (Python) | Notes |
|---|---|---|---|
| `app.open(File(path))` | Open file | `Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))` | Returns `Gimp.Image`. Requires `Gio` for file refs. |
| `app.activeDocument` | Current doc | `Gimp.list_images()[0]` | No single "active" doc in batch mode |
| `doc.close(SaveOptions.NO)` | Close | `image.delete()` | Removes from memory |
| `doc.saveAs(file, PNGSaveOptions)` | Export PNG | `Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, image.get_active_drawable(), Gio.File.new_for_path(path))` | Must provide drawable |
| `doc.width` / `doc.height` | Dimensions | `image.get_width()` / `image.get_height()` | |
| `doc.resolution` | DPI | `image.get_resolution()` | Returns tuple `(x_res, y_res)` |
| `doc.flatten()` | Flatten | `image.flatten()` | Merges all, removes alpha |

---

## 2. Layer Traversal

| Photoshop (JSX) | Purpose | GIMP 3 (Python) | Notes |
|---|---|---|---|
| `doc.layers` | Top-level layers | `image.get_layers()` | **Only** top-level (root) layers |
| `doc.layers.getByName("N")` | Find by name | See `find_layer_by_name()` below | No built-in — must iterate |
| `layer.layers` | Group children | `layer.get_children()` | Only if `layer.is_group()` |
| `layer.parent` | Parent group | `layer.get_parent()` | Returns `None` if root |
| `layer.typename` | Layer type | `isinstance(layer, Gimp.GroupLayer)` | Check `Gimp.TextLayer`, `Gimp.GroupLayer` |
| `layer.kind` | Layer kind | `layer.is_text_layer()`, `layer.is_group()` | |

### Recursive Layer Finder (Critical Utility)

```python
def find_layer_by_name(image_or_group, name):
    """Recursively search for a layer by name.
    
    Replaces Photoshop's getByName() which only searches one level.
    This searches the entire layer tree.
    """
    if hasattr(image_or_group, 'get_layers'):
        layers = image_or_group.get_layers()
    elif hasattr(image_or_group, 'get_children'):
        layers = image_or_group.get_children()
    else:
        return None
    
    for layer in layers:
        if layer.get_name() == name:
            return layer
        if hasattr(layer, 'is_group') and layer.is_group():
            result = find_layer_by_name(layer, name)
            if result:
                return result
    return None
```

**Note:** The original Photoshop code uses `getByName()` at specific group levels. The GIMP version can either:
- Replicate exact behavior: search only children of a specific group
- Use recursive search: find anywhere in tree (simpler but may be ambiguous if names repeat)

Recommend: Start with recursive, add scoped search where ambiguity exists.

---

## 3. Layer Properties

| Photoshop (JSX) | Purpose | GIMP 3 (Python) | Notes |
|---|---|---|---|
| `layer.bounds` `[L, T, R, B]` | Position & size | `layer.get_offsets()` → `(x, y)` + `layer.get_width()` / `layer.get_height()` | Must compute bounds manually |
| `layer.visible = bool` | Visibility | `layer.set_visible(bool)` / `layer.get_visible()` | |
| `layer.name` | Name | `layer.set_name("N")` / `layer.get_name()` | |
| `layer.opacity` (0-100) | Opacity | `layer.set_opacity(float)` / `layer.get_opacity()` | GIMP uses 0.0–100.0 float |
| `layer.blendMode` | Blend mode | `layer.set_mode(Gimp.LayerMode.NORMAL)` | Enum: `MULTIPLY`, `SCREEN`, `OVERLAY`, etc. |

### Computing Photoshop-Style Bounds

```python
def get_layer_bounds(layer):
    """Returns (left, top, right, bottom) like Photoshop's layer.bounds."""
    offsets = layer.get_offsets()
    left = offsets[1]  # x offset
    top = offsets[2]   # y offset
    right = left + layer.get_width()
    bottom = top + layer.get_height()
    return (left, top, right, bottom)
```

---

## 4. Layer Transforms

| Photoshop (JSX) | Purpose | GIMP 3 (Python) | Notes |
|---|---|---|---|
| `layer.resize(w%, h%, anchor)` | Scale | `layer.scale(new_w, new_h, local_origin=True)` | Absolute pixels, not percentage |
| `layer.translate(dx, dy)` | Move relative | `layer.set_offsets(new_x, new_y)` | **Absolute** position — add to current for relative |
| `layer.rotate(angle, anchor)` | Rotate | `layer.transform_rotate(radians, auto_center, cx, cy)` | Angle in **radians**, returns transformed item |

### Scale Layer to Fit Reference Bounds

```python
def scale_layer_to_fit(layer, ref_width, ref_height):
    """Scale layer to fit within reference dimensions, maintaining aspect ratio."""
    w = layer.get_width()
    h = layer.get_height()
    scale = min(ref_width / w, ref_height / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    layer.scale(new_w, new_h, True)
    return (new_w, new_h)

def scale_layer_to_fill(layer, ref_width, ref_height):
    """Scale layer to fill reference dimensions (may crop), maintaining aspect ratio."""
    w = layer.get_width()
    h = layer.get_height()
    scale = max(ref_width / w, ref_height / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    layer.scale(new_w, new_h, True)
    return (new_w, new_h)
```

### Position Layer Centered on Reference

```python
def center_layer_on(layer, ref_x, ref_y, ref_width, ref_height):
    """Center a layer within a reference rectangle."""
    lw = layer.get_width()
    lh = layer.get_height()
    new_x = ref_x + (ref_width - lw) // 2
    new_y = ref_y + (ref_height - lh) // 2
    layer.set_offsets(new_x, new_y)
```

---

## 5. Layer Management

| Photoshop (JSX) | Purpose | GIMP 3 (Python) | Notes |
|---|---|---|---|
| `layer.duplicate()` | Duplicate | `new_layer = Gimp.Layer.new_from_drawable(layer, image)` then `image.insert_layer(new_layer, parent, position)` | **Two steps** — create then insert |
| `layer.remove()` | Delete | `image.remove_layer(layer)` | |
| `layer.rasterize(ENTIRE)` | Rasterize | `layer.discard_text_information()` | For text layers only |
| `layer.merge()` | Merge down | `image.merge_down(layer, Gimp.MergeType.CLIP_TO_BOTTOM_LAYER)` | |
| `doc.mergeVisibleLayers()` | Merge visible | `image.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)` | |
| `doc.artLayers.add()` | New layer | `layer = Gimp.Layer.new(image, "Name", w, h, type, opacity, mode)` then `image.insert_layer(layer, parent, position)` | NOT auto-added to image |

### Creating and Inserting a Layer

```python
def create_layer(image, name, width, height, parent=None, position=0):
    """Create a new layer and insert it into the image."""
    layer = Gimp.Layer.new(
        image, name, width, height,
        Gimp.ImageType.RGBA_IMAGE,  # or RGB_IMAGE
        100.0,  # opacity
        Gimp.LayerMode.NORMAL
    )
    image.insert_layer(layer, parent, position)
    return layer
```

---

## 6. Selection & Alignment

| Photoshop (JSX) | Purpose | GIMP 3 (Python) | Notes |
|---|---|---|---|
| `sel.select([[x1,y1],...])` | Select polygon | `image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)` | Rectangle only — polygon needs PDB |
| `sel.selectAll()` | Select all | `image.select_all()` | |
| `sel.deselect()` | Deselect | `image.select_none()` | |
| `align(layer, CENTER)` | Align to selection | Manual math — no native API | See snippet below |

### Manual Alignment (Replaces Photoshop's Align)

```python
def align_layer_to_rect(layer, rect_x, rect_y, rect_w, rect_h, 
                         h_align="center", v_align="center"):
    """Align a layer within a rectangle.
    
    h_align: "left", "center", "right"
    v_align: "top", "center", "bottom"
    """
    lw = layer.get_width()
    lh = layer.get_height()
    
    if h_align == "left":
        x = rect_x
    elif h_align == "center":
        x = rect_x + (rect_w - lw) // 2
    elif h_align == "right":
        x = rect_x + rect_w - lw
    
    if v_align == "top":
        y = rect_y
    elif v_align == "center":
        y = rect_y + (rect_h - lh) // 2
    elif v_align == "bottom":
        y = rect_y + rect_h - lh
    
    layer.set_offsets(x, y)
```

---

## 7. Color & Context

| Photoshop (JSX) | Purpose | GIMP 3 (Python) | Notes |
|---|---|---|---|
| `new SolidColor()` | Create color | `Gegl.Color.new("rgb(R,G,B)")` or `Gegl.Color.new("#RRGGBB")` | Uses `Gegl`, not `Gimp` |
| `app.foregroundColor = c` | Set FG color | `Gimp.context_set_foreground(color)` | Global context |
| `app.backgroundColor = c` | Set BG color | `Gimp.context_set_background(color)` | Global context |

---

## 8. File Import / Paste

| Photoshop (JSX) | Purpose | GIMP 3 (Python) | Notes |
|---|---|---|---|
| `app.load(File(path))` | Load as new doc | `Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))` | Returns new `Gimp.Image` |
| Load as layer | Insert external image into current doc | `layer = Gimp.file_load_layer(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(path))` then `image.insert_layer(layer, parent, pos)` | Two steps |
| `doc.paste()` | Paste clipboard | `layer = Gimp.Edit.paste(drawable, True)` | Creates floating selection |
| `sel.copy()` | Copy selection | `Gimp.Edit.copy(drawable)` | Copies to clipboard |

### Loading Artwork as Layer (Critical for MTG)

```python
def load_art_layer(image, art_path, parent_group=None, position=0):
    """Load an external image file as a layer in the current image.
    
    This replaces the Photoshop pattern of:
    1. Open art file
    2. Select all → Copy
    3. Switch to template → Paste
    """
    gfile = Gio.File.new_for_path(art_path)
    layer = Gimp.file_load_layer(
        Gimp.RunMode.NONINTERACTIVE, image, gfile
    )
    image.insert_layer(layer, parent_group, position)
    return layer
```

---

## 9. Blend Mode Mapping

| Photoshop BlendMode | GIMP 3 LayerMode |
|---|---|
| `NORMAL` | `Gimp.LayerMode.NORMAL` |
| `MULTIPLY` | `Gimp.LayerMode.MULTIPLY` |
| `SCREEN` | `Gimp.LayerMode.SCREEN` |
| `OVERLAY` | `Gimp.LayerMode.OVERLAY` |
| `SOFTLIGHT` | `Gimp.LayerMode.SOFTLIGHT` |
| `HARDLIGHT` | `Gimp.LayerMode.HARDLIGHT` |
| `COLORDODGE` | `Gimp.LayerMode.DODGE` |
| `COLORBURN` | `Gimp.LayerMode.BURN` |
| `DARKEN` | `Gimp.LayerMode.DARKEN_ONLY` |
| `LIGHTEN` | `Gimp.LayerMode.LIGHTEN_ONLY` |
| `DIFFERENCE` | `Gimp.LayerMode.DIFFERENCE` |
| `EXCLUSION` | `Gimp.LayerMode.EXCLUSION` |
| `HUE` | `Gimp.LayerMode.HSL_COLOR` (approximate) |
| `SATURATION` | `Gimp.LayerMode.HSV_SATURATION` |
| `COLOR` | `Gimp.LayerMode.HSL_COLOR` |
| `LUMINOSITY` | `Gimp.LayerMode.HSV_VALUE` |
| `DISSOLVE` | `Gimp.LayerMode.DISSOLVE` |
| `PASSTHROUGH` (groups) | `Gimp.LayerMode.PASS_THROUGH` |

---

## 10. Gotchas & Behavioral Differences

### `layer.get_offsets()` returns a result tuple
The return value is `(success, x, y)` — you need indices `[1]` and `[2]` for the actual offsets.

### No `getByName()` — must iterate
The most-called Photoshop method has no GIMP equivalent. Build a helper and cache layer lookups for performance.

### `layer.scale()` uses absolute pixels, not percentages
Photoshop's `resize()` uses percentages. Always calculate target pixel dimensions first.

### New layers are NOT auto-added
After `Gimp.Layer.new()`, you MUST call `image.insert_layer()` or the layer won't appear.

### `transform_rotate()` uses radians
Photoshop uses degrees. Convert: `radians = degrees * (math.pi / 180)`

### Flatten removes alpha
`image.flatten()` composites against the background color and removes transparency. If you need alpha in the final PNG, merge visible layers instead.

### File operations require Gio
All file paths must be wrapped: `Gio.File.new_for_path(path)`. Raw strings won't work.
