"""
Constants for MTG GIMP Automation.

Converted from mtg-photoshop-automation/scripts/constants.jsx.
Contains layer names, symbol mappings, ability words, card classes,
font names, spacing values, and symbol color definitions.
"""

# File paths (relative to project root)
JSON_FILE_PATH = "/scripts/card.json"
IMAGE_FILE_PATH = "/scripts/card.jpg"

# ---------------------------------------------------------------------------
# Card classes — finer grained than Scryfall layouts
# ---------------------------------------------------------------------------
NORMAL_CLASS = "normal"
TRANSFORM_FRONT_CLASS = "transform_front"
TRANSFORM_BACK_CLASS = "transform_back"
IXALAN_CLASS = "ixalan"
MDFC_FRONT_CLASS = "mdfc_front"
MDFC_BACK_CLASS = "mdfc_back"
MUTATE_CLASS = "mutate"
ADVENTURE_CLASS = "adventure"
LEVELER_CLASS = "leveler"
SAGA_CLASS = "saga"
MIRACLE_CLASS = "miracle"
PLANESWALKER_CLASS = "planeswalker"
SNOW_CLASS = "snow"
BASIC_CLASS = "basic"
PLANAR_CLASS = "planar"
TOKEN_CLASS = "token"


# ---------------------------------------------------------------------------
# Layer names — string constants matching .psd/.xcf layer and group names
# ---------------------------------------------------------------------------
class LayerNames:
    """String constants for every named layer/group in the template files."""

    # Color identity layers
    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"
    WU = "WU"
    UB = "UB"
    BR = "BR"
    RG = "RG"
    GW = "GW"
    WB = "WB"
    BG = "BG"
    GU = "GU"
    UR = "UR"
    RW = "RW"
    ARTIFACT = "Artifact"
    COLOURLESS = "Colourless"
    LAND = "Land"
    GOLD = "Gold"
    VEHICLE = "Vehicle"

    # Frame layer group names
    PT_BOX = "PT Box"
    PT_AND_LEVEL_BOXES = "PT and Level Boxes"
    TWINS = "Name & Title Boxes"
    LEGENDARY_CROWN = "Legendary Crown"
    PINLINES_TEXTBOX = "Pinlines & Textbox"
    PINLINES_AND_SAGA_STRIPE = "Pinlines & Saga Stripe"
    PINLINES = "Pinlines"
    LAND_PINLINES_TEXTBOX = "Land Pinlines & Textbox"
    COMPANION = "Companion"
    BACKGROUND = "Background"
    NYX = "Nyx"
    FRAME = "Frame"
    LEGENDARY = "Legendary"
    NON_LEGENDARY = "Non-Legendary"
    CREATURE = "Creature"
    NON_CREATURE = "Non-Creature"
    TYPE_LINE_AND_RULES_TEXT = "Typeline and Rules Text"
    FULL_ART = "Full Art"
    ONE_LINE_RULES_TEXT = "One-Line Rules Text"

    # Borders
    BORDER = "Border"
    NORMAL_BORDER = "Normal Border"
    LEGENDARY_BORDER = "Legendary Border"

    # Shadows
    SHADOWS = "Shadows"
    HOLLOW_CROWN_SHADOW = "Hollow Crown Shadow"

    # Legal
    LEGAL = "Legal"
    ARTIST = "Artist"
    NONCREATURE_COPYRIGHT = "Noncreature WotC Copyright"
    CREATURE_COPYRIGHT = "Creature WotC Copyright"

    # Text and icons
    TEXT_AND_ICONS = "Text and Icons"
    NAME = "Card Name"
    NAME_SHIFT = "Card Name Shift"
    NAME_ADVENTURE = "Card Name - Adventure"
    TYPE_LINE = "Typeline"
    TYPE_LINE_SHIFT = "Typeline Shift"
    TYPE_LINE_ADVENTURE = "Typeline - Adventure"
    MANA_COST = "Mana Cost"
    MANA_COST_ADVENTURE = "Mana Cost - Adventure"
    EXPANSION_SYMBOL = "Expansion Symbol"
    COLOUR_INDICATOR = "Colour Indicator"
    POWER_TOUGHNESS = "Power / Toughness"
    FLIPSIDE_POWER_TOUGHNESS = "Flipside Power / Toughness"
    RULES_TEXT = "Rules Text"
    RULES_TEXT_NONCREATURE = "Rules Text - Noncreature"
    RULES_TEXT_NONCREATURE_FLIP = "Rules Text - Noncreature Flip"
    RULES_TEXT_CREATURE = "Rules Text - Creature"
    RULES_TEXT_CREATURE_FLIP = "Rules Text - Creature Flip"
    RULES_TEXT_ADVENTURE = "Rules Text - Adventure"
    MUTATE = "Mutate"

    # Planar text and icons
    STATIC_ABILITY = "Static Ability"
    CHAOS_ABILITY = "Chaos Ability"
    CHAOS_SYMBOL = "Chaos Symbol"
    PHENOMENON = "Phenomenon"
    TEXTBOX = "Textbox"

    # Textbox references
    TEXTBOX_REFERENCE = "Textbox Reference"
    TEXTBOX_REFERENCE_LAND = "Textbox Reference Land"
    TEXTBOX_REFERENCE_ADVENTURE = "Textbox Reference - Adventure"
    MUTATE_REFERENCE = "Mutate Reference"
    PT_REFERENCE = "PT Adjustment Reference"
    PT_TOP_REFERENCE = "PT Top Reference"

    # Planeswalker
    FIRST_ABILITY = "First Ability"
    SECOND_ABILITY = "Second Ability"
    THIRD_ABILITY = "Third Ability"
    FOURTH_ABILITY = "Fourth Ability"
    STARTING_LOYALTY = "Starting Loyalty"
    LOYALTY_GRAPHICS = "Loyalty Graphics"
    STATIC_TEXT = "Static Text"
    ABILITY_TEXT = "Ability Text"
    TEXT = "Text"
    COST = "Cost"

    # Art frames
    ART_FRAME = "Art Frame"
    FULL_ART_FRAME = "Full Art Frame"
    BASIC_ART_FRAME = "Basic Art Frame"
    PLANESWALKER_ART_FRAME = "Planeswalker Art Frame"
    SCRYFALL_SCAN_FRAME = "Scryfall Scan Frame"

    # Transform
    TF_FRONT = "tf-front"
    TF_BACK = "tf-back"
    MDFC_FRONT = "mdfc-front"
    MDFC_BACK = "mdfc-back"
    MOON_ELDRAZI_DFC = "mooneldrazidfc"

    # MDFC
    TOP = "Top"
    BOTTOM = "Bottom"
    LEFT = "Left"
    RIGHT = "Right"

    # Classic
    NONLAND = "Nonland"
    # LAND already defined above


