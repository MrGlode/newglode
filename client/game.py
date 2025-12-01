import math
import random

import pygame
import time
from typing import Optional

from client.network import NetworkClient
from client.renderer import Renderer
from client.input_handler import InputHandler
from client.world_view import WorldView
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
        self.inspected_entity = None  # Entité actuellement inspectée

        # Debug
        self.show_debug = True
        self.fps = 0
        self.bandwidth = 0

    def connect(self, host: str = 'localhost', port: int = 5555, name: str = "Player"):
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

    def on_authenticated(self, player_id: int, x: float, y: float):
        self.player_id = player_id
        self.player_x = x
        self.player_y = y
        self.connected = True
        self.connecting = False
        print(f"Connecté en tant que joueur {player_id} à ({x}, {y})")

    def on_disconnected(self):
        self.connected = False
        self.connecting = False
        self.player_id = None
        print("Déconnecté du serveur")

    def run(self):
        last_time = time.perf_counter()
        last_move_sync = time.perf_counter()
        last_position = (None, None)

        name = 'TestPlayer' + str(random.randint(0, 10))

        # Connexion automatique pour test
        self.connect('localhost', 5555, name)

        while self.running:
            current_time = time.perf_counter()
            dt = current_time - last_time
            last_time = current_time

            # Events
            self.input_handler.handle_events()

            # Update
            if self.connected:
                self.update(dt)

                # Sync position avec le serveur (toutes les 50ms ou si changement)
                current_pos = (round(self.player_x, 2), round(self.player_y, 2))
                if current_time - last_move_sync > 0.05:  # 20 Hz
                    if self.network and current_pos != last_position:
                        self.network.send_move(self.player_x, self.player_y)
                        last_position = current_pos
                    last_move_sync = current_time

            # Network
            if self.network:
                self.network.receive()
                self.bandwidth = self.network.bandwidth

            # Render
            self.renderer.render(self)

            # FPS
            self.fps = self.clock.get_fps()
            self.clock.tick(240)

    def update(self, dt: float):
        from shared.constants import PLAYER_SPEED

        # Mouvement joueur
        if self.velocity_x != 0 or self.velocity_y != 0:
            # Normalise la diagonale
            if self.velocity_x != 0 and self.velocity_y != 0:
                factor = 0.7071  # 1/sqrt(2)
                self.player_x += self.velocity_x * PLAYER_SPEED * dt * factor
                self.player_y += self.velocity_y * PLAYER_SPEED * dt * factor
            else:
                self.player_x += self.velocity_x * PLAYER_SPEED * dt
                self.player_y += self.velocity_y * PLAYER_SPEED * dt

        # Met à jour la caméra
        self.world_view.camera_x = self.player_x
        self.world_view.camera_y = self.player_y

        # Interpole les autres joueurs
        self.world_view.update_players_interpolation(dt)

        # Demande les chunks manquants
        if self.network:
            needed = self.world_view.get_visible_chunks(self.screen.get_width(), self.screen.get_height())
            for cx, cy in needed:
                if (cx, cy) not in self.world_view.chunks and (cx, cy) not in self.world_view.pending_chunks:
                    self.network.request_chunk(cx, cy)
                    self.world_view.pending_chunks.add((cx, cy))

    def set_velocity(self, vx: float, vy: float):
        self.velocity_x = vx
        self.velocity_y = vy

    def build_at_cursor(self):
        import math

        if not self.connected or self.selected_entity_type is None:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.renderer.screen_to_world(mouse_x, mouse_y)

        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)

        if self.network:
            self.network.send_build(tile_x, tile_y, self.selected_entity_type, self.selected_direction)

    def destroy_at_cursor(self):
        import math

        if not self.connected:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.renderer.screen_to_world(mouse_x, mouse_y)

        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)

        # Trouve l'entité à cette position
        entity = self.world_view.get_entity_at(tile_x, tile_y)
        if entity and self.network:
            self.network.send_destroy(entity['id'])

    def rotate_selection(self):
        self.selected_direction = (self.selected_direction + 1) % 4

    def cleanup(self):
        if self.network:
            self.network.disconnect()

    def inspect_at_cursor(self):
        """Inspecte l'entité sous le curseur."""
        import math

        if not self.connected:
            return False

        mouse_x, mouse_y = pygame.mouse.get_pos()
        world_x, world_y = self.renderer.screen_to_world(mouse_x, mouse_y)

        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)

        entity = self.world_view.get_entity_at(tile_x, tile_y)
        if entity:
            self.inspected_entity = entity
            return True

        return False

    def close_inspection(self):
        """Ferme l'interface d'inspection."""
        self.inspected_entity = None