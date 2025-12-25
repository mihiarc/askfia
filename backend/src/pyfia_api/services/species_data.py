"""Comprehensive species reference data for FIA lookups.

This module provides an in-memory species database that replaces the need
to query the REF_SPECIES table, which may not be available in MotherDuck databases.

Source: USDA Forest Service FIA Reference Species Table
"""

SPECIES_DATA = {
    # Pines
    110: {"common_name": "shortleaf pine", "scientific_name": "Pinus echinata"},
    111: {"common_name": "sand pine", "scientific_name": "Pinus clausa"},
    108: {"common_name": "lodgepole pine", "scientific_name": "Pinus contorta"},
    117: {"common_name": "jack pine", "scientific_name": "Pinus banksiana"},
    121: {"common_name": "longleaf pine", "scientific_name": "Pinus palustris"},
    122: {"common_name": "ponderosa pine", "scientific_name": "Pinus ponderosa"},
    123: {"common_name": "Apache pine", "scientific_name": "Pinus engelmannii"},
    125: {"common_name": "Jeffrey pine", "scientific_name": "Pinus jeffreyi"},
    126: {"common_name": "sugar pine", "scientific_name": "Pinus lambertiana"},
    127: {"common_name": "western white pine", "scientific_name": "Pinus monticola"},
    128: {"common_name": "whitebark pine", "scientific_name": "Pinus albicaulis"},
    129: {"common_name": "limber pine", "scientific_name": "Pinus flexilis"},
    131: {"common_name": "slash pine", "scientific_name": "Pinus elliottii"},
    132: {"common_name": "eastern white pine", "scientific_name": "Pinus strobus"},
    133: {"common_name": "spruce pine", "scientific_name": "Pinus glabra"},
    134: {"common_name": "pitch pine", "scientific_name": "Pinus rigida"},
    135: {"common_name": "pond pine", "scientific_name": "Pinus serotina"},
    136: {"common_name": "Table Mountain pine", "scientific_name": "Pinus pungens"},
    137: {"common_name": "Virginia pine", "scientific_name": "Pinus virginiana"},
    138: {"common_name": "red pine", "scientific_name": "Pinus resinosa"},
    316: {"common_name": "loblolly pine", "scientific_name": "Pinus taeda"},
    # Douglas-fir and True Firs
    202: {"common_name": "Douglas-fir", "scientific_name": "Pseudotsuga menziesii"},
    11: {"common_name": "balsam fir", "scientific_name": "Abies balsamea"},
    15: {"common_name": "white fir", "scientific_name": "Abies concolor"},
    17: {"common_name": "grand fir", "scientific_name": "Abies grandis"},
    19: {"common_name": "Pacific silver fir", "scientific_name": "Abies amabilis"},
    20: {"common_name": "noble fir", "scientific_name": "Abies procera"},
    21: {"common_name": "California red fir", "scientific_name": "Abies magnifica"},
    22: {"common_name": "subalpine fir", "scientific_name": "Abies lasiocarpa"},
    # Spruces
    90: {"common_name": "white spruce", "scientific_name": "Picea glauca"},
    91: {"common_name": "black spruce", "scientific_name": "Picea mariana"},
    92: {"common_name": "red spruce", "scientific_name": "Picea rubens"},
    93: {"common_name": "Engelmann spruce", "scientific_name": "Picea engelmannii"},
    94: {"common_name": "blue spruce", "scientific_name": "Picea pungens"},
    95: {"common_name": "Sitka spruce", "scientific_name": "Picea sitchensis"},
    97: {"common_name": "Norway spruce", "scientific_name": "Picea abies"},
    # Hemlocks
    261: {"common_name": "eastern hemlock", "scientific_name": "Tsuga canadensis"},
    263: {"common_name": "western hemlock", "scientific_name": "Tsuga heterophylla"},
    264: {"common_name": "mountain hemlock", "scientific_name": "Tsuga mertensiana"},
    # Cedars
    64: {"common_name": "Alaska yellow-cedar", "scientific_name": "Callitropsis nootkatensis"},
    73: {"common_name": "western redcedar", "scientific_name": "Thuja plicata"},
    81: {"common_name": "incense-cedar", "scientific_name": "Calocedrus decurrens"},
    241: {"common_name": "Atlantic white-cedar", "scientific_name": "Chamaecyparis thyoides"},
    242: {"common_name": "Port-Orford-cedar", "scientific_name": "Chamaecyparis lawsoniana"},
    # Oaks - White Oak Group
    800: {"common_name": "white oak", "scientific_name": "Quercus alba"},
    806: {"common_name": "swamp white oak", "scientific_name": "Quercus bicolor"},
    813: {"common_name": "Oregon white oak", "scientific_name": "Quercus garryana"},
    814: {"common_name": "bur oak", "scientific_name": "Quercus macrocarpa"},
    815: {"common_name": "swamp chestnut oak", "scientific_name": "Quercus michauxii"},
    816: {"common_name": "chinkapin oak", "scientific_name": "Quercus muehlenbergii"},
    818: {"common_name": "chestnut oak", "scientific_name": "Quercus montana"},
    820: {"common_name": "post oak", "scientific_name": "Quercus stellata"},
    824: {"common_name": "overcup oak", "scientific_name": "Quercus lyrata"},
    826: {"common_name": "live oak", "scientific_name": "Quercus virginiana"},
    # Oaks - Red Oak Group
    802: {"common_name": "northern red oak", "scientific_name": "Quercus rubra"},
    809: {"common_name": "scarlet oak", "scientific_name": "Quercus coccinea"},
    810: {"common_name": "pin oak", "scientific_name": "Quercus palustris"},
    812: {"common_name": "Shumard oak", "scientific_name": "Quercus shumardii"},
    821: {"common_name": "southern red oak", "scientific_name": "Quercus falcata"},
    823: {"common_name": "water oak", "scientific_name": "Quercus nigra"},
    827: {"common_name": "willow oak", "scientific_name": "Quercus phellos"},
    833: {"common_name": "black oak", "scientific_name": "Quercus velutina"},
    837: {"common_name": "laurel oak", "scientific_name": "Quercus laurifolia"},
    # Maples
    311: {"common_name": "sugar maple", "scientific_name": "Acer saccharum"},
    312: {"common_name": "black maple", "scientific_name": "Acer nigrum"},
    313: {"common_name": "silver maple", "scientific_name": "Acer saccharinum"},
    314: {"common_name": "red maple", "scientific_name": "Acer rubrum"},
    315: {"common_name": "bigleaf maple", "scientific_name": "Acer macrophyllum"},
    317: {"common_name": "boxelder", "scientific_name": "Acer negundo"},
    318: {"common_name": "striped maple", "scientific_name": "Acer pensylvanicum"},
    # Hickories
    400: {"common_name": "pignut hickory", "scientific_name": "Carya glabra"},
    401: {"common_name": "pecan", "scientific_name": "Carya illinoinensis"},
    402: {"common_name": "water hickory", "scientific_name": "Carya aquatica"},
    403: {"common_name": "bitternut hickory", "scientific_name": "Carya cordiformis"},
    404: {"common_name": "shagbark hickory", "scientific_name": "Carya ovata"},
    405: {"common_name": "shellbark hickory", "scientific_name": "Carya laciniosa"},
    407: {"common_name": "mockernut hickory", "scientific_name": "Carya tomentosa"},
    409: {"common_name": "nutmeg hickory", "scientific_name": "Carya myristiciformis"},
    # Birches
    371: {"common_name": "yellow birch", "scientific_name": "Betula alleghaniensis"},
    372: {"common_name": "sweet birch", "scientific_name": "Betula lenta"},
    373: {"common_name": "paper birch", "scientific_name": "Betula papyrifera"},
    375: {"common_name": "river birch", "scientific_name": "Betula nigra"},
    376: {"common_name": "gray birch", "scientific_name": "Betula populifolia"},
    # Ashes
    541: {"common_name": "white ash", "scientific_name": "Fraxinus americana"},
    542: {"common_name": "black ash", "scientific_name": "Fraxinus nigra"},
    543: {"common_name": "green ash", "scientific_name": "Fraxinus pennsylvanica"},
    544: {"common_name": "blue ash", "scientific_name": "Fraxinus quadrangulata"},
    # Poplars and Aspens
    741: {"common_name": "balsam poplar", "scientific_name": "Populus balsamifera"},
    742: {"common_name": "eastern cottonwood", "scientific_name": "Populus deltoides"},
    743: {"common_name": "bigtooth aspen", "scientific_name": "Populus grandidentata"},
    746: {"common_name": "black cottonwood", "scientific_name": "Populus trichocarpa"},
    747: {"common_name": "quaking aspen", "scientific_name": "Populus tremuloides"},
    # Other Important Hardwoods
    531: {"common_name": "yellow-poplar", "scientific_name": "Liriodendron tulipifera"},
    611: {"common_name": "sweetgum", "scientific_name": "Liquidambar styraciflua"},
    621: {"common_name": "American sycamore", "scientific_name": "Platanus occidentalis"},
    631: {"common_name": "red alder", "scientific_name": "Alnus rubra"},
    701: {"common_name": "black cherry", "scientific_name": "Prunus serotina"},
    762: {"common_name": "American basswood", "scientific_name": "Tilia americana"},
    951: {"common_name": "American beech", "scientific_name": "Fagus grandifolia"},
    971: {"common_name": "American elm", "scientific_name": "Ulmus americana"},
    972: {"common_name": "slippery elm", "scientific_name": "Ulmus rubra"},
    973: {"common_name": "winged elm", "scientific_name": "Ulmus alata"},
    975: {"common_name": "cedar elm", "scientific_name": "Ulmus crassifolia"},
    981: {"common_name": "tanoak", "scientific_name": "Notholithocarpus densiflorus"},
    # Cypress and Redwoods
    221: {"common_name": "baldcypress", "scientific_name": "Taxodium distichum"},
    231: {"common_name": "redwood", "scientific_name": "Sequoia sempervirens"},
    # Western Species
    116: {"common_name": "western larch", "scientific_name": "Larix occidentalis"},
    211: {"common_name": "western juniper", "scientific_name": "Juniperus occidentalis"},
    # Fruit and Nut Trees
    602: {"common_name": "black walnut", "scientific_name": "Juglans nigra"},
    901: {"common_name": "American chestnut", "scientific_name": "Castanea dentata"},
    # Southern Species
    460: {"common_name": "flowering dogwood", "scientific_name": "Cornus florida"},
    591: {"common_name": "eastern redbud", "scientific_name": "Cercis canadensis"},
    652: {"common_name": "Osage-orange", "scientific_name": "Maclura pomifera"},
}


def lookup_by_code(spcd: int) -> dict | None:
    """Lookup species information by species code.

    Args:
        spcd: Species code (e.g., 316 for loblolly pine)

    Returns:
        Dictionary with common_name and scientific_name, or None if not found
    """
    return SPECIES_DATA.get(spcd)


def search_by_name(common_name: str, limit: int = 10) -> list[dict]:
    """Search for species by common name (case-insensitive partial match).

    Args:
        common_name: Common name to search for (e.g., "pine", "oak")
        limit: Maximum number of results to return

    Returns:
        List of dictionaries with spcd, common_name, and scientific_name
    """
    search_term = common_name.lower()
    results = []

    for spcd, info in SPECIES_DATA.items():
        if search_term in info["common_name"].lower():
            results.append({
                "spcd": spcd,
                "common_name": info["common_name"],
                "scientific_name": info["scientific_name"],
            })

            if len(results) >= limit:
                break

    return results


def get_all_species() -> list[dict]:
    """Get all species in the reference data.

    Returns:
        List of all species with spcd, common_name, and scientific_name
    """
    return [
        {
            "spcd": spcd,
            "common_name": info["common_name"],
            "scientific_name": info["scientific_name"],
        }
        for spcd, info in SPECIES_DATA.items()
    ]
