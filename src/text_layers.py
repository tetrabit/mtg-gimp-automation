import gi

gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, Gegl

from src.helpers import (
    compute_layer_dimensions,
    compute_text_layer_dimensions,
    compute_text_layer_bounds,
    get_layer_bounds,
    find_layer_by_name,
    rgb_black,
    rgb_white,
    apply_stroke,
    clip_layer_to_alpha,
    create_new_layer,
    ensure_text_layer,
    get_font_by_name,
    get_pango_family,
)
from src.format_text import format_text, generate_italics, escape_pango, rgb_to_hex
from src.constants import RARITY_COMMON, RARITY_BONUS, RARITY_SPECIAL, RARITY_MYTHIC


_ = (Gegl, create_new_layer)

# ---------------------------------------------------------------------------
# Font sizes (in pixels) calibrated against XCF template layer dimensions.
# Canvas is 3288×4488.  Each size targets ~80% of the layer's pixel height
# so ascenders/descenders fit without clipping.
# ---------------------------------------------------------------------------
FONT_SIZE_CARD_NAME = 140.0       # Card Name layer: 836×147  → enlarged to fill name bar
FONT_SIZE_MANA_COST = 130.0       # Mana Cost layer: 872×128  → enlarged for NDPMTG circle+icon
FONT_SIZE_TYPE_LINE = 104.0       # Typeline layer: 1291×131  → acceptable as-is
FONT_SIZE_RULES_TEXT = 100.0       # Rules Text: ~71% of card name size, matching real MTG proportions
FONT_SIZE_POWER_TOUGHNESS = 100.0  # P/T layer: 250×126        → ~80% of 126
FONT_SIZE_EXPANSION = 130.0        # Expansion Symbol: 155×164  → ~80% of 164
FONT_SIZE_ARTIST = 44.0            # Artist layer: 223×56       → ~80% of 56
FONT_SIZE_DEFAULT = 40.0           # Fallback for any unspecified field

def _dimension_height(dimensions):
    if hasattr(dimensions, "height"):
        return float(dimensions.height)
    if isinstance(dimensions, dict):
        return float(dimensions.get("height", 0.0))
    if isinstance(dimensions, (tuple, list)) and len(dimensions) > 1:
        return float(dimensions[1])
    return 0.0


def _bound_value(bound):
    as_method = getattr(bound, "as", None)
    if callable(as_method):
        try:
            value = as_method("px")
            if isinstance(value, (int, float, str)):
                return float(value)
        except Exception:
            pass
    try:
        return float(bound)
    except Exception:
        return 0.0


def _bounds_to_float(bounds):
    if len(bounds) < 4:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        _bound_value(bounds[0]),
        _bound_value(bounds[1]),
        _bound_value(bounds[2]),
        _bound_value(bounds[3]),
    )


def _font_size_tuple(layer):
    font_size = layer.get_font_size()
    if isinstance(font_size, (tuple, list)):
        if len(font_size) >= 3 and isinstance(font_size[1], (int, float)):
            return float(font_size[1]), font_size[2]
        if len(font_size) >= 2 and isinstance(font_size[0], (int, float)):
            return float(font_size[0]), font_size[1]
        if len(font_size) == 1 and isinstance(font_size[0], (int, float)):
            return float(font_size[0]), Gimp.Unit.point()
    if isinstance(font_size, (int, float)):
        return float(font_size), Gimp.Unit.point()
    return 0.0, Gimp.Unit.point()


def _set_relative_y(layer, delta):
    offsets = layer.get_offsets()
    if isinstance(offsets, (tuple, list)) and len(offsets) >= 3:
        x = int(offsets[1])
        y = int(offsets[2])
    elif isinstance(offsets, (tuple, list)) and len(offsets) >= 2:
        x = int(offsets[0])
        y = int(offsets[1])
    else:
        x = 0
        y = 0
    layer.set_offsets(x, int(round(y + delta)))


def scale_text_right_overlap(layer, reference_layer):
    step_size = 0.2
    reference_left = _bounds_to_float(get_layer_bounds(reference_layer))[0]
    layer_left, _, layer_right, _ = _bounds_to_float(get_layer_bounds(layer))
    if reference_left < layer_left:
        return

    font_size, font_unit = _font_size_tuple(layer)
    while layer_right > reference_left - 24 and font_size > 0:
        font_size -= step_size
        if font_size <= 0:
            break
        layer.set_font_size(font_size, font_unit)
        layer_right = _bounds_to_float(get_layer_bounds(layer))[2]


