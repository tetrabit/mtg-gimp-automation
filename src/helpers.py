import gi
gi.require_version('Gimp', '3.0')
import gi.repository as gir
import subprocess
import os
import re
from src.constants import RGB_BLACK, RGB_WHITE

Gimp = getattr(gir, "Gimp")
Gio = getattr(gir, "Gio")
Gegl = getattr(gir, "Gegl")
GObject = getattr(gir, "GObject")

_GIMP_SUFFIX_RE = re.compile(r' #\d+$')

# Default font used when creating replacement text layers from non-text placeholders.
# This gets overridden by set_font/set_markup later, but we need a valid font to
# construct the TextLayer.
_DEFAULT_FONT_NAME = 'Plantin MT Pro Regular'
_DEFAULT_FONT_SIZE = 40.0


def _get_default_font():
    """Get a Gimp.Font object for the default font."""
    # GIMP 3 API: use Font.get_by_name instead of deprecated fonts_get_list
    font = Gimp.Font.get_by_name(_DEFAULT_FONT_NAME)
    if font is not None:
        return font
    # Fallback: try generic safe fonts
    for fallback in ('Sans', 'serif', 'monospace'):
        font = Gimp.Font.get_by_name(fallback)
        if font is not None:
            print(f"Warning: Font '{_DEFAULT_FONT_NAME}' not found, using '{fallback}'")
            return font
    # Last resort: whatever GIMP has active
    font = Gimp.context_get_font()
    if font is not None:
        print(f"Warning: Font '{_DEFAULT_FONT_NAME}' not found, using context font")
        return font
    raise RuntimeError(
        f"No fonts available in GIMP. Ensure '{_DEFAULT_FONT_NAME}' (or any font) is installed."
    )


def get_font_by_name(font_name):
    """Look up a Gimp.Font object by name. Returns None if not found."""
    return Gimp.Font.get_by_name(font_name)


# Cache for GIMP font name → fontconfig family name lookups.
# Stable within a single GIMP session.
_pango_family_cache = {}
# System fontconfig families, lazily loaded once.
_fontconfig_families = None


def _get_fontconfig_families():
    """Lazily load and cache the set of system fontconfig family names."""
    global _fontconfig_families
    if _fontconfig_families is not None:
        return _fontconfig_families
    _fontconfig_families = set()
    try:
        import gi as _gi
        _gi.require_version('PangoCairo', '1.0')
        PangoCairo = getattr(__import__('gi.repository', fromlist=['PangoCairo']), 'PangoCairo')
        fontmap = PangoCairo.font_map_get_default()
        for fam in fontmap.list_families():
            _fontconfig_families.add(fam.get_name())
    except Exception:
        pass
    return _fontconfig_families


def get_pango_family(gimp_font_name):
    """Resolve a GIMP font name to a fontconfig family name for Pango markup.

    GIMP font names are typically 'Family Face' format, e.g.:
      'Plantin MT Pro Regular' → family 'Plantin MT Pro'
      'NDPMTG Regular'          → family 'NDPMTG'
      'Beleren2016 Bold'        → family 'Beleren2016'

    We match against the system fontconfig font map (what Pango actually uses
    for rendering via set_markup) rather than GIMP's internal gimpfontNNN IDs.

    Args:
        gimp_font_name: The human-readable GIMP font name
            (e.g. 'Plantin MT Pro Regular').
        The fontconfig family name (e.g. 'Plantin MT Pro'), or the original
        gimp_font_name as fallback if resolution fails.
    """
    if gimp_font_name in _pango_family_cache:
        return _pango_family_cache[gimp_font_name]
    families = _get_fontconfig_families()

    # Strategy: find the longest fontconfig family name that the GIMP font
    # name starts with. E.g. 'Plantin MT Pro Regular' starts with
    # 'Plantin MT Pro' (len 14) which is longer than 'Plantin' (len 7).
    best_match = None
    best_len = 0
    for fam_name in families:
        if gimp_font_name == fam_name or gimp_font_name.startswith(fam_name + ' '):
            if len(fam_name) > best_len:
                best_match = fam_name
                best_len = len(fam_name)

    result = best_match if best_match is not None else gimp_font_name
    _pango_family_cache[gimp_font_name] = result
    return result

