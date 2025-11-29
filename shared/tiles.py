from dataclasses import dataclass, field
from enum import IntEnum

class TileType(IntEnum):
    VOID = 0
    GRASS = 1
    DIRT = 2
    STONE = 3
    WATER = 4
    IRON_ORE = 5
    COPPER_ORE = 6
    GOLD_ORE = 7
    DIAMOND_ORE = 8
    BAUXITE_ORE = 9
    TIN_ORE = 10
    URANIUM_ORE = 11
    COAL = 12