import pygame
from typing import TYPE_CHECKING, Tuple

from shared.constants import TILE_SIZE, CHUNK_SIZE
from shared.tiles import TileType
from shared.entities import EntityType, Direction

if TYPE_CHECKING:
    from client.game import Game
    from client.world_view import WorldView


class Renderer:
    # Couleurs des tiles
    TILE_COLORS = {
        TileType.VOID: (20, 20, 30),
        TileType.GRASS: (34, 139, 34),
        TileType.DIRT: (139, 90, 43),
        TileType.STONE: (128, 128, 128),
        TileType.WATER: (30, 144, 255),
        TileType.IRON_ORE: (160, 160, 180),
        TileType.COPPER_ORE: (184, 115, 51),
        TileType.COAL: (40, 40, 40),
    }

    # Couleurs des entités
    ENTITY_COLORS = {
        EntityType.PLAYER: (255, 255, 255),
        EntityType.CONVEYOR: (255, 200, 0),
        EntityType.MINER: (200, 100, 50),
        EntityType.FURNACE: (255, 100, 0),
        EntityType.ASSEMBLER: (100, 100, 200),
        EntityType.CHEST: (139, 90, 43),
        EntityType.INSERTER: (150, 150, 150),
    }

    def __init__(self, screen: pygame.Surface, world_view: 'WorldView'):
        self.screen = screen
        self.world_view = world_view
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)


        # Offset pour le rendu isométrique
        self.iso_tile_width = TILE_SIZE
        self.iso_tile_height = TILE_SIZE // 2
        self.tile_size = 32

    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Convertit coordonnées monde en coordonnées écran (2D standard)."""
        rel_x = world_x - self.world_view.camera_x
        rel_y = world_y - self.world_view.camera_y

        screen_x = rel_x * self.tile_size
        screen_y = rel_y * self.tile_size

        screen_x += self.screen.get_width() // 2
        screen_y += self.screen.get_height() // 2

        return int(screen_x), int(screen_y)

    def screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """Convertit coordonnées écran en coordonnées monde."""
        rel_x = screen_x - self.screen.get_width() // 2
        rel_y = screen_y - self.screen.get_height() // 2

        world_x = rel_x / self.tile_size
        world_y = rel_y / self.tile_size

        world_x += self.world_view.camera_x
        world_y += self.world_view.camera_y

        return world_x, world_y

    def render(self, game: 'Game'):
        self.screen.fill((20, 20, 30))
        self.render_world(game)
        self.render_entities(game)
        self.render_players(game)
        self.render_cursor(game)
        self.render_minimap(game)

        if game.show_debug:
            self.render_debug(game)

        pygame.display.flip()

    def render_world(self, game: 'Game'):
        """Rendu des chunks (optimisé avec cache)."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        cam_x = self.world_view.camera_x
        cam_y = self.world_view.camera_y

        # Calcule les chunks visibles
        half_w = screen_w // 2
        half_h = screen_h // 2

        min_cx = int((cam_x - half_w / self.tile_size) // 32) - 1
        max_cx = int((cam_x + half_w / self.tile_size) // 32) + 1
        min_cy = int((cam_y - half_h / self.tile_size) // 32) - 1
        max_cy = int((cam_y + half_h / self.tile_size) // 32) + 1

        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                surface = self.get_chunk_surface(cx, cy)
                if surface:
                    # Position écran du coin haut-gauche du chunk
                    chunk_world_x = cx * 32
                    chunk_world_y = cy * 32
                    screen_x, screen_y = self.world_to_screen(chunk_world_x, chunk_world_y)

                    # Ajuste car world_to_screen centre sur la tile
                    screen_x -= self.tile_size // 2
                    screen_y -= self.tile_size // 2

                    self.screen.blit(surface, (screen_x, screen_y))

    def get_chunk_surface(self, cx: int, cy: int) -> pygame.Surface:
        """Retourne une surface cachée pour le chunk."""
        if not hasattr(self, '_chunk_surfaces'):
            self._chunk_surfaces = {}

        if (cx, cy) not in self._chunk_surfaces:
            chunk = self.world_view.chunks.get((cx, cy))
            if not chunk:
                return None

            chunk_size = 32 * self.tile_size
            surface = pygame.Surface((chunk_size, chunk_size))

            for ty in range(32):
                for tx in range(32):
                    tile_type = chunk['tiles'][ty][tx]
                    if tile_type != TileType.VOID:
                        color = self.TILE_COLORS.get(TileType(tile_type), (100, 100, 100))
                        x = tx * self.tile_size
                        y = ty * self.tile_size

                        # Fond
                        surface.fill(color, (x, y, self.tile_size, self.tile_size))

                        # Bordure
                        darker = tuple(max(0, c - 30) for c in color)
                        pygame.draw.rect(surface, darker, (x, y, self.tile_size, self.tile_size), 1)

            self._chunk_surfaces[(cx, cy)] = surface

        return self._chunk_surfaces[(cx, cy)]

    def draw_tile(self, x: int, y: int, color: Tuple[int, int, int]):
        """Dessine une tile carrée (optimisé)."""
        half = self.tile_size // 2
        self.screen.fill(color, (x - half, y - half, self.tile_size, self.tile_size))

    def render_entities(self, game: 'Game'):
        """Rendu des entités (machines, convoyeurs...)."""
        for entity in self.world_view.entities.values():
            screen_x, screen_y = self.world_to_screen(entity['x'], entity['y'])

            # Vérifie si visible
            if not (0 < screen_x < self.screen.get_width() and 0 < screen_y < self.screen.get_height()):
                continue

            entity_type = EntityType(entity['type'])
            color = self.ENTITY_COLORS.get(entity_type, (200, 200, 200))

            # Dessine l'entité
            self.draw_entity(screen_x, screen_y, color, entity)

    def draw_entity(self, x: int, y: int, color: Tuple[int, int, int], entity: dict):
        """Dessine une entité."""
        size = self.iso_tile_width // 3

        # Rectangle simple pour l'instant
        rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
        pygame.draw.rect(self.screen, color, rect)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, 1)

        # Flèche de direction pour convoyeurs/inserters
        entity_type = EntityType(entity['type'])
        if entity_type in (EntityType.CONVEYOR, EntityType.INSERTER, EntityType.MINER):
            direction = Direction(entity.get('dir', 0))
            self.draw_direction_arrow(x, y, direction)

    def draw_direction_arrow(self, x: int, y: int, direction: Direction):
        """Dessine une flèche de direction."""
        arrows = {
            Direction.NORTH: [(0, -8), (-4, 0), (4, 0)],
            Direction.EAST: [(8, 0), (0, -4), (0, 4)],
            Direction.SOUTH: [(0, 8), (-4, 0), (4, 0)],
            Direction.WEST: [(-8, 0), (0, -4), (0, 4)],
        }

        points = [(x + dx, y + dy) for dx, dy in arrows[direction]]
        pygame.draw.polygon(self.screen, (255, 255, 255), points)

    def render_players(self, game: 'Game'):
        """Rendu des joueurs."""
        # Debug
        #print(f"Mon ID: {game.player_id}, Autres joueurs: {list(self.world_view.other_players.keys())}")

        # Autres joueurs
        for player in self.world_view.other_players.values():
            # Ne pas afficher le joueur local
            if player['id'] == game.player_id:
                continue

            screen_x, screen_y = self.world_to_screen(player['x'], player['y'])

            # Corps
            pygame.draw.circle(self.screen, (100, 100, 255), (screen_x, screen_y - 10), 12)
            pygame.draw.circle(self.screen, (255, 255, 255), (screen_x, screen_y - 10), 12, 2)

            # Nom
            name_surface = self.small_font.render(player['name'], True, (255, 255, 255))
            name_rect = name_surface.get_rect(center=(screen_x, screen_y - 30))
            self.screen.blit(name_surface, name_rect)

        # Joueur local
        if game.player_id:
            screen_x, screen_y = self.world_to_screen(game.player_x, game.player_y)

            pygame.draw.circle(self.screen, (50, 205, 50), (screen_x, screen_y - 10), 12)
            pygame.draw.circle(self.screen, (255, 255, 255), (screen_x, screen_y - 10), 12, 2)

            name_surface = self.small_font.render(game.player_name, True, (255, 255, 255))
            name_rect = name_surface.get_rect(center=(screen_x, screen_y - 30))
            self.screen.blit(name_surface, name_rect)

    def render_cursor(self, game: 'Game'):
        """Rendu du curseur de construction."""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.screen_to_world(mouse_x, mouse_y)

        # Arrondit à la tile
        tile_x = int(world_x)
        tile_y = int(world_y)

        screen_x, screen_y = self.world_to_screen(tile_x, tile_y)

        # Curseur tile (carré)
        half = self.tile_size // 2
        rect = pygame.Rect(screen_x - half, screen_y - half, self.tile_size, self.tile_size)

        if game.selected_entity_type is not None:
            # Mode construction
            pygame.draw.rect(self.screen, (0, 255, 0), rect, 2)

            # Preview de l'entité
            entity_color = self.ENTITY_COLORS.get(EntityType(game.selected_entity_type), (200, 200, 200))
            preview_color = tuple(c // 2 for c in entity_color)
            self.draw_entity(screen_x, screen_y, preview_color, {
                'type': game.selected_entity_type,
                'dir': game.selected_direction
            })
        else:
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 1)

    def render_ui(self, game: 'Game'):
        """Rendu de l'interface utilisateur."""
        # Barre d'outils en bas
        toolbar_height = 60
        toolbar_y = self.screen.get_height() - toolbar_height

        pygame.draw.rect(self.screen, (40, 40, 50), (0, toolbar_y, self.screen.get_width(), toolbar_height))

        # Boutons d'entités
        entities = [
            (EntityType.CONVEYOR, "Convoyeur", pygame.K_1),
            (EntityType.MINER, "Foreuse", pygame.K_2),
            (EntityType.FURNACE, "Four", pygame.K_3),
            (EntityType.ASSEMBLER, "Assembleur", pygame.K_4),
            (EntityType.CHEST, "Coffre", pygame.K_5),
            (EntityType.INSERTER, "Inserter", pygame.K_6),
        ]

        x_offset = 20
        for entity_type, name, key in entities:
            color = self.ENTITY_COLORS.get(entity_type, (200, 200, 200))

            # Sélectionné ?
            if game.selected_entity_type == entity_type:
                pygame.draw.rect(self.screen, (100, 100, 100), (x_offset - 5, toolbar_y + 5, 50, 50))

            pygame.draw.rect(self.screen, color, (x_offset, toolbar_y + 10, 40, 40))

            # Raccourci
            key_text = self.small_font.render(pygame.key.name(key).upper(), True, (200, 200, 200))
            self.screen.blit(key_text, (x_offset + 15, toolbar_y + 45))

            x_offset += 60

        # Instructions
        instructions = [
            "ZQSD: Déplacer",
            "1-6: Sélectionner",
            "R: Tourner",
            "Clic gauche: Construire",
            "Clic droit: Détruire",
            "F3: Debug",
        ]

        x = self.screen.get_width() - 150
        for i, text in enumerate(instructions):
            surface = self.small_font.render(text, True, (150, 150, 150))
            self.screen.blit(surface, (x, toolbar_y + 5 + i * 15))

    def render_loading(self, game: 'Game'):
        """Écran de chargement."""
        text = "Connexion..." if game.connecting else "Déconnecté"
        surface = self.font.render(text, True, (255, 255, 255))
        rect = surface.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
        self.screen.blit(surface, rect)

    def render_minimap(self, game: 'Game'):
        """Rendu de la mini-carte en haut à droite (optimisé)."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        minimap_size = int(min(screen_w, screen_h) * 0.15)

        margin = 10
        minimap_x = screen_w - minimap_size - margin
        minimap_y = margin

        if not hasattr(self, 'minimap_zoom_level'):
            self.minimap_zoom_level = 1
        zoom_levels = [32, 64, 128, 256]
        tiles_range = zoom_levels[self.minimap_zoom_level]

        # Échantillonnage pour les grands zooms
        sample_step = max(1, tiles_range // 64)

        tile_pixel = minimap_size / tiles_range * sample_step

        center_x = game.player_x
        center_y = game.player_y

        cache_key = (int(center_x // sample_step), int(center_y // sample_step), minimap_size, tiles_range)
        if not hasattr(self, '_minimap_cache') or self._minimap_cache_key != cache_key:
            minimap_surface = pygame.Surface((minimap_size, minimap_size), pygame.SRCALPHA)
            minimap_surface.fill((0, 0, 0, 180))

            start_tx = int(center_x - tiles_range // 2)
            end_tx = int(center_x + tiles_range // 2)
            start_ty = int(center_y - tiles_range // 2)
            end_ty = int(center_y + tiles_range // 2)

            for world_tx in range(start_tx, end_tx, sample_step):
                for world_ty in range(start_ty, end_ty, sample_step):
                    cx = world_tx // 32
                    cy = world_ty // 32
                    local_tx = world_tx % 32
                    local_ty = world_ty % 32

                    chunk = self.world_view.chunks.get((cx, cy))
                    if chunk:
                        tile_type = chunk['tiles'][local_ty][local_tx]
                        color = self.TILE_COLORS.get(tile_type, (100, 100, 100))

                        mx = (world_tx - start_tx) / tiles_range * minimap_size
                        my = (world_ty - start_ty) / tiles_range * minimap_size

                        pygame.draw.rect(minimap_surface, color,
                                         (mx, my, max(1, tile_pixel + 1), max(1, tile_pixel + 1)))

            pygame.draw.rect(minimap_surface, (255, 255, 255), (0, 0, minimap_size, minimap_size), 1)

            self._minimap_cache = minimap_surface
            self._minimap_cache_key = cache_key

        self.screen.blit(self._minimap_cache, (minimap_x, minimap_y))

        # Joueurs
        center_px = minimap_x + minimap_size // 2
        center_py = minimap_y + minimap_size // 2
        tile_scale = minimap_size / tiles_range

        for player in self.world_view.other_players.values():
            dx = player['x'] - center_x
            dy = player['y'] - center_y
            if abs(dx) < tiles_range // 2 and abs(dy) < tiles_range // 2:
                px = center_px + dx * tile_scale
                py = center_py + dy * tile_scale
                pygame.draw.circle(self.screen, (100, 100, 255), (int(px), int(py)), 3)

        pygame.draw.circle(self.screen, (50, 255, 50), (center_px, center_py), 3)

        zoom_text = self.small_font.render(f"{tiles_range}x{tiles_range}", True, (200, 200, 200))
        self.screen.blit(zoom_text, (minimap_x + 4, minimap_y + minimap_size - 16))

    def render_debug(self, game: 'Game'):
        """Informations de debug."""
        lines = [
            f"FPS: {game.fps:.0f}",
            f"Pos: ({game.player_x:.1f}, {game.player_y:.1f})",
            f"Chunks: {len(self.world_view.chunks)}",
            f"Entities: {len(self.world_view.entities)}",
            f"Players: {len(self.world_view.other_players) + 1}",
            f"Bandwidth: {game.bandwidth} B/s",
            f"Tiles in minimap: {len(self.world_view.chunks) * 32 * 32}"
        ]

        y = 10
        for line in lines:
            surface = self.small_font.render(line, True, (200, 200, 200))
            self.screen.blit(surface, (10, y))
            y += 18