import pygame
from typing import TYPE_CHECKING

from shared.entities import EntityType

if TYPE_CHECKING:
    from client.game import Game


class InputHandler:
    def __init__(self, game: 'Game'):
        self.game = game

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game.running = False

            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)

            elif event.type == pygame.KEYUP:
                self.handle_keyup(event.key)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mousedown(event.button)

            elif event.type == pygame.MOUSEWHEEL:
                self.handle_mousewheel(event.y)

        # Mouvement continu
        self.update_movement()

    def handle_keydown(self, key: int):
        # Sélection d'entité
        entity_keys = {
            pygame.K_1: EntityType.CONVEYOR,
            pygame.K_2: EntityType.MINER,
            pygame.K_3: EntityType.FURNACE,
            pygame.K_4: EntityType.ASSEMBLER,
            pygame.K_5: EntityType.CHEST,
            pygame.K_6: EntityType.INSERTER,
        }

        if key in entity_keys:
            current = self.game.selected_entity_type
            new = entity_keys[key]
            # Toggle si même touche
            self.game.selected_entity_type = None if current == new else new

        elif key == pygame.K_r:
            self.game.rotate_selection()

        elif key == pygame.K_F3:
            self.game.show_debug = not self.game.show_debug

        elif key == pygame.K_ESCAPE:
            self.game.selected_entity_type = None

    def handle_mousewheel(self, direction: int):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        screen_w = self.game.screen.get_width()
        screen_h = self.game.screen.get_height()
        minimap_size = int(min(screen_w, screen_h) * 0.15)
        margin = 10

        # Vérifie si la souris est sur la minimap
        minimap_x = screen_w - minimap_size - margin
        minimap_y = margin

        if minimap_x <= mouse_x <= minimap_x + minimap_size and minimap_y <= mouse_y <= minimap_y + minimap_size:
            # Zoom minimap
            renderer = self.game.renderer
            if direction > 0:  # Scroll up = zoom in (moins de tiles)
                renderer.minimap_zoom_level = max(0, renderer.minimap_zoom_level - 1)
            else:  # Scroll down = zoom out (plus de tiles)
                renderer.minimap_zoom_level = min(3, renderer.minimap_zoom_level + 1)

    def handle_keyup(self, key: int):
        pass

    def handle_mousedown(self, button: int):
        if button == 1:  # Clic gauche
            self.game.build_at_cursor()
        elif button == 3:  # Clic droit
            self.game.destroy_at_cursor()

    def update_movement(self):
        keys = pygame.key.get_pressed()

        vx = 0
        vy = 0

        if keys[pygame.K_z] or keys[pygame.K_UP]:
            vy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            vy += 1
        if keys[pygame.K_q] or keys[pygame.K_LEFT]:
            vx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            vx += 1

        self.game.set_velocity(vx, vy)