def scale_text_to_fit_reference(image, layer, reference_layer):
    fine_step = 0.25
    coarse_step = 4.0  # large step for fast initial convergence
    font_size, font_unit = _font_size_tuple(layer)
    reference_height = _dimension_height(compute_layer_dimensions(reference_layer)) - 64.0
    layer_height = _dimension_height(compute_text_layer_dimensions(image, layer))
    scaled = False
    # Phase 1: Coarse pass — step down quickly until text is near reference height.
    # This avoids hundreds of slow 0.25px iterations when starting font is much too large.
    while reference_height < layer_height and font_size > coarse_step:
        scaled = True
        font_size -= coarse_step
        layer.set_font_size(font_size, font_unit)
        layer_height = _dimension_height(compute_text_layer_dimensions(image, layer))
    # Phase 2: If we overshot (text now smaller than reference), step back up once
    if scaled and layer_height < reference_height:
        font_size += coarse_step
        layer.set_font_size(font_size, font_unit)
        layer_height = _dimension_height(compute_text_layer_dimensions(image, layer))
    # Phase 3: Fine pass — step down 0.25px for pixel-accurate fit
    while reference_height < layer_height and font_size > 0:
        scaled = True
        font_size -= fine_step
        if font_size <= 0:
            break
        layer.set_font_size(font_size, font_unit)
        layer_height = _dimension_height(compute_text_layer_dimensions(image, layer))
    return scaled


def vertically_align_text(image, layer, reference_layer):
    ref_left, ref_top, ref_right, ref_bottom = _bounds_to_float(get_layer_bounds(reference_layer))
    ref_height = ref_bottom - ref_top

    ink_bounds = _bounds_to_float(compute_text_layer_bounds(image, layer))
    ink_top = ink_bounds[1]
    ink_bottom = ink_bounds[3]
    ink_height = ink_bottom - ink_top

    if ink_height <= 0 or ref_height <= 0:
        return

    desired_ink_top = ref_top + (ref_height - ink_height) / 2.0
    delta = desired_ink_top - ink_top
    _set_relative_y(layer, delta)


def vertically_nudge_creature_text(image, layer, reference_layer, top_reference_layer):
    _ = image
    layer_left, layer_top, layer_right, layer_bottom = _bounds_to_float(get_layer_bounds(layer))
    pt_left, pt_top, pt_right, pt_bottom = _bounds_to_float(get_layer_bounds(reference_layer))
    _, _, _, top_ref_bottom = _bounds_to_float(get_layer_bounds(top_reference_layer))

    if layer_right < pt_left:
        return

    overlap_left = max(layer_left, pt_left)
    overlap_top = max(layer_top, pt_top)
    overlap_right = min(layer_right, pt_right)
    overlap_bottom = min(layer_bottom, pt_bottom)
    if overlap_right <= overlap_left or overlap_bottom <= overlap_top:
        return

    delta = top_ref_bottom - overlap_bottom
    if delta < 0:
        _set_relative_y(layer, delta)


