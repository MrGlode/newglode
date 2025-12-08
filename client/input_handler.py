import pygame
from typing import TYPE_CHECKING

from shared.entities import EntityType
from client.audio import get_audio

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

    def handle_event(self, event: pygame.event.Event):
        """Gère un seul événement pygame."""
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

        # Met à jour le mouvement
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
            get_audio().play_select()

        elif key == pygame.K_r:
            self.game.rotate_selection()

        elif key == pygame.K_F3:
            self.game.show_debug = not self.game.show_debug
            get_audio().play_ui_click()

        elif key == pygame.K_ESCAPE:
            if self.game.inventory_ui.visible:
                self.game.inventory_ui.close()
                get_audio().play_ui_click()
            elif self.game.inspected_entity:
                self.game.close_inspection()
            else:
                self.game.selected_entity_type = None
                get_audio().play_ui_click()

        elif key == pygame.K_m:
            # Toggle audio
            enabled = get_audio().toggle_audio()
            print(f"Audio: {'activé' if enabled else 'désactivé'}")

        elif key == pygame.K_i or key == pygame.K_e:
            # Toggle inventaire
            self.game.toggle_inventory()

        elif key == pygame.K_f:
            # Ramasser items proches
            self.game.pickup_items()

        elif key == pygame.K_PLUS or key == pygame.K_KP_PLUS or key == pygame.K_EQUALS:
            # Augmenter volume
            audio = get_audio()
            audio.set_master_volume(audio.master_volume + 0.1)
            print(f"Volume: {int(audio.master_volume * 100)}%")

        elif key == pygame.K_MINUS or key == pygame.K_KP_MINUS:
            # Diminuer volume
            audio = get_audio()
            audio.set_master_volume(audio.master_volume - 0.1)
            print(f"Volume: {int(audio.master_volume * 100)}%")

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
            if direction > 0:
                renderer.minimap_zoom_level = max(0, renderer.minimap_zoom_level - 1)
            else:
                renderer.minimap_zoom_level = min(3, renderer.minimap_zoom_level + 1)
        else:
            # Zoom map principale
            renderer = self.game.renderer
            old_size = renderer.tile_size

            if direction > 0:
                renderer.tile_size = min(64, renderer.tile_size + 4)
            else:
                renderer.tile_size = max(16, renderer.tile_size - 4)

    def handle_keyup(self, key: int):
        pass

    def handle_mousedown(self, button: int):
        # Vérifie d'abord si l'inventaire est ouvert et consomme le clic
        if self.game.inventory_ui.visible:
            mouse_pos = pygame.mouse.get_pos()
            if self.game.inventory_ui.handle_click(mouse_pos, button, self.game):
                return
            # Clic en dehors du panneau = ferme l'inventaire
            if button == 1 or button == 3:
                self.game.inventory_ui.close()
                return

        if button == 1:  # Clic gauche
            # Vérifie si on clique sur un bouton de recette
            if self.game.inspected_entity:
                from shared.entities import EntityType
                entity_type = EntityType(self.game.inspected_entity['type'])

                if entity_type == EntityType.ASSEMBLER:
                    if self.handle_recipe_click():
                        return

                # Vérifie si on clique sur le panneau d'inspection
                if self.is_click_on_inspection_panel():
                    return

                self.game.close_inspection()
                return

            # Essaie d'inspecter une entité existante
            if self.game.inspect_at_cursor():
                return

            # Sinon, construit
            self.game.build_at_cursor()

        elif button == 3:  # Clic droit
            if self.game.inspected_entity:
                self.game.close_inspection()
            else:
                self.game.destroy_at_cursor()

    def handle_recipe_click(self) -> bool:
        """Gère le clic sur un bouton de recette. Retourne True si un bouton a été cliqué."""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        renderer = self.game.renderer

        if not hasattr(renderer, '_recipe_buttons'):
            return False

        for recipe, rect in renderer._recipe_buttons.items():
            if rect.collidepoint(mouse_x, mouse_y):
                # Envoie le changement de recette au serveur
                entity = self.game.inspected_entity
                if entity and self.game.network:
                    self.game.network.send_set_recipe(entity['id'], recipe)
                    get_audio().play_ui_click()
                return True

        return False

    def is_click_on_inspection_panel(self) -> bool:
        """Vérifie si le clic est sur le panneau d'inspection."""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        screen_w = self.game.screen.get_width()
        screen_h = self.game.screen.get_height()

        # Panneau à droite
        panel_width = 250
        panel_height = 300
        panel_x = screen_w - panel_width - 20
        panel_y = (screen_h - panel_height) // 2

        return (panel_x <= mouse_x <= panel_x + panel_width and
                panel_y <= mouse_y <= panel_y + panel_height)

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