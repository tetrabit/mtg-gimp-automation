"""Template class hierarchy for MTG card rendering in GIMP 3.

This module is converted from `mtg-photoshop-automation/scripts/templates.jsx`.
It contains the shared base templates and concrete template classes used by the
render pipeline to load card templates, place art, enable frame layers, and
populate text fields.
"""

import os

import gi
gi.require_version('Gimp', '3.0')
import gi.repository as gir

from src.constants import LayerNames, DEFAULT_LAYER, FONT_NAME_BELEREN, FONT_NAME_KEYRUNE
from src.config import EXPANSION_SYMBOL_CHARACTER, get_expansion_symbol_character
from src.helpers import (
    find_layer_by_name, paste_file, frame_layer, save_and_close,
    rgb_black, rgb_white, get_text_layer_colour, strip_reminder_text,
    replace_text, enable_active_layer_mask, disable_active_layer_mask,
    enable_active_vector_mask, disable_active_vector_mask,
    insert_scryfall_scan, in_array, ensure_text_layer,
)
from src.text_layers import (
    TextField, ScaledTextField, ExpansionSymbolField,
    BasicFormattedTextField, FormattedTextField,
    FormattedTextArea, CreatureFormattedTextArea,
)
from src.text_layers import (
    FONT_SIZE_CARD_NAME, FONT_SIZE_MANA_COST, FONT_SIZE_TYPE_LINE,
    FONT_SIZE_POWER_TOUGHNESS, FONT_SIZE_ARTIST,
)

Gimp = getattr(gir, "Gimp")
Gio = getattr(gir, "Gio")


_ = (
    save_and_close,
    strip_reminder_text,
    disable_active_layer_mask,
    enable_active_vector_mask,
    disable_active_vector_mask,
    FormattedTextField,
)


class BaseTemplate:
    def __init__(self, layout, file, file_path):
        self.layout = layout
        self.file = file
        self.file_path = file_path
        self.exit_early = False
        self.expansion_symbol_character = get_expansion_symbol_character(getattr(self.layout, 'set_code', ''))
        self.art_reference = None

        self.load_template(file_path)

        self.art_layer = self._layer(self.image, DEFAULT_LAYER)
        self.legal = self._layer(self.image, LayerNames.LEGAL)
        self.text_layers = [
            TextField(
                image=self.image,
                layer=self._layer(self.legal, LayerNames.ARTIST),
                text_contents=self.layout.artist,
                text_colour=rgb_white(),
                font_size=FONT_SIZE_ARTIST,
            ),
        ]

    def _layer(self, image_or_group, name):
        layer = find_layer_by_name(image_or_group, name)
        if layer is None:
            layer = find_layer_by_name(image_or_group, name, recursive=True)
        if layer is None:
            raise RuntimeError(f"Layer not found: {name}")
        return layer

    def template_file_name(self) -> str:
        raise NotImplementedError("Template name not specified!")

    def template_suffix(self) -> str:
        return ""

    @staticmethod
    def _hide_children(group):
        try:
            children = group.get_children() if hasattr(group, "get_children") else []
            for child in children:
                child.set_visible(False)
        except Exception:
            pass

    def load_template(self, file_path):
        template_path = os.path.join(file_path, "templates", self.template_file_name() + ".xcf")
        template_file = Gio.File.new_for_path(template_path)
        try:
            self.image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, template_file)
        except Exception as err:
            raise RuntimeError(
                f"\n\nFailed to open the template for this card at:\n\n"
                f"{template_path}\n\nCheck your templates folder and try again"
            ) from err

    def enable_frame_layers(self):
        raise NotImplementedError("Frame layers not specified!")

    # Layer names that exist only as positioning references and should never
    # be visible in final output.  PSD->XCF conversion may leave them visible.
    _REFERENCE_LAYERS = (
        LayerNames.ART_FRAME,
        LayerNames.FULL_ART_FRAME,
        LayerNames.TEXTBOX_REFERENCE,
        LayerNames.PT_REFERENCE,
        LayerNames.PT_TOP_REFERENCE,
    )

    def _hide_reference_layers(self):
        """Hide structural/reference layers that should not render visibly."""
        for name in self._REFERENCE_LAYERS:
            try:
                layer = find_layer_by_name(self.image, name, recursive=True)
                if layer is not None:
                    layer.set_visible(False)
            except Exception:
                pass

    def load_artwork(self):
        self.art_layer = paste_file(self.image, self.art_layer, self.file)

    def execute(self):
        self.load_artwork()
        frame_layer(self.image, self.art_layer, self.art_reference)
        self.enable_frame_layers()
        # Fix Shadows blend mode — PSD→XCF conversion loses MULTIPLY mode
        shadows = find_layer_by_name(self.image, LayerNames.SHADOWS)
        if shadows is not None:
            shadows.set_mode(Gimp.LayerMode.MULTIPLY_LEGACY)
        self._hide_reference_layers()
        for text_layer in self.text_layers:
            text_layer.execute()
        file_name = self.layout.name
        suffix = self.template_suffix()
        if suffix:
            file_name = f"{file_name} ({suffix})"
        return file_name


