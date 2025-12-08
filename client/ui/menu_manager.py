"""
Gestionnaire de menus et machine à états du jeu.
"""

import pygame
from enum import Enum, auto
from typing import Optional, Dict, Any

from client.ui.screens import PauseScreen


class GameState(Enum):
    """États possibles du jeu."""
    TITLE = auto()
    MAIN_MENU = auto()
    CONNECT = auto()
    OPTIONS = auto()
    PLAYING = auto()
    PAUSED = auto()


class MenuManager:
    """Gère les écrans de menu et leurs transitions."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.state = GameState.TITLE
        self.previous_state: Optional[GameState] = None
        self.screens: Dict[GameState, Any] = {}

        # Données partagées entre écrans
        self.shared_data = {
            'host': 'localhost',
            'port': '5555',
            'player_name': '',
            'music_volume': 0.3,
            'sfx_volume': 0.5,
            'fullscreen': False,
        }

        # Transition
        self.transitioning = False
        self.transition_alpha = 0
        self.transition_target: Optional[GameState] = None
        self.transition_speed = 500
        self.transition_phase = 'fade_out'

    def init_screens(self):
        """Initialise tous les écrans."""
        from client.ui.screens import TitleScreen, MainMenuScreen, ConnectScreen, OptionsScreen

        self.screens = {
            GameState.TITLE: TitleScreen(self),
            GameState.MAIN_MENU: MainMenuScreen(self),
            GameState.CONNECT: ConnectScreen(self),
            GameState.OPTIONS: OptionsScreen(self),
            GameState.PAUSED: PauseScreen(self)
        }

    def change_state(self, new_state: GameState, instant: bool = False):
        """Change d'état avec transition optionnelle."""
        if new_state == self.state:
            return

        if instant:
            # Force le changement, annule toute transition en cours
            self.transitioning = False
            self._do_state_change(new_state)
        else:
            # Ignore si une transition est déjà en cours
            if self.transitioning:
                return
            self.transitioning = True
            self.transition_target = new_state
            self.transition_alpha = 0
            self.transition_phase = 'fade_out'

    def _do_state_change(self, new_state: GameState):
        old_screen = self.screens.get(self.state)
        if old_screen and hasattr(old_screen, 'on_exit'):
            old_screen.on_exit()

        self.previous_state = self.state
        self.state = new_state

        new_screen = self.screens.get(new_state)
        if new_screen and hasattr(new_screen, 'on_enter'):
            new_screen.on_enter()

    def go_back(self):
        if self.previous_state:
            self.change_state(self.previous_state)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Gère un événement. Retourne True si on reste dans les menus."""
        if self.state == GameState.PLAYING:
            return False

        # Bloque les events pendant une transition
        if self.transitioning:
            return True

        screen = self.screens.get(self.state)
        if screen:
            screen.handle_event(event)

        return True

    def update(self, dt: float):
        if self.transitioning:
            if self.transition_phase == 'fade_out':
                # Phase 1 : fondu vers noir
                self.transition_alpha += self.transition_speed * dt
                if self.transition_alpha >= 255:
                    self.transition_alpha = 255
                    self._do_state_change(self.transition_target)
                    self.transition_phase = 'fade_in'
            else:
                # Phase 2 : fondu depuis noir
                self.transition_alpha -= self.transition_speed * dt
                if self.transition_alpha <= 0:
                    self.transition_alpha = 0
                    self.transitioning = False
                    self.transition_target = None

        if self.state != GameState.PLAYING:
            screen = self.screens.get(self.state)
            if screen:
                screen.update(dt)

    def render(self):
        if self.state == GameState.PLAYING:
            return

        screen = self.screens.get(self.state)
        if screen:
            screen.render(self.screen)

        if self.transitioning and self.transition_alpha > 0:
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((20, 22, 30, int(self.transition_alpha)))
            self.screen.blit(overlay, (0, 0))

    def is_in_menu(self) -> bool:
        return self.state != GameState.PLAYING

    def get_connection_info(self) -> tuple:
        """Retourne (host, port, name)."""
        return (
            self.shared_data['host'],
            int(self.shared_data['port']),
            self.shared_data['player_name']
        )

    def set_option(self, key: str, value: Any):
        self.shared_data[key] = value

    def get_option(self, key: str, default: Any = None) -> Any:
        return self.shared_data.get(key, default)