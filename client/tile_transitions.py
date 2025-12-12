"""
Système d'auto-tiling avec bitmasking pour les transitions entre tiles.
Génère des bordures douces entre les différents types de terrain.
"""

import pygame
from typing import Dict, Tuple, Optional, TYPE_CHECKING
from shared.tiles import TileType

if TYPE_CHECKING:
    from client.world_view import WorldView


# Priorité de rendu des tiles (plus élevé = dessus)
# Les tiles de priorité supérieure "débordent" sur les tiles de priorité inférieure
TILE_PRIORITY: Dict[TileType, int] = {
    TileType.VOID: 0,
    TileType.WATER: 1,
    TileType.DIRT: 2,
    TileType.GRASS: 3,
    TileType.STONE: 4,
    # Minerais - même priorité que leur terrain de base
    TileType.COAL: 4,
    TileType.IRON_ORE: 4,
    TileType.COPPER_ORE: 4,
    TileType.GOLD_ORE: 4,
    TileType.DIAMOND_ORE: 4,
    TileType.BAUXITE_ORE: 4,
    TileType.TIN_ORE: 4,
    TileType.URANIUM_ORE: 4,
}

# Groupes de tiles similaires (pas de transition entre eux)
TILE_GROUPS = {
    'terrain': {TileType.GRASS, TileType.DIRT, TileType.STONE},
    'water': {TileType.WATER},
    'ore': {
        TileType.IRON_ORE, TileType.COPPER_ORE, TileType.COAL,
        TileType.GOLD_ORE, TileType.DIAMOND_ORE, TileType.BAUXITE_ORE,
        TileType.TIN_ORE, TileType.URANIUM_ORE
    },
}


def get_tile_group(tile_type: TileType) -> str:
    """Retourne le groupe d'une tile."""
    for group_name, tiles in TILE_GROUPS.items():
        if tile_type in tiles:
            return group_name
    return 'other'


def should_blend(tile_a: TileType, tile_b: TileType) -> bool:
    """Détermine si deux tiles doivent avoir une transition."""
    if tile_a == tile_b:
        return False

    # Pas de transition entre minerais et leur terrain de base
    if tile_a in TILE_GROUPS['ore'] and tile_b == TileType.STONE:
        return False
    if tile_b in TILE_GROUPS['ore'] and tile_a == TileType.STONE:
        return False

    # Transition si priorités différentes
    prio_a = TILE_PRIORITY.get(tile_a, 2)
    prio_b = TILE_PRIORITY.get(tile_b, 2)

    return prio_a != prio_b