def _resize_text_layer(text_layer, width, height):
    """Switch a TextLayer to fixed-box mode with the given width/height.

    Uses the GObject-Introspection ``resize`` method first (GIMP ≥ 3.0),
    falling back to the ``gimp-text-layer-resize`` PDB procedure.
    """
    # GI method (preferred)
    if hasattr(text_layer, 'resize'):
        try:
            text_layer.resize(width, height)
            return
        except Exception:
            pass
    # PDB fallback
    try:
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-text-layer-resize')
        if proc is not None:
            cfg = proc.create_config()
            cfg.set_property('layer', text_layer)
            cfg.set_property('width', float(width))
            cfg.set_property('height', float(height))
            proc.run(cfg)
    except Exception:
        pass

def ensure_text_layer(image, layer, default_text='', fixed_width=None, font_size=None):
    """Ensure a layer is a Gimp.TextLayer.
    Gimp.Layer objects. This function checks if the layer is already a TextLayer
    (via get_by_id cast). If not, it creates a new TextLayer at the same position
    with the same name, size, and parent/position, removes the old layer, and
    returns the new TextLayer.
    Args:
        image: The Gimp.Image containing the layer.
        layer: A Gimp.Layer (possibly non-text) to convert.
        default_text: Initial text content for the new text layer.
        fixed_width: If set, create a fixed-box TextLayer that wraps text at
            this width (in pixels). If None (default), create a dynamic
            TextLayer whose bounds equal the rendered ink extent -- required
            for scaling functions that compare layer bounds.
        font_size: Explicit font size in pixels.  When provided this overrides
            the legacy behaviour of using the old layer's pixel height which
            gives wildly wrong sizes for group layers and small placeholders.
            Callers should pass a sensible default (e.g. 40.0 for most text,
            80.0 for rules text that will be scaled down).
    Returns:
        A Gimp.TextLayer with set_text/set_color/set_markup etc. available.
    """
    # Fast path: already a text layer
    tl = Gimp.TextLayer.get_by_id(layer.get_id())
    if tl is not None:
        return tl
    offsets = layer.get_offsets()
    old_x = offsets[1]
    old_y = offsets[2]
    old_w = layer.get_width()
    old_h = layer.get_height()
    old_name = layer.get_name()
    old_visible = layer.get_visible()
    parent = layer.get_parent() if hasattr(layer, 'get_parent') else None
    try:
        old_position = image.get_item_position(layer)
    except Exception:
        old_position = 0
    # Determine initial font size:
    #   - Explicit font_size parameter takes priority.
    #   - Fallback: use _DEFAULT_FONT_SIZE (40px) — a reasonable starting point.
    #   The old approach of `float(old_h)` produced absurd sizes (e.g. 1200px
    #   for a group layer) or too-small sizes (e.g. 30px for a tiny placeholder).
    if font_size is not None:
        initial_font_size = float(font_size)
    else:
        initial_font_size = _DEFAULT_FONT_SIZE
    # Create replacement TextLayer
    font_obj = _get_default_font()
    new_tl = Gimp.TextLayer.new(image, default_text, font_obj, initial_font_size, Gimp.Unit.pixel())
    new_tl.set_name(old_name)
    new_tl.set_visible(old_visible)
    image.insert_layer(new_tl, parent, old_position)
    image.remove_layer(layer)
    new_tl.set_offsets(old_x, old_y)
    if fixed_width is not None:
        # Fixed-box mode: text wraps at the given width.  Height must be
        # generous so ALL text renders without clipping — scaling functions
        # compare rendered ink extent vs reference area.  Use max(12× font, 2500px)
        # to guarantee no clipping before scale_text_to_fit_reference runs.
        _resize_text_layer(new_tl, float(fixed_width), max(initial_font_size * 12.0, 2500.0))
    # Otherwise leave in dynamic mode -- layer bounds == rendered ink extent,
    # which is required for scale_text_right_overlap() comparisons.
    return new_tl

def _color_from_rgb_tuple(rgb_tuple):
    return Gegl.Color.new(f"rgb({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]})")


def _get_layer_text(layer):
    if hasattr(layer, "get_text"):
        return layer.get_text()
    if hasattr(layer, "get_property"):
        try:
            return layer.get_property("text")
        except Exception:
            return ""
    return ""


def _set_layer_text(layer, text):
    if hasattr(layer, "set_text"):
        layer.set_text(text)
        return
    if hasattr(layer, "set_property"):
        try:
            layer.set_property("text", text)
        except Exception:
            pass


def _get_text_layer_color(layer):
    if hasattr(layer, "get_color"):
        return layer.get_color()
    if hasattr(layer, "get_property"):
        try:
            return layer.get_property("color")
        except Exception:
            return None
    return None


