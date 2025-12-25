"""FIA Forest Type reference data.

This module provides forest type code to name mappings for when
REF_FOREST_TYPE table is not available (e.g., in MotherDuck databases).

Source: FIA Database User Guide Appendix D - REF_FOREST_TYPE
https://research.fs.usda.gov/understory/forest-inventory-and-analysis-database-user-guide-nfi
"""

# FIA Forest Type Codes (FORTYPCD) reference
# Based on official FIA Database documentation
FOREST_TYPE_NAMES = {
    # White/Red/Jack Pine Group (100-159)
    101: "Jack pine",
    102: "Red pine",
    103: "Eastern white pine",
    104: "Eastern white pine / eastern hemlock",
    105: "Eastern hemlock",
    121: "Balsam fir",
    122: "White spruce",
    123: "Red spruce",
    124: "Red spruce / balsam fir",
    125: "Black spruce",
    126: "Tamarack",
    127: "Northern white-cedar",
    141: "Scotch pine",
    142: "Exotic softwoods",
    # Loblolly/Shortleaf Pine Group (160-169)
    161: "Loblolly pine",
    162: "Slash pine",
    163: "Longleaf pine",
    164: "Shortleaf pine",
    165: "Virginia pine",
    166: "Sand pine",
    167: "Table Mountain pine",
    168: "Pond pine",
    169: "Pitch pine",
    # Pinyon/Juniper Group (180-189)
    182: "Rocky Mountain juniper",
    184: "Juniper woodland",
    185: "Pinyon / juniper woodland",
    # Douglas-fir Group (200-209)
    201: "Douglas-fir",
    202: "Port-Orford-cedar",
    203: "Incense-cedar",
    # Ponderosa Pine Group (220-229)
    221: "Ponderosa pine",
    222: "Jeffrey pine",
    224: "Coulter pine",
    225: "Gray pine",
    226: "Monterey pine",
    # Western White Pine Group (240-249)
    241: "Western white pine",
    # Fir/Spruce/Mountain Hemlock Group (260-289)
    261: "White fir",
    262: "Red fir",
    263: "Noble fir",
    264: "Pacific silver fir",
    265: "Engelmann spruce",
    266: "Engelmann spruce / subalpine fir",
    267: "Grand fir",
    268: "Subalpine fir",
    269: "Blue spruce",
    270: "Mountain hemlock",
    271: "Alaska-yellow-cedar",
    # Lodgepole Pine Group (280-289)
    281: "Lodgepole pine",
    # Hemlock/Sitka Spruce Group (300-309)
    301: "Western hemlock",
    304: "Western redcedar",
    305: "Sitka spruce",
    # Redwood Group (360-369)
    361: "Redwood",
    362: "Giant sequoia",
    # California Mixed Conifer Group (370-379)
    371: "California mixed conifer",
    # Exotic Softwoods Group (380-389)
    381: "Scotch pine",
    383: "Other exotic softwoods",
    384: "Norway spruce",
    385: "Introduced larch",
    # Oak/Pine Group (400-409)
    401: "Post oak / blackjack oak",
    402: "Chestnut oak",
    403: "White oak / red oak / hickory",
    404: "White oak",
    405: "Northern red oak",
    406: "Yellow-poplar / white oak / northern red oak",
    407: "Southern scrub oak",
    408: "Swamp chestnut oak / cherrybark oak",
    409: "Scarlet oak",
    # Oak/Hickory Group (500-599)
    501: "Bur oak",
    502: "White oak",
    503: "Chestnut oak",
    504: "Northern red oak",
    505: "Yellow-poplar / white oak / northern red oak",
    506: "Sassafras / persimmon",
    507: "Sweetgum / yellow-poplar",
    508: "Black walnut",
    509: "Black locust",
    510: "Mixed upland hardwoods",
    511: "Post oak / blackjack oak",
    512: "Southern scrub oak",
    513: "Chestnut oak / black oak / scarlet oak",
    514: "Yellow-poplar",
    515: "Black cherry",
    516: "White oak / red oak / hickory",
    517: "Sugar maple / beech / yellow birch",
    519: "Red maple / oak",
    520: "Cabbage palmetto",
    # Oak/Gum/Cypress Group (600-699)
    601: "Swamp chestnut oak / cherrybark oak",
    602: "Sweetgum / Nuttall oak / willow oak",
    605: "Overcup oak / water hickory",
    606: "Sycamore / pecan / American elm",
    607: "Black ash / American elm / red maple",
    608: "Red maple / lowland",
    609: "Cottonwood",
    610: "Willow",
    # Elm/Ash/Cottonwood Group (700-759)
    701: "Black ash / American elm / red maple",
    702: "Sugarberry / hackberry / elm / green ash",
    703: "River birch / sycamore",
    704: "Silver maple / American elm",
    706: "Cottonwood",
    707: "Willow",
    708: "Red maple / lowland",
    722: "Oregon ash",
    # Maple/Beech/Birch Group (800-809)
    801: "Sugar maple / beech / yellow birch",
    802: "Black cherry",
    805: "Hard maple / basswood",
    # Aspen/Birch Group (900-909)
    901: "Aspen",
    902: "Paper birch",
    903: "Balsam poplar",
    904: "Gray birch",
    905: "Black cottonwood",
    911: "Red alder",
    912: "Bigleaf maple",
    922: "Oregon white oak",
    923: "California black oak",
    924: "Canyon live oak",
    931: "Coast live oak",
    935: "Blue oak",
    941: "Tanoak",
    943: "Giant chinkapin",
    950: "Other exotic hardwoods",
    962: "Tropical hardwoods",
    980: "Non-commercial hardwoods",
    999: "Nonstocked",
}


def get_forest_type_name(fortypcd: int) -> str:
    """Get forest type name from code.

    Parameters
    ----------
    fortypcd : int
        Forest type code (FORTYPCD)

    Returns
    -------
    str
        Forest type name, or "Unknown (code: {fortypcd})" if not found
    """
    return FOREST_TYPE_NAMES.get(fortypcd, f"Unknown (code: {fortypcd})")
