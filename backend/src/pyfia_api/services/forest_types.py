"""FIA Forest Type reference data.

This module provides forest type code to name mappings for when
REF_FOREST_TYPE table is not available (e.g., in MotherDuck databases).
"""

# FIA Forest Type Codes (FORTYPCD) reference
# Source: USDA Forest Service FIA Database Manual
# Complete list of common forest types across the United States
FOREST_TYPE_NAMES = {
    # Pine Types (100-199)
    101: "Jack pine",
    102: "Red pine",
    103: "White pine",
    104: "Scots pine",
    105: "Eastern white pine-eastern hemlock",
    121: "Longleaf pine",
    122: "Slash pine",
    123: "Loblolly pine",
    124: "Shortleaf pine",
    125: "Virginia pine",
    126: "Sand pine",
    127: "Pond pine",
    128: "Pitch pine",
    129: "Eastern white pine-northern red oak-white ash",
    141: "Spruce-fir",
    142: "White spruce",
    161: "Black spruce",
    162: "Tamarack",
    163: "Balsam poplar",
    164: "Aspen",
    165: "Paper birch",
    166: "Balsam fir",
    167: "Red spruce",
    168: "Red spruce-Fraser fir",
    # Western Softwoods (200-399)
    201: "White spruce",
    202: "Sitka spruce",
    221: "Douglas-fir",
    222: "Western hemlock",
    223: "Western redcedar",
    224: "Port-Orford-cedar",
    225: "Redwood",
    226: "Ponderosa pine",
    227: "Jeffrey pine",
    228: "Sugar pine",
    241: "Western white pine",
    261: "Fir-spruce",
    262: "Western larch",
    263: "Incense-cedar",
    264: "Lodgepole pine",
    265: "Engelmann spruce-subalpine fir",
    266: "Mountain hemlock",
    267: "Pacific silver fir",
    268: "Noble fir",
    281: "Grand fir",
    301: "Juniper woodland",
    321: "Pinyon-juniper",
    361: "Ponderosa pine-Douglas-fir",
    362: "Arizona cypress",
    363: "Knobcone pine",
    364: "Monterey pine",
    365: "Bishop pine",
    366: "Coulter pine",
    367: "Digger pine",
    368: "Whitebark pine",
    369: "Foxtail pine-bristlecone pine",
    # Oak-Hickory Types (400-599)
    401: "White oak-red oak-hickory",
    402: "White oak",
    403: "Northern red oak",
    404: "Yellow-poplar-white oak-northern red oak",
    405: "Chestnut oak",
    406: "Scarlet oak",
    407: "Southern red oak",
    408: "Blackjack oak",
    409: "Post oak-blackjack oak",
    421: "Yellow-poplar",
    501: "Sweetgum-yellow-poplar",
    502: "Sweetgum-Nuttall oak-willow oak",
    503: "Sugarberry-hackberry-elm-green ash",
    504: "Black ash-American elm-red maple",
    505: "River birch-sycamore",
    506: "Cottonwood",
    507: "Willow",
    508: "Sycamore-sweetgum-American elm",
    509: "Red maple-oak",
    511: "Hackberry",
    512: "Live oak",
    513: "Swamp chestnut oak-cherrybark oak",
    514: "Overcup oak-water hickory",
    515: "Atlantic white-cedar",
    516: "Baldcypress-water tupelo",
    519: "Sweetbay-swamp tupelo-redbay",
    520: "Cabbage palmetto",
    # Maple-Beech-Birch Types (600-799)
    601: "Sugar maple-beech-yellow birch",
    602: "Black cherry",
    603: "Hard maple-basswood",
    604: "Yellow birch-sugar maple",
    605: "Red maple-upland",
    606: "Pin cherry-reverting field",
    607: "Mixed upland hardwoods",
    608: "Northern white-cedar",
    701: "Elm-ash-cottonwood",
    702: "Black walnut",
    703: "Butternut",
    704: "Black locust",
    705: "Sweetgum",
    706: "Pecan-American elm",
    708: "Honeylocust",
    # Aspen-Birch Types (800-899)
    801: "Aspen",
    802: "Paper birch",
    809: "Red maple-lowland",
    901: "Mesquite",
    902: "Exotic hardwoods",
    903: "Exotic softwoods",
    905: "Tropical hardwoods",
    # Special/Nonstocked
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