class ChilliBaseTemplate(BaseTemplate):
    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)

        self.is_creature = self.layout.power is not None and self.layout.toughness is not None
        self.is_legendary = "Legendary" in self.layout.type_line
        self.is_land = "Land" in self.layout.type_line
        self.is_companion = in_array(self.layout.frame_effects, "companion")
        self.name_shifted = False
        self.type_line_shifted = False

    def basic_text_layers(self, text_and_icons):
        name = self._layer(text_and_icons, LayerNames.NAME)
        name_selected = name
        try:
            name_shift = self._layer(text_and_icons, LayerNames.NAME_SHIFT)
            if self.name_shifted:
                name_selected = name_shift
                name.set_visible(False)
                name_shift.set_visible(True)
            else:
                name_shift.set_visible(False)
                name.set_visible(True)
        except Exception:
            pass

        type_line = self._layer(text_and_icons, LayerNames.TYPE_LINE)
        type_line_selected = type_line
        try:
            type_line_shift = self._layer(text_and_icons, LayerNames.TYPE_LINE_SHIFT)
            if self.type_line_shifted:
                type_line_selected = type_line_shift
                type_line.set_visible(False)
                type_line_shift.set_visible(True)

                colour_indicator = self._layer(self.image, LayerNames.COLOUR_INDICATOR)
                self._layer(colour_indicator, self.layout.pinlines).set_visible(True)
            else:
                type_line_shift.set_visible(False)
                type_line.set_visible(True)
        except Exception:
            pass

        mana_cost = self._layer(text_and_icons, LayerNames.MANA_COST)
        expansion_symbol = self._layer(text_and_icons, LayerNames.EXPANSION_SYMBOL)

        self.text_layers.extend([
            BasicFormattedTextField(
                image=self.image,
                layer=mana_cost,
                text_contents=self.layout.mana_cost,
                text_colour=rgb_black(),
                font_size=FONT_SIZE_MANA_COST,
                justification=Gimp.TextJustification.RIGHT,
            ),
            ScaledTextField(
                image=self.image,
                layer=name_selected,
                text_contents=self.layout.name,
                text_colour=get_text_layer_colour(name_selected),
                reference_layer=mana_cost,
                font_name=FONT_NAME_BELEREN,
                font_size=FONT_SIZE_CARD_NAME,
            ),
            ExpansionSymbolField(
                image=self.image,
                layer=expansion_symbol,
                text_contents=self.expansion_symbol_character,
                rarity=self.layout.rarity,
                font_name=FONT_NAME_KEYRUNE,
            ),
            ScaledTextField(
                image=self.image,
                layer=type_line_selected,
                text_contents=self.layout.type_line,
                text_colour=get_text_layer_colour(type_line_selected),
                reference_layer=expansion_symbol,
                font_name=FONT_NAME_BELEREN,
                font_size=FONT_SIZE_TYPE_LINE,
            ),
        ])

    def enable_hollow_crown(self, crown, pinlines):
        enable_active_layer_mask(crown)
        enable_active_layer_mask(pinlines)
        enable_active_layer_mask(self._layer(self.image, LayerNames.SHADOWS))
        self._layer(self.image, LayerNames.HOLLOW_CROWN_SHADOW).set_visible(True)

    def paste_scryfall_scan(self, reference_layer, file_path, rotate=False):
        layer = insert_scryfall_scan(self.image, self.layout.scryfall_scan, file_path)
        if rotate is True:
            layer.transform_rotate_simple(Gimp.RotationType.DEGREES90, True, 0, 0)
        frame_layer(self.image, layer, reference_layer)


class NormalTemplate(ChilliBaseTemplate):
    def template_file_name(self) -> str:
        return "normal"

    def rules_text_and_pt_layers(self, text_and_icons):
        is_centred = (
            len(self.layout.flavour_text) <= 1
            and len(self.layout.oracle_text) <= 70
            and "\n" not in self.layout.oracle_text
        )

        noncreature_copyright = self._layer(self.legal, LayerNames.NONCREATURE_COPYRIGHT)
        creature_copyright = self._layer(self.legal, LayerNames.CREATURE_COPYRIGHT)

        power_toughness = self._layer(text_and_icons, LayerNames.POWER_TOUGHNESS)
        if self.is_creature:
            rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_CREATURE)
            self.text_layers.extend([
                TextField(
                    image=self.image,
                    layer=power_toughness,
                    text_contents=f"{self.layout.power}/{self.layout.toughness}",
                    text_colour=get_text_layer_colour(power_toughness),
                    font_name=FONT_NAME_BELEREN,
                    font_size=FONT_SIZE_POWER_TOUGHNESS,
                ),
                CreatureFormattedTextArea(
                    image=self.image,
                    layer=rules_text,
                    text_contents=self.layout.oracle_text,
                    text_colour=get_text_layer_colour(rules_text),
                    flavour_text=self.layout.flavour_text,
                    is_centred=is_centred,
                    reference_layer=self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE),
                    pt_reference_layer=self._layer(text_and_icons, LayerNames.PT_REFERENCE),
                    pt_top_reference_layer=self._layer(text_and_icons, LayerNames.PT_TOP_REFERENCE),
                ),
            ])

            noncreature_copyright.set_visible(False)
            creature_copyright.set_visible(True)
            # Hide the unused noncreature rules text group
            noncreature_rules = self._layer(text_and_icons, LayerNames.RULES_TEXT_NONCREATURE)
            noncreature_rules.set_visible(False)
        else:
            rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_NONCREATURE)
            self.text_layers.append(
                FormattedTextArea(
                    image=self.image,
                    layer=rules_text,
                    text_contents=self.layout.oracle_text,
                    text_colour=get_text_layer_colour(rules_text),
                    flavour_text=self.layout.flavour_text,
                    is_centred=is_centred,
                    reference_layer=self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE),
                ),
            )

            power_toughness.set_visible(False)

            # Hide the unused creature rules text group
            creature_rules = self._layer(text_and_icons, LayerNames.RULES_TEXT_CREATURE)
            creature_rules.set_visible(False)
    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)

        self.art_reference = self._layer(self.image, LayerNames.ART_FRAME)
        if self.layout.is_colourless:
            self.art_reference = self._layer(self.image, LayerNames.FULL_ART_FRAME)

        self.name_shifted = self.layout.transform_icon is not None
        self.type_line_shifted = self.layout.colour_indicator is not None

        text_and_icons = self._layer(self.image, LayerNames.TEXT_AND_ICONS)
        self.basic_text_layers(text_and_icons)
        self.rules_text_and_pt_layers(text_and_icons)

    def enable_frame_layers(self):
        twins = self._layer(self.image, LayerNames.TWINS)
        self._hide_children(twins)
        self._layer(twins, self.layout.twins).set_visible(True)
        if self.is_creature:
            pt_box = self._layer(self.image, LayerNames.PT_BOX)
            self._hide_children(pt_box)
            self._layer(pt_box, self.layout.twins).set_visible(True)

        pinlines = self._layer(self.image, LayerNames.PINLINES_TEXTBOX)
        if self.is_land:
            pinlines = self._layer(self.image, LayerNames.LAND_PINLINES_TEXTBOX)
        self._hide_children(pinlines)
        self._layer(pinlines, self.layout.pinlines).set_visible(True)

        if self.is_land:
            self._layer(self.image, LayerNames.PINLINES_TEXTBOX).set_visible(False)
        else:
            self._layer(self.image, LayerNames.LAND_PINLINES_TEXTBOX).set_visible(False)

        background = self._layer(self.image, LayerNames.BACKGROUND)
        if self.layout.is_nyx:
            background = self._layer(self.image, LayerNames.NYX)
        self._hide_children(background)
        self._layer(background, self.layout.background).set_visible(True)

        crown = None
        if self.is_legendary:
            crown = self._layer(self.image, LayerNames.LEGENDARY_CROWN)
            self._hide_children(crown)
            self._layer(crown, self.layout.pinlines).set_visible(True)
            border = self._layer(self.image, LayerNames.BORDER)
            self._hide_children(border)
            self._layer(border, LayerNames.NORMAL_BORDER).set_visible(False)
            self._layer(border, LayerNames.LEGENDARY_BORDER).set_visible(True)

        if self.is_companion:
            companion = self._layer(self.image, LayerNames.COMPANION)
            self._layer(companion, self.layout.pinlines).set_visible(True)

        if (self.is_legendary and self.layout.is_nyx) or self.is_companion:
            self.enable_hollow_crown(crown, pinlines)


