import random
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from shared.constants import CHUNK_SIZE
from shared.tiles import TileType
from shared.entities import Entity


@dataclass
class Chunk:
    cx: int  # Coordonnées chunk
    cy: int
    tiles: List[List[TileType]] = field(default_factory=list)
    entities: Dict[int, Entity] = field(default_factory=dict)
    dirty: bool = False  # Modifié depuis dernière sauvegarde

    def __post_init__(self):
        if not self.tiles:
            self.tiles = [[TileType.VOID] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]

    """
    def generate(self, world_seed: int):
        ""Génère le terrain procédural pour ce chunk.""
        chunk_seed = hash((world_seed, self.cx, self.cy))
        rng = random.Random(chunk_seed)

        for y in range(CHUNK_SIZE):
            for x in range(CHUNK_SIZE):
                # Génération simple pour commencer
                roll = rng.random()
                if roll < 0.02:
                    self.tiles[y][x] = TileType.IRON_ORE
                elif roll < 0.04:
                    self.tiles[y][x] = TileType.COPPER_ORE
                elif roll < 0.06:
                    self.tiles[y][x] = TileType.COAL
                elif roll < 0.1:
                    self.tiles[y][x] = TileType.WATER
                elif roll < 0.3:
                    self.tiles[y][x] = TileType.DIRT
                else:
                    self.tiles[y][x] = TileType.GRASS

        self.dirty = True
    """

    def generate(self, world_seed: int):
        from server.world_generator import get_world_generator

        generator = get_world_generator(world_seed)
        self.tiles = generator.generate_chunk_tiles(self.cx, self.cy)
        self.dirty = True


    def get_tile(self, local_x: int, local_y: int) -> TileType:
        if 0 <= local_x < CHUNK_SIZE and 0 <= local_y < CHUNK_SIZE:
            return self.tiles[local_y][local_x]
        return TileType.VOID

    def set_tile(self, local_x: int, local_y: int, tile: TileType):
        if 0 <= local_x < CHUNK_SIZE and 0 <= local_y < CHUNK_SIZE:
            self.tiles[local_y][local_x] = tile
            self.dirty = True

    def add_entity(self, entity: Entity):
        self.entities[entity.id] = entity
        self.dirty = True

    def remove_entity(self, entity_id: int) -> Optional[Entity]:
        entity = self.entities.pop(entity_id, None)
        if entity:
            self.dirty = True
        return entity

    def to_dict(self) -> dict:
        return {
            'cx': self.cx,
            'cy': self.cy,
            'tiles': [[int(t) for t in row] for row in self.tiles],
            'entities': [e.to_dict() for e in self.entities.values()]
        }

    @staticmethod
    def from_dict(d: dict) -> 'Chunk':
        chunk = Chunk(cx=d['cx'], cy=d['cy'])
        chunk.tiles = [[TileType(t) for t in row] for row in d['tiles']]
        for e_data in d.get('entities', []):
            entity = Entity.from_dict(e_data)
            chunk.entities[entity.id] = entity
        return chunk