def _get_insertion_context(image, active_layer):
    if active_layer is None:
        return (None, 0)

    parent = active_layer.get_parent() if hasattr(active_layer, "get_parent") else None
    siblings = parent.get_children() if parent else image.get_layers()

    index = 0
    for i, sibling in enumerate(siblings):
        if sibling == active_layer:
            index = i
            break
    return (parent, index + 1)


def rgb_black():
    """
    Creates and returns a SolidColour with RGB values for solid black.
    """
    return Gegl.Color.new("rgb(0,0,0)")


def rgb_white():
    """
    Creates and returns a SolidColour with RGB values for solid white.
    """
    return Gegl.Color.new("rgb(255,255,255)")


def compute_layer_dimensions(layer):
    """
    Return an object with the specified layer's width and height (computed from its bounds).
    """
    return {
        "width": layer.get_width(),
        "height": layer.get_height(),
    }


def _get_ink_bounds(image, layer):
    """
    Return the ink bounding box (left, top, right, bottom) of a text layer.
    Creates a copy of the layer, uses alpha-to-selection via the correct
    GIMP 3 PDB call pattern (lookup_procedure + create_config + run),
    then reads the selection bounds.
    Falls back to the full layer bounds if the selection approach fails
    (e.g. fully transparent layer).
    """
    # Copy the layer and insert it (preserves text layer status)
    layer_copy = layer.copy()
    image.insert_layer(layer_copy, None, 0)
    layer_copy.set_visible(True)
    ink_bounds = None
    try:
        pdb = Gimp.get_pdb()
        # Alpha-to-selection on the copy using correct GIMP 3 PDB pattern
        sel_proc = pdb.lookup_procedure('gimp-image-select-item')
        sel_cfg = sel_proc.create_config()
        sel_cfg.set_property('image', image)
        sel_cfg.set_property('operation', 2)  # CHANNEL_OP_REPLACE
        sel_cfg.set_property('item', layer_copy)
        sel_proc.run(sel_cfg)

        # Read selection bounds via PDB
        sb_proc = pdb.lookup_procedure('gimp-selection-bounds')
        sb_cfg = sb_proc.create_config()
        sb_cfg.set_property('image', image)
        sb_result = sb_proc.run(sb_cfg)
        non_empty = sb_result.index(1)
        x1 = sb_result.index(2)
        y1 = sb_result.index(3)
        x2 = sb_result.index(4)
        y2 = sb_result.index(5)

        if non_empty and (x2 - x1) > 0 and (y2 - y1) > 0:
            ink_bounds = (x1, y1, x2, y2)
        sel_none = pdb.lookup_procedure('gimp-selection-none')
        snc = sel_none.create_config()
        snc.set_property('image', image)
        sel_none.run(snc)
    except Exception as e:
        print(f'[helpers] _get_ink_bounds: selection approach failed: {e}')
    # Clean up the temporary copy
    image.remove_layer(layer_copy)
    # Fallback: full layer bounds
    if ink_bounds is None:
        ink_bounds = get_layer_bounds(layer)
    return ink_bounds


def _is_fixed_box_text_layer(layer):
    """Check if a TextLayer is in fixed-box mode (height >> natural text height)."""
    tl = Gimp.TextLayer.get_by_id(layer.get_id())
    if tl is None:
        return False
    try:
        font_size_result = tl.get_font_size()
        if isinstance(font_size_result, (tuple, list)):
            fs = float(font_size_result[0])
        else:
            fs = float(font_size_result)
    except Exception:
        return False
    natural_height = fs * 2.0
    return layer.get_height() > natural_height * 3