class TileTransitionRenderer:
    """Génère et cache les sprites de transition."""

    # Index des voisins pour le bitmask (4 directions cardinales)
    # Bit 0 = Nord, Bit 1 = Est, Bit 2 = Sud, Bit 3 = Ouest
    NORTH = 1
    EAST = 2
    SOUTH = 4
    WEST = 8

    # Directions avec leurs deltas
    CARDINAL_DIRS = [
        (0, -1, NORTH),  # Nord
        (1, 0, EAST),    # Est
        (0, 1, SOUTH),   # Sud
        (-1, 0, WEST),   # Ouest
    ]

    # Coins (pour les transitions diagonales)
    CORNER_NE = 16
    CORNER_SE = 32
    CORNER_SW = 64
    CORNER_NW = 128

    DIAGONAL_DIRS = [
        (1, -1, CORNER_NE),   # Nord-Est
        (1, 1, CORNER_SE),    # Sud-Est
        (-1, 1, CORNER_SW),   # Sud-Ouest
        (-1, -1, CORNER_NW),  # Nord-Ouest
    ]

    def __init__(self, tile_colors: Dict[int, Tuple[int, int, int]], tile_size: int = 32):
        self.tile_colors = tile_colors
        self.tile_size = tile_size

        # Cache des surfaces de transition {(tile_type, mask): Surface}
        self._transition_cache: Dict[Tuple[TileType, int], pygame.Surface] = {}

        # Taille de la bordure de transition (en pixels)
        self.border_size = 8

    def invalidate_cache(self):
        """Vide le cache des transitions."""
        self._transition_cache.clear()

    def get_transition_surface(self, tile_type: TileType, mask: int) -> Optional[pygame.Surface]:
        """
        Retourne une surface de transition pour une tile et un masque donné.
        Le masque indique quels côtés/coins doivent avoir une transition.
        """
        if mask == 0:
            return None

        cache_key = (tile_type, mask)
        if cache_key not in self._transition_cache:
            self._transition_cache[cache_key] = self._generate_transition(tile_type, mask)

        return self._transition_cache[cache_key]

    def _generate_transition(self, tile_type: TileType, mask: int) -> pygame.Surface:
        """Génère une surface de transition procédurale."""
        surface = pygame.Surface((self.tile_size, self.tile_size), pygame.SRCALPHA)

        color = self.tile_colors.get(int(tile_type), (100, 100, 100))
        border = self.border_size
        size = self.tile_size

        # Dessine les bordures cardinales avec dégradé
        if mask & self.NORTH:
            self._draw_gradient_edge(surface, color, 'north', border)
        if mask & self.SOUTH:
            self._draw_gradient_edge(surface, color, 'south', border)
        if mask & self.EAST:
            self._draw_gradient_edge(surface, color, 'east', border)
        if mask & self.WEST:
            self._draw_gradient_edge(surface, color, 'west', border)

        # Coins extérieurs (seulement si les deux côtés adjacents ne sont pas déjà dessinés)
        if mask & self.CORNER_NE and not (mask & self.NORTH) and not (mask & self.EAST):
            self._draw_corner(surface, color, 'ne', border)
        if mask & self.CORNER_SE and not (mask & self.SOUTH) and not (mask & self.EAST):
            self._draw_corner(surface, color, 'se', border)
        if mask & self.CORNER_SW and not (mask & self.SOUTH) and not (mask & self.WEST):
            self._draw_corner(surface, color, 'sw', border)
        if mask & self.CORNER_NW and not (mask & self.NORTH) and not (mask & self.WEST):
            self._draw_corner(surface, color, 'nw', border)

        # Coins intérieurs (quand deux bords adjacents sont actifs, remplir l'angle)
        if (mask & self.NORTH) and (mask & self.EAST):
            self._draw_inner_corner(surface, color, 'ne', border)
        if (mask & self.SOUTH) and (mask & self.EAST):
            self._draw_inner_corner(surface, color, 'se', border)
        if (mask & self.SOUTH) and (mask & self.WEST):
            self._draw_inner_corner(surface, color, 'sw', border)
        if (mask & self.NORTH) and (mask & self.WEST):
            self._draw_inner_corner(surface, color, 'nw', border)

        return surface

    def _draw_gradient_edge(self, surface: pygame.Surface, color: Tuple[int, int, int],
                            direction: str, border_size: int):
        """Dessine une bordure avec dégradé d'alpha."""
        size = self.tile_size

        for i in range(border_size):
            # Alpha décroissant vers l'intérieur
            alpha = int(255 * (1 - i / border_size) * 0.7)
            rgba = (*color, alpha)

            if direction == 'north':
                pygame.draw.line(surface, rgba, (0, i), (size - 1, i))
            elif direction == 'south':
                pygame.draw.line(surface, rgba, (0, size - 1 - i), (size - 1, size - 1 - i))
            elif direction == 'east':
                pygame.draw.line(surface, rgba, (size - 1 - i, 0), (size - 1 - i, size - 1))
            elif direction == 'west':
                pygame.draw.line(surface, rgba, (i, 0), (i, size - 1))

    def _draw_corner(self, surface: pygame.Surface, color: Tuple[int, int, int],
                     corner: str, border_size: int):
        """Dessine un coin extérieur avec dégradé radial."""
        size = self.tile_size

        # Position du coin
        if corner == 'ne':
            cx, cy = size - 1, 0
        elif corner == 'se':
            cx, cy = size - 1, size - 1
        elif corner == 'sw':
            cx, cy = 0, size - 1
        elif corner == 'nw':
            cx, cy = 0, 0
        else:
            return

        # Dessine des cercles concentriques pour simuler un dégradé radial
        for r in range(border_size, 0, -1):
            alpha = int(255 * (1 - r / border_size) * 0.6)
            rgba = (*color, alpha)
            pygame.draw.circle(surface, rgba, (cx, cy), r)

    def _draw_inner_corner(self, surface: pygame.Surface, color: Tuple[int, int, int],
                           corner: str, border_size: int):
        """Dessine un coin intérieur (quart de disque) pour combler l'angle entre deux bords."""
        size = self.tile_size

        # Position du centre et limites du quart de cercle
        if corner == 'ne':
            cx, cy = size - border_size, border_size
            x_range = range(cx, size)
            y_range = range(0, cy + 1)
        elif corner == 'se':
            cx, cy = size - border_size, size - border_size
            x_range = range(cx, size)
            y_range = range(cy, size)
        elif corner == 'sw':
            cx, cy = border_size, size - border_size
            x_range = range(0, cx + 1)
            y_range = range(cy, size)
        elif corner == 'nw':
            cx, cy = border_size, border_size
            x_range = range(0, cx + 1)
            y_range = range(0, cy + 1)
        else:
            return

        # Dessine pixel par pixel dans le quart de cercle
        for px in x_range:
            for py in y_range:
                # Distance au centre
                dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                if dist <= border_size:
                    # Alpha basé sur la distance (plus proche du centre = plus transparent)
                    alpha = int(255 * (dist / border_size) * 0.7)
                    rgba = (*color, alpha)
                    surface.set_at((px, py), rgba)

    def calculate_transition_mask(self, world_view: 'WorldView',
                                   world_x: int, world_y: int,
                                   current_tile: TileType) -> Dict[TileType, int]:
        """
        Calcule les masques de transition pour une tile.
        Retourne un dict {tile_type_voisin: mask} pour chaque type de tile
        de priorité supérieure qui doit déborder sur cette tile.
        """
        current_priority = TILE_PRIORITY.get(current_tile, 2)
        masks: Dict[TileType, int] = {}

        # Vérifie les 4 directions cardinales
        for dx, dy, bit in self.CARDINAL_DIRS:
            neighbor_tile = world_view.get_tile(world_x + dx, world_y + dy)
            neighbor_priority = TILE_PRIORITY.get(neighbor_tile, 2)

            # Le voisin a une priorité supérieure -> il déborde sur nous
            if neighbor_priority > current_priority and should_blend(current_tile, neighbor_tile):
                if neighbor_tile not in masks:
                    masks[neighbor_tile] = 0
                masks[neighbor_tile] |= bit

        # Vérifie les 4 coins (diagonales)
        for dx, dy, bit in self.DIAGONAL_DIRS:
            neighbor_tile = world_view.get_tile(world_x + dx, world_y + dy)
            neighbor_priority = TILE_PRIORITY.get(neighbor_tile, 2)

            if neighbor_priority > current_priority and should_blend(current_tile, neighbor_tile):
                if neighbor_tile not in masks:
                    masks[neighbor_tile] = 0
                masks[neighbor_tile] |= bit

        return masks


