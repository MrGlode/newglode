from typing import Dict, Set, Tuple, Optional, List
from shared.constants import CHUNK_SIZE, PLAYER_VIEW_DISTANCE


class WorldView:
    """Vue locale du monde côté client."""

    def __init__(self):
        self.chunks: Dict[Tuple[int, int], dict] = {}
        self.pending_chunks: Set[Tuple[int, int]] = set()
        self.entities: Dict[int, dict] = {}
        self.other_players: Dict[int, dict] = {}

        # Caméra (en coordonnées monde/tiles)
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.zoom = 1.0

    def add_chunk(self, chunk_data: dict):
        key = (chunk_data['cx'], chunk_data['cy'])
        self.chunks[key] = chunk_data
        self.pending_chunks.discard(key)

        # Indexe les entités
        for entity in chunk_data.get('entities', []):
            self.entities[entity['id']] = entity

    def add_entity(self, entity: dict):
        self.entities[entity['id']] = entity

        # Ajoute aussi au chunk
        cx = int(entity['x'] // CHUNK_SIZE)
        cy = int(entity['y'] // CHUNK_SIZE)
        key = (cx, cy)
        if key in self.chunks:
            chunk = self.chunks[key]
            if 'entities' not in chunk:
                chunk['entities'] = []
            # Évite les doublons
            chunk['entities'] = [e for e in chunk['entities'] if e['id'] != entity['id']]
            chunk['entities'].append(entity)

    def remove_entity(self, entity_id: int):
        entity = self.entities.pop(entity_id, None)
        if entity:
            cx = int(entity['x'] // CHUNK_SIZE)
            cy = int(entity['y'] // CHUNK_SIZE)
            key = (cx, cy)
            if key in self.chunks:
                chunk = self.chunks[key]
                chunk['entities'] = [e for e in chunk.get('entities', []) if e['id'] != entity_id]

    def update_entity(self, entity_id: int, data: dict):
        if entity_id in self.entities:
            self.entities[entity_id].update(data)

    def get_entity_at(self, tile_x: int, tile_y: int) -> Optional[dict]:
        for entity in self.entities.values():
            if int(entity['x']) == tile_x and int(entity['y']) == tile_y:
                return entity
        return None

    def get_tile(self, tile_x: int, tile_y: int) -> int:
        cx = tile_x // CHUNK_SIZE
        cy = tile_y // CHUNK_SIZE
        lx = tile_x % CHUNK_SIZE
        ly = tile_y % CHUNK_SIZE

        key = (cx, cy)
        if key in self.chunks:
            tiles = self.chunks[key].get('tiles', [])
            if 0 <= ly < len(tiles) and 0 <= lx < len(tiles[ly]):
                return tiles[ly][lx]
        return 0  # VOID

    def get_visible_chunks(self, screen_width: int, screen_height: int) -> Set[Tuple[int, int]]:
        """Retourne les chunks visibles à l'écran."""
        from shared.constants import TILE_SIZE

        tiles_x = (screen_width // TILE_SIZE) + 4
        tiles_y = (screen_height // TILE_SIZE) + 4

        chunks = set()
        start_cx = int((self.camera_x - tiles_x // 2) // CHUNK_SIZE) - 1
        start_cy = int((self.camera_y - tiles_y // 2) // CHUNK_SIZE) - 1
        end_cx = int((self.camera_x + tiles_x // 2) // CHUNK_SIZE) + 1
        end_cy = int((self.camera_y + tiles_y // 2) // CHUNK_SIZE) + 1

        for cx in range(start_cx, end_cx + 1):
            for cy in range(start_cy, end_cy + 1):
                chunks.add((cx, cy))

        return chunks

    def add_player(self, player_id: int, name: str, x: float, y: float):
        self.other_players[player_id] = {
            'id': player_id,
            'name': name,
            'x': x,
            'y': y,
            'target_x': x,
            'target_y': y
        }

    def remove_player(self, player_id: int):
        self.other_players.pop(player_id, None)

    def move_player(self, player_id: int, x: float, y: float):
        if player_id in self.other_players:
            # Définit la cible pour l'interpolation
            self.other_players[player_id]['target_x'] = x
            self.other_players[player_id]['target_y'] = y

    def update_players_interpolation(self, dt: float):
        """Interpole les positions des autres joueurs."""
        interpolation_speed = 10.0  # Vitesse de rattrapage

        for player in self.other_players.values():
            dx = player['target_x'] - player['x']
            dy = player['target_y'] - player['y']

            # Si très proche, snap
            if abs(dx) < 0.01 and abs(dy) < 0.01:
                player['x'] = player['target_x']
                player['y'] = player['target_y']
            else:
                # Interpolation smooth
                player['x'] += dx * min(1.0, interpolation_speed * dt)
                player['y'] += dy * min(1.0, interpolation_speed * dt)