def _measure_text_via_dynamic_twin(image, layer):
    """
    Measure the actual ink dimensions of a fixed-box TextLayer by creating
    a temporary dynamic TextLayer with the same content/markup, then resizing
    it to the original layer's width so word-wrapping is applied correctly.
    Returns {'width': int, 'height': int} or None on failure.
    """
    tl = Gimp.TextLayer.get_by_id(layer.get_id())
    if tl is None:
        return None
    markup = tl.get_markup()
    text = tl.get_text()
    try:
        font_size_result = tl.get_font_size()
        if isinstance(font_size_result, (tuple, list)):
            fs = float(font_size_result[0])
            font_unit = font_size_result[1]
        else:
            fs = float(font_size_result)
            font_unit = Gimp.Unit.pixel()
    except Exception:
        fs = _DEFAULT_FONT_SIZE
        font_unit = Gimp.Unit.pixel()
    font_obj = _get_default_font()
    twin = Gimp.TextLayer.new(image, text or 'x', font_obj, fs, font_unit)
    image.insert_layer(twin, None, 0)
    twin.set_visible(False)
    if markup:
        twin.set_color(Gegl.Color.new('rgb(255,255,255)'))
        twin.set_markup(markup)
    elif text:
        twin.set_text(text)
    line_spacing = tl.get_line_spacing()
    if line_spacing:
        twin.set_line_spacing(line_spacing)
    # CRITICAL: resize the dynamic twin to the original layer's width so that
    # word-wrapping matches the fixed-box layout.  Without this, the dynamic
    # twin spreads text horizontally giving an incorrectly short height.
    original_width = layer.get_width()
    twin.resize(original_width, twin.get_height())
    w = twin.get_width()
    h = twin.get_height()
    image.remove_layer(twin)
    return {'width': w, 'height': h}


def _measure_bounds_via_dynamic_twin(image, layer):
    """
    Measure the actual ink bounding box of a fixed-box TextLayer.
    Creates a dynamic twin (with width constraint for wrapping), then uses
    alpha-to-selection on the twin to get true ink bounds.
    Returns (left, top, right, bottom) or None on failure.
    """
    tl = Gimp.TextLayer.get_by_id(layer.get_id())
    if tl is None:
        return None
    markup = tl.get_markup()
    text = tl.get_text()
    try:
        font_size_result = tl.get_font_size()
        if isinstance(font_size_result, (tuple, list)):
            fs = float(font_size_result[0])
            font_unit = font_size_result[1]
        else:
            fs = float(font_size_result)
            font_unit = Gimp.Unit.pixel()
    except Exception:
        fs = _DEFAULT_FONT_SIZE
        font_unit = Gimp.Unit.pixel()
    font_obj = _get_default_font()
    twin = Gimp.TextLayer.new(image, text or 'x', font_obj, fs, font_unit)
    # Position twin at the same location as original
    offsets = layer.get_offsets()
    ox = offsets[1] if len(offsets) >= 3 else (offsets[0] if len(offsets) >= 2 else 0)
    oy = offsets[2] if len(offsets) >= 3 else (offsets[1] if len(offsets) >= 2 else 0)
    image.insert_layer(twin, None, 0)
    twin.set_offsets(int(ox), int(oy))
    twin.set_visible(True)  # must be visible for alpha-to-selection
    if markup:
        twin.set_color(Gegl.Color.new('rgb(255,255,255)'))
        twin.set_markup(markup)
    elif text:
        twin.set_text(text)
    line_spacing = tl.get_line_spacing()
    if line_spacing:
        twin.set_line_spacing(line_spacing)
    # Apply width constraint for wrapping
    original_width = layer.get_width()
    twin.resize(original_width, twin.get_height())
    # Now measure ink bounds on the dynamic twin (which has transparent bg)
    bounds = _get_ink_bounds(image, twin)
    image.remove_layer(twin)
    return bounds


def compute_text_layer_dimensions(image, layer):
    """
    Return {'width': int, 'height': int} for the actual text ink extent.
    Uses alpha-to-selection via _get_ink_bounds for accurate measurement
    of both dynamic and fixed-box text layers.
    """
    left, top, right, bottom = _get_ink_bounds(image, layer)
    return {
        'width': right - left,
        'height': bottom - top,
    }


def compute_text_layer_bounds(image, layer):
    """
    Return the ink bounding box (left, top, right, bottom) of a text layer.
    Uses alpha-to-selection via _get_ink_bounds for accurate measurement
    of both dynamic and fixed-box text layers.
    """
    return _get_ink_bounds(image, layer)


def get_layer_bounds(layer):
    """Returns (left, top, right, bottom) like Photoshop's layer.bounds.
    GIMP layer.get_offsets() returns (success, x, y) - use indices [1] and [2]."""
    offsets = layer.get_offsets()
    left = offsets[1]
    top = offsets[2]
    right = left + layer.get_width()
    bottom = top + layer.get_height()
    return (left, top, right, bottom)


def _strip_gimp_suffix(layer_name):
    """Strip GIMP's '#N' deduplication suffix from a layer name.
    e.g. 'Legal #1' -> 'Legal', 'W #7' -> 'W', 'Artist' -> 'Artist'
    """
    return _GIMP_SUFFIX_RE.sub('', layer_name)