class TextField:
    def __init__(self, image, layer, text_contents, text_colour, font_name=None,
                 font_size=None, justification=None):
        self.image = image
        self.layer = layer
        self.text_contents = ""
        if text_contents is not None:
            self.text_contents = str(text_contents)
        self.text_colour = text_colour
        self.font_name = font_name
        self.font_size = font_size if font_size is not None else FONT_SIZE_DEFAULT
        self.justification = justification
        # Capture original layer bounds before ensure_text_layer replaces it.
        # Needed for right-alignment of dynamic text layers (e.g. mana cost).
        orig_bounds = _bounds_to_float(get_layer_bounds(layer))
        self._original_right = orig_bounds[2]
        self._original_top = orig_bounds[1]
        self._original_bottom = orig_bounds[3]

    def execute(self):
        self.layer = ensure_text_layer(
            self.image, self.layer, self.text_contents,
            font_size=self.font_size,
        )
        self.layer.set_visible(True)
        if self.font_name is not None:
            # Use Pango markup with fontconfig family name (proven approach).
            # Gimp.Font.get_by_name() uses GIMP internal IDs (gimpfontNNN)
            # which don't match fontconfig names — set_font() silently fails.
            # set_markup() uses the system Pango font map which resolves
            # fontconfig families correctly.
            family = get_pango_family(self.font_name)
            escaped = escape_pango(self.text_contents)
            color_attr = ''
            if self.text_colour is not None:
                rgb = self.text_colour
                if isinstance(rgb, (tuple, list)) and len(rgb) >= 3:
                    color_attr = f' foreground="{rgb_to_hex(rgb)}"'
                elif hasattr(rgb, 'get_rgba'):
                    rgba = rgb.get_rgba()
                    if isinstance(rgba, (tuple, list)) and len(rgba) >= 3:
                        r, g, b = rgba[0], rgba[1], rgba[2]
                        if max(r, g, b) <= 1.0:
                            color_attr = f' foreground="{rgb_to_hex((int(round(r * 255)), int(round(g * 255)), int(round(b * 255))))}"'
                        else:
                            color_attr = f' foreground="{rgb_to_hex((int(round(r)), int(round(g)), int(round(b))))}"'
            # Set base color to white so GIMP's outer <span color="#RRGGBB"> wrapper
            # doesn't suppress inner foreground= attributes (see gimptextlayout.c:655)
            self.layer.set_color(Gegl.Color.new("rgb(255,255,255)"))
            self.layer.set_markup(
                f'<span font_family="{family}"{color_attr}>{escaped}</span>'
            )
        else:
            self.layer.set_text(self.text_contents)
            if self.text_colour is not None:
                self.layer.set_color(self.text_colour)
        # Apply justification if specified
        if self.justification is not None:
            self.layer.set_justification(self.justification)


class ScaledTextField(TextField):
    def __init__(self, image, layer, text_contents, text_colour, reference_layer, font_name=None, font_size=None):
        super().__init__(image, layer, text_contents, text_colour, font_name=font_name, font_size=font_size)
        self.reference_layer = reference_layer

    def execute(self):
        super().execute()
        scale_text_right_overlap(self.layer, self.reference_layer)


class ExpansionSymbolField(TextField):
    def __init__(self, image, layer, text_contents, rarity, font_name=None):
        super().__init__(
            image, layer, text_contents, rgb_black(),
            font_name=font_name,
            font_size=FONT_SIZE_EXPANSION,
        )
        self.rarity = rarity
        if rarity in (RARITY_BONUS, RARITY_SPECIAL):
            self.rarity = RARITY_MYTHIC

    def execute(self):
        super().execute()
        stroke_weight = 6
        if self.rarity == RARITY_COMMON:
            apply_stroke(self.image, self.layer, stroke_weight, rgb_white())
            return
        # For non-common rarities, enable the rarity gradient overlay and
        # clip it to the glyph shape (emulating Photoshop clipping masks).
        parent = self.layer.get_parent()
        if parent is not None:
            mask_layer = find_layer_by_name(parent, self.rarity)
            if mask_layer is not None:
                mask_layer.set_visible(True)
                # Clip the rarity gradient to the Keyrune glyph shape
                clip_layer_to_alpha(self.image, self.layer, mask_layer)
        apply_stroke(self.image, self.layer, stroke_weight, rgb_black())


class BasicFormattedTextField(TextField):
    def __init__(self, image, layer, text_contents, text_colour,
                 font_size=None, justification=None):
        super().__init__(
            image, layer, text_contents, text_colour,
            font_size=font_size,
            justification=justification,
        )

    def execute(self):
        super().execute()
        italic_text = generate_italics(self.text_contents)
        format_text(self.layer, self.text_contents, italic_text, -1, False)
        # Re-apply justification after format_text (which sets LEFT by default)
        if self.justification is not None:
            self.layer.set_justification(self.justification)
        # Reposition layer after format_text resizes it.
        # For RIGHT-justified text (e.g. mana cost), move so right edge
        # aligns with the original rasterized layer's right edge.
        # For all fields, vertically center within original bounds.
        if self.justification == Gimp.TextJustification.RIGHT and self._original_right > 0:
            new_width = self.layer.get_width()
            new_x = int(self._original_right - new_width)
            orig_mid_y = (self._original_top + self._original_bottom) / 2.0
            new_height = self.layer.get_height()
            new_y = int(orig_mid_y - new_height / 2.0)
            self.layer.set_offsets(new_x, new_y)


