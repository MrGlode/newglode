import pygame
import math
from typing import TYPE_CHECKING, Tuple, Dict, Optional

from shared.constants import TILE_SIZE, CHUNK_SIZE
from shared.tiles import TileType
from shared.entities import EntityType, Direction
from admin.config import get_config
from client.tile_transitions import TileTransitionRenderer, TILE_PRIORITY, should_blend

if TYPE_CHECKING:
    from client.game import Game
    from client.world_view import WorldView


class Renderer:
    def __init__(self, screen: pygame.Surface, world_view: 'WorldView'):
        self.screen = screen
        self.world_view = world_view
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)

        self.iso_tile_width = TILE_SIZE
        self.iso_tile_height = TILE_SIZE // 2
        self.tile_size = 32

        # Cache chunks
        self._chunk_surfaces: Dict[Tuple[int, int], pygame.Surface] = {}
        self._old_chunk_surfaces = {}
        self._old_tile_size = 32
        self._cached_tile_size = 32
        self._chunks_rebuilt_this_frame = 0

        # Cache zoom
        self._scaled_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self._scaled_tile_size = 32

        # Minimap
        self.minimap_zoom_level = 1

        # Charge les couleurs depuis la config
        config = get_config()
        self.TILE_COLORS = config.tile_colors
        self.ENTITY_COLORS = config.entity_colors

        # Charge les textures de tiles
        self.tile_textures = self._load_tile_textures()

        # Renderer de transitions
        self.transition_renderer = TileTransitionRenderer(self.TILE_COLORS, 32)

        # Active/désactive les transitions (pour debug/performance)
        self.enable_transitions = True

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

        return world_x, world_y

    def _load_tile_textures(self) -> dict:
        """Charge les textures des tiles depuis les fichiers PNG."""
        import os

        textures = {}
        config = get_config()

        # Chemin vers les textures de tiles
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(current_dir, "assets", "images", "tiles")

        for tile_id, tile_config in config.tiles.items():
            tile_name = tile_config.name.lower()
            texture_path = os.path.join(base_path, f"{tile_name}.png")

            if os.path.exists(texture_path):
                try:
                    texture = pygame.image.load(texture_path).convert()
                    # Redimensionne à 32x32 si nécessaire
                    if texture.get_size() != (32, 32):
                        texture = pygame.transform.scale(texture, (32, 32))
                    textures[tile_id] = texture
                    print(f"Texture chargée: {texture_path}")
                except Exception as e:
                    print(f"Erreur chargement texture {texture_path}: {e}")

        print(f"Textures tiles chargées: {len(textures)}/{len(config.tiles)}")
        return textures

    def render(self, game: 'Game'):
        self._chunks_rebuilt_this_frame = 0

        self.screen.fill((20, 20, 30))
        self.render_world(game)
        self.render_entities(game)
        self.render_players(game)
        self.render_cursor(game)
        self.render_minimap(game)
        self.render_ui(game)

        # Hotbar inventaire (toujours visible si inventaire fermé)
        game.inventory_ui.render_hotbar(self.screen, game)

        if game.inspected_entity:
            self.render_inspection_panel(game)

        # Inventaire complet (par-dessus tout)
        game.inventory_ui.render(self.screen, game)

        if game.show_debug:
            self.render_debug(game)

        pygame.display.flip()

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

        # Invalide le cache scalé si zoom changé
        if self._scaled_tile_size != self.tile_size:
            self._scaled_cache.clear()
            self._scaled_tile_size = self.tile_size

        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                surface = self.get_chunk_surface(cx, cy)
                if surface:
                    # La première tile du chunk est à (cx * 32, cy * 32)
                    # Son centre est donc à (cx * 32 + 0.5, cy * 32 + 0.5)
                    # Mais on veut le coin supérieur gauche de la surface
                    first_tile_x = cx * 32
                    first_tile_y = cy * 32
                    # world_to_screen donne la position du CENTRE d'une tile
                    # On veut le coin, donc on passe les coordonnées du centre de la première tile
                    # puis on soustrait pour avoir le coin
                    screen_x, screen_y = self.world_to_screen(first_tile_x + 0.5, first_tile_y + 0.5)
                    screen_x -= self.tile_size // 2
                    screen_y -= self.tile_size // 2

                    # Scale avec cache si nécessaire
                    if self.tile_size != 32:
                        if (cx, cy) not in self._scaled_cache:
                            target_size = 32 * self.tile_size
                            self._scaled_cache[(cx, cy)] = pygame.transform.scale(surface, (target_size, target_size))
                        surface = self._scaled_cache[(cx, cy)]

                    self.screen.blit(surface, (screen_x, screen_y))

    def invalidate_chunk_cache(self, cx: int = None, cy: int = None):
        """Invalide le cache des chunks."""
        if cx is not None and cy is not None:
            # Invalide un chunk spécifique et ses voisins (pour les transitions)
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    key = (cx + dx, cy + dy)
                    self._chunk_surfaces.pop(key, None)
                    self._scaled_cache.pop(key, None)
        else:
            # Invalide tout le cache
            self._chunk_surfaces.clear()
            self._scaled_cache.clear()

    def get_chunk_surface(self, cx: int, cy: int) -> Optional[pygame.Surface]:
        """Retourne une surface cachée pour le chunk (toujours à tile_size=32)."""
        if (cx, cy) not in self._chunk_surfaces:
            chunk = self.world_view.chunks.get((cx, cy))
            if not chunk:
                return None

            # Toujours construire à taille fixe (32 pixels par tile)
            base_tile_size = 32
            chunk_size = 32 * base_tile_size
            surface = pygame.Surface((chunk_size, chunk_size))

            # Première passe : tiles de base
            for ty in range(32):
                for tx in range(32):
                    tile_type = chunk['tiles'][ty][tx]
                    if tile_type != TileType.VOID:
                        x = tx * base_tile_size
                        y = ty * base_tile_size

                        # Utilise la texture si disponible, sinon la couleur
                        if tile_type in self.tile_textures:
                            surface.blit(self.tile_textures[tile_type], (x, y))
                        else:
                            color = self.TILE_COLORS.get(tile_type, (100, 100, 100))
                            surface.fill(color, (x, y, base_tile_size, base_tile_size))

            # Deuxième passe : transitions (si activées)
            if self.enable_transitions:
                self._render_chunk_transitions(surface, cx, cy, chunk, base_tile_size)

            self._chunk_surfaces[(cx, cy)] = surface

        return self._chunk_surfaces[(cx, cy)]

    def _render_chunk_transitions(self, surface: pygame.Surface, cx: int, cy: int,
                                  chunk: dict, tile_size: int):
        """Rend les transitions de tiles sur la surface du chunk."""
        tiles = chunk['tiles']

        for ty in range(32):
            for tx in range(32):
                tile_type = TileType(tiles[ty][tx])
                if tile_type == TileType.VOID:
                    continue

                # Coordonnées monde de cette tile
                world_x = cx * 32 + tx
                world_y = cy * 32 + ty

                current_priority = TILE_PRIORITY.get(tile_type, 2)

                # Calcule le masque de transition pour chaque type de tile voisin
                neighbor_masks: Dict[TileType, int] = {}

                # Vérifie les 4 directions cardinales
                for dx, dy, bit in self.transition_renderer.CARDINAL_DIRS:
                    neighbor_tile = self._get_tile_at(world_x + dx, world_y + dy)
                    if neighbor_tile is None:
                        continue

                    neighbor_priority = TILE_PRIORITY.get(neighbor_tile, 2)

                    # Le voisin a une priorité supérieure -> il déborde sur nous
                    if neighbor_priority > current_priority and should_blend(tile_type, neighbor_tile):
                        if neighbor_tile not in neighbor_masks:
                            neighbor_masks[neighbor_tile] = 0
                        neighbor_masks[neighbor_tile] |= bit

                # Vérifie les 4 coins (diagonales)
                for dx, dy, bit in self.transition_renderer.DIAGONAL_DIRS:
                    neighbor_tile = self._get_tile_at(world_x + dx, world_y + dy)
                    if neighbor_tile is None:
                        continue

                    neighbor_priority = TILE_PRIORITY.get(neighbor_tile, 2)

                    if neighbor_priority > current_priority and should_blend(tile_type, neighbor_tile):
                        if neighbor_tile not in neighbor_masks:
                            neighbor_masks[neighbor_tile] = 0
                        neighbor_masks[neighbor_tile] |= bit

                # Dessine les overlays de transition
                x = tx * tile_size
                y = ty * tile_size

                # Trie par priorité pour dessiner dans le bon ordre
                sorted_tiles = sorted(
                    neighbor_masks.keys(),
                    key=lambda t: TILE_PRIORITY.get(t, 2)
                )

                for neighbor_tile in sorted_tiles:
                    mask = neighbor_masks[neighbor_tile]
                    if mask > 0:
                        transition_surface = self.transition_renderer.get_transition_surface(
                            neighbor_tile, mask
                        )
                        if transition_surface:
                            surface.blit(transition_surface, (x, y))

    def _get_tile_at(self, world_x: int, world_y: int) -> Optional[TileType]:
        """Récupère le type de tile à une position monde (avec accès inter-chunk)."""
        tile_id = self.world_view.get_tile(world_x, world_y)
        if tile_id == 0:  # VOID - peut être chunk non chargé
            # Vérifie si le chunk existe
            cx = world_x // 32
            cy = world_y // 32
            if (cx, cy) not in self.world_view.chunks:
                return None  # Chunk non chargé
        return TileType(tile_id)

    def draw_tile(self, x: int, y: int, color: Tuple[int, int, int]):
        """Dessine une tile carrée (optimisé)."""
        half = self.tile_size // 2
        self.screen.fill(color, (x - half, y - half, self.tile_size, self.tile_size))

    def render_entities(self, game: 'Game'):
        """Rendu des entités (machines, convoyeurs...)."""
        for entity in self.world_view.entities.values():
            # +0.5 pour centrer l'entité sur la tile
            screen_x, screen_y = self.world_to_screen(entity['x'] + 0.5, entity['y'] + 0.5)

            # Vérifie si visible
            if not (0 < screen_x < self.screen.get_width() and 0 < screen_y < self.screen.get_height()):
                continue

            entity_type = EntityType(entity['type'])
            color = self.ENTITY_COLORS.get(int(entity_type), (200, 200, 200))

            # Dessine l'entité
            self.draw_entity(screen_x, screen_y, color, entity)

    def draw_entity(self, x: int, y: int, color: Tuple[int, int, int], entity: dict):
        """Dessine une entité."""
        config = get_config()
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
                item_x = x + int((progress - 0.5) * self.tile_size * dx)
                item_y = y + int((progress - 0.5) * self.tile_size * dy)

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

        # Affiche l'item porté par l'inserter
        if entity_type == EntityType.INSERTER:
            held_item = data.get('held_item', None)

            if held_item:
                progress = data.get('progress', 0.0)
                direction = Direction(entity.get('dir', 0))
                dx, dy = self.direction_to_delta(direction)

                offset = progress - 0.5
                item_x = x + int(offset * self.tile_size * dx)
                item_y = y + int(offset * self.tile_size * dy)

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
        config = get_config()
        return config.get_item_color(item_name)

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
        # Autres joueurs
        for player in self.world_view.other_players.values():
            if player['id'] == game.player_id:
                continue

            screen_x, screen_y = self.world_to_screen(player['x'], player['y'])

            pygame.draw.circle(self.screen, (100, 100, 255), (screen_x, screen_y), 12)
            pygame.draw.circle(self.screen, (255, 255, 255), (screen_x, screen_y), 12, 2)

            name_surface = self.small_font.render(player['name'], True, (255, 255, 255))
            name_rect = name_surface.get_rect(center=(screen_x, screen_y - 20))
            self.screen.blit(name_surface, name_rect)

        # Joueur local
        if game.player_id:
            screen_x, screen_y = self.world_to_screen(game.player_x, game.player_y)

            pygame.draw.circle(self.screen, (50, 205, 50), (screen_x, screen_y), 12)
            pygame.draw.circle(self.screen, (255, 255, 255), (screen_x, screen_y), 12, 2)

            name_surface = self.small_font.render(game.player_name, True, (255, 255, 255))
            name_rect = name_surface.get_rect(center=(screen_x, screen_y - 20))
            self.screen.blit(name_surface, name_rect)

    def render_cursor(self, game: 'Game'):
        """Rendu du curseur de construction."""
        config = get_config()

        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.screen_to_world(mouse_x, mouse_y)

        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)

        # +0.5 pour centrer le curseur sur la tile
        screen_x, screen_y = self.world_to_screen(tile_x + 0.5, tile_y + 0.5)

        half = self.tile_size // 2
        rect = pygame.Rect(screen_x - half, screen_y - half, self.tile_size, self.tile_size)

        if game.selected_entity_type is not None:
            # Vérifie si placement valide
            tile_id = self.world_view.get_tile(tile_x, tile_y)
            entity_at = self.world_view.get_entity_at(tile_x, tile_y)

            tile_config = config.tiles.get(tile_id)
            tile_name = tile_config.name if tile_config else 'VOID'

            entity_config = config.entities.get(int(game.selected_entity_type))
            entity_name = entity_config.name if entity_config else None

            valid = True

            # Pas sur une entité existante
            if entity_at:
                valid = False

            # Vérifie les règles de placement
            if entity_name and not config.can_place_entity(entity_name, tile_name):
                valid = False

            # Couleur selon validité
            cursor_color = (0, 255, 0) if valid else (255, 0, 0)
            pygame.draw.rect(self.screen, cursor_color, rect, 2)

            # Preview de l'entité
            entity_color = self.ENTITY_COLORS.get(int(game.selected_entity_type), (200, 200, 200))
            preview_color = tuple(c // 2 for c in entity_color)
            self.draw_entity(screen_x, screen_y, preview_color, {
                'type': game.selected_entity_type,
                'dir': game.selected_direction
            })
        else:
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 1)

    def render_ui(self, game: 'Game'):
        """Rendu de l'interface utilisateur."""
        config = get_config()

        toolbar_height = 80
        toolbar_y = self.screen.get_height() - toolbar_height
        pygame.draw.rect(self.screen, (40, 40, 50), (0, toolbar_y, self.screen.get_width(), toolbar_height))

        # Boutons d'entités depuis la config
        entities = [
            (EntityType.CONVEYOR, pygame.K_1),
            (EntityType.MINER, pygame.K_2),
            (EntityType.FURNACE, pygame.K_3),
            (EntityType.ASSEMBLER, pygame.K_4),
            (EntityType.CHEST, pygame.K_5),
            (EntityType.INSERTER, pygame.K_6),
        ]

        x_offset = 20
        for entity_type, key in entities:
            entity_config = config.entities.get(int(entity_type))
            color = entity_config.color if entity_config else (200, 200, 200)
            name = entity_config.display_name if entity_config else "?"

            if game.selected_entity_type == entity_type:
                pygame.draw.rect(self.screen, (100, 100, 100), (x_offset - 5, toolbar_y + 5, 50, 70))

            pygame.draw.rect(self.screen, color, (x_offset, toolbar_y + 10, 40, 40))

            key_text = self.small_font.render(pygame.key.name(key).upper(), True, (200, 200, 200))
            key_rect = key_text.get_rect(center=(x_offset + 20, toolbar_y + 30))
            self.screen.blit(key_text, key_rect)

            name_text = self.small_font.render(name, True, (180, 180, 180))
            name_rect = name_text.get_rect(center=(x_offset + 20, toolbar_y + 60))
            self.screen.blit(name_text, name_rect)

            x_offset += 70

        # Instructions à droite
        instructions = [
            "ZQSD: Déplacer",
            "1-6: Sélectionner",
            "R: Tourner",
            "I/E: Inventaire",
            "F: Ramasser",
            "Clic G/D: Actions",
            "F3: Debug",
        ]
        x = self.screen.get_width() - 130
        for i, text in enumerate(instructions):
            surface = self.small_font.render(text, True, (150, 150, 150))
            self.screen.blit(surface, (x, toolbar_y + 5 + i * 12))

    def render_inspection_panel(self, game: 'Game'):
        """Affiche le panneau d'inspection d'une entité."""
        config = get_config()
        entity = game.inspected_entity
        if not entity:
            return

        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        panel_width = 250
        panel_height = 300
        panel_x = screen_w - panel_width - 20
        panel_y = (screen_h - panel_height) // 2

        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(self.screen, (30, 30, 40), panel_rect)
        pygame.draw.rect(self.screen, (100, 100, 120), panel_rect, 2)

        entity_type = EntityType(entity['type'])
        title = config.get_entity_display_name(int(entity_type))
        title_surface = self.font.render(title, True, (255, 255, 255))
        self.screen.blit(title_surface, (panel_x + 10, panel_y + 10))

        pygame.draw.line(self.screen, (100, 100, 120),
                         (panel_x + 10, panel_y + 40),
                         (panel_x + panel_width - 10, panel_y + 40))

        y_offset = panel_y + 50
        data = entity.get('data', {})

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

            recipe_text = selected_recipe if selected_recipe else "(aucune recette)"
            recipe_label = self.small_font.render(f"Recette: {recipe_text}", True, (200, 200, 100))
            self.screen.blit(recipe_label, (panel_x + 10, y_offset))
            y_offset += 25

            # Boutons de recettes depuis la config
            recipes = config.get_assembler_recipe_names()
            for i, recipe in enumerate(recipes):
                btn_x = panel_x + 10 + (i % 2) * 115
                btn_y = y_offset + (i // 2) * 30
                btn_rect = pygame.Rect(btn_x, btn_y, 110, 25)

                if selected_recipe == recipe:
                    btn_color = (80, 120, 80)
                else:
                    btn_color = (60, 60, 70)

                pygame.draw.rect(self.screen, btn_color, btn_rect)
                pygame.draw.rect(self.screen, (100, 100, 120), btn_rect, 1)

                recipe_config = config.assembler_recipes.get(recipe)
                recipe_name = recipe_config.display_name if recipe_config else recipe.replace('_', ' ').title()
                text = self.small_font.render(recipe_name, True, (220, 220, 220))
                text_rect = text.get_rect(center=btn_rect.center)
                self.screen.blit(text, text_rect)

                if not hasattr(self, '_recipe_buttons'):
                    self._recipe_buttons = {}
                self._recipe_buttons[recipe] = btn_rect

            y_offset += ((len(recipes) + 1) // 2) * 30 + 10

            y_offset = self.render_item_list("Entrée", input_items, panel_x + 10, y_offset, panel_width - 20)
            y_offset += 10
            self.render_item_list("Sortie", output_items, panel_x + 10, y_offset, panel_width - 20)

        help_text = self.small_font.render("Échap ou clic droit pour fermer", True, (150, 150, 150))
        self.screen.blit(help_text, (panel_x + 10, panel_y + panel_height - 25))

    def render_item_list(self, title: str, items: list, x: int, y: int, width: int) -> int:
        """Affiche une liste d'items groupés par type. Retourne la position Y finale."""
        title_surface = self.small_font.render(f"{title}:", True, (200, 200, 200))
        self.screen.blit(title_surface, (x, y))
        y += 20

        if not items:
            empty_text = self.small_font.render("(vide)", True, (100, 100, 100))
            self.screen.blit(empty_text, (x + 10, y))
            return y + 20

        item_counts = {}
        for item in items:
            item_name = item.get('item', 'inconnu')
            item_counts[item_name] = item_counts.get(item_name, 0) + 1

        for item_name, count in item_counts.items():
            color = self.get_item_color(item_name)

            pygame.draw.rect(self.screen, color, (x + 10, y + 2, 12, 12))
            pygame.draw.rect(self.screen, (255, 255, 255), (x + 10, y + 2, 12, 12), 1)

            display_name = item_name.replace('_', ' ').title()
            text = f"{display_name}: {count}"
            text_surface = self.small_font.render(text, True, (220, 220, 220))
            self.screen.blit(text_surface, (x + 28, y))

            y += 18

        return y

    def render_minimap(self, game: 'Game'):
        """Rendu de la mini-carte en haut à droite (optimisé)."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        minimap_size = int(min(screen_w, screen_h) * 0.15)

        margin = 10
        minimap_x = screen_w - minimap_size - margin
        minimap_y = margin

        zoom_levels = [32, 64, 128, 256]
        tiles_range = zoom_levels[self.minimap_zoom_level]

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
            f"Transitions: {'ON' if self.enable_transitions else 'OFF'}",
        ]

        y = 10
        for line in lines:
            surface = self.small_font.render(line, True, (200, 200, 200))
            self.screen.blit(surface, (10, y))
            y += 18