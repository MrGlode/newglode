import threading
from typing import Dict, Set, Tuple, Optional
from dataclasses import dataclass, field

from shared.constants import CHUNK_SIZE, PLAYER_VIEW_DISTANCE
from shared.entities import Entity, EntityType
from server.chunk import Chunk


@dataclass
class Player:
    id: int
    name: str
    x: float = 0.0
    y: float = 0.0
    loaded_chunks: Set[Tuple[int, int]] = field(default_factory=set)


class World:
    def __init__(self, seed: int = None):
        self.seed = seed or hash("default_world")
        self.chunks: Dict[Tuple[int, int], Chunk] = {}
        self.players: Dict[int, Player] = {}
        self.entities: Dict[int, Entity] = {}  # Index global des entités
        self.next_entity_id = 1
        self.tick = 0
        self.lock = threading.RLock()

    def get_chunk(self, cx: int, cy: int) -> Chunk:
        """Récupère ou génère un chunk."""
        key = (cx, cy)
        with self.lock:
            if key not in self.chunks:
                chunk = Chunk(cx=cx, cy=cy)
                chunk.generate(self.seed)
                self.chunks[key] = chunk
            return self.chunks[key]

    def world_to_chunk(self, x: float, y: float) -> Tuple[int, int, int, int]:
        """Convertit coordonnées monde en (chunk_x, chunk_y, local_x, local_y)."""
        cx = int(x // CHUNK_SIZE)
        cy = int(y // CHUNK_SIZE)
        lx = int(x % CHUNK_SIZE)
        ly = int(y % CHUNK_SIZE)
        return cx, cy, lx, ly

    def get_tile(self, x: float, y: float):
        cx, cy, lx, ly = self.world_to_chunk(x, y)
        chunk = self.get_chunk(cx, cy)
        return chunk.get_tile(lx, ly)

    def add_player(self, player_id: int, name: str) -> Player:
        with self.lock:
            player = Player(id=player_id, name=name)
            self.players[player_id] = player
            return player

    def remove_player(self, player_id: int):
        with self.lock:
            self.players.pop(player_id, None)

    def move_player(self, player_id: int, x: float, y: float):
        with self.lock:
            if player_id in self.players:
                self.players[player_id].x = x
                self.players[player_id].y = y

    def get_chunks_around(self, x: float, y: float) -> Set[Tuple[int, int]]:
        """Retourne les coordonnées des chunks autour d'une position."""
        cx = int(x // CHUNK_SIZE)
        cy = int(y // CHUNK_SIZE)
        chunks = set()
        for dx in range(-PLAYER_VIEW_DISTANCE, PLAYER_VIEW_DISTANCE + 1):
            for dy in range(-PLAYER_VIEW_DISTANCE, PLAYER_VIEW_DISTANCE + 1):
                chunks.add((cx + dx, cy + dy))
        return chunks

    def create_entity(self, entity_type: EntityType, x: float, y: float, **kwargs) -> Entity:
        with self.lock:
            entity = Entity(
                id=self.next_entity_id,
                entity_type=entity_type,
                x=x,
                y=y,
                **kwargs
            )
            self.next_entity_id += 1

            # Ajoute au chunk correspondant
            cx, cy, _, _ = self.world_to_chunk(x, y)
            chunk = self.get_chunk(cx, cy)
            chunk.add_entity(entity)
            self.entities[entity.id] = entity

            return entity

    def remove_entity(self, entity_id: int) -> Optional[Entity]:
        with self.lock:
            entity = self.entities.pop(entity_id, None)
            if entity:
                cx, cy, _, _ = self.world_to_chunk(entity.x, entity.y)
                if (cx, cy) in self.chunks:
                    self.chunks[(cx, cy)].remove_entity(entity_id)
            return entity

    def get_entity_at(self, x: int, y: int) -> Optional[Entity]:
        """Retourne l'entité à la position donnée, ou None."""
        with self.lock:
            for entity in self.entities.values():
                if int(entity.x) == x and int(entity.y) == y:
                    return entity
            return None