def find_layer_by_name(image_or_group, name, recursive=False):
    """Search for a layer by name among direct children of image_or_group.

    Matches both exact names and GIMP's deduplicated names (e.g. 'Legal #1'
    matches search for 'Legal'). This handles the PSD->XCF import where GIMP
    appends '#N' suffixes to layers with duplicate names across groups.

    Photoshop's getByName() only searches direct children, so recursive=False
    is the default to match that behavior.
    """
    if hasattr(image_or_group, 'get_layers'):
        layers = image_or_group.get_layers()
    elif hasattr(image_or_group, 'get_children'):
        layers = image_or_group.get_children()
    else:
        return None

    for layer in layers:
        layer_name = layer.get_name()
        # Exact match first
        if layer_name == name:
            return layer
        # Match with GIMP's #N suffix stripped
        if _strip_gimp_suffix(layer_name) == name:
            return layer

    # Optional recursive search (not used by default)
    if recursive:
        for layer in layers:
            if hasattr(layer, 'is_group') and layer.is_group():
                result = find_layer_by_name(layer, name, recursive=True)
                if result:
                    return result

    return None


def select_layer_pixels(image, layer):
    """
    Select the bounding box of a given layer.
    """
    left, top, right, bottom = get_layer_bounds(layer)
    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure('gimp-image-select-rectangle')
    if proc is not None:
        config = proc.create_config()
        config.set_property('image', image)
        config.set_property('operation', 2)  # CHANNEL_OP_REPLACE
        config.set_property('x', float(left))
        config.set_property('y', float(top))
        config.set_property('width', float(right - left))
        config.set_property('height', float(bottom - top))
        proc.run(config)
    else:
        # Fallback: try direct method
        image.select_rectangle(
            Gimp.ChannelOps.REPLACE,
            left, top, right - left, bottom - top
        )


def clear_selection(image):
    """
    Clear the current selection.
    """
    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure('gimp-selection-none')
    if proc is not None:
        config = proc.create_config()
        config.set_property('image', image)
        proc.run(config)


def align_layer_to_selection(image, layer, h_align="center", v_align="center", preserve_x=False, preserve_y=False):
    """Align layer relative to current selection bounds using manual math."""
    # Use PDB gimp-selection-bounds (image.get_selection_bounds doesn't exist in GIMP 3.0.4)
    try:
        pdb = Gimp.get_pdb()
        sb_proc = pdb.lookup_procedure('gimp-selection-bounds')
        sb_cfg = sb_proc.create_config()
        sb_cfg.set_property('image', image)
        sb_result = sb_proc.run(sb_cfg)
        success = sb_result.index(1)
        x1 = sb_result.index(2)
        y1 = sb_result.index(3)
        x2 = sb_result.index(4)
        y2 = sb_result.index(5)
    except Exception:
        success, x1, y1, x2, y2 = (False, 0, 0, image.get_width(), image.get_height())

    if not success:
        x1 = 0
        y1 = 0
        x2 = image.get_width()
        y2 = image.get_height()

    selection_width = x2 - x1
    selection_height = y2 - y1
    layer_width = layer.get_width()
    layer_height = layer.get_height()
    offsets = layer.get_offsets()
    current_x = offsets[1]
    current_y = offsets[2]

    if h_align == "left":
        target_x = x1
    elif h_align == "right":
        target_x = x1 + selection_width - layer_width
    else:
        target_x = x1 + (selection_width - layer_width) // 2

    if v_align == "top":
        target_y = y1
    elif v_align == "bottom":
        target_y = y1 + selection_height - layer_height
    else:
        target_y = y1 + (selection_height - layer_height) // 2

    if preserve_x:
        target_x = current_x
    if preserve_y:
        target_y = current_y

    layer.set_offsets(target_x, target_y)


def align(image, layer, align_type):
    """
    Align the currently active layer with respect to the current selection, either vertically or horizontally.
    Intended to be used with align_vertical() or align_horizontal().
    """
    if align_type == "AdCV":
        align_layer_to_selection(image, layer, h_align="center", v_align="center", preserve_x=True)
    elif align_type == "AdCH":
        align_layer_to_selection(image, layer, h_align="center", v_align="center", preserve_y=True)


def align_vertical(image, layer):
    """
    Align the currently active layer vertically with respect to the current selection.
    """
    align(image, layer, "AdCV")


def align_horizontal(image, layer):
    """
    Align the currently active layer horizontally with respect to the current selection.
    """
    align(image, layer, "AdCH")


