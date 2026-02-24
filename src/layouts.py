import re
from types import SimpleNamespace

from src.constants import (
    NORMAL_CLASS,
    TRANSFORM_FRONT_CLASS,
    TRANSFORM_BACK_CLASS,
    IXALAN_CLASS,
    MDFC_FRONT_CLASS,
    MDFC_BACK_CLASS,
    MUTATE_CLASS,
    ADVENTURE_CLASS,
    LEVELER_CLASS,
    SAGA_CLASS,
    MIRACLE_CLASS,
    PLANESWALKER_CLASS,
    SNOW_CLASS,
    BASIC_CLASS,
    PLANAR_CLASS,
    TOKEN_CLASS,
    Faces,
    LayerNames,
)
from src.frame_logic import select_frame_layers


def determine_card_face(scryfall, card_name):
    if scryfall["card_faces"][0]["name"] == card_name:
        return Faces.FRONT
    if scryfall["card_faces"][1]["name"] == card_name:
        return Faces.BACK
    raise Exception("Shit broke")


class BaseLayout:
    def __init__(self, scryfall, card_name):
        self.scryfall = scryfall
        self.card_name_raw = card_name
        self.face = None
        self.mana_cost = ""
        self.type_line = ""
        self.oracle_text = ""

        self.unpack_scryfall()
        self.set_card_class()

        ret = select_frame_layers(
            self.mana_cost,
            self.type_line,
            self.oracle_text,
            self.colour_identity,
            self.colour_indicator,
        )

        self.twins = ret["twins"]
        self.pinlines = ret["pinlines"]
        self.background = ret["background"]
        self.is_nyx = "nyxtouched" in self.frame_effects
        self.is_colourless = ret["is_colourless"]

    def unpack_scryfall(self):
        self.rarity = self.scryfall["rarity"]
        self.artist = self.scryfall["artist"]
        self.colour_identity = self.scryfall["color_identity"]
        self.colour_indicator = None
        self.transform_icon = None
        self.keywords = []
        if "keywords" in self.scryfall:
            self.keywords = self.scryfall["keywords"]
        self.frame_effects = []
        if "frame_effects" in self.scryfall:
            self.frame_effects = self.scryfall["frame_effects"]
        self.set_code = self.scryfall.get("set", "")

    def get_default_class(self):
        default_class = self.scryfall.get("layout")
        if default_class is None:
            raise Exception("Default card class not defined!")
        return default_class

    def set_card_class(self):
        self.card_class = self.get_default_class()
        if self.get_default_class() == TRANSFORM_FRONT_CLASS and self.face == Faces.BACK:
            self.card_class = TRANSFORM_BACK_CLASS
            if "Land" in self.type_line:
                self.card_class = IXALAN_CLASS
        elif self.get_default_class() == MDFC_FRONT_CLASS and self.face == Faces.BACK:
            self.card_class = MDFC_BACK_CLASS
        elif "Planeswalker" in self.type_line:
            self.card_class = PLANESWALKER_CLASS
        elif "Snow" in self.type_line:
            self.card_class = SNOW_CLASS
        elif "Mutate" in self.keywords:
            self.card_class = MUTATE_CLASS
        elif "miracle" in self.frame_effects:
            self.card_class = MIRACLE_CLASS