DEFAULT_LAYER = "Layer 1"

# ---------------------------------------------------------------------------
# Basic land names
# ---------------------------------------------------------------------------
BASIC_LAND_NAMES = [
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    "Wastes",
    "Snow-Covered Plains",
    "Snow-Covered Island",
    "Snow-Covered Swamp",
    "Snow-Covered Mountain",
    "Snow-Covered Forest",
]

# ---------------------------------------------------------------------------
# Card faces
# ---------------------------------------------------------------------------
class Faces:
    FRONT = 0
    BACK = 1


# ---------------------------------------------------------------------------
# Font names
# ---------------------------------------------------------------------------
FONT_NAME_MPLANTIN = "Plantin MT Pro Regular"
FONT_NAME_MPLANTIN_ITALIC = "Plantin MT Pro Italic"
FONT_NAME_NDPMTG = "NDPMTG Regular"
FONT_NAME_BELEREN = "Beleren2016 Bold"
FONT_NAME_KEYRUNE = "Keyrune Regular"

# ---------------------------------------------------------------------------
# Font spacing (in points)
# ---------------------------------------------------------------------------
MODAL_INDENT = 5.7
LINE_BREAK_LEAD = 2.4
FLAVOUR_TEXT_LEAD = 4.4

# ---------------------------------------------------------------------------
# Symbol colors — RGB tuples (red, green, blue)
# ---------------------------------------------------------------------------
RGB_C = (215, 208, 205)  # Colorless
RGB_W = (254, 253, 224)  # White
RGB_U = (186, 231, 252)  # Blue
RGB_B = (159, 146, 143)  # Black
RGB_R = (250, 186, 159)  # Red
RGB_G = (171, 221, 189)  # Green
RGB_BLACK = (0, 0, 0)
RGB_WHITE = (255, 255, 255)