def frame_layer(image, layer, reference_layer):
    """
    Scale a layer equally to the bounds of a reference layer, then centre the layer vertically and horizontally
    within those bounds.
    """
    layer_dimensions = compute_layer_dimensions(layer)
    reference_dimensions = compute_layer_dimensions(reference_layer)

    scale_factor = max(
        reference_dimensions["width"] / float(max(1, layer_dimensions["width"])),
        reference_dimensions["height"] / float(max(1, layer_dimensions["height"])),
    )

    target_width = max(1, int(layer_dimensions["width"] * scale_factor))
    target_height = max(1, int(layer_dimensions["height"] * scale_factor))
    layer.scale(target_width, target_height, True)

    ref_left, ref_top, ref_right, ref_bottom = get_layer_bounds(reference_layer)
    ref_width = ref_right - ref_left
    ref_height = ref_bottom - ref_top
    new_x = ref_left + (ref_width - layer.get_width()) // 2
    new_y = ref_top + (ref_height - layer.get_height()) // 2
    layer.set_offsets(new_x, new_y)


def set_active_layer_mask(layer, visible):
    """
    Set the visibility of the active layer's layer mask.
    """
    if layer is None:
        return
    mask = layer.get_mask() if hasattr(layer, "get_mask") else None
    if mask is None:
        return

    if hasattr(layer, "set_apply_mask"):
        layer.set_apply_mask(visible)
        return

    try:
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-layer-set-apply-mask')
        if proc is not None:
            config = proc.create_config()
            config.set_property('layer', layer)
            config.set_property('apply-mask', bool(visible))
            proc.run(config)
    except Exception:
        pass


def enable_active_layer_mask(layer):
    """
    Enables the active layer's layer mask.
    """
    set_active_layer_mask(layer, True)


def disable_active_layer_mask(layer):
    """
    Disables the active layer's layer mask.
    """
    set_active_layer_mask(layer, False)


def set_active_vector_mask(layer, visible):
    """
    Set the visibility of the active layer's vector mask.

    TODO: GIMP has no direct Photoshop-style vector mask visibility toggle. This is a
    no-op shim for API parity and should be replaced with path/mask composition logic
    if template files rely on vector masks.
    """
    _ = (layer, visible)
    return False


def enable_active_vector_mask(layer):
    """
    Enables the active layer's vector mask.
    """
    return set_active_vector_mask(layer, True)


def disable_active_vector_mask(layer):
    """
    Disables the active layer's vector mask.
    """
    return set_active_vector_mask(layer, False)

def clip_layer_to_alpha(image, source_layer, target_layer):
    """
    Clip target_layer to the alpha channel of source_layer by adding a layer mask.

    This emulates Photoshop's clipping mask behaviour: the target_layer (e.g. a rarity
    gradient overlay) becomes visible only where source_layer (e.g. a Keyrune glyph)
    has opaque pixels.

    Works on both regular layers and group layers.

    Steps:
    1. Alpha-to-selection on source_layer
    2. Create a layer mask on target_layer initialised from the current selection
    3. Add the mask to target_layer
    4. Clear the selection
    """
    pdb = Gimp.get_pdb()
    try:
        # Remove any existing mask on the target layer first
        existing_mask = target_layer.get_mask() if hasattr(target_layer, 'get_mask') else None
        if existing_mask is not None:
            remove_proc = pdb.lookup_procedure('gimp-layer-remove-mask')
            remove_cfg = remove_proc.create_config()
            remove_cfg.set_property('layer', target_layer)
            remove_cfg.set_property('mode', 0)  # MASK_DISCARD
            remove_proc.run(remove_cfg)

        # Step 1: Alpha-to-selection on the source (glyph) layer
        sel_proc = pdb.lookup_procedure('gimp-image-select-item')
        sel_cfg = sel_proc.create_config()
        sel_cfg.set_property('image', image)
        sel_cfg.set_property('operation', 2)  # CHANNEL_OP_REPLACE
        sel_cfg.set_property('item', source_layer)
        sel_proc.run(sel_cfg)

        # Step 2: Create a mask from the current selection
        # ADD_MASK_SELECTION = 4 in GimpAddMaskType
        mask_proc = pdb.lookup_procedure('gimp-layer-create-mask')
        mask_cfg = mask_proc.create_config()
        mask_cfg.set_property('layer', target_layer)
        mask_cfg.set_property('mask-type', 4)  # ADD_MASK_SELECTION
        mask_result = mask_proc.run(mask_cfg)
        mask = mask_result.index(1)

        # Step 3: Add the mask to the target layer
        add_proc = pdb.lookup_procedure('gimp-layer-add-mask')
        add_cfg = add_proc.create_config()
        add_cfg.set_property('layer', target_layer)
        add_cfg.set_property('mask', mask)
        add_proc.run(add_cfg)

        # Step 4: Clear selection
        clear_selection(image)
        return True
    except Exception as e:
        clear_selection(image)
        return False