class NormalLayout(BaseLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        self.name = self.scryfall["name"]
        self.mana_cost = self.scryfall.get("mana_cost", "")
        self.type_line = self.scryfall["type_line"]
        self.oracle_text = self.scryfall.get("oracle_text", "").replace("\u2212", "-")
        self.flavour_text = ""
        if "flavor_text" in self.scryfall:
            self.flavour_text = self.scryfall["flavor_text"]
        self.power = self.scryfall.get("power") or None
        self.toughness = self.scryfall.get("toughness") or None
        self.colour_indicator = self.scryfall.get("color_indicator")

        self.scryfall_scan = self.scryfall["image_uris"]["large"]

    def get_default_class(self):
        return str(NORMAL_CLASS)


class TransformLayout(BaseLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        self.face = determine_card_face(self.scryfall, self.card_name_raw)
        self.other_face = -1 * (self.face - 1)

        self.name = self.scryfall["card_faces"][self.face]["name"]
        self.mana_cost = self.scryfall["card_faces"][self.face]["mana_cost"]
        self.type_line = self.scryfall["card_faces"][self.face]["type_line"]
        self.oracle_text = self.scryfall["card_faces"][self.face]["oracle_text"].replace("\u2212", "-")
        self.flavour_text = ""
        if "flavor_text" in self.scryfall["card_faces"][self.face]:
            self.flavour_text = self.scryfall["card_faces"][self.face]["flavor_text"]
        self.power = self.scryfall["card_faces"][self.face].get("power") or None
        self.other_face_power = self.scryfall["card_faces"][self.other_face].get("power") or None
        self.toughness = self.scryfall["card_faces"][self.face].get("toughness") or None
        self.other_face_toughness = self.scryfall["card_faces"][self.other_face].get("toughness") or None
        self.colour_indicator = self.scryfall["card_faces"][self.face].get("color_indicator")
        # TODO: safe to assume the first frame effect will be the transform icon?
        self.transform_icon = self.scryfall["frame_effects"][0]

        self.scryfall_scan = self.scryfall["card_faces"][self.face]["image_uris"]["large"]

    def get_default_class(self):
        return str(TRANSFORM_FRONT_CLASS)


class MeldLayout(NormalLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        self.face = Faces.FRONT
        all_parts = self.scryfall["all_parts"]
        meld_result_name = ""
        meld_result_idx = 0
        for i in range(len(all_parts)):
            if all_parts[i]["component"] == "meld_result":
                meld_result_name = all_parts[i]["name"]
                meld_result_idx = i
                break

        if self.name == meld_result_name:
            self.face = Faces.BACK
        else:
            self.other_face_power = self.scryfall["all_parts"][meld_result_idx]["info"]["power"]
            self.other_face_toughness = self.scryfall["all_parts"][meld_result_idx]["info"]["toughness"]

        # TODO: safe to assume the first frame effect will be the transform icon?
        self.transform_icon = self.scryfall["frame_effects"][0]

        self.scryfall_scan = self.scryfall["image_uris"]["large"]

    def get_default_class(self):
        return str(TRANSFORM_FRONT_CLASS)


class ModalDoubleFacedLayout(BaseLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        self.face = determine_card_face(self.scryfall, self.card_name_raw)
        self.other_face = -1 * (self.face - 1)

        self.name = self.scryfall["card_faces"][self.face]["name"]
        self.mana_cost = self.scryfall["card_faces"][self.face]["mana_cost"]
        self.type_line = self.scryfall["card_faces"][self.face]["type_line"]
        self.oracle_text = self.scryfall["card_faces"][self.face]["oracle_text"].replace("\u2212", "-")
        self.flavour_text = ""
        if "flavor_text" in self.scryfall["card_faces"][self.face]:
            self.flavour_text = self.scryfall["card_faces"][self.face]["flavor_text"]
        self.power = self.scryfall["card_faces"][self.face].get("power") or None
        self.toughness = self.scryfall["card_faces"][self.face].get("toughness") or None
        self.colour_indicator = self.scryfall["card_faces"][self.face].get("color_indicator")
        self.transform_icon = "modal_dfc"

        self.other_face_twins = select_frame_layers(
            self.scryfall["card_faces"][self.other_face]["mana_cost"],
            self.scryfall["card_faces"][self.other_face]["type_line"],
            self.scryfall["card_faces"][self.other_face]["oracle_text"],
            self.scryfall["card_faces"][self.other_face]["color_identity"],
            self.scryfall["card_faces"][self.other_face].get("colour_indicator"),
        )["twins"]
        other_face_type_line_split = self.scryfall["card_faces"][self.other_face]["type_line"].split(" ")
        self.other_face_left = other_face_type_line_split[len(other_face_type_line_split) - 1]
        self.other_face_right = self.scryfall["card_faces"][self.other_face]["mana_cost"]
        if "Land" in self.scryfall["card_faces"][self.other_face]["type_line"]:
            other_face_oracle_text_split = self.scryfall["card_faces"][self.other_face]["oracle_text"].split("\n")
            other_face_mana_text = self.scryfall["card_faces"][self.other_face]["oracle_text"]
            if len(other_face_oracle_text_split) > 1:
                for i in range(len(other_face_oracle_text_split)):
                    if other_face_oracle_text_split[i][0:3] == "{T}":
                        other_face_mana_text = other_face_oracle_text_split[i]
                        break

            self.other_face_right = other_face_mana_text.split(".")[0] + "."

        self.scryfall_scan = self.scryfall["card_faces"][self.face]["image_uris"]["large"]

    def get_default_class(self):
        return str(MDFC_FRONT_CLASS)


class AdventureLayout(BaseLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        self.name = self.scryfall["card_faces"][0]["name"]
        self.mana_cost = self.scryfall["card_faces"][0]["mana_cost"]
        self.type_line = self.scryfall["card_faces"][0]["type_line"]
        self.oracle_text = self.scryfall["card_faces"][0]["oracle_text"]

        self.adventure = SimpleNamespace(
            name=self.scryfall["card_faces"][1]["name"],
            mana_cost=self.scryfall["card_faces"][1]["mana_cost"],
            type_line=self.scryfall["card_faces"][1]["type_line"],
            oracle_text=self.scryfall["card_faces"][1]["oracle_text"],
        )

        self.flavour_text = ""
        if "flavor_text" in self.scryfall["card_faces"][0]:
            self.flavour_text = self.scryfall["card_faces"][0]["flavor_text"]
        self.power = self.scryfall.get("power") or None
        self.toughness = self.scryfall.get("toughness") or None
        self.rarity = self.scryfall["rarity"]
        self.artist = self.scryfall["artist"]

        self.scryfall_scan = self.scryfall["image_uris"]["large"]

    def get_default_class(self):
        return str(ADVENTURE_CLASS)


class LevelerLayout(NormalLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        leveler_regex = r"^([\s\S]*)\nLEVEL (\d*-\d*)\n(\d*\/\d*)\n([\s\S]*)\n?LEVEL (\d*\+)\n(\d*\/\d*)\n([\s\S]*)?$"
        leveler_match = re.match(leveler_regex, self.oracle_text)
        if leveler_match is None:
            raise Exception("Shit broke")
        self.level_up_text = leveler_match.group(1)
        self.middle_level = leveler_match.group(2)
        self.middle_power_toughness = leveler_match.group(3)
        self.levels_x_y_text = leveler_match.group(4)
        self.bottom_level = leveler_match.group(5)
        self.bottom_power_toughness = leveler_match.group(6)
        self.levels_z_plus_text = leveler_match.group(7)

    def get_default_class(self):
        return str(LEVELER_CLASS)


class SagaLayout(NormalLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        self.saga_lines = self.oracle_text.split("\n")[1:]
        for i in range(len(self.saga_lines)):
            self.saga_lines[i] = self.saga_lines[i].split(" \u2014 ")[1]

    def get_default_class(self):
        return str(SAGA_CLASS)


class PlanarLayout(BaseLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        self.name = self.scryfall["name"]
        self.mana_cost = ""
        self.type_line = self.scryfall["type_line"]
        self.oracle_text = self.scryfall["oracle_text"]
        self.rarity = self.scryfall["rarity"]
        self.artist = self.scryfall["artist"]

        self.scryfall_scan = self.scryfall["image_uris"]["large"]

    def get_default_class(self):
        return str(PLANAR_CLASS)


class TokenLayout(BaseLayout):
    def unpack_scryfall(self):
        super().unpack_scryfall()

        self.name = self.scryfall["name"]
        self.mana_cost = self.scryfall.get("mana_cost", "")
        self.type_line = self.scryfall["type_line"]
        self.oracle_text = self.scryfall.get("oracle_text", "")
        self.flavour_text = ""
        if "flavor_text" in self.scryfall:
            self.flavour_text = self.scryfall["flavor_text"]
        self.power = self.scryfall.get("power") or None
        self.toughness = self.scryfall.get("toughness") or None

    def get_default_class(self):
        return str(TOKEN_CLASS)


layout_map = {
    "normal": NormalLayout,
    "transform": TransformLayout,
    "meld": MeldLayout,
    "modal_dfc": ModalDoubleFacedLayout,
    "adventure": AdventureLayout,
    "leveler": LevelerLayout,
    "saga": SagaLayout,
    "planar": PlanarLayout,
    "token": TokenLayout,
}