class NormalClassicTemplate(ChilliBaseTemplate):
    def template_file_name(self) -> str:
        return "normal-classic"

    def template_suffix(self) -> str:
        return "Classic"

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)

        self.art_reference = self._layer(self.image, LayerNames.ART_FRAME)

        legal = self._layer(self.image, LayerNames.LEGAL)
        replace_text(
            self._layer(legal, LayerNames.ARTIST),
            "Artist",
            self.layout.artist,
        )
        self.text_layers = []

        text_and_icons = self._layer(self.image, LayerNames.TEXT_AND_ICONS)
        self.basic_text_layers(text_and_icons)

        is_centred = (
            len(self.layout.flavour_text) <= 1
            and len(self.layout.oracle_text) <= 70
            and "\n" not in self.layout.oracle_text
        )
        reference_layer = self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE)
        if self.is_land:
            reference_layer = self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE_LAND)
        rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT)
        self.text_layers.append(
            FormattedTextArea(
                image=self.image,
                layer=rules_text,
                text_contents=self.layout.oracle_text,
                text_colour=get_text_layer_colour(rules_text),
                flavour_text=self.layout.flavour_text,
                is_centred=is_centred,
                reference_layer=reference_layer,
            ),
        )

        power_toughness = self._layer(text_and_icons, LayerNames.POWER_TOUGHNESS)
        if self.is_creature:
            self.text_layers.append(
                TextField(
                    image=self.image,
                    layer=power_toughness,
                    text_contents=f"{self.layout.power}/{self.layout.toughness}",
                    text_colour=get_text_layer_colour(power_toughness),
                    font_name=FONT_NAME_BELEREN,
                    font_size=FONT_SIZE_POWER_TOUGHNESS,
                ),
            )
        else:
            power_toughness.set_visible(False)

    def enable_frame_layers(self):
        layers = self._layer(self.image, LayerNames.NONLAND)
        selected_layer = self.layout.background
        if self.is_land:
            layers = self._layer(self.image, LayerNames.LAND)
            selected_layer = self.layout.pinlines

        self._layer(layers, selected_layer).set_visible(True)


class NormalExtendedTemplate(NormalTemplate):
    def template_file_name(self):
        return "normal-extended"

    def template_suffix(self):
        return "Extended"

    def __init__(self, layout, file, file_path):
        layout.oracle_text = strip_reminder_text(layout.oracle_text)
        super().__init__(layout, file, file_path)


class WomensDayTemplate(NormalTemplate):
    def template_file_name(self):
        return "womensday"

    def template_suffix(self):
        return "Showcase"

    def __init__(self, layout, file, file_path):
        layout.oracle_text = strip_reminder_text(layout.oracle_text)
        super().__init__(layout, file, file_path)

    def enable_frame_layers(self):
        twins = self._layer(self.image, LayerNames.TWINS)
        self._layer(twins, self.layout.twins).set_visible(True)
        if self.is_creature:
            pt_box = self._layer(self.image, LayerNames.PT_BOX)
            self._layer(pt_box, self.layout.twins).set_visible(True)

        pinlines = self._layer(self.image, LayerNames.PINLINES_TEXTBOX)
        if self.is_land:
            pinlines = self._layer(self.image, LayerNames.LAND_PINLINES_TEXTBOX)
        self._layer(pinlines, self.layout.pinlines).set_visible(True)

        if self.is_legendary:
            crown = self._layer(self.image, LayerNames.LEGENDARY_CROWN)
            self._layer(crown, self.layout.pinlines).set_visible(True)
            enable_active_layer_mask(pinlines)


class StargazingTemplate(NormalTemplate):
    def template_file_name(self):
        return "stargazing"

    def template_suffix(self):
        return "Stargazing"

    def __init__(self, layout, file, file_path):
        layout.oracle_text = strip_reminder_text(layout.oracle_text)
        layout.is_nyx = True
        super().__init__(layout, file, file_path)


class MasterpieceTemplate(NormalTemplate):
    def template_file_name(self):
        return "masterpiece"

    def template_suffix(self):
        return "Masterpiece"

    def __init__(self, layout, file, file_path):
        layout.is_colourless = False
        layout.twins = "Bronze"
        layout.background = "Bronze"
        layout.oracle_text = strip_reminder_text(layout.oracle_text)
        super().__init__(layout, file, file_path)

    def enable_frame_layers(self):
        super().enable_frame_layers()
        if self.is_legendary:
            crown = self._layer(self.image, LayerNames.LEGENDARY_CROWN)
            pinlines = self._layer(self.image, LayerNames.PINLINES_TEXTBOX)
            self.enable_hollow_crown(crown, pinlines)