def apply_stroke(image, layer, stroke_weight, stroke_colour):
    """
    Applies an outer stroke to a layer, emulating Photoshop's Layer Style > Stroke.

    GIMP 3 has no non-destructive layer effects. This emulates outer stroke by:
    1. Selecting the layer's alpha channel (glyph shape, not bounding box)
    2. Growing the selection by stroke_weight pixels
    3. Creating a new layer below, filling with stroke_colour
    4. Clearing the selection

    This produces a clean outer stroke that follows the glyph contour.
    """
    if layer is None:
        return False
    color = stroke_colour if stroke_colour is not None else rgb_black()
    pdb = Gimp.get_pdb()
    try:
        # Step 1: Alpha-to-selection on the text layer (selects glyph pixels)
        sel_proc = pdb.lookup_procedure('gimp-image-select-item')
        sel_cfg = sel_proc.create_config()
        sel_cfg.set_property('image', image)
        sel_cfg.set_property('operation', 2)  # CHANNEL_OP_REPLACE
        sel_cfg.set_property('item', layer)
        sel_proc.run(sel_cfg)
        # Step 2: Grow selection by stroke_weight to create outer stroke area
        grow_proc = pdb.lookup_procedure('gimp-selection-grow')
        grow_cfg = grow_proc.create_config()
        grow_cfg.set_property('image', image)
        grow_cfg.set_property('steps', stroke_weight)
        grow_proc.run(grow_cfg)
        parent = layer.get_parent()
        if parent is not None:
            siblings = parent.get_children()
        else:
            siblings = image.get_layers()
        layer_pos = 0
        for i, sib in enumerate(siblings):
            if sib.get_id() == layer.get_id():
                layer_pos = i
                break
        stroke_layer = Gimp.Layer.new(
            image,
            f"{layer.get_name()} Stroke",
            image.get_width(),
            image.get_height(),
            Gimp.ImageType.RGBA_IMAGE,
            100.0,  # full opacity
            Gimp.LayerMode.NORMAL,
        )
        image.insert_layer(stroke_layer, parent, layer_pos + 1)  # just below text layer
        Gimp.context_set_foreground(color)
        fill_proc = pdb.lookup_procedure('gimp-drawable-edit-fill')
        fill_cfg = fill_proc.create_config()
        fill_cfg.set_property('drawable', stroke_layer)
        fill_cfg.set_property('fill-type', 0)  # FILL_FOREGROUND
        fill_proc.run(fill_cfg)
        clear_selection(image)
        return True
    except Exception:
        clear_selection(image)
        return False


def save_and_close(image, file_name, file_path):
    from src import config
    output_dir = os.path.join(file_path, "out")
    os.makedirs(output_dir, exist_ok=True)
    image.flatten()

    fmt = getattr(config, 'OUTPUT_FORMAT', 'png').lower()
    max_kb = getattr(config, 'OUTPUT_MAX_SIZE_KB', None)

    if fmt == 'jpeg' or fmt == 'jpg':
        ext = '.jpg'
        out_path = os.path.join(output_dir, f"{file_name}{ext}")
        _export_jpeg_under_limit(image, out_path, max_kb)
    else:
        out_path = os.path.join(output_dir, f"{file_name}.png")
        output_file = Gio.File.new_for_path(out_path)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, output_file)
    image.delete()

def _export_jpeg_under_limit(image, out_path, max_kb=None, start_quality=0.95):
    """Export image as JPEG, stepping quality down to stay under max_kb."""
    pdb = Gimp.get_pdb()
    pdb_proc = pdb.lookup_procedure('file-jpeg-export')
    quality = start_quality

    while quality >= 0.10:
        pdb_config = pdb_proc.create_config()
        pdb_config.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
        pdb_config.set_property('image', image)
        pdb_config.set_property('file', Gio.File.new_for_path(out_path))
        pdb_config.set_property('quality', quality)
        ret = pdb_proc.run(pdb_config)

        if max_kb is None:
            return  # No size limit, done after first export

        file_size_kb = os.path.getsize(out_path) / 1024
        if file_size_kb <= max_kb:
            return  # Under limit, done

        # File too big — step down quality and retry
        quality -= 0.05

    # Exhausted quality steps; file is as small as we can get it


