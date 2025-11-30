import math

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

        self.iso_tile_width = TILE_SIZE
        self.iso_tile_height = TILE_SIZE // 2
        self.tile_size = 32

        # Cache chunks
        self._chunk_surfaces = {}
        self._old_chunk_surfaces = {}
        self._old_tile_size = 32
        self._cached_tile_size = 32
        self._chunks_rebuilt_this_frame = 0

        # Minimap
        self.minimap_zoom_level = 1

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

        world_x = rel_x / self.tile_size + self.world_view.camera_x
        world_y = rel_y / self.tile_size + self.world_view.camera_y

        world_x += 0.5
        world_y += 0.5

        return world_x, world_y

    def render(self, game: 'Game'):
        self._chunks_rebuilt_this_frame = 0
        self.screen.fill((20, 20, 30))
        self.render_world(game)
        self.render_entities(game)
        self.render_players(game)
        self.render_cursor(game)
        self.render_minimap(game)
        self.render_ui(game)

        if game.show_debug:
            self.render_debug(game)

        if game.inspected_entity:
            self.render_inspection_panel(game)

        pygame.display.flip()

    def invalidate_chunk_cache(self):
        """Invalide le cache des chunks."""
        # Sauvegarde l'ancien cache et tile_size
        self._old_chunk_surfaces = self._chunk_surfaces.copy()
        self._old_tile_size = getattr(self, '_cached_tile_size', self.tile_size)
        self._cached_tile_size = self.tile_size
        self._chunk_surfaces = {}

    def render_world(self, game: 'Game'):
        """Rendu des chunks (optimisé avec cache)."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        cam_x = self.world_view.camera_x
        cam_y = self.world_view.camera_y
        half_w = screen_w // 2
        half_h = screen_h // 2

        min_cx = int((cam_x - half_w / self.tile_size) // 32) - 1
        max_cx = int((cam_x + half_w / self.tile_size) // 32) + 1
        min_cy = int((cam_y - half_h / self.tile_size) // 32) - 1
        max_cy = int((cam_y + half_h / self.tile_size) // 32) + 1

        target_chunk_size = 32 * self.tile_size

        # Cache des surfaces scalées pour ce tile_size
        if not hasattr(self, '_scaled_cache'):
            self._scaled_cache = {}
            self._scaled_tile_size = self.tile_size

        # Invalide le cache scalé si tile_size a changé
        if self._scaled_tile_size != self.tile_size:
            self._scaled_cache.clear()
            self._scaled_tile_size = self.tile_size

        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                surface = self.get_chunk_surface(cx, cy)
                if surface:
                    chunk_world_x = cx * 32
                    chunk_world_y = cy * 32
                    screen_x, screen_y = self.world_to_screen(chunk_world_x, chunk_world_y)
                    screen_x -= self.tile_size // 2
                    screen_y -= self.tile_size // 2

                    # Scale avec cache
                    if self.tile_size != 32:
                        if (cx, cy) not in self._scaled_cache:
                            self._scaled_cache[(cx, cy)] = pygame.transform.scale(surface, (target_chunk_size,
                                                                                            target_chunk_size))
                        surface = self._scaled_cache[(cx, cy)]

                    self.screen.blit(surface, (screen_x, screen_y))

    def get_chunk_surface(self, cx: int, cy: int) -> pygame.Surface:
        """Retourne une surface cachée pour le chunk (toujours à tile_size=32)."""
        if (cx, cy) not in self._chunk_surfaces:
            chunk = self.world_view.chunks.get((cx, cy))
            if not chunk:
                return None

            # Toujours construire à taille fixe (32 pixels par tile)
            base_tile_size = 32
            chunk_size = 32 * base_tile_size
            surface = pygame.Surface((chunk_size, chunk_size))

            for ty in range(32):
                for tx in range(32):
                    tile_type = chunk['tiles'][ty][tx]
                    if tile_type != TileType.VOID:
                        color = self.TILE_COLORS.get(TileType(tile_type), (100, 100, 100))
                        x = tx * base_tile_size
                        y = ty * base_tile_size
                        surface.fill(color, (x, y, base_tile_size, base_tile_size))
                        darker = tuple(max(0, c - 30) for c in color)
                        pygame.draw.rect(surface, darker, (x, y, base_tile_size, base_tile_size), 1)

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
        size = self.tile_size // 3

        # Rectangle simple pour l'instant
        rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
        pygame.draw.rect(self.screen, color, rect)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, 1)

        # Flèche de direction pour convoyeurs/inserters/miners
        entity_type = EntityType(entity['type'])
        if entity_type in (EntityType.CONVEYOR, EntityType.INSERTER, EntityType.MINER):
            direction = Direction(entity.get('dir', 0))
            self.draw_direction_arrow(x, y, direction)

        # Affiche le contenu du buffer pour miners/furnaces/chests
        data = entity.get('data', {})
        output = data.get('output', [])

        if output:
            count_text = self.small_font.render(str(len(output)), True, (255, 255, 0))
            self.screen.blit(count_text, (x + size // 2, y - size // 2 - 5))

        # Affiche les items sur les convoyeurs
        if entity_type == EntityType.CONVEYOR:
            items = data.get('items', [])
            direction = Direction(entity.get('dir', 0))
            dx, dy = self.direction_to_delta(direction)

            for item in items:
                progress = item.get('progress', 0)
                # Position de l'item sur le convoyeur
                item_x = x + int((progress - 0.5) * self.tile_size * dx)
                item_y = y + int((progress - 0.5) * self.tile_size * dy)

                # Couleur selon le type d'item
                item_color = self.get_item_color(item.get('item', ''))
                pygame.draw.circle(self.screen, item_color, (item_x, item_y), 4)
                pygame.draw.circle(self.screen, (255, 255, 255), (item_x, item_y), 4, 1)

        # Affiche le nombre d'items dans les chests
        if entity_type == EntityType.CHEST:
            items = data.get('items', [])
            if items:
                count_text = self.small_font.render(str(len(items)), True, (255, 255, 0))
                self.screen.blit(count_text, (x + size // 2, y - size // 2 - 5))

        # Affiche input/output pour furnaces
        if entity_type == EntityType.FURNACE:
            input_items = data.get('input', [])
            output_items = data.get('output', [])
            if input_items or output_items:
                text = f"{len(input_items)}>{len(output_items)}"
                count_text = self.small_font.render(text, True, (255, 200, 0))
                self.screen.blit(count_text, (x + size // 2, y - size // 2 - 5))

        if entity_type == EntityType.INSERTER:
            data = entity.get('data', {})
            held_item = data.get('held_item', None)

            if held_item:
                progress = data.get('progress', 0.0)
                direction = Direction(entity.get('dir', 0))
                dx, dy = self.direction_to_delta(direction)

                # Position de l'item : de -0.5 tile (source) à +0.5 tile (dest)
                offset = progress - 0.5  # -0.5 à 0.5
                item_x = x + int(offset * self.tile_size * dx)
                item_y = y + int(offset * self.tile_size * dy)

                # Dessine l'item
                item_color = self.get_item_color(held_item.get('item', ''))
                pygame.draw.circle(self.screen, item_color, (item_x, item_y), 5)
                pygame.draw.circle(self.screen, (255, 255, 255), (item_x, item_y), 5, 1)

    def direction_to_delta(self, direction: Direction) -> Tuple[int, int]:
        """Convertit une direction en delta x, y."""
        deltas = {
            Direction.NORTH: (0, -1),
            Direction.EAST: (1, 0),
            Direction.SOUTH: (0, 1),
            Direction.WEST: (-1, 0)
        }
        return deltas.get(direction, (0, 0))

    def get_item_color(self, item_name: str) -> Tuple[int, int, int]:
        """Retourne la couleur d'un item."""
        colors = {
            'iron_ore': (160, 160, 180),
            'copper_ore': (184, 115, 51),
            'coal': (40, 40, 40),
            'iron_plate': (200, 200, 210),
            'copper_plate': (210, 140, 80),
        }
        return colors.get(item_name, (150, 150, 150))

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
        import math
        from shared.tiles import TileType

        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.screen_to_world(mouse_x, mouse_y)

        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)

        screen_x, screen_y = self.world_to_screen(tile_x, tile_y)

        half = self.tile_size // 2
        rect = pygame.Rect(screen_x - half, screen_y - half, self.tile_size, self.tile_size)

        if game.selected_entity_type is not None:
            # Vérifie si placement valide
            tile = self.world_view.get_tile(tile_x, tile_y)
            entity_at = self.world_view.get_entity_at(tile_x, tile_y)

            valid = True

            # Pas sur l'eau
            if tile == TileType.WATER:
                valid = False

            # Pas sur une entité existante
            if entity_at:
                valid = False

            # Foreuse uniquement sur minerai
            if game.selected_entity_type == EntityType.MINER:
                if tile not in (TileType.IRON_ORE, TileType.COPPER_ORE, TileType.COAL):
                    valid = False

            # Four uniquement sur herbe/terre
            if game.selected_entity_type == EntityType.FURNACE:
                if tile not in (TileType.GRASS, TileType.DIRT):
                    valid = False

            # Couleur selon validité
            cursor_color = (0, 255, 0) if valid else (255, 0, 0)
            pygame.draw.rect(self.screen, cursor_color, rect, 2)

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
        toolbar_height = 80
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
                pygame.draw.rect(self.screen, (100, 100, 100), (x_offset - 5, toolbar_y + 5, 50, 70))

            # Bouton coloré
            pygame.draw.rect(self.screen, color, (x_offset, toolbar_y + 10, 40, 40))

            # Raccourci clavier
            key_text = self.small_font.render(pygame.key.name(key).upper(), True, (200, 200, 200))
            key_rect = key_text.get_rect(center=(x_offset + 20, toolbar_y + 30))
            self.screen.blit(key_text, key_rect)

            # Nom de l'entité
            name_text = self.small_font.render(name, True, (180, 180, 180))
            name_rect = name_text.get_rect(center=(x_offset + 20, toolbar_y + 60))
            self.screen.blit(name_text, name_rect)

            x_offset += 70

        # Instructions à droite
        instructions = [
            "ZQSD: Déplacer",
            "1-6: Sélectionner",
            "R: Tourner",
            "Clic G: Construire",
            "Clic D: Détruire",
            "F3: Debug",
        ]
        x = self.screen.get_width() - 130
        for i, text in enumerate(instructions):
            surface = self.small_font.render(text, True, (150, 150, 150))
            self.screen.blit(surface, (x, toolbar_y + 5 + i * 12))

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

    def render_inspection_panel(self, game: 'Game'):
        """Affiche le panneau d'inspection d'une entité."""
        entity = game.inspected_entity

        if not entity:
            return

        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        # Dimensions du panneau
        panel_width = 250
        panel_height = 300
        panel_x = screen_w - panel_width - 20
        panel_y = (screen_h - panel_height) // 2

        # Fond du panneau
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(self.screen, (30, 30, 40), panel_rect)
        pygame.draw.rect(self.screen, (100, 100, 120), panel_rect, 2)

        # Titre
        entity_type = EntityType(entity['type'])

        names = {
            EntityType.MINER: "Foreuse",
            EntityType.FURNACE: "Four",
            EntityType.CHEST: "Coffre",
            EntityType.ASSEMBLER: "Assembleur",
            EntityType.CONVEYOR: "Convoyeur",
            EntityType.INSERTER: "Inserter",
        }

        title = names.get(entity_type, "Entité")
        title_surface = self.font.render(title, True, (255, 255, 255))
        self.screen.blit(title_surface, (panel_x + 10, panel_y + 10))

        # Ligne de séparation
        pygame.draw.line(self.screen, (100, 100, 120),
                         (panel_x + 10, panel_y + 40),
                         (panel_x + panel_width - 10, panel_y + 40))

        y_offset = panel_y + 50
        data = entity.get('data', {})

        # Affiche selon le type
        if entity_type == EntityType.MINER:
            output = data.get('output', [])
            self.render_item_list("Buffer sortie", output, panel_x + 10, y_offset, panel_width - 20)

        elif entity_type == EntityType.FURNACE:
            input_items = data.get('input', [])
            output_items = data.get('output', [])
            y_offset = self.render_item_list("Entrée", input_items, panel_x + 10, y_offset, panel_width - 20)
            y_offset += 10
            self.render_item_list("Sortie", output_items, panel_x + 10, y_offset, panel_width - 20)

        elif entity_type == EntityType.CHEST:
            items = data.get('items', [])
            self.render_item_list("Contenu", items, panel_x + 10, y_offset, panel_width - 20)

        elif entity_type == EntityType.CONVEYOR:
            items = data.get('items', [])
            self.render_item_list("Items", items, panel_x + 10, y_offset, panel_width - 20)

        elif entity_type == EntityType.ASSEMBLER:
            input_items = data.get('input', [])
            output_items = data.get('output', [])
            selected_recipe = data.get('recipe', None)

            # Affiche la recette sélectionnée
            recipe_text = selected_recipe if selected_recipe else "(aucune recette)"
            recipe_label = self.small_font.render(f"Recette: {recipe_text}", True, (200, 200, 100))
            self.screen.blit(recipe_label, (panel_x + 10, y_offset))
            y_offset += 25

            # Boutons de recettes
            recipes = ['iron_gear', 'copper_wire', 'circuit', 'automation_science']

            for i, recipe in enumerate(recipes):
                btn_x = panel_x + 10 + (i % 2) * 115
                btn_y = y_offset + (i // 2) * 30
                btn_rect = pygame.Rect(btn_x, btn_y, 110, 25)

                # Couleur du bouton
                if selected_recipe == recipe:
                    btn_color = (80, 120, 80)
                else:
                    btn_color = (60, 60, 70)

                pygame.draw.rect(self.screen, btn_color, btn_rect)
                pygame.draw.rect(self.screen, (100, 100, 120), btn_rect, 1)

                # Nom de la recette
                recipe_name = recipe.replace('_', ' ').title()
                text = self.small_font.render(recipe_name, True, (220, 220, 220))
                text_rect = text.get_rect(center=btn_rect.center)
                self.screen.blit(text, text_rect)

                # Stocke le rect pour la détection de clic
                if not hasattr(self, '_recipe_buttons'):
                    self._recipe_buttons = {}

                self._recipe_buttons[recipe] = btn_rect

            y_offset += 70
            y_offset = self.render_item_list("Entrée", input_items, panel_x + 10, y_offset, panel_width - 20)
            y_offset += 10

            self.render_item_list("Sortie", output_items, panel_x + 10, y_offset, panel_width - 20)

        # Instructions
        help_text = self.small_font.render("Échap ou clic droit pour fermer", True, (150, 150, 150))
        self.screen.blit(help_text, (panel_x + 10, panel_y + panel_height - 25))

    def render_item_list(self, title: str, items: list, x: int, y: int, width: int) -> int:
        """Affiche une liste d'items groupés par type. Retourne la position Y finale."""
        # Titre de la section
        title_surface = self.small_font.render(f"{title}:", True, (200, 200, 200))
        self.screen.blit(title_surface, (x, y))
        y += 20

        if not items:
            empty_text = self.small_font.render("(vide)", True, (100, 100, 100))
            self.screen.blit(empty_text, (x + 10, y))
            return y + 20

        # Groupe les items par type
        item_counts = {}
        for item in items:
            item_name = item.get('item', 'inconnu')
            item_counts[item_name] = item_counts.get(item_name, 0) + 1

        # Affiche chaque type
        for item_name, count in item_counts.items():
            color = self.get_item_color(item_name)

            # Petit carré de couleur
            pygame.draw.rect(self.screen, color, (x + 10, y + 2, 12, 12))
            pygame.draw.rect(self.screen, (255, 255, 255), (x + 10, y + 2, 12, 12), 1)

            # Nom et quantité
            display_name = item_name.replace('_', ' ').title()
            text = f"{display_name}: {count}"
            text_surface = self.small_font.render(text, True, (220, 220, 220))
            self.screen.blit(text_surface, (x + 28, y))

            y += 18

        return y