def render_chunk_with_transitions(surface: pygame.Surface,
                                   chunk_data: dict,
                                   world_view: 'WorldView',
                                   tile_colors: Dict[int, Tuple[int, int, int]],
                                   tile_textures: Dict[int, pygame.Surface],
                                   tile_size: int = 32):
    """
    Rend un chunk avec transitions entre tiles.

    Args:
        surface: Surface pygame où dessiner
        chunk_data: Données du chunk {'cx', 'cy', 'tiles'}
        world_view: Vue du monde pour accéder aux chunks voisins
        tile_colors: Dict des couleurs par type de tile
        tile_textures: Dict des textures par type de tile
        tile_size: Taille d'une tile en pixels
    """
    cx = chunk_data['cx']
    cy = chunk_data['cy']
    tiles = chunk_data['tiles']

    transition_renderer = TileTransitionRenderer(tile_colors, tile_size)

    # Première passe : dessine les tiles de base
    for ty in range(32):
        for tx in range(32):
            tile_type = TileType(tiles[ty][tx])
            if tile_type == TileType.VOID:
                continue

            x = tx * tile_size
            y = ty * tile_size

            # Texture ou couleur de base
            if int(tile_type) in tile_textures:
                surface.blit(tile_textures[int(tile_type)], (x, y))
            else:
                color = tile_colors.get(int(tile_type), (100, 100, 100))
                surface.fill(color, (x, y, tile_size, tile_size))

    # Deuxième passe : dessine les transitions
    for ty in range(32):
        for tx in range(32):
            tile_type = TileType(tiles[ty][tx])
            if tile_type == TileType.VOID:
                continue

            # Coordonnées monde
            world_x = cx * 32 + tx
            world_y = cy * 32 + ty

            # Calcule les masques de transition
            masks = transition_renderer.calculate_transition_mask(
                world_view, world_x, world_y, tile_type
            )

            # Dessine les overlays de transition
            x = tx * tile_size
            y = ty * tile_size

            # Trie par priorité pour dessiner dans le bon ordre
            sorted_tiles = sorted(
                masks.keys(),
                key=lambda t: TILE_PRIORITY.get(t, 2)
            )

            for neighbor_tile in sorted_tiles:
                mask = masks[neighbor_tile]
                if mask > 0:
                    transition_surface = transition_renderer.get_transition_surface(
                        neighbor_tile, mask
                    )
                    if transition_surface:
                        surface.blit(transition_surface, (x, y))