def strip_reminder_text(oracle_text):
    """
    Strip out any reminder text that a card's oracle text has (reminder text in parentheses).
    If this would empty the string, instead return the original string.
    """
    oracle_text_stripped = re.sub(r"\(.*?\)", "", oracle_text, count=1)

    oracle_text_stripped = re.sub(r" +", " ", oracle_text_stripped)
    if oracle_text_stripped != "":
        return oracle_text_stripped
    return oracle_text


def get_text_layer_colour(layer):
    """
    Occasionally, Photoshop has issues with retrieving the colour of a text layer. This helper guards
    against errors and null values by defaulting to rgb_black() in the event of a problem.
    """
    text_layer_colour = None
    try:
        text_layer_colour = _get_text_layer_color(layer)
        if text_layer_colour is None:
            text_layer_colour = _color_from_rgb_tuple(RGB_BLACK)
    except Exception:
        text_layer_colour = _color_from_rgb_tuple(RGB_BLACK)
    return text_layer_colour


def create_new_layer(image, layer_name="Layer"):
    """
    Creates a new layer below the currently active layer. The layer will be visible.
    """
    if layer_name is None:
        layer_name = "Layer"

    selected_layers = image.get_selected_layers() if hasattr(image, "get_selected_layers") else []
    active_layer = selected_layers[0] if selected_layers else (image.get_layers()[0] if image.get_layers() else None)

    parent, position = _get_insertion_context(image, active_layer)
    layer = Gimp.Layer.new(
        image,
        layer_name,
        image.get_width(),
        image.get_height(),
        Gimp.ImageType.RGBA_IMAGE,
        100.0,
        Gimp.LayerMode.NORMAL,
    )
    layer.set_visible(True)
    image.insert_layer(layer, parent, position)
    return layer


def array_index(array, thing):
    """
    Get the first index of thing in array, since Extendscript doesn't come with this.
    """
    if array is not None:
        try:
            return array.index(thing)
        except ValueError:
            return -1
    return -1


def in_array(array, thing):
    """
    Returns true if thing in array.
    """
    return array_index(array, thing) >= 0


def replace_text(layer, replace_this, replace_with):
    """
    Replace all instances of `replace_this` in the specified layer with `replace_with`.
    """
    text = _get_layer_text(layer)
    if text is None:
        return
    _set_layer_text(layer, text.replace(replace_this, replace_with))


def paste_file(image, layer, file):
    """
    Pastes the given file into the specified layer.
    """
    file_path = file.get_path() if isinstance(file, Gio.File) else str(file)
    imported_layer = Gimp.file_load_layer(
        Gimp.RunMode.NONINTERACTIVE,
        image,
        Gio.File.new_for_path(file_path),
    )

    parent = layer.get_parent() if layer is not None and hasattr(layer, "get_parent") else None
    position = 0
    siblings = parent.get_children() if parent else image.get_layers()
    for i, sibling in enumerate(siblings):
        if sibling == layer:
            position = i
            break

    image.insert_layer(imported_layer, parent, position)

    if layer is not None:
        imported_layer.set_name(layer.get_name())
        imported_layer.set_visible(layer.get_visible())
        image.remove_layer(layer)

    return imported_layer


def paste_file_into_new_layer(image, file):
    """
    Wrapper for paste_file which creates a new layer for the file next to the active layer. Returns the new layer.
    """
    new_layer = create_new_layer(image, "New Layer")
    return paste_file(image, new_layer, file)


def retrieve_scryfall_scan(image_url, file_path):
    """
    Calls the Python script which queries Scryfall for full-res scan and saves the resulting jpeg to disk in /scripts.
    Returns a file path for the scan if the Python call was successful, or raises an error if it wasn't.
    """
    script_path = os.path.join(file_path, "scripts", "get_card_scan.py")
    python_command = os.environ.get("PYTHON", "python3")
    subprocess.run([python_command, script_path, image_url], check=True)
    return os.path.join(file_path, "scripts", "card.jpg")


def insert_scryfall_scan(image, image_url, file_path):
    """
    Downloads the specified scryfall scan and inserts it into a new layer next to the active layer. Returns the new layer.
    """
    scryfall_scan = retrieve_scryfall_scan(image_url, file_path)
    return paste_file_into_new_layer(image, scryfall_scan)