class ExpeditionTemplate(NormalTemplate):
    def template_file_name(self):
        return "znrexp"

    def template_suffix(self):
        return "Expedition"

    def __init__(self, layout, file, file_path):
        layout.oracle_text = strip_reminder_text(layout.oracle_text)
        super().__init__(layout, file, file_path)

    def basic_text_layers(self, text_and_icons):
        name = self._layer(text_and_icons, LayerNames.NAME)
        expansion_symbol = self._layer(text_and_icons, LayerNames.EXPANSION_SYMBOL)
        type_line = self._layer(text_and_icons, LayerNames.TYPE_LINE)
        self.text_layers.extend([
            TextField(
                image=self.image,
                layer=name,
                text_contents=self.layout.name,
                text_colour=get_text_layer_colour(name),
                font_name=FONT_NAME_BELEREN,
            ),
            ExpansionSymbolField(
                image=self.image,
                layer=expansion_symbol,
                text_contents=self.expansion_symbol_character,
                rarity=self.layout.rarity,
                font_name=FONT_NAME_KEYRUNE,
            ),
            ScaledTextField(
                image=self.image,
                layer=type_line,
                text_contents=self.layout.type_line,
                text_colour=get_text_layer_colour(type_line),
                reference_layer=expansion_symbol,
                font_name=FONT_NAME_BELEREN,
            ),
        ])

    def rules_text_and_pt_layers(self, text_and_icons):
        rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_NONCREATURE)
        self.text_layers.append(
            FormattedTextArea(
                image=self.image,
                layer=rules_text,
                text_contents=self.layout.oracle_text,
                text_colour=get_text_layer_colour(rules_text),
                flavour_text=self.layout.flavour_text,
                is_centred=False,
                reference_layer=self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE),
            ),
        )

    def enable_frame_layers(self):
        twins = self._layer(self.image, LayerNames.TWINS)
        self._layer(twins, self.layout.twins).set_visible(True)

        pinlines = self._layer(self.image, LayerNames.LAND_PINLINES_TEXTBOX)
        self._layer(pinlines, self.layout.pinlines).set_visible(True)

        if self.is_legendary:
            crown = self._layer(self.image, LayerNames.LEGENDARY_CROWN)
            self._layer(crown, self.layout.pinlines).set_visible(True)
            enable_active_layer_mask(pinlines)

            border = self._layer(self.image, LayerNames.BORDER)
            self._layer(border, LayerNames.NORMAL_BORDER).set_visible(False)
            self._layer(border, LayerNames.LEGENDARY_BORDER).set_visible(True)


class SnowTemplate(NormalTemplate):
    def template_file_name(self):
        return "snow"


class MiracleTemplate(NormalTemplate):
    def template_file_name(self):
        return "miracle"

    def rules_text_and_pt_layers(self, text_and_icons):
        rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_NONCREATURE)
        self.text_layers.append(
            FormattedTextArea(
                image=self.image,
                layer=rules_text,
                text_contents=self.layout.oracle_text,
                text_colour=get_text_layer_colour(rules_text),
                flavour_text=self.layout.flavour_text,
                is_centred=False,
                reference_layer=self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE),
            ),
        )


class TransformBackTemplate(NormalTemplate):
    def template_file_name(self) -> str:
        return "tf-back"

    def dfc_layer_group(self) -> str:
        return LayerNames.TF_BACK

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)
        transform_group = self._layer(
            self._layer(self.image, LayerNames.TEXT_AND_ICONS),
            self.dfc_layer_group(),
        )
        self._layer(transform_group, self.layout.transform_icon).set_visible(True)

    def basic_text_layers(self, text_and_icons):
        if self.layout.transform_icon == LayerNames.MOON_ELDRAZI_DFC:
            name = self._layer(text_and_icons, LayerNames.NAME)
            if self.name_shifted:
                name = self._layer(text_and_icons, LayerNames.NAME_SHIFT)

            type_line = self._layer(text_and_icons, LayerNames.TYPE_LINE)
            if self.type_line_shifted:
                type_line = self._layer(text_and_icons, LayerNames.TYPE_LINE_SHIFT)

            power_toughness = self._layer(text_and_icons, LayerNames.POWER_TOUGHNESS)

            # These layers are plain Gimp.Layer (not TextLayer) due to PSD->XCF import.
            # Convert them to TextLayer before calling set_color().
            name = ensure_text_layer(self.image, name)
            type_line = ensure_text_layer(self.image, type_line)
            power_toughness = ensure_text_layer(self.image, power_toughness)

            name.set_color(rgb_black())
            type_line.set_color(rgb_black())
            power_toughness.set_color(rgb_black())

        super().basic_text_layers(text_and_icons)


