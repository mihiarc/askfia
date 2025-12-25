"""FIA Species reference data.

This module provides species code (SPCD) to name mappings for when
REF_SPECIES table is not available (e.g., in MotherDuck databases).

Source: USDA Forest Service FIA Codes
https://www.fs.usda.gov/nrs/atlas/products/resources/FIA_codes.pdf
"""

# FIA Species Codes (SPCD) reference
# Based on official USDA Forest Service FIA documentation
SPECIES_DATA = {
    # Conifers - Firs (Eastern)
    12: {"common_name": "balsam fir", "scientific_name": "Abies balsamea"},
    # Conifers - Firs (Western)
    15: {"common_name": "white fir", "scientific_name": "Abies concolor"},
    17: {"common_name": "grand fir", "scientific_name": "Abies grandis"},
    19: {"common_name": "subalpine fir", "scientific_name": "Abies lasiocarpa"},
    20: {"common_name": "California red fir", "scientific_name": "Abies magnifica"},
    21: {"common_name": "Pacific silver fir", "scientific_name": "Abies amabilis"},
    22: {"common_name": "noble fir", "scientific_name": "Abies procera"},
    # Conifers - Cedars and Junipers
    41: {"common_name": "Port-Orford-cedar", "scientific_name": "Chamaecyparis lawsoniana"},
    42: {"common_name": "Alaska yellow-cedar", "scientific_name": "Cupressus nootkatensis"},
    43: {"common_name": "Atlantic white-cedar", "scientific_name": "Chamaecyparis thyoides"},
    64: {"common_name": "Rocky Mountain juniper", "scientific_name": "Juniperus scopulorum"},
    66: {"common_name": "Utah juniper", "scientific_name": "Juniperus osteosperma"},
    68: {"common_name": "eastern redcedar", "scientific_name": "Juniperus virginiana"},
    # Conifers - Incense-cedar
    81: {"common_name": "incense-cedar", "scientific_name": "Calocedrus decurrens"},
    # Conifers - Larches
    71: {"common_name": "tamarack", "scientific_name": "Larix laricina"},
    72: {"common_name": "western larch", "scientific_name": "Larix occidentalis"},
    # Conifers - Spruces
    91: {"common_name": "Engelmann spruce", "scientific_name": "Picea engelmannii"},
    93: {"common_name": "Sitka spruce", "scientific_name": "Picea sitchensis"},
    94: {"common_name": "white spruce", "scientific_name": "Picea glauca"},
    95: {"common_name": "black spruce", "scientific_name": "Picea mariana"},
    96: {"common_name": "blue spruce", "scientific_name": "Picea pungens"},
    97: {"common_name": "red spruce", "scientific_name": "Picea rubens"},
    # Conifers - Pines (Eastern)
    105: {"common_name": "jack pine", "scientific_name": "Pinus banksiana"},
    107: {"common_name": "sand pine", "scientific_name": "Pinus clausa"},
    110: {"common_name": "shortleaf pine", "scientific_name": "Pinus echinata"},
    111: {"common_name": "slash pine", "scientific_name": "Pinus elliottii"},
    115: {"common_name": "spruce pine", "scientific_name": "Pinus glabra"},
    121: {"common_name": "longleaf pine", "scientific_name": "Pinus palustris"},
    123: {"common_name": "Table Mountain pine", "scientific_name": "Pinus pungens"},
    125: {"common_name": "red pine", "scientific_name": "Pinus resinosa"},
    126: {"common_name": "pitch pine", "scientific_name": "Pinus rigida"},
    128: {"common_name": "pond pine", "scientific_name": "Pinus serotina"},
    129: {"common_name": "eastern white pine", "scientific_name": "Pinus strobus"},
    131: {"common_name": "loblolly pine", "scientific_name": "Pinus taeda"},
    132: {"common_name": "Virginia pine", "scientific_name": "Pinus virginiana"},
    # Conifers - Pines (Western)
    101: {"common_name": "whitebark pine", "scientific_name": "Pinus albicaulis"},
    103: {"common_name": "bristlecone pine", "scientific_name": "Pinus aristata"},
    104: {"common_name": "foxtail pine", "scientific_name": "Pinus balfouriana"},
    108: {"common_name": "lodgepole pine", "scientific_name": "Pinus contorta"},
    109: {"common_name": "Coulter pine", "scientific_name": "Pinus coulteri"},
    112: {"common_name": "Apache pine", "scientific_name": "Pinus engelmannii"},
    113: {"common_name": "limber pine", "scientific_name": "Pinus flexilis"},
    116: {"common_name": "Jeffrey pine", "scientific_name": "Pinus jeffreyi"},
    117: {"common_name": "sugar pine", "scientific_name": "Pinus lambertiana"},
    119: {"common_name": "western white pine", "scientific_name": "Pinus monticola"},
    122: {"common_name": "ponderosa pine", "scientific_name": "Pinus ponderosa"},
    124: {"common_name": "Monterey pine", "scientific_name": "Pinus radiata"},
    127: {"common_name": "gray pine", "scientific_name": "Pinus sabiniana"},
    # Conifers - Douglas-fir
    202: {"common_name": "Douglas-fir", "scientific_name": "Pseudotsuga menziesii"},
    # Conifers - Cypress
    221: {"common_name": "bald cypress", "scientific_name": "Taxodium distichum"},
    222: {"common_name": "pond cypress", "scientific_name": "Taxodium distichum var. nutans"},
    # Conifers - Redwoods and Sequoias
    211: {"common_name": "redwood", "scientific_name": "Sequoia sempervirens"},
    212: {"common_name": "giant sequoia", "scientific_name": "Sequoiadendron giganteum"},
    # Conifers - Cedars
    241: {"common_name": "northern white-cedar", "scientific_name": "Thuja occidentalis"},
    242: {"common_name": "western redcedar", "scientific_name": "Thuja plicata"},
    # Conifers - Hemlocks
    261: {"common_name": "eastern hemlock", "scientific_name": "Tsuga canadensis"},
    263: {"common_name": "western hemlock", "scientific_name": "Tsuga heterophylla"},
    264: {"common_name": "mountain hemlock", "scientific_name": "Tsuga mertensiana"},
    # Hardwoods - Maples (Eastern)
    311: {"common_name": "Florida maple", "scientific_name": "Acer barbatum"},
    313: {"common_name": "boxelder", "scientific_name": "Acer negundo"},
    314: {"common_name": "black maple", "scientific_name": "Acer nigrum"},
    315: {"common_name": "striped maple", "scientific_name": "Acer pensylvanicum"},
    316: {"common_name": "red maple", "scientific_name": "Acer rubrum"},
    317: {"common_name": "silver maple", "scientific_name": "Acer saccharinum"},
    318: {"common_name": "sugar maple", "scientific_name": "Acer saccharum"},
    319: {"common_name": "mountain maple", "scientific_name": "Acer spicatum"},
    # Hardwoods - Maples (Western)
    312: {"common_name": "bigleaf maple", "scientific_name": "Acer macrophyllum"},
    # Hardwoods - Alders
    351: {"common_name": "red alder", "scientific_name": "Alnus rubra"},
    352: {"common_name": "white alder", "scientific_name": "Alnus rhombifolia"},
    # Hardwoods - Madrone
    361: {"common_name": "Pacific madrone", "scientific_name": "Arbutus menziesii"},
    # Hardwoods - Buckeyes
    331: {"common_name": "Ohio buckeye", "scientific_name": "Aesculus glabra"},
    332: {"common_name": "yellow buckeye", "scientific_name": "Aesculus octandra"},
    # Hardwoods - Serviceberry
    356: {"common_name": "serviceberry", "scientific_name": "Amelanchier sp."},
    # Hardwoods - Pawpaw
    367: {"common_name": "pawpaw", "scientific_name": "Asimina triloba"},
    # Hardwoods - Birches
    371: {"common_name": "yellow birch", "scientific_name": "Betula alleghaniensis"},
    372: {"common_name": "sweet birch", "scientific_name": "Betula lenta"},
    373: {"common_name": "river birch", "scientific_name": "Betula nigra"},
    375: {"common_name": "paper birch", "scientific_name": "Betula papyrifera"},
    379: {"common_name": "gray birch", "scientific_name": "Betula populifolia"},
    # Hardwoods - Bumelia
    381: {"common_name": "gum bumelia", "scientific_name": "Bumelia lanuginosa"},
    # Hardwoods - Hornbeam
    391: {"common_name": "American hornbeam", "scientific_name": "Carpinus caroliniana"},
    # Hardwoods - Hickories
    401: {"common_name": "water hickory", "scientific_name": "Carya aquatica"},
    402: {"common_name": "bitternut hickory", "scientific_name": "Carya cordiformis"},
    403: {"common_name": "pignut hickory", "scientific_name": "Carya glabra"},
    404: {"common_name": "pecan", "scientific_name": "Carya illinoensis"},
    405: {"common_name": "shellbark hickory", "scientific_name": "Carya laciniosa"},
    407: {"common_name": "shagbark hickory", "scientific_name": "Carya ovata"},
    408: {"common_name": "black hickory", "scientific_name": "Carya texana"},
    409: {"common_name": "mockernut hickory", "scientific_name": "Carya tomentosa"},
    # Hardwoods - Chestnut
    421: {"common_name": "American chestnut", "scientific_name": "Castanea dentata"},
    # Hardwoods - Catalpa
    452: {"common_name": "northern catalpa", "scientific_name": "Catalpa speciosa"},
    # Hardwoods - Hackberries
    461: {"common_name": "sugarberry", "scientific_name": "Celtis laevigata"},
    462: {"common_name": "hackberry", "scientific_name": "Celtis occidentalis"},
    # Hardwoods - Redbud
    471: {"common_name": "eastern redbud", "scientific_name": "Cercis canadensis"},
    # Hardwoods - Dogwood
    491: {"common_name": "flowering dogwood", "scientific_name": "Cornus florida"},
    # Hardwoods - Persimmon
    521: {"common_name": "common persimmon", "scientific_name": "Diospyros virginiana"},
    # Hardwoods - Beech
    531: {"common_name": "American beech", "scientific_name": "Fagus grandifolia"},
    # Hardwoods - Ashes
    541: {"common_name": "white ash", "scientific_name": "Fraxinus americana"},
    543: {"common_name": "black ash", "scientific_name": "Fraxinus nigra"},
    544: {"common_name": "green ash", "scientific_name": "Fraxinus pennsylvanica"},
    546: {"common_name": "blue ash", "scientific_name": "Fraxinus quadrangulata"},
    # Hardwoods - Locusts
    551: {"common_name": "waterlocust", "scientific_name": "Gleditsia aquatica"},
    552: {"common_name": "honeylocust", "scientific_name": "Gleditsia triacanthos"},
    # Hardwoods - Loblolly-bay
    555: {"common_name": "loblolly-bay", "scientific_name": "Gordonia lasianthus"},
    # Hardwoods - Kentucky coffeetree
    571: {"common_name": "Kentucky coffeetree", "scientific_name": "Gymnocladus dioicus"},
    # Hardwoods - Silverbell
    580: {"common_name": "silverbell", "scientific_name": "Halesia sp."},
    # Hardwoods - Holly
    591: {"common_name": "American holly", "scientific_name": "Ilex opaca"},
    # Hardwoods - Walnuts
    601: {"common_name": "butternut", "scientific_name": "Juglans cinerea"},
    602: {"common_name": "black walnut", "scientific_name": "Juglans nigra"},
    # Hardwoods - Sweetgum
    611: {"common_name": "sweetgum", "scientific_name": "Liquidambar styraciflua"},
    # Hardwoods - Yellow-poplar
    621: {"common_name": "yellow-poplar", "scientific_name": "Liriodendron tulipifera"},
    # Hardwoods - Osage-orange
    641: {"common_name": "Osage-orange", "scientific_name": "Maclura pomifera"},
    # Hardwoods - Magnolias
    651: {"common_name": "cucumbertree", "scientific_name": "Magnolia acuminata"},
    652: {"common_name": "southern magnolia", "scientific_name": "Magnolia grandiflora"},
    653: {"common_name": "sweetbay", "scientific_name": "Magnolia virginiana"},
    654: {"common_name": "bigleaf magnolia", "scientific_name": "Magnolia macrophylla"},
    # Hardwoods - Mulberry
    682: {"common_name": "red mulberry", "scientific_name": "Morus rubra"},
    # Hardwoods - Tupelos
    691: {"common_name": "water tupelo", "scientific_name": "Nyssa aquatica"},
    692: {"common_name": "Ogeechee tupelo", "scientific_name": "Nyssa ogeche"},
    693: {"common_name": "blackgum", "scientific_name": "Nyssa sylvatica"},
    694: {"common_name": "swamp tupelo", "scientific_name": "Nyssa biflora"},
    # Hardwoods - Hophornbeam
    701: {"common_name": "eastern hophornbeam", "scientific_name": "Ostrya virginiana"},
    # Hardwoods - Sourwood
    711: {"common_name": "sourwood", "scientific_name": "Oxydendrum arboreum"},
    # Hardwoods - Redbay
    721: {"common_name": "redbay", "scientific_name": "Persea borbonia"},
    # Hardwoods - Water elm
    722: {"common_name": "water elm", "scientific_name": "Planera aquatica"},
    # Hardwoods - Sycamore
    731: {"common_name": "sycamore", "scientific_name": "Platanus occidentalis"},
    # Hardwoods - Poplars and Aspens
    741: {"common_name": "balsam poplar", "scientific_name": "Populus balsamifera"},
    742: {"common_name": "eastern cottonwood", "scientific_name": "Populus deltoides"},
    743: {"common_name": "bigtooth aspen", "scientific_name": "Populus grandidentata"},
    746: {"common_name": "quaking aspen", "scientific_name": "Populus tremuloides"},
    # Hardwoods - Cherries
    761: {"common_name": "pin cherry", "scientific_name": "Prunus pensylvanica"},
    762: {"common_name": "black cherry", "scientific_name": "Prunus serotina"},
    763: {"common_name": "chokecherry", "scientific_name": "Prunus virginiana"},
    766: {"common_name": "wild plum", "scientific_name": "Prunus americana"},
    # Hardwoods - Oaks (White Oak Group)
    802: {"common_name": "white oak", "scientific_name": "Quercus alba"},
    804: {"common_name": "swamp white oak", "scientific_name": "Quercus bicolor"},
    822: {"common_name": "overcup oak", "scientific_name": "Quercus lyrata"},
    823: {"common_name": "bur oak", "scientific_name": "Quercus macrocarpa"},
    825: {"common_name": "swamp chestnut oak", "scientific_name": "Quercus michauxii"},
    826: {"common_name": "chinkapin oak", "scientific_name": "Quercus muehlenbergii"},
    832: {"common_name": "chestnut oak", "scientific_name": "Quercus prinus"},
    835: {"common_name": "post oak", "scientific_name": "Quercus stellata"},
    838: {"common_name": "live oak", "scientific_name": "Quercus virginiana"},
    # Hardwoods - Oaks (Red Oak Group)
    806: {"common_name": "scarlet oak", "scientific_name": "Quercus coccinea"},
    808: {"common_name": "Durand oak", "scientific_name": "Quercus durandii"},
    809: {"common_name": "northern pin oak", "scientific_name": "Quercus ellipsoidalis"},
    812: {"common_name": "southern red oak", "scientific_name": "Quercus falcata var. falcata"},
    813: {"common_name": "cherrybark oak", "scientific_name": "Quercus falcata var. pagodaefolia"},
    816: {"common_name": "bear oak", "scientific_name": "Quercus ilicifolia"},
    817: {"common_name": "shingle oak", "scientific_name": "Quercus imbricaria"},
    819: {"common_name": "turkey oak", "scientific_name": "Quercus laevis"},
    820: {"common_name": "laurel oak", "scientific_name": "Quercus laurifolia"},
    824: {"common_name": "blackjack oak", "scientific_name": "Quercus marilandica"},
    827: {"common_name": "water oak", "scientific_name": "Quercus nigra"},
    828: {"common_name": "Nuttall oak", "scientific_name": "Quercus nuttallii"},
    830: {"common_name": "pin oak", "scientific_name": "Quercus palustris"},
    831: {"common_name": "willow oak", "scientific_name": "Quercus phellos"},
    833: {"common_name": "northern red oak", "scientific_name": "Quercus rubra"},
    834: {"common_name": "Shumard oak", "scientific_name": "Quercus shumardii"},
    837: {"common_name": "black oak", "scientific_name": "Quercus velutina"},
    842: {"common_name": "bluejack oak", "scientific_name": "Quercus incana"},
    # Hardwoods - Oaks (Western)
    801: {"common_name": "California white oak", "scientific_name": "Quercus lobata"},
    803: {"common_name": "Arizona white oak", "scientific_name": "Quercus arizonica"},
    805: {"common_name": "canyon live oak", "scientific_name": "Quercus chrysolepis"},
    807: {"common_name": "blue oak", "scientific_name": "Quercus douglasii"},
    811: {"common_name": "Emory oak", "scientific_name": "Quercus emoryi"},
    814: {"common_name": "Oregon white oak", "scientific_name": "Quercus garryana"},
    815: {"common_name": "Gambel oak", "scientific_name": "Quercus gambelii"},
    818: {"common_name": "California black oak", "scientific_name": "Quercus kelloggii"},
    821: {"common_name": "coast live oak", "scientific_name": "Quercus agrifolia"},
    829: {"common_name": "interior live oak", "scientific_name": "Quercus wislizeni"},
    839: {"common_name": "Mexican blue oak", "scientific_name": "Quercus oblongifolia"},
    # Hardwoods - Tanoak
    631: {"common_name": "tanoak", "scientific_name": "Notholithocarpus densiflorus"},
    # Hardwoods - Chinquapin
    431: {"common_name": "golden chinquapin", "scientific_name": "Chrysolepis chrysophylla"},
    # Hardwoods - Black locust
    901: {"common_name": "black locust", "scientific_name": "Robinia psuedoacacia"},
    # Hardwoods - Willows
    921: {"common_name": "peachleaf willow", "scientific_name": "Salix amygdaloides"},
    922: {"common_name": "black willow", "scientific_name": "Salix nigra"},
    # Hardwoods - Sassafras
    931: {"common_name": "sassafras", "scientific_name": "Sassafras albidum"},
    # Hardwoods - Mountain-ash
    935: {"common_name": "American mountain-ash", "scientific_name": "Sorbus americana"},
    # Hardwoods - Basswood
    951: {"common_name": "American basswood", "scientific_name": "Tilia americana"},
    # Hardwoods - Elms
    971: {"common_name": "winged elm", "scientific_name": "Ulmus alata"},
    972: {"common_name": "American elm", "scientific_name": "Ulmus americana"},
    973: {"common_name": "cedar elm", "scientific_name": "Ulmus crassifolia"},
    975: {"common_name": "slippery elm", "scientific_name": "Ulmus rubra"},
    977: {"common_name": "rock elm", "scientific_name": "Ulmus thomasii"},
}


def lookup_by_code(spcd: int) -> dict | None:
    """Lookup species information by species code.

    Args:
        spcd: Species code (e.g., 131 for loblolly pine)

    Returns:
        Dictionary with common_name and scientific_name, or None if not found
    """
    return SPECIES_DATA.get(spcd)


def get_species_name(spcd: int) -> str:
    """Get common name for a species code.

    Args:
        spcd: Species code (SPCD)

    Returns:
        Common name, or "Unknown (code: {spcd})" if not found
    """
    info = SPECIES_DATA.get(spcd)
    if info:
        return info["common_name"]
    return f"Unknown (code: {spcd})"


def search_by_name(name: str, limit: int = 10) -> list[dict]:
    """Search for species by common or scientific name (case-insensitive partial match).

    Args:
        name: Name to search for (e.g., "pine", "oak", "Quercus")
        limit: Maximum number of results to return

    Returns:
        List of dictionaries with spcd, common_name, and scientific_name
    """
    search_term = name.lower()
    results = []

    for spcd, info in SPECIES_DATA.items():
        if (search_term in info["common_name"].lower() or
            search_term in info["scientific_name"].lower()):
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
        for spcd, info in sorted(SPECIES_DATA.items())
    ]
