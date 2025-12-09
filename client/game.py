"""
Logique principale du jeu Factorio-like.
Gère l'état du joueur, la connexion réseau et la boucle de jeu.
"""

import random
import math
import pygame
import time
from typing import Optional

from client.network import NetworkClient
from client.renderer import Renderer
from client.input_handler import InputHandler
from client.world_view import WorldView
from client.audio import get_audio
from client.inventory import InventoryUI
from shared.constants import WORLD_TICK_INTERVAL


class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.running = True

        # Composants
        self.network: Optional[NetworkClient] = None
        self.world_view = WorldView()
        self.renderer = Renderer(screen, self.world_view)
        self.input_handler = InputHandler(self)
        self.inventory_ui = InventoryUI()

        # État joueur
        self.player_id: Optional[int] = None
        self.player_x = 0.0
        self.player_y = 0.0
        self.player_name = "Player"

        # Mouvement
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        # UI State
        self.connected = False
        self.connecting = False
        self.selected_entity_type = None
        self.selected_direction = 0
        self.inspected_entity = None

        # Debug
        self.show_debug = True
        self.fps = 0
        self.bandwidth = 0

        # Sync
        self.last_move_sync = time.perf_counter()
        self.last_position = (None, None)

    def connect(self, host: str = 'localhost', port: int = 5555, name: str = "Player"):
        """Connecte au serveur."""
        self.player_name = name
        self.connecting = True

        try:
            self.network = NetworkClient(self, host, port)
            self.network.connect()
            self.network.authenticate(name)
        except Exception as e:
            print(f"Erreur de connexion: {e}")
            self.connecting = False
            self.network = None
            raise

    def on_authenticated(self, player_id: int, x: float, y: float):
        """Callback appelé quand l'authentification réussit."""
        self.player_id = player_id
        self.player_x = x
        self.player_y = y
        self.connected = True
        self.connecting = False
        print(f"Connecté en tant que joueur {player_id} à ({x}, {y})")

    def on_disconnected(self):
        """Callback appelé lors de la déconnexion."""
        self.connected = False
        self.connecting = False
        self.player_id = None
        print("Déconnecté du serveur")

    def on_inventory_update(self, data: dict):
        """Reçoit la mise à jour de l'inventaire depuis le serveur."""
        slots = data.get('slots', [])
        self.inventory_ui.update_slots(slots)

    def run(self):
        """Boucle principale autonome (pour usage sans menus)."""
        last_time = time.perf_counter()

        name = 'TestPlayer' + str(random.randint(0, 10))
        self.connect('localhost', 5555, name)

        while self.running:
            current_time = time.perf_counter()
            dt = current_time - last_time
            last_time = current_time

            # Events
            self.input_handler.handle_events()

            # Update
            if self.connected:
                self.update_single(dt)

            # Network
            if self.network:
                self.network.receive()
                self.bandwidth = self.network.bandwidth

            # Render
            self.renderer.render(self)

            # Hotbar inventaire
            self.inventory_ui.render_hotbar(self.screen, self)

            if self.inspected_entity:
                self.renderer.render_inspection_panel(self)

            # Inventaire complet
            self.inventory_ui.render(self.screen, self)

            if self.show_debug:
                self.renderer.render_debug(self)

            pygame.display.flip()

            # FPS
            self.clock.tick(240)

    def update_single(self, dt: float):
        """Met à jour le jeu pour un frame (appelé par main.py)."""
        from shared.constants import PLAYER_SPEED

        current_time = time.perf_counter()

        # Mouvement joueur avec collision circulaire
        if self.velocity_x != 0 or self.velocity_y != 0:
            # Calcule la nouvelle position
            if self.velocity_x != 0 and self.velocity_y != 0:
                factor = 0.7071  # 1/sqrt(2)
                new_x = self.player_x + self.velocity_x * PLAYER_SPEED * dt * factor
                new_y = self.player_y + self.velocity_y * PLAYER_SPEED * dt * factor
            else:
                new_x = self.player_x + self.velocity_x * PLAYER_SPEED * dt
                new_y = self.player_y + self.velocity_y * PLAYER_SPEED * dt

            # Hitbox circulaire
            radius = 0.4

            # Fonction helper pour convertir une coordonnée monde en coordonnée tile
            def to_tile(coord):
                return int(math.floor(coord))

            # Fonction helper pour tester si une position est valide
            # Teste 12 points sur le cercle + le centre
            def can_be_at(px, py):
                # Test centre
                if not self.is_tile_walkable(to_tile(px), to_tile(py)):
                    return False
                # Test 12 points sur le périmètre
                for i in range(12):
                    angle = i * (360 / 12)
                    rad = math.radians(angle)
                    test_x = px + radius * math.cos(rad)
                    test_y = py + radius * math.sin(rad)
                    if not self.is_tile_walkable(to_tile(test_x), to_tile(test_y)):
                        return False
                return True

            # Test mouvement complet
            if can_be_at(new_x, new_y):
                self.player_x = new_x
                self.player_y = new_y
            else:
                # Essaie les axes séparément (glissement)
                if self.velocity_x != 0 and can_be_at(new_x, self.player_y):
                    self.player_x = new_x
                if self.velocity_y != 0 and can_be_at(self.player_x, new_y):
                    self.player_y = new_y

        # Met à jour la caméra
        self.world_view.camera_x = self.player_x
        self.world_view.camera_y = self.player_y

        # Interpole les autres joueurs
        self.world_view.update_players_interpolation(dt)

        # Sync position avec le serveur (toutes les 50ms ou si changement)
        current_pos = (round(self.player_x, 2), round(self.player_y, 2))
        if current_time - self.last_move_sync > 0.05:  # 20 Hz
            if self.network and current_pos != self.last_position:
                self.network.send_move(self.player_x, self.player_y)
                self.last_position = current_pos
            self.last_move_sync = current_time

        # Demande les chunks manquants
        if self.network:
            needed = self.world_view.get_visible_chunks(self.screen.get_width(), self.screen.get_height())
            for cx, cy in needed:
                if (cx, cy) not in self.world_view.chunks and (cx, cy) not in self.world_view.pending_chunks:
                    self.network.request_chunk(cx, cy)
                    self.world_view.pending_chunks.add((cx, cy))

        # Met à jour les sons des machines
        audio = get_audio()
        audio.update_machine_sounds(
            self.world_view.entities,
            self.player_x,
            self.player_y
        )

    def is_tile_walkable(self, x: int, y: int) -> bool:
        """Vérifie si une tile est traversable."""
        from admin.config import get_config
        from shared.constants import CHUNK_SIZE

        # Calcul correct du chunk avec math.floor
        cx = math.floor(x / CHUNK_SIZE)
        cy = math.floor(y / CHUNK_SIZE)

        # Si le chunk n'est pas chargé, on autorise le mouvement
        if (cx, cy) not in self.world_view.chunks:
            return True

        config = get_config()
        tile_type = self.world_view.get_tile(x, y)
        tile_config = config.tiles.get(tile_type)

        if tile_config:
            return tile_config.walkable

        # Par défaut, walkable si tile inconnue
        return True

    def set_velocity(self, vx: float, vy: float):
        """Définit la vélocité du joueur."""
        self.velocity_x = vx
        self.velocity_y = vy

    def inspect_at_cursor(self):
        """Inspecte l'entité sous le curseur."""
        if not self.connected:
            return False

        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.renderer.screen_to_world(mouse_x, mouse_y)

        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)

        entity = self.world_view.get_entity_at(tile_x, tile_y)
        if entity:
            self.inspected_entity = entity
            get_audio().play_ui_click()
            return True

        return False

    def close_inspection(self):
        """Ferme l'interface d'inspection."""
        self.inspected_entity = None
        get_audio().play_ui_click()

    def build_at_cursor(self):
        """Construit une entité à la position du curseur."""
        if not self.connected or self.selected_entity_type is None:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.renderer.screen_to_world(mouse_x, mouse_y)

        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)

        if self.network:
            self.network.send_build(tile_x, tile_y, self.selected_entity_type, self.selected_direction)
            get_audio().play_build()

    def destroy_at_cursor(self):
        """Détruit l'entité à la position du curseur."""
        if not self.connected:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.renderer.screen_to_world(mouse_x, mouse_y)

        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)

        entity = self.world_view.get_entity_at(tile_x, tile_y)
        if entity and self.network:
            self.network.send_destroy(entity['id'])
            get_audio().play_destroy()

    def rotate_selection(self):
        """Tourne la sélection de 90 degrés."""
        self.selected_direction = (self.selected_direction + 1) % 4
        get_audio().play_ui_click()

    def toggle_inventory(self):
        """Ouvre/ferme l'inventaire."""
        self.inventory_ui.toggle()
        get_audio().play_ui_click()

    def pickup_items(self):
        """Ramasse les items proches."""
        if not self.connected or not self.network:
            return

        self.network.send_inventory_pickup(int(self.player_x), int(self.player_y))
        get_audio().play_ui_click()

    def transfer_to_entity(self, entity_id: int, item: str, count: int = 1):
        """Transfère des items vers une entité."""
        if self.network:
            self.network.send_inventory_transfer_to(entity_id, item, count)

    def transfer_from_entity(self, entity_id: int, item: str, count: int = 1):
        """Transfère des items depuis une entité."""
        if self.network:
            self.network.send_inventory_transfer_from(entity_id, item, count)

    def cleanup(self):
        """Nettoie les ressources."""
        if self.network:
            self.network.disconnect()