class TransformFrontTemplate(TransformBackTemplate):
    def template_file_name(self) -> str:
        return "tf-front"

    def dfc_layer_group(self) -> str:
        return LayerNames.TF_FRONT

    def __init__(self, layout, file, file_path):
        self.other_face_is_creature = (
            layout.other_face_power is not None and layout.other_face_toughness is not None
        )
        super().__init__(layout, file, file_path)

        if self.other_face_is_creature:
            flipside_power_toughness = self._layer(
                self._layer(self.image, LayerNames.TEXT_AND_ICONS),
                LayerNames.FLIPSIDE_POWER_TOUGHNESS,
            )
            self.text_layers.append(
                TextField(
                    image=self.image,
                    layer=flipside_power_toughness,
                    text_contents=f"{self.layout.other_face_power}/{self.layout.other_face_toughness}",
                    text_colour=get_text_layer_colour(flipside_power_toughness),
                    font_name=FONT_NAME_BELEREN,
                ),
            )

    def rules_text_and_pt_layers(self, text_and_icons):
        is_centred = (
            len(self.layout.flavour_text) <= 1
            and len(self.layout.oracle_text) <= 70
            and "\n" not in self.layout.oracle_text
        )

        noncreature_copyright = self._layer(self.legal, LayerNames.NONCREATURE_COPYRIGHT)
        creature_copyright = self._layer(self.legal, LayerNames.CREATURE_COPYRIGHT)

        power_toughness = self._layer(text_and_icons, LayerNames.POWER_TOUGHNESS)
        if self.is_creature:
            rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_CREATURE)
            if self.other_face_is_creature:
                rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_CREATURE_FLIP)

            self.text_layers.extend([
                TextField(
                    image=self.image,
                    layer=power_toughness,
                    text_contents=f"{self.layout.power}/{self.layout.toughness}",
                    text_colour=get_text_layer_colour(power_toughness),
                    font_name=FONT_NAME_BELEREN,
                ),
                CreatureFormattedTextArea(
                    image=self.image,
                    layer=rules_text,
                    text_contents=self.layout.oracle_text,
                    text_colour=get_text_layer_colour(rules_text),
                    flavour_text=self.layout.flavour_text,
                    is_centred=is_centred,
                    reference_layer=self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE),
                    pt_reference_layer=self._layer(text_and_icons, LayerNames.PT_REFERENCE),
                    pt_top_reference_layer=self._layer(text_and_icons, LayerNames.PT_TOP_REFERENCE),
                ),
            ])

            noncreature_copyright.set_visible(False)
            creature_copyright.set_visible(True)
        else:
            rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_NONCREATURE)
            if self.other_face_is_creature:
                rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_NONCREATURE_FLIP)

            self.text_layers.append(
                FormattedTextArea(
                    image=self.image,
                    layer=rules_text,
                    text_contents=self.layout.oracle_text,
                    text_colour=get_text_layer_colour(rules_text),
                    flavour_text=self.layout.flavour_text,
                    is_centred=is_centred,
                    reference_layer=self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE),
                ),
            )

            power_toughness.set_visible(False)


class IxalanTemplate(NormalTemplate):
    def template_file_name(self):
        return "ixalan"

    def basic_text_layers(self, text_and_icons):
        name = self._layer(text_and_icons, LayerNames.NAME)
        expansion_symbol = self._layer(text_and_icons, LayerNames.EXPANSION_SYMBOL)
        type_line = self._layer(text_and_icons, LayerNames.TYPE_LINE)
        self.text_layers.extend([
            TextField(
                image=self.image,
                layer=name,
                text_contents=self.layout.name,
                text_colour=get_text_layer_colour(name),
                font_name=FONT_NAME_BELEREN,
            ),
            ExpansionSymbolField(
                image=self.image,
                layer=expansion_symbol,
                text_contents=self.expansion_symbol_character,
                rarity=self.layout.rarity,
                font_name=FONT_NAME_KEYRUNE,
            ),
            TextField(
                image=self.image,
                layer=type_line,
                text_contents=self.layout.type_line,
                text_colour=get_text_layer_colour(type_line),
                font_name=FONT_NAME_BELEREN,
            ),
        ])

    def rules_text_and_pt_layers(self, text_and_icons):
        rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_NONCREATURE)
        self.text_layers.append(
            FormattedTextArea(
                image=self.image,
                layer=rules_text,
                text_contents=self.layout.oracle_text,
                text_colour=get_text_layer_colour(rules_text),
                flavour_text=self.layout.flavour_text,
                is_centred=False,
                reference_layer=self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE),
            ),
        )

    def enable_frame_layers(self):
        background = self._layer(self.image, LayerNames.BACKGROUND)
        self._layer(background, self.layout.background).set_visible(True)


class MDFCBackTemplate(NormalTemplate):
    def template_file_name(self) -> str:
        return "mdfc-back"

    def dfc_layer_group(self) -> str:
        return LayerNames.MDFC_BACK

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)
        mdfc_group = self._layer(
            self._layer(self.image, LayerNames.TEXT_AND_ICONS),
            self.dfc_layer_group(),
        )
        top = self._layer(mdfc_group, LayerNames.TOP)
        bottom = self._layer(mdfc_group, LayerNames.BOTTOM)
        self._layer(top, self.layout.twins).set_visible(True)
        self._layer(bottom, self.layout.other_face_twins).set_visible(True)

        left = self._layer(mdfc_group, LayerNames.LEFT)
        right = self._layer(mdfc_group, LayerNames.RIGHT)
        self.text_layers.extend([
            BasicFormattedTextField(
                image=self.image,
                layer=right,
                text_contents=self.layout.other_face_right,
                text_colour=get_text_layer_colour(right),
            ),
            ScaledTextField(
                image=self.image,
                layer=left,
                text_contents=self.layout.other_face_left,
                text_colour=get_text_layer_colour(left),
                reference_layer=right,
            ),
        ])


class MDFCFrontTemplate(MDFCBackTemplate):
    def template_file_name(self) -> str:
        return "mdfc-front"

    def dfc_layer_group(self) -> str:
        return LayerNames.MDFC_FRONT


class MutateTemplate(NormalTemplate):
    def template_file_name(self):
        return "mutate"

    def __init__(self, layout, file, file_path):
        split_rules_text = layout.oracle_text.split("\n")
        layout.mutate_text = split_rules_text[0]
        layout.oracle_text = "\n".join(split_rules_text[1:])

        super().__init__(layout, file, file_path)

        text_and_icons = self._layer(self.image, LayerNames.TEXT_AND_ICONS)
        mutate = self._layer(text_and_icons, LayerNames.MUTATE)
        self.text_layers.append(
            FormattedTextArea(
                image=self.image,
                layer=mutate,
                text_contents=self.layout.mutate_text,
                text_colour=get_text_layer_colour(mutate),
                flavour_text=self.layout.flavour_text,
                is_centred=False,
                reference_layer=self._layer(text_and_icons, LayerNames.MUTATE_REFERENCE),
            ),
        )