# ---------------------------------------------------------------------------
# NDPMTG font dictionary — translates Scryfall symbol strings to NDPMTG
# font character sequences
# ---------------------------------------------------------------------------
SYMBOLS = {
    "{W/P}": "Qp",
    "{U/P}": "Qp",
    "{B/P}": "Qp",
    "{R/P}": "Qp",
    "{G/P}": "Qp",
    "{W/U/P}": "Qqp",
    "{U/B/P}": "Qqp",
    "{B/R/P}": "Qqp",
    "{R/G/P}": "Qqp",
    "{G/W/P}": "Qqp",
    "{W/B/P}": "Qqp",
    "{B/G/P}": "Qqp",
    "{G/U/P}": "Qqp",
    "{U/R/P}": "Qqp",
    "{R/W/P}": "Qqp",
    "{E}": "e",
    "{P}": "p",
    "{T}": "ot",
    "{X}": "ox",
    "{0}": "o0",
    "{1}": "o1",
    "{2}": "o2",
    "{3}": "o3",
    "{4}": "o4",
    "{5}": "o5",
    "{6}": "o6",
    "{7}": "o7",
    "{8}": "o8",
    "{9}": "o9",
    "{10}": "oA",
    "{11}": "oB",
    "{12}": "oC",
    "{13}": "oD",
    "{14}": "oE",
    "{15}": "oF",
    "{16}": "oG",
    "{20}": "oK",
    "{W}": "ow",
    "{U}": "ou",
    "{B}": "ob",
    "{R}": "or",
    "{G}": "og",
    "{C}": "oc",
    "{W/U}": "QqLS",
    "{U/B}": "QqMT",
    "{B/R}": "QqNU",
    "{R/G}": "QqOV",
    "{G/W}": "QqPR",
    "{W/B}": "QqLT",
    "{B/G}": "QqNV",
    "{G/U}": "QqPS",
    "{U/R}": "QqMU",
    "{R/W}": "QqOR",
    "{2/W}": "QqWR",
    "{2/U}": "QqWS",
    "{2/B}": "QqWT",
    "{2/R}": "QqWU",
    "{2/G}": "QqWV",
    "{C/W}": "Qq[R",
    "{C/U}": "Qq[S",
    "{C/B}": "Qq[T",
    "{C/R}": "Qq[U",
    "{C/G}": "Qq[V",
    "{S}": "omn",
    "{Q}": "ol",
    "{CHAOS}": "?",
}

# ---------------------------------------------------------------------------
# Ability words — these should be italicised in formatted rules text
# ---------------------------------------------------------------------------
ABILITY_WORDS = [
    "Adamant",
    "Addendum",
    "Battalion",
    "Bloodrush",
    "Channel",
    "Chroma",
    "Cohort",
    "Constellation",
    "Converge",
    "Council's dilemma",
    "Delirium",
    "Domain",
    "Eminence",
    "Enrage",
    "Fateful hour",
    "Ferocious",
    "Formidable",
    "Grandeur",
    "Hellbent",
    "Heroic",
    "Imprint",
    "Inspired",
    "Join forces",
    "Kinship",
    "Landfall",
    "Lieutenant",
    "Metalcraft",
    "Morbid",
    "Parley",
    "Radiance",
    "Raid",
    "Rally",
    "Revolt",
    "Spell mastery",
    "Strive",
    "Sweep",
    "Tempting offer",
    "Threshold",
    "Undergrowth",
    "Will of the council",
    "Magecraft",

    # AFR ability words
    "Antimagic Cone",
    "Fear Ray",
    "Pack tactics",
    "Acid Breath",
    "Teleport",
    "Lightning Breath",
    "Wild Magic Surge",
    "Two-Weapon Fighting",
    "Archery",
    "Bear Form",
    "Mage Hand",
    "Cure Wounds",
    "Dispel Magic",
    "Gentle Reprise",
    "Beacon of Hope",
    "Displacement",
    "Drag Below",
    "Siege Monster",
    "Dark One's Own Luck",
    "Climb Over",
    "Tie Up",
    "Rappel Down",
    "Rejuvenation",
    "Engulf",
    "Dissolve",
    "Poison Breath",
    "Tragic Backstory",
    "Cunning Action",
    "Stunning Strike",
    "Circle of Death",
    "Bardic Inspiration",
    "Song of Rest",
    "Sneak Attack",
    "Tail Spikes",
    "Dominate Monster",
    "Flurry of Blows",
    "Divine Intervention",
    "Split",
    "Magical Tinkering",
    "Keen Senses",
    "Grant an Advantage",
    "Smash the Chest",
    "Pry It Open",
    "Fire Breath",
    "Cone of Cold",
    "Brave the Stench",
    "Search the Body",
    "Bewitching Whispers",
    "Whispers of the Grave",
    "Animate Walking Statue",
    "Trapped!",
    "Invoke Duplicity",
    "Combat Inspiration",
    "Cold Breath",
    "Life Drain",
    "Fight the Current",
    "Find a Crossing",
    "Intimidate Them",
    "Fend Them Off",
    "Smash It",
    "Lift the Curse",
    "Steal Its Eyes",
    "Break Their Chains",
    "Interrogate Them",
    "Foil Their Scheme",
    "Learn Their Secrets",
    "Journey On",
    "Make Camp",
    "Rouse the Party",
    "Set Off Traps",
    "Form a Party",
    "Start a Brawl",
    "Make a Retreat",
    "Stand and Fight",
    "Distract the Guards",
    "Hide",
    "Charge Them",
    "Befriend Them",
    "Negative Energy Cone",

    # Midnight Hunt words
    "Coven",
]

# ---------------------------------------------------------------------------
# Card rarities
# ---------------------------------------------------------------------------
RARITY_COMMON = "common"
RARITY_UNCOMMON = "uncommon"
RARITY_RARE = "rare"
RARITY_MYTHIC = "mythic"
RARITY_SPECIAL = "special"
RARITY_BONUS = "bonus"
