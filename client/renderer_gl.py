import pygame
import moderngl
import numpy as np
from typing import TYPE_CHECKING, Tuple, Dict

from shared.constants import TILE_SIZE, CHUNK_SIZE
from shared.tiles import TileType
from shared.entities import EntityType, Direction

if TYPE_CHECKING:
    from client.game import Game
    from client.world_view import WorldView


class RendererGL:
    """Renderer GPU avec ModernGL."""

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
        self.tile_size = 32

        # Fonts pygame pour l'UI
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)

        # Initialise ModernGL
        self.ctx = moderngl.create_context()

        # Shader pour les tiles
        self.prog = self.ctx.program(
            vertex_shader='''
                #version 330
                in vec2 in_position;
                in vec3 in_color;
                out vec3 v_color;
                uniform vec2 u_resolution;
                uniform vec2 u_camera;
                uniform float u_tile_size;

                void main() {
                    vec2 world_pos = in_position;
                    vec2 screen_pos = (world_pos - u_camera) * u_tile_size;
                    screen_pos += u_resolution * 0.5;

                    // Normalise en coordonnées OpenGL (-1 à 1)
                    vec2 ndc = (screen_pos / u_resolution) * 2.0 - 1.0;
                    // Inverse Y pour correspondre aux coordonnées écran
                    ndc.y = -ndc.y;

                    gl_Position = vec4(ndc, 0.0, 1.0);
                    v_color = in_color;
                }
            ''',
            fragment_shader='''
                #version 330
                in vec3 v_color;
                out vec4 f_color;

                void main() {
                    f_color = vec4(v_color, 1.0);
                }
            ''',
        )

        # Shader pour dessiner la texture pygame
        self.prog_texture = self.ctx.program(
            vertex_shader='''
                #version 330
                in vec2 in_position;
                in vec2 in_texcoord;
                out vec2 v_texcoord;

                void main() {
                    gl_Position = vec4(in_position, 0.0, 1.0);
                    v_texcoord = in_texcoord;
                }
            ''',
            fragment_shader='''
                #version 330
                in vec2 v_texcoord;
                out vec4 f_color;
                uniform sampler2D u_texture;

                void main() {
                    f_color = texture(u_texture, v_texcoord);
                }
            ''',
        )

        # Quad fullscreen pour le blit de texture pygame
        quad_vertices = np.array([
            -1, -1, 0, 0,
             1, -1, 1, 0,
             1,  1, 1, 1,
            -1, -1, 0, 0,
             1,  1, 1, 1,
            -1,  1, 0, 1,
        ], dtype='f4')

        self.quad_vbo = self.ctx.buffer(quad_vertices)
        self.quad_vao = self.ctx.vertex_array(
            self.prog_texture,
            [(self.quad_vbo, '2f 2f', 'in_position', 'in_texcoord')]
        )

        # Texture pour l'overlay pygame
        self.pg_texture = None

        # Cache pour les VBO de chunks
        self._chunk_vbos: Dict[Tuple[int, int], moderngl.VertexArray] = {}

        # Minimap
        self.minimap_zoom_level = 1

    def _create_chunk_vao(self, cx: int, cy: int) -> moderngl.VertexArray:
        """Crée un VAO pour un chunk."""
        chunk = self.world_view.chunks.get((cx, cy))
        if not chunk:
            return None

        vertices = []

        for ty in range(32):
            for tx in range(32):
                tile_type = chunk['tiles'][ty][tx]
                if tile_type == TileType.VOID:
                    continue

                color = self.TILE_COLORS.get(TileType(tile_type), (100, 100, 100))
                r, g, b = color[0] / 255, color[1] / 255, color[2] / 255

                world_x = cx * 32 + tx
                world_y = cy * 32 + ty

                # Deux triangles pour un quad
                # Triangle 1
                vertices.extend([world_x, world_y, r, g, b])
                vertices.extend([world_x + 1, world_y, r, g, b])
                vertices.extend([world_x + 1, world_y + 1, r, g, b])
                # Triangle 2
                vertices.extend([world_x, world_y, r, g, b])
                vertices.extend([world_x + 1, world_y + 1, r, g, b])
                vertices.extend([world_x, world_y + 1, r, g, b])

        if not vertices:
            return None

        vbo = self.ctx.buffer(np.array(vertices, dtype='f4'))
        vao = self.ctx.vertex_array(
            self.prog,
            [(vbo, '2f 3f', 'in_position', 'in_color')]
        )
        return vao

    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Convertit coordonnées monde en coordonnées écran."""
        rel_x = world_x - self.world_view.camera_x
        rel_y = world_y - self.world_view.camera_y
        screen_x = rel_x * self.tile_size + self.screen.get_width() // 2
        screen_y = rel_y * self.tile_size + self.screen.get_height() // 2
        return int(screen_x), int(screen_y)

    def screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """Convertit coordonnées écran en coordonnées monde."""
        rel_x = screen_x - self.screen.get_width() // 2
        rel_y = screen_y - self.screen.get_height() // 2
        world_x = rel_x / self.tile_size + self.world_view.camera_x
        world_y = rel_y / self.tile_size + self.world_view.camera_y
        return world_x, world_y

    def render(self, game: 'Game'):
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        # Configure le viewport
        self.ctx.viewport = (0, 0, screen_w, screen_h)
        self.ctx.clear(20 / 255, 20 / 255, 30 / 255)

        # Render tiles avec GPU
        self._render_tiles_gl(game)

        # Crée une surface pygame transparente pour l'overlay
        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 0))

        # Render UI sur la surface pygame
        self._render_entities_pg(game, overlay)
        self._render_players_pg(game, overlay)
        self._render_cursor_pg(game, overlay)
        self._render_minimap_pg(game, overlay)

        if game.show_debug:
            self._render_debug_pg(game, overlay)

        # Blit l'overlay pygame sur le contexte GL
        self._blit_pygame_surface(overlay)

        pygame.display.flip()

    def _render_tiles_gl(self, game: 'Game'):
        """Render les tiles avec OpenGL."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        cam_x = self.world_view.camera_x
        cam_y = self.world_view.camera_y

        # Chunks visibles
        half_w = screen_w // 2
        half_h = screen_h // 2

        min_cx = int((cam_x - half_w / self.tile_size) // 32) - 1
        max_cx = int((cam_x + half_w / self.tile_size) // 32) + 1
        min_cy = int((cam_y - half_h / self.tile_size) // 32) - 1
        max_cy = int((cam_y + half_h / self.tile_size) // 32) + 1

        # Uniforms
        self.prog['u_resolution'].value = (screen_w, screen_h)
        self.prog['u_camera'].value = (cam_x, cam_y)
        self.prog['u_tile_size'].value = self.tile_size

        # Render chaque chunk
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                if (cx, cy) not in self._chunk_vbos:
                    vao = self._create_chunk_vao(cx, cy)
                    if vao:
                        self._chunk_vbos[(cx, cy)] = vao

                if (cx, cy) in self._chunk_vbos:
                    self._chunk_vbos[(cx, cy)].render(moderngl.TRIANGLES)

    def _blit_pygame_surface(self, surface: pygame.Surface):
        """Blit une surface pygame sur le contexte GL."""
        data = pygame.image.tostring(surface, 'RGBA', False)
        w, h = surface.get_size()

        if self.pg_texture is None or self.pg_texture.size != (w, h):
            if self.pg_texture:
                self.pg_texture.release()
            self.pg_texture = self.ctx.texture((w, h), 4, data)
            self.pg_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        else:
            self.pg_texture.write(data)

        # Active le blending pour la transparence
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        # Render le quad
        self.pg_texture.use(0)
        self.quad_vao.render(moderngl.TRIANGLES)

        self.ctx.disable(moderngl.BLEND)

    def _render_entities_pg(self, game: 'Game', surface: pygame.Surface):
        """Render les entités sur une surface pygame."""
        for entity in self.world_view.entities.values():
            screen_x, screen_y = self.world_to_screen(entity['x'], entity['y'])

            if not (0 < screen_x < surface.get_width() and 0 < screen_y < surface.get_height()):
                continue

            entity_type = EntityType(entity['type'])
            color = self.ENTITY_COLORS.get(entity_type, (200, 200, 200))

            size = self.tile_size // 3
            rect = pygame.Rect(screen_x - size // 2, screen_y - size // 2, size, size)
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, (255, 255, 255), rect, 1)

    def _render_players_pg(self, game: 'Game', surface: pygame.Surface):
        """Render les joueurs sur une surface pygame."""
        # Autres joueurs
        for player in self.world_view.other_players.values():
            if player['id'] == game.player_id:
                continue

            screen_x, screen_y = self.world_to_screen(player['x'], player['y'])
            pygame.draw.circle(surface, (100, 100, 255), (screen_x, screen_y - 10), 12)
            pygame.draw.circle(surface, (255, 255, 255), (screen_x, screen_y - 10), 12, 2)

            name_surface = self.small_font.render(player['name'], True, (255, 255, 255))
            name_rect = name_surface.get_rect(center=(screen_x, screen_y - 30))
            surface.blit(name_surface, name_rect)

        # Joueur local
        if game.player_id:
            screen_x, screen_y = self.world_to_screen(game.player_x, game.player_y)
            pygame.draw.circle(surface, (50, 205, 50), (screen_x, screen_y - 10), 12)
            pygame.draw.circle(surface, (255, 255, 255), (screen_x, screen_y - 10), 12, 2)

            name_surface = self.small_font.render(game.player_name, True, (255, 255, 255))
            name_rect = name_surface.get_rect(center=(screen_x, screen_y - 30))
            surface.blit(name_surface, name_rect)

    def _render_cursor_pg(self, game: 'Game', surface: pygame.Surface):
        """Render le curseur sur une surface pygame."""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.screen_to_world(mouse_x, mouse_y)

        tile_x = int(world_x)
        tile_y = int(world_y)
        screen_x, screen_y = self.world_to_screen(tile_x, tile_y)

        half = self.tile_size // 2
        rect = pygame.Rect(screen_x - half, screen_y - half, self.tile_size, self.tile_size)

        if game.selected_entity_type is not None:
            pygame.draw.rect(surface, (0, 255, 0), rect, 2)
        else:
            pygame.draw.rect(surface, (255, 255, 255), rect, 1)

    def _render_minimap_pg(self, game: 'Game', surface: pygame.Surface):
        """Render la minimap sur une surface pygame."""
        screen_w = surface.get_width()
        screen_h = surface.get_height()
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
                        color = self.TILE_COLORS.get(TileType(tile_type), (100, 100, 100))

                        mx = (world_tx - start_tx) / tiles_range * minimap_size
                        my = (world_ty - start_ty) / tiles_range * minimap_size

                        pygame.draw.rect(minimap_surface, color,
                                         (mx, my, max(1, tile_pixel + 1), max(1, tile_pixel + 1)))

            pygame.draw.rect(minimap_surface, (255, 255, 255), (0, 0, minimap_size, minimap_size), 1)

            self._minimap_cache = minimap_surface
            self._minimap_cache_key = cache_key

        surface.blit(self._minimap_cache, (minimap_x, minimap_y))

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
                pygame.draw.circle(surface, (100, 100, 255), (int(px), int(py)), 3)

        pygame.draw.circle(surface, (50, 255, 50), (center_px, center_py), 3)

        zoom_text = self.small_font.render(f"{tiles_range}x{tiles_range}", True, (200, 200, 200))
        surface.blit(zoom_text, (minimap_x + 4, minimap_y + minimap_size - 16))

    def _render_debug_pg(self, game: 'Game', surface: pygame.Surface):
        """Render le debug sur une surface pygame."""
        lines = [
            f"FPS: {game.fps:.0f}",
            f"Pos: ({game.player_x:.1f}, {game.player_y:.1f})",
            f"Chunks: {len(self.world_view.chunks)}",
            f"Entities: {len(self.world_view.entities)}",
            f"Players: {len(self.world_view.other_players) + 1}",
            f"Bandwidth: {game.bandwidth} B/s",
            f"GPU Chunks: {len(self._chunk_vbos)}",
        ]

        y = 10
        for line in lines:
            text_surface = self.small_font.render(line, True, (200, 200, 200))
            surface.blit(text_surface, (10, y))
            y += 18