class AdventureTemplate(NormalTemplate):
    def template_file_name(self):
        return "adventure"

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)

        text_and_icons = self._layer(self.image, LayerNames.TEXT_AND_ICONS)
        name = self._layer(text_and_icons, LayerNames.NAME_ADVENTURE)
        mana_cost = self._layer(text_and_icons, LayerNames.MANA_COST_ADVENTURE)
        rules_text = self._layer(text_and_icons, LayerNames.RULES_TEXT_ADVENTURE)
        type_line = self._layer(text_and_icons, LayerNames.TYPE_LINE_ADVENTURE)
        self.text_layers.extend([
            BasicFormattedTextField(
                image=self.image,
                layer=mana_cost,
                text_contents=self.layout.adventure.mana_cost,
                text_colour=rgb_black(),
            ),
            ScaledTextField(
                image=self.image,
                layer=name,
                text_contents=self.layout.adventure.name,
                text_colour=get_text_layer_colour(name),
                reference_layer=mana_cost,
                font_name=FONT_NAME_BELEREN,
            ),
            FormattedTextArea(
                image=self.image,
                layer=rules_text,
                text_contents=self.layout.adventure.oracle_text,
                text_colour=get_text_layer_colour(rules_text),
                flavour_text="",
                is_centred=False,
                reference_layer=self._layer(text_and_icons, LayerNames.TEXTBOX_REFERENCE_ADVENTURE),
            ),
            TextField(
                image=self.image,
                layer=type_line,
                text_contents=self.layout.adventure.type_line,
                text_colour=get_text_layer_colour(type_line),
                font_name=FONT_NAME_BELEREN,
            ),
        ])


class LevelerTemplate(NormalTemplate):
    def template_file_name(self):
        return "leveler"

    def rules_text_and_pt_layers(self, text_and_icons):
        leveler_text_group = self._layer(text_and_icons, "Leveler Text")
        self.text_layers.extend([
            BasicFormattedTextField(
                image=self.image,
                layer=self._layer(leveler_text_group, "Rules Text - Level Up"),
                text_contents=self.layout.level_up_text,
                text_colour=rgb_black(),
            ),
            TextField(
                image=self.image,
                layer=self._layer(leveler_text_group, "Top Power / Toughness"),
                text_contents=f"{self.layout.power}/{self.layout.toughness}",
                text_colour=rgb_black(),
                font_name=FONT_NAME_BELEREN,
            ),
            TextField(
                image=self.image,
                layer=self._layer(leveler_text_group, "Middle Level"),
                text_contents=self.layout.middle_level,
                text_colour=rgb_black(),
            ),
            TextField(
                image=self.image,
                layer=self._layer(leveler_text_group, "Middle Power / Toughness"),
                text_contents=self.layout.middle_power_toughness,
                text_colour=rgb_black(),
                font_name=FONT_NAME_BELEREN,
            ),
            BasicFormattedTextField(
                image=self.image,
                layer=self._layer(leveler_text_group, "Rules Text - Levels X-Y"),
                text_contents=self.layout.levels_x_y_text,
                text_colour=rgb_black(),
            ),
            TextField(
                image=self.image,
                layer=self._layer(leveler_text_group, "Bottom Level"),
                text_contents=self.layout.bottom_level,
                text_colour=rgb_black(),
            ),
            TextField(
                image=self.image,
                layer=self._layer(leveler_text_group, "Bottom Power / Toughness"),
                text_contents=self.layout.bottom_power_toughness,
                text_colour=rgb_black(),
                font_name=FONT_NAME_BELEREN,
            ),
            BasicFormattedTextField(
                image=self.image,
                layer=self._layer(leveler_text_group, "Rules Text - Levels Z+"),
                text_contents=self.layout.levels_z_plus_text,
                text_colour=rgb_black(),
            ),
        ])
        self.exit_early = True

    def enable_frame_layers(self):
        twins = self._layer(self.image, LayerNames.TWINS)
        self._layer(twins, self.layout.twins).set_visible(True)

        pt_box = self._layer(self.image, LayerNames.PT_AND_LEVEL_BOXES)
        self._layer(pt_box, self.layout.twins).set_visible(True)

        pinlines = self._layer(self.image, LayerNames.PINLINES_TEXTBOX)
        self._layer(pinlines, self.layout.pinlines).set_visible(True)

        background = self._layer(self.image, LayerNames.BACKGROUND)
        self._layer(background, self.layout.background).set_visible(True)


class SagaTemplate(NormalTemplate):
    def template_file_name(self):
        return "saga"

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)
        self.paste_scryfall_scan(self._layer(self.image, LayerNames.SCRYFALL_SCAN_FRAME), file_path)

    def rules_text_and_pt_layers(self, text_and_icons):
        saga_text_group = self._layer(text_and_icons, "Saga")
        stages = ["I", "II", "III", "IV"]

        for i, saga_line in enumerate(self.layout.saga_lines):
            stage_group = self._layer(saga_text_group, stages[i])
            stage_group.set_visible(True)
            self.text_layers.append(
                BasicFormattedTextField(
                    image=self.image,
                    layer=self._layer(stage_group, "Text"),
                    text_contents=saga_line,
                    text_colour=rgb_black(),
                ),
            )

        self.exit_early = True

    def enable_frame_layers(self):
        twins = self._layer(self.image, LayerNames.TWINS)
        self._layer(twins, self.layout.twins).set_visible(True)

        pinlines = self._layer(self.image, LayerNames.PINLINES_AND_SAGA_STRIPE)
        self._layer(pinlines, self.layout.pinlines).set_visible(True)

        textbox = self._layer(self.image, LayerNames.TEXTBOX)
        self._layer(textbox, self.layout.background).set_visible(True)

        background = self._layer(self.image, LayerNames.BACKGROUND)
        self._layer(background, self.layout.background).set_visible(True)




# --- END PART 2 --- Planeswalker, Planar, Token, BasicLand classes below ---

