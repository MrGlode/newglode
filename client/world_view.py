"""
Vue du monde côté client.
Stocke les chunks, entités et joueurs visibles.
"""

from typing import Dict, Set, Optional, Tuple, List
from shared.constants import CHUNK_SIZE, PLAYER_VIEW_DISTANCE


class WorldView:
    """Représentation locale du monde pour le client."""

    def __init__(self):
        # Chunks chargés {(cx, cy): chunk_data}
        self.chunks: Dict[Tuple[int, int], dict] = {}

        # Chunks en attente de chargement
        self.pending_chunks: Set[Tuple[int, int]] = set()

        # Entités visibles {entity_id: entity_data}
        self.entities: Dict[int, dict] = {}

        # Autres joueurs {player_id: player_data}
        self.other_players: Dict[int, dict] = {}

        # Position caméra
        self.camera_x = 0.0
        self.camera_y = 0.0

    def add_chunk(self, chunk_data: dict):
        """Ajoute un chunk reçu du serveur."""
        cx = chunk_data['cx']
        cy = chunk_data['cy']

        self.chunks[(cx, cy)] = chunk_data
        self.pending_chunks.discard((cx, cy))

        # Ajoute les entités du chunk
        for entity_data in chunk_data.get('entities', []):
            self.entities[entity_data['id']] = entity_data

    def get_visible_chunks(self, screen_width: int, screen_height: int) -> Set[Tuple[int, int]]:
        """Retourne les chunks qui devraient être visibles."""
        # Calcule la zone visible en chunks
        view_distance = PLAYER_VIEW_DISTANCE

        center_cx = int(self.camera_x) // CHUNK_SIZE
        center_cy = int(self.camera_y) // CHUNK_SIZE

        visible = set()
        for dx in range(-view_distance, view_distance + 1):
            for dy in range(-view_distance, view_distance + 1):
                visible.add((center_cx + dx, center_cy + dy))

        return visible

    def add_entity(self, entity_data: dict):
        """Ajoute une nouvelle entité."""
        self.entities[entity_data['id']] = entity_data

    def update_entity(self, entity_data: dict):
        """Met à jour une entité existante."""
        entity_id = entity_data.get('id')
        if entity_id is not None:
            self.entities[entity_id] = entity_data

    def remove_entity(self, entity_id: int):
        """Supprime une entité."""
        self.entities.pop(entity_id, None)

    def get_entity_at(self, x: int, y: int) -> Optional[dict]:
        """Retourne l'entité à la position donnée, ou None."""
        for entity in self.entities.values():
            if entity['x'] == x and entity['y'] == y:
                return entity
        return None

    def add_player(self, player_data: dict):
        """Ajoute un autre joueur."""
        player_id = player_data['id']
        self.other_players[player_id] = {
            'id': player_id,
            'name': player_data.get('name', f'Player{player_id}'),
            'x': player_data.get('x', 0),
            'y': player_data.get('y', 0),
            'target_x': player_data.get('x', 0),
            'target_y': player_data.get('y', 0)
        }

    def update_player(self, player_data: dict):
        """Met à jour la position d'un autre joueur."""
        player_id = player_data['id']
        if player_id in self.other_players:
            # Définit la cible pour l'interpolation
            self.other_players[player_id]['target_x'] = player_data['x']
            self.other_players[player_id]['target_y'] = player_data['y']

    def remove_player(self, player_id: int):
        """Supprime un autre joueur."""
        self.other_players.pop(player_id, None)

    def update_players_interpolation(self, dt: float):
        """Interpole la position des autres joueurs pour un mouvement fluide."""
        lerp_speed = 10.0  # Vitesse d'interpolation

        for player in self.other_players.values():
            dx = player['target_x'] - player['x']
            dy = player['target_y'] - player['y']

            # Interpolation linéaire
            player['x'] += dx * lerp_speed * dt
            player['y'] += dy * lerp_speed * dt

    def get_tile(self, world_x: int, world_y: int) -> int:
        """Retourne le type de tile à une position monde."""
        cx = world_x // CHUNK_SIZE
        cy = world_y // CHUNK_SIZE
        local_x = world_x % CHUNK_SIZE
        local_y = world_y % CHUNK_SIZE

        # Gère les coordonnées négatives
        if world_x < 0 and local_x != 0:
            cx -= 1
            local_x = CHUNK_SIZE + (world_x % CHUNK_SIZE)
        if world_y < 0 and local_y != 0:
            cy -= 1
            local_y = CHUNK_SIZE + (world_y % CHUNK_SIZE)

        chunk = self.chunks.get((cx, cy))
        if chunk:
            tiles = chunk.get('tiles', [])
            if 0 <= local_y < len(tiles) and 0 <= local_x < len(tiles[local_y]):
                return tiles[local_y][local_x]

        return 0  # VOID par défaut

    def clear_distant_chunks(self, center_x: float, center_y: float, max_distance: int = 5):
        """Supprime les chunks trop éloignés pour libérer la mémoire."""
        center_cx = int(center_x) // CHUNK_SIZE
        center_cy = int(center_y) // CHUNK_SIZE

        to_remove = []
        for (cx, cy) in self.chunks.keys():
            if abs(cx - center_cx) > max_distance or abs(cy - center_cy) > max_distance:
                to_remove.append((cx, cy))

        for key in to_remove:
            chunk = self.chunks.pop(key, None)
            if chunk:
                # Supprime aussi les entités de ce chunk
                for entity_data in chunk.get('entities', []):
                    self.entities.pop(entity_data['id'], None)