class FormattedTextField(TextField):
    def __init__(self, image, layer, text_contents, text_colour, flavour_text, is_centred):
        super().__init__(image, layer, text_contents, text_colour)
        self.flavour_text = ""
        if flavour_text is not None:
            self.flavour_text = str(flavour_text)
        self.is_centred = is_centred

    def execute(self):
        super().execute()
        italic_text = generate_italics(self.text_contents)
        flavour_index = -1

        if len(self.flavour_text) > 1:
            flavour_text_split = self.flavour_text.split("*")
            if len(flavour_text_split) > 1:
                for i in range(0, len(flavour_text_split), 2):
                    if flavour_text_split[i] != "":
                        italic_text.append(flavour_text_split[i])
                self.flavour_text = "".join(flavour_text_split)
            else:
                italic_text.append(self.flavour_text)
            flavour_index = len(self.text_contents)

        format_text(
            self.layer,
            self.text_contents + "\n" + self.flavour_text,
            italic_text,
            flavour_index,
            self.is_centred,
        )
        if self.is_centred:
            self.layer.set_justification(Gimp.TextJustification.CENTER)


class FormattedTextArea(FormattedTextField):
    def __init__(
        self,
        image,
        layer,
        text_contents,
        text_colour,
        flavour_text,
        is_centred,
        reference_layer,
    ):
        super().__init__(image, layer, text_contents, text_colour, flavour_text, is_centred)
        self.reference_layer = reference_layer
    def execute(self):
        # Rules text needs fixed-box mode for word wrapping.
        # Use the REFERENCE LAYER's width for the text box, not the original
        # rasterized placeholder which is often much narrower (e.g. 1297 vs 2584).
        # A small inset keeps text from touching the textbox edges.
        ref_width = self.reference_layer.get_width()
        text_box_width = int(ref_width * 0.95)  # 5% inset total (2.5% each side)
        self.layer = ensure_text_layer(
            self.image, self.layer, self.text_contents,
            fixed_width=text_box_width,
            font_size=FONT_SIZE_RULES_TEXT,
        )
        # Position text layer horizontally centered within reference area
        ref_offsets = self.reference_layer.get_offsets()
        ref_x = ref_offsets[1] if len(ref_offsets) >= 3 else ref_offsets[0]
        inset = (ref_width - text_box_width) // 2
        layer_offsets = self.layer.get_offsets()
        layer_y = layer_offsets[2] if len(layer_offsets) >= 3 else layer_offsets[1]
        self.layer.set_offsets(int(ref_x + inset), int(layer_y))
        self.layer.set_visible(True)
        self.layer.set_text(self.text_contents)
        # NOTE: format_text() sets layer base color to white before set_markup().
        # This ensures GIMP's outer <span color="..."> wrapper doesn't suppress
        # per-character foreground= color attributes (mana symbol colors).
        # Apply formatting (mana symbols, italics, flavour text)
        italic_text = generate_italics(self.text_contents)
        flavour_index = -1
        if len(self.flavour_text) > 1:
            flavour_text_split = self.flavour_text.split("*")
            if len(flavour_text_split) > 1:
                for i in range(0, len(flavour_text_split), 2):
                    if flavour_text_split[i] != "":
                        italic_text.append(flavour_text_split[i])
                self.flavour_text = "".join(flavour_text_split)
            else:
                italic_text.append(self.flavour_text)
            flavour_index = len(self.text_contents)
        format_text(
            self.layer,
            self.text_contents + "\n" + self.flavour_text,
            italic_text,
            flavour_index,
            self.is_centred,
        )
        if self.is_centred:
            self.layer.set_justification(Gimp.TextJustification.CENTER)
        # Scale to fit reference and align
        if self.text_contents != "" or self.flavour_text != "":
            scale_text_to_fit_reference(self.image, self.layer, self.reference_layer)
            vertically_align_text(self.image, self.layer, self.reference_layer)


class CreatureFormattedTextArea(FormattedTextArea):
    def __init__(
        self,
        image,
        layer,
        text_contents,
        text_colour,
        flavour_text,
        is_centred,
        reference_layer,
        pt_reference_layer,
        pt_top_reference_layer,
    ):
        super().__init__(
            image,
            layer,
            text_contents,
            text_colour,
            flavour_text,
            is_centred,
            reference_layer,
        )
        self.pt_reference_layer = pt_reference_layer
        self.pt_top_reference_layer = pt_top_reference_layer

    def execute(self):
        super().execute()
        vertically_nudge_creature_text(
            self.image,
            self.layer,
            self.pt_reference_layer,
            self.pt_top_reference_layer,
        )