class PlaneswalkerTemplate(ChilliBaseTemplate):
    """Planeswalker template - 3 or 4 loyalty abilities."""

    def template_file_name(self) -> str:
        return "pw"

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)

        self.exit_early = True

        self.art_reference = self._layer(self.image, LayerNames.PLANESWALKER_ART_FRAME)
        if self.layout.is_colourless:
            self.art_reference = self._layer(self.image, LayerNames.FULL_ART_FRAME)

        ability_array = self.layout.oracle_text.split("\n")
        num_abilities = 3
        if len(ability_array) > 3:
            num_abilities = 4

        # docref for everything but legal and art reference is based on number of abilities
        self.docref = self._layer(self.image, "pw-" + str(num_abilities))
        self.docref.set_visible(True)

        text_and_icons = self._layer(self.docref, LayerNames.TEXT_AND_ICONS)
        self.basic_text_layers(text_and_icons)

        # planeswalker ability layers
        group_names = [
            LayerNames.FIRST_ABILITY,
            LayerNames.SECOND_ABILITY,
            LayerNames.THIRD_ABILITY,
            LayerNames.FOURTH_ABILITY,
        ]
        loyalty_group = self._layer(self.docref, LayerNames.LOYALTY_GRAPHICS)

        for i in range(min(len(ability_array), 4)):
            ability_group = self._layer(loyalty_group, group_names[i])

            ability_text = ability_array[i]
            static_text_layer = self._layer(ability_group, LayerNames.STATIC_TEXT)
            ability_text_layer = self._layer(ability_group, LayerNames.ABILITY_TEXT)
            ability_layer = ability_text_layer
            colon_index = ability_text.find(": ")

            # determine if this is a static or activated ability by the presence of ":" near the start
            if 0 < colon_index < 5:
                # activated ability - determine which loyalty group to enable
                loyalty_graphic = self._layer(ability_group, ability_text[0])
                loyalty_graphic.set_visible(True)
                self.text_layers.append(
                    TextField(
                        image=self.image,
                        layer=self._layer(loyalty_graphic, LayerNames.COST),
                        text_contents=ability_text[:colon_index],
                        text_colour=rgb_white(),
                    )
                )
                ability_text = ability_text[colon_index + 2:]
            else:
                # static ability
                ability_layer = static_text_layer
                ability_text_layer.set_visible(False)
                static_text_layer.set_visible(True)
                self._layer(ability_group, "Colon").set_visible(False)

            self.text_layers.append(
                BasicFormattedTextField(
                    image=self.image,
                    layer=ability_layer,
                    text_contents=ability_text,
                    text_colour=get_text_layer_colour(ability_layer),
                )
            )

        # starting loyalty
        starting_loyalty_group = self._layer(loyalty_group, LayerNames.STARTING_LOYALTY)
        self.text_layers.append(
            TextField(
                image=self.image,
                layer=self._layer(starting_loyalty_group, LayerNames.TEXT),
                text_contents=self.layout.scryfall.get("loyalty", "") if isinstance(self.layout.scryfall, dict) else getattr(self.layout.scryfall, "loyalty", ""),
                text_colour=rgb_white(),
            )
        )

        # paste scryfall scan
        self.paste_scryfall_scan(
            self._layer(self.image, LayerNames.SCRYFALL_SCAN_FRAME), file_path
        )

    def enable_frame_layers(self):
        # twins
        twins = self._layer(self.docref, LayerNames.TWINS)
        self._layer(twins, self.layout.twins).set_visible(True)

        # pinlines
        pinlines = self._layer(self.docref, LayerNames.PINLINES)
        self._layer(pinlines, self.layout.pinlines).set_visible(True)

        # background
        self.enable_background()

    def enable_background(self):
        background = self._layer(self.docref, LayerNames.BACKGROUND)
        self._layer(background, self.layout.background).set_visible(True)


class PlaneswalkerExtendedTemplate(PlaneswalkerTemplate):
    """Extended art planeswalker - no background textures."""

    def template_file_name(self) -> str:
        return "pw-extended"

    def enable_background(self):
        pass


class PlanarTemplate(ChilliBaseTemplate):
    """Planechase card template - planes and phenomena."""

    def template_file_name(self):
        return "planar"

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)
        self.exit_early = True

        self.art_reference = self._layer(self.image, LayerNames.ART_FRAME)

        # artist (uses replace_text because of paintbrush symbol)
        replace_text(
            self._layer(self._layer(self.image, LayerNames.LEGAL), LayerNames.ARTIST),
            "Artist",
            self.layout.artist,
        )

        # card name, type line, expansion symbol
        text_and_icons = self._layer(self.image, LayerNames.TEXT_AND_ICONS)
        name = self._layer(text_and_icons, LayerNames.NAME)
        type_line = self._layer(text_and_icons, LayerNames.TYPE_LINE)
        expansion_symbol = self._layer(text_and_icons, LayerNames.EXPANSION_SYMBOL)

        # overwrite text_layers because artist was handled via replace_text
        self.text_layers = [
            TextField(
                image=self.image,
                layer=name,
                text_contents=self.layout.name,
                text_colour=get_text_layer_colour(name),
                font_name=FONT_NAME_BELEREN,
            ),
            ScaledTextField(
                image=self.image,
                layer=type_line,
                text_contents=self.layout.type_line,
                text_colour=get_text_layer_colour(type_line),
                reference_layer=expansion_symbol,
                font_name=FONT_NAME_BELEREN,
            ),
        ]

        static_ability = self._layer(text_and_icons, LayerNames.STATIC_ABILITY)
        chaos_ability = self._layer(text_and_icons, LayerNames.CHAOS_ABILITY)

        if self.layout.type_line == LayerNames.PHENOMENON:
            # phenomenon card
            self.text_layers.append(
                BasicFormattedTextField(
                    image=self.image,
                    layer=static_ability,
                    text_contents=self.layout.oracle_text,
                    text_colour=get_text_layer_colour(static_ability),
                )
            )
            textbox = self._layer(self.image, LayerNames.TEXTBOX)
            disable_active_layer_mask(textbox)
            self._layer(text_and_icons, LayerNames.CHAOS_SYMBOL).set_visible(False)
            chaos_ability.set_visible(False)
        else:
            # plane card - split oracle text on last newline
            linebreak_index = self.layout.oracle_text.rfind("\n")
            self.text_layers.extend([
                BasicFormattedTextField(
                    image=self.image,
                    layer=static_ability,
                    text_contents=self.layout.oracle_text[:linebreak_index],
                    text_colour=get_text_layer_colour(static_ability),
                ),
                BasicFormattedTextField(
                    image=self.image,
                    layer=chaos_ability,
                    text_contents=self.layout.oracle_text[linebreak_index + 1:],
                    text_colour=get_text_layer_colour(chaos_ability),
                ),
            ])

        # paste scryfall scan (rotated for planar cards)
        self.paste_scryfall_scan(
            self._layer(self.image, LayerNames.SCRYFALL_SCAN_FRAME), file_path, rotate=True
        )

    def enable_frame_layers(self):
        pass


