from src.constants import LayerNames


def fix_colour_pair(input_str):
    """Standardise ordering of colour pairs from frame_logic.jsx."""
    colour_pairs = [
        LayerNames.WU,
        LayerNames.UB,
        LayerNames.BR,
        LayerNames.RG,
        LayerNames.GW,
        LayerNames.WB,
        LayerNames.BG,
        LayerNames.GU,
        LayerNames.UR,
        LayerNames.RW,
    ]
    for colour_pair in colour_pairs:
        if colour_pair[0] in input_str and colour_pair[1] in input_str:
            return colour_pair


def select_frame_layers(mana_cost, type_line, oracle_text, colour_identity_array, colour_indicator):
    """Select frame layers using original JSX branching rules."""
    colours = [LayerNames.WHITE, LayerNames.BLUE, LayerNames.BLACK, LayerNames.RED, LayerNames.GREEN]
    basic_colours = {
        "Plains": LayerNames.WHITE,
        "Island": LayerNames.BLUE,
        "Swamp": LayerNames.BLACK,
        "Mountain": LayerNames.RED,
        "Forest": LayerNames.GREEN,
    }
    hybrid_symbols = ["W/U", "U/B", "B/R", "R/G", "G/W", "W/B", "B/G", "G/U", "U/R", "R/W"]

    background = None
    pinlines = None
    twins = None

    if type_line.find(LayerNames.LAND) >= 0:
        twins = ""

        basic_identity = ""
        for basic in basic_colours:
            if type_line.find(basic) >= 0:
                basic_identity = basic_identity + basic_colours[basic]

        if len(basic_identity) == 1:
            twins = basic_identity
        elif len(basic_identity) == 2:
            fixed = fix_colour_pair(basic_identity)
            if fixed is not None:
                basic_identity = fixed
            return {
                "background": LayerNames.LAND,
                "pinlines": basic_identity,
                "twins": LayerNames.LAND,
                "is_colourless": False,
            }

        rules_lines = oracle_text.split("\n")
        colours_tapped = ""

        for line in rules_lines:
            if line.lower().find("search your library") >= 0 and line.lower().find("cycling") < 0:
                basic_identity = ""
                for basic in basic_colours:
                    if line.find(basic) >= 0:
                        basic_identity = basic_identity + basic_colours[basic]

                if len(basic_identity) == 1:
                    return {
                        "background": LayerNames.LAND,
                        "pinlines": basic_identity,
                        "twins": basic_identity,
                        "is_colourless": False,
                    }
                elif len(basic_identity) == 2:
                    fixed = fix_colour_pair(basic_identity)
                    if fixed is not None:
                        basic_identity = fixed
                    return {
                        "background": LayerNames.LAND,
                        "pinlines": basic_identity,
                        "twins": LayerNames.LAND,
                        "is_colourless": False,
                    }
                elif len(basic_identity) == 3:
                    return {
                        "background": LayerNames.LAND,
                        "pinlines": LayerNames.LAND,
                        "twins": LayerNames.LAND,
                        "is_colourless": False,
                    }
                elif line.find(LayerNames.LAND.lower()) >= 0:
                    if line.find("tapped") < 0 or line.find("untap") >= 0:
                        return {
                            "background": LayerNames.LAND,
                            "pinlines": LayerNames.GOLD,
                            "twins": LayerNames.GOLD,
                            "is_colourless": False,
                        }
                    else:
                        return {
                            "background": LayerNames.LAND,
                            "pinlines": LayerNames.LAND,
                            "twins": LayerNames.LAND,
                            "is_colourless": False,
                        }

            if (
                (line.lower().find("add") >= 0 and line.find("mana") >= 0)
                and (
                    line.find("color ") > 0
                    or line.find("colors ") > 0
                    or line.find("color.") > 0
                    or line.find("colors.") > 0
                )
            ):
                if (
                    line.find("enters the battlefield") < 0
                    and line.find("Remove a charge counter") < 0
                    and line.find("Sacrifice") < 0
                    and line.find("luck counter") < 0
                ):
                    return {
                        "background": LayerNames.LAND,
                        "pinlines": LayerNames.GOLD,
                        "twins": LayerNames.GOLD,
                        "is_colourless": False,
                    }

            tap_index = line.find("{T}")
            colon_index = line.find(":")
            if tap_index < colon_index and line.lower().find("add") >= 0:
                for colour in colours:
                    if line.find("{" + colour + "}") >= 0 and colours_tapped.find(colour) < 0:
                        colours_tapped = colours_tapped + colour

        if len(colours_tapped) == 1:
            pinlines = colours_tapped
            if twins == "":
                twins = colours_tapped
        elif len(colours_tapped) == 2:
            fixed = fix_colour_pair(colours_tapped)
            if fixed is not None:
                colours_tapped = fixed
            pinlines = colours_tapped
            if twins == "":
                twins = LayerNames.LAND
        elif len(colours_tapped) > 2:
            pinlines = LayerNames.GOLD
            if twins == "":
                twins = LayerNames.GOLD
        else:
            pinlines = LayerNames.LAND
            if twins == "":
                twins = LayerNames.LAND

        return {
            "background": LayerNames.LAND,
            "pinlines": pinlines,
            "twins": twins,
            "is_colourless": False,
        }

    else:
        colour_identity = ""
        if mana_cost == "" or (mana_cost == "{0}" and type_line.find(LayerNames.ARTIFACT) < 0):
            if colour_identity_array is None or len(colour_identity_array) == 0:
                colour_identity = ""
            elif colour_indicator is not None:
                colour_identity = "".join(colour_indicator)
            else:
                colour_identity = "".join(colour_identity_array)
        else:
            for colour in colours:
                if mana_cost.find("{" + colour) >= 0 or mana_cost.find(colour + "}") >= 0:
                    colour_identity = colour_identity + colour

        if len(colour_identity) == 2:
            fixed = fix_colour_pair(colour_identity)
            if fixed is not None:
                colour_identity = fixed

        if oracle_text.find(" is all colors.") > 0:
            colour_identity = "WUBRG"

        devoid = oracle_text.find("Devoid") >= 0 and len(colour_identity) > 0
        if (
            (len(colour_identity) <= 0 and type_line.find(LayerNames.ARTIFACT) < 0)
            or devoid
            or (mana_cost == "" and type_line.find("Eldrazi") >= 0)
        ):
            background = LayerNames.COLOURLESS
            pinlines = LayerNames.COLOURLESS
            twins = LayerNames.COLOURLESS

            if devoid:
                if len(colour_identity) > 1:
                    twins = LayerNames.GOLD
                    background = LayerNames.GOLD
                else:
                    twins = colour_identity
                    background = colour_identity

            return {
                "background": background,
                "pinlines": pinlines,
                "twins": twins,
                "is_colourless": True,
            }

        hybrid = False
        if len(colour_identity) == 2:
            for hybrid_symbol in hybrid_symbols:
                if mana_cost.find(hybrid_symbol) >= 0:
                    hybrid = True
                    break

        if type_line.find(LayerNames.ARTIFACT) >= 0:
            background = LayerNames.ARTIFACT
        elif hybrid:
            background = colour_identity
        elif len(colour_identity) >= 2:
            background = LayerNames.GOLD
        else:
            background = colour_identity

        if type_line.find(LayerNames.VEHICLE) >= 0:
            background = LayerNames.VEHICLE

        if len(colour_identity) <= 0:
            pinlines = LayerNames.ARTIFACT
        elif len(colour_identity) <= 2:
            pinlines = colour_identity
        else:
            pinlines = LayerNames.GOLD

        if len(colour_identity) <= 0:
            twins = LayerNames.ARTIFACT
        elif len(colour_identity) == 1:
            twins = colour_identity
        elif hybrid:
            twins = LayerNames.LAND
        elif len(colour_identity) >= 2:
            twins = LayerNames.GOLD

        return {
            "background": background,
            "pinlines": pinlines,
            "twins": twins,
            "is_colourless": False,
        }