class TokenTemplate(BaseTemplate):
    """Token card template."""

    def template_file_name(self):
        return "token"

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)

        self.is_creature = self.layout.power is not None and self.layout.toughness is not None
        self.is_legendary = "Legendary" in self.layout.type_line

        self.art_reference = self._layer(self.image, LayerNames.ART_FRAME)
        text_and_icons = self._layer(self.image, LayerNames.TEXT_AND_ICONS)
        type_line_and_rules_text = self._layer(self.image, LayerNames.TYPE_LINE_AND_RULES_TEXT)
        name_layer = self._layer(text_and_icons, LayerNames.NAME)
        self.text_layers.append(
            TextField(
                image=self.image,
                layer=name_layer,
                text_contents=self.layout.name,
                text_colour=get_text_layer_colour(name_layer),
                font_name=FONT_NAME_BELEREN,
            )
        )

        power_toughness_layer = self._layer(text_and_icons, LayerNames.POWER_TOUGHNESS)
        noncreature_copyright = self._layer(self.legal, LayerNames.NONCREATURE_COPYRIGHT)
        creature_copyright = self._layer(self.legal, LayerNames.CREATURE_COPYRIGHT)

        if self.is_creature:
            self.text_layers.append(
                TextField(
                    image=self.image,
                    layer=power_toughness_layer,
                    text_contents=str(self.layout.power) + "/" + str(self.layout.toughness),
                    text_colour=rgb_white(),
                    font_name=FONT_NAME_BELEREN,
                )
            )
            enable_active_vector_mask(type_line_and_rules_text)
            noncreature_copyright.set_visible(False)
            creature_copyright.set_visible(True)
        else:
            power_toughness_layer.set_visible(False)
            disable_active_vector_mask(type_line_and_rules_text)
            noncreature_copyright.set_visible(True)
            creature_copyright.set_visible(False)

        # rules text selection
        if self.layout.oracle_text == "" and self.layout.flavour_text == "":
            rules_text_group = self._layer(type_line_and_rules_text, LayerNames.FULL_ART)
        elif (
            "\n" not in self.layout.oracle_text
            and "\n" not in self.layout.flavour_text
            and (self.layout.oracle_text == "" or self.layout.flavour_text == "")
        ):
            rules_text_group = self._layer(type_line_and_rules_text, LayerNames.ONE_LINE_RULES_TEXT)
            self.text_layers.append(
                FormattedTextField(
                    image=self.image,
                    layer=self._layer(rules_text_group, LayerNames.RULES_TEXT),
                    text_contents=self.layout.oracle_text,
                    text_colour=rgb_white(),
                    flavour_text=self.layout.flavour_text,
                    is_centred=False,
                )
            )
        else:
            rules_text_group = self._layer(type_line_and_rules_text, LayerNames.RULES_TEXT)
            self.text_layers.append(
                FormattedTextArea(
                    image=self.image,
                    layer=self._layer(rules_text_group, LayerNames.RULES_TEXT),
                    text_contents=self.layout.oracle_text,
                    text_colour=rgb_white(),
                    flavour_text=self.layout.flavour_text,
                    is_centred=False,
                    reference_layer=self._layer(rules_text_group, LayerNames.TEXTBOX_REFERENCE),
                )
            )

        rules_text_group.set_visible(True)
        self.text_layers.append(
            TextField(
                image=self.image,
                layer=self._layer(rules_text_group, LayerNames.TYPE_LINE),
                text_contents=self.layout.type_line,
                text_colour=rgb_white(),
                font_name=FONT_NAME_BELEREN,
            )
        )

    def enable_frame_layers(self):
        frame_group = self._layer(self.image, LayerNames.FRAME)
        if self.is_legendary:
            frame_group = self._layer(frame_group, LayerNames.LEGENDARY)
        else:
            frame_group = self._layer(frame_group, LayerNames.NON_LEGENDARY)
        if self.is_creature:
            frame_group = self._layer(frame_group, LayerNames.CREATURE)
        else:
            frame_group = self._layer(frame_group, LayerNames.NON_CREATURE)
        self._layer(frame_group, self.layout.pinlines).set_visible(True)


class BasicLandTemplate(BaseTemplate):
    """Basic land template - full art, no text except legal."""

    def template_file_name(self) -> str:
        return "basic"

    def template_suffix(self):
        return self.layout.artist

    def __init__(self, layout, file, file_path):
        super().__init__(layout, file, file_path)
        self.art_reference = self._layer(self.image, LayerNames.BASIC_ART_FRAME)

    def enable_frame_layers(self):
        self._layer(self.image, self.layout.name).set_visible(True)


class BasicLandTherosTemplate(BasicLandTemplate):
    """Theros Nyx full-art basic land."""

    def template_file_name(self) -> str:
        return "basic-theros"


class BasicLandUnstableTemplate(BasicLandTemplate):
    """Unstable borderless basic land."""

    def template_file_name(self) -> str:
        return "basic-unstable"


class BasicLandClassicTemplate(BasicLandTemplate):
    """7th Edition classic frame basic land."""

    def template_file_name(self) -> str:
        return "basic-classic"
