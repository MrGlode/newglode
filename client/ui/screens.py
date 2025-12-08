"""
Écrans de menu du jeu.
Titre, Menu principal, Connexion, Options.
"""

import pygame
import math
import random
from typing import TYPE_CHECKING, List

from client.ui.widgets import Button, TextInput, Slider, Label, Checkbox, Colors

if TYPE_CHECKING:
    from client.ui.menu_manager import MenuManager, GameState


class BaseScreen:
    """Classe de base pour tous les écrans."""

    def __init__(self, manager: 'MenuManager'):
        self.manager = manager
        self.widgets = []

    def on_enter(self):
        """Appelé quand on entre dans cet écran."""
        pass

    def on_exit(self):
        """Appelé quand on quitte cet écran."""
        pass

    def handle_event(self, event: pygame.event.Event):
        """Gère les événements."""
        for widget in self.widgets:
            if widget.handle_event(event):
                break

    def update(self, dt: float):
        """Met à jour l'écran."""
        for widget in self.widgets:
            widget.update(dt)

    def render(self, screen: pygame.Surface):
        """Affiche l'écran."""
        screen.fill(Colors.BG_DARK)
        for widget in self.widgets:
            widget.render(screen)

    def rebuild_layout(self, screen_width: int, screen_height: int):
        """Reconstruit le layout pour la taille d'écran donnée."""
        pass


class TitleScreen(BaseScreen):
    """Écran titre avec animation."""

    def __init__(self, manager: 'MenuManager'):
        super().__init__(manager)

        self.title_font = pygame.font.Font(None, 120)
        self.subtitle_font = pygame.font.Font(None, 36)
        self.prompt_font = pygame.font.Font(None, 28)

        # Animation
        self.time = 0.0
        self.prompt_alpha = 255
        self.prompt_fade_dir = -1

        # Particules de fond
        self.particles = []
        self._init_particles()

    def _init_particles(self):
        """Crée les particules de fond."""
        for _ in range(50):
            self.particles.append({
                'x': random.random(),
                'y': random.random(),
                'size': random.uniform(1, 3),
                'speed': random.uniform(0.01, 0.03),
                'alpha': random.randint(30, 100)
            })

    def on_enter(self):
        self.time = 0.0

    def handle_event(self, event: pygame.event.Event):
        # N'importe quelle touche ou clic -> menu principal
        if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
            from client.ui.menu_manager import GameState
            self.manager.change_state(GameState.MAIN_MENU)

    def update(self, dt: float):
        self.time += dt

        # Animation du prompt
        self.prompt_alpha += self.prompt_fade_dir * 200 * dt
        if self.prompt_alpha <= 50:
            self.prompt_fade_dir = 1
        elif self.prompt_alpha >= 255:
            self.prompt_fade_dir = -1
        self.prompt_alpha = max(50, min(255, self.prompt_alpha))

        # Particules
        for p in self.particles:
            p['y'] -= p['speed'] * dt
            if p['y'] < 0:
                p['y'] = 1.0
                p['x'] = random.random()

    def render(self, screen: pygame.Surface):
        screen.fill(Colors.BG_DARK)

        sw, sh = screen.get_size()

        # Particules
        for p in self.particles:
            x = int(p['x'] * sw)
            y = int(p['y'] * sh)
            color = (Colors.PRIMARY[0], Colors.PRIMARY[1], Colors.PRIMARY[2], p['alpha'])
            pygame.draw.circle(screen, (color[0], color[1], color[2]), (x, y), int(p['size']))

        # Titre avec effet de vague
        title_text = "FACTORIO-LIKE"
        title_y = sh // 3

        # Ombre
        shadow_surface = self.title_font.render(title_text, True, (0, 0, 0))
        shadow_rect = shadow_surface.get_rect(center=(sw // 2 + 4, title_y + 4))
        screen.blit(shadow_surface, shadow_rect)

        # Titre principal avec couleur
        title_surface = self.title_font.render(title_text, True, Colors.PRIMARY)
        title_rect = title_surface.get_rect(center=(sw // 2, title_y))
        screen.blit(title_surface, title_rect)

        # Sous-titre
        subtitle_text = "Industrial Automation Game"
        subtitle_surface = self.subtitle_font.render(subtitle_text, True, Colors.TEXT_DIM)
        subtitle_rect = subtitle_surface.get_rect(center=(sw // 2, title_y + 70))
        screen.blit(subtitle_surface, subtitle_rect)

        # Ligne décorative
        line_width = 300
        line_y = title_y + 110
        pygame.draw.line(screen, Colors.PRIMARY_DARK,
                         (sw // 2 - line_width // 2, line_y),
                         (sw // 2 + line_width // 2, line_y), 2)

        # Prompt "Press any key"
        prompt_text = "Appuyez sur une touche pour continuer"
        prompt_surface = self.prompt_font.render(prompt_text, True, Colors.TEXT)
        prompt_surface.set_alpha(int(self.prompt_alpha))
        prompt_rect = prompt_surface.get_rect(center=(sw // 2, sh * 2 // 3))
        screen.blit(prompt_surface, prompt_rect)

        # Version
        version_text = "v0.1.0 - Alpha"
        version_surface = self.prompt_font.render(version_text, True, Colors.TEXT_DARK)
        screen.blit(version_surface, (10, sh - 30))


class MainMenuScreen(BaseScreen):
    """Menu principal."""

    def __init__(self, manager: 'MenuManager'):
        super().__init__(manager)

        self.title_font = pygame.font.Font(None, 72)

        # Les boutons seront créés dans rebuild_layout
        self.btn_play = None
        self.btn_options = None
        self.btn_quit = None

    def on_enter(self):
        # Rebuild au cas où la taille a changé
        screen = self.manager.screen
        self.rebuild_layout(screen.get_width(), screen.get_height())

    def rebuild_layout(self, sw: int, sh: int):
        self.widgets.clear()

        btn_width = 280
        btn_height = 50
        btn_spacing = 20

        center_x = sw // 2 - btn_width // 2
        start_y = sh // 2 - 50

        from client.ui.menu_manager import GameState

        self.btn_play = Button(
            center_x, start_y,
            btn_width, btn_height,
            "Jouer",
            lambda: self.manager.change_state(GameState.CONNECT)
        )

        self.btn_options = Button(
            center_x, start_y + btn_height + btn_spacing,
            btn_width, btn_height,
            "Options",
            lambda: self.manager.change_state(GameState.OPTIONS)
        )

        self.btn_quit = Button(
            center_x, start_y + (btn_height + btn_spacing) * 2,
            btn_width, btn_height,
            "Quitter",
            self._on_quit
        )

        self.widgets = [self.btn_play, self.btn_options, self.btn_quit]

    def _on_quit(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def handle_event(self, event: pygame.event.Event):
        super().handle_event(event)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                from client.ui.menu_manager import GameState
                self.manager.change_state(GameState.TITLE)

        elif event.type == pygame.VIDEORESIZE:
            self.rebuild_layout(event.w, event.h)

    def render(self, screen: pygame.Surface):
        screen.fill(Colors.BG_DARK)

        sw, sh = screen.get_size()

        # Titre
        title_surface = self.title_font.render("FACTORIO-LIKE", True, Colors.PRIMARY)
        title_rect = title_surface.get_rect(center=(sw // 2, sh // 4))
        screen.blit(title_surface, title_rect)

        # Widgets
        for widget in self.widgets:
            widget.render(screen)


class ConnectScreen(BaseScreen):
    """Écran de connexion au serveur."""

    def __init__(self, manager: 'MenuManager'):
        super().__init__(manager)
        self.title_font = pygame.font.Font(None, 48)
        self.label_font = pygame.font.Font(None, 24)
        self.input_host = None
        self.input_port = None
        self.input_name = None
        self.error_message = ""
        self.error_timer = 0.0

    def on_enter(self):
        screen = self.manager.screen
        self._rebuild_layout(screen.get_width(), screen.get_height())
        self.input_host.set_text(self.manager.get_option('host', 'localhost'))
        self.input_port.set_text(self.manager.get_option('port', '5555'))
        self.input_name.set_text(self.manager.get_option('player_name', ''))
        self.error_message = ""

    def _rebuild_layout(self, sw: int, sh: int):
        self.widgets.clear()

        panel_width = 400
        panel_x = sw // 2 - panel_width // 2
        input_width = panel_width - 40
        spacing = 80
        start_y = sh // 3

        self.input_host = TextInput(panel_x + 20, start_y, input_width, 40, placeholder="localhost")
        self.input_port = TextInput(panel_x + 20, start_y + spacing, input_width, 40, placeholder="5555", max_length=5)
        self.input_name = TextInput(panel_x + 20, start_y + spacing * 2, input_width, 40, placeholder="Votre pseudo",
                                    max_length=20)

        btn_width = 150
        btn_y = start_y + spacing * 3 + 20

        # Boutons EN PREMIER pour qu'ils reçoivent les clics avant les TextInputs
        self.widgets = [
            Button(sw // 2 - btn_width - 10, btn_y, btn_width, 45, "Connexion", self._on_connect),
            Button(sw // 2 + 10, btn_y, btn_width, 45, "Retour", self._on_back),
            self.input_host, self.input_port, self.input_name,
        ]

    def _on_connect(self):
        host = self.input_host.get_text().strip() or 'localhost'
        port_str = self.input_port.get_text().strip() or '5555'
        name = self.input_name.get_text().strip()

        if not name:
            self.error_message = "Veuillez entrer un pseudo"
            self.error_timer = 3.0
            return

        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError()
        except ValueError:
            self.error_message = "Port invalide (1-65535)"
            self.error_timer = 3.0
            return

        self.manager.set_option('host', host)
        self.manager.set_option('port', port_str)
        self.manager.set_option('player_name', name)

        from client.ui.menu_manager import GameState
        self.manager.change_state(GameState.PLAYING)

    def _on_back(self):
        from client.ui.menu_manager import GameState
        self.manager.change_state(GameState.MAIN_MENU)

    def handle_event(self, event: pygame.event.Event):
        super().handle_event(event)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._on_back()
            elif event.key == pygame.K_RETURN:
                self._on_connect()
            elif event.key == pygame.K_TAB:
                inputs = [self.input_host, self.input_port, self.input_name]
                focused_idx = -1
                for i, inp in enumerate(inputs):
                    if inp.focused:
                        focused_idx = i
                        inp.focused = False
                        break
                inputs[(focused_idx + 1) % len(inputs)].focused = True
        elif event.type == pygame.VIDEORESIZE:
            self._rebuild_layout(event.w, event.h)

    def update(self, dt: float):
        super().update(dt)
        if self.error_timer > 0:
            self.error_timer -= dt
            if self.error_timer <= 0:
                self.error_message = ""

    def render(self, screen: pygame.Surface):
        screen.fill(Colors.BG_DARK)
        sw, sh = screen.get_size()

        title = self.title_font.render("Connexion au serveur", True, Colors.TEXT)
        screen.blit(title, title.get_rect(center=(sw // 2, sh // 5)))

        panel_x = sw // 2 - 200
        start_y = sh // 3
        spacing = 80  # Corrigé

        for text, y in [("Adresse du serveur", start_y - 25), ("Port", start_y + spacing - 25), ("Pseudo", start_y + spacing * 2 - 25)]:
            label = self.label_font.render(text, True, Colors.TEXT_DIM)
            screen.blit(label, (panel_x + 20, y))

        for widget in self.widgets:
            widget.render(screen)

        if self.error_message:
            error = self.label_font.render(self.error_message, True, Colors.ERROR)
            screen.blit(error, error.get_rect(center=(sw // 2, start_y + spacing * 3 + 80)))


class OptionsScreen(BaseScreen):
    """Écran des options."""

    def __init__(self, manager: 'MenuManager'):
        super().__init__(manager)
        self.title_font = pygame.font.Font(None, 48)
        self.label_font = pygame.font.Font(None, 24)
        self.slider_music = None
        self.slider_sfx = None
        self.checkbox_fullscreen = None

    def on_enter(self):
        screen = self.manager.screen
        self._rebuild_layout(screen.get_width(), screen.get_height())

        try:
            from client.audio import get_audio
            audio = get_audio()
            self.slider_music.set_value(audio.music_volume)
            self.slider_sfx.set_value(audio.sfx_volume)
        except:
            self.slider_music.set_value(0.3)
            self.slider_sfx.set_value(0.5)

        flags = pygame.display.get_surface().get_flags()
        self.checkbox_fullscreen.set_checked(bool(flags & pygame.FULLSCREEN))

    def _rebuild_layout(self, sw: int, sh: int):
        self.widgets.clear()

        panel_x = sw // 2 - 250
        spacing = 80
        start_y = sh // 3

        self.slider_music = Slider(panel_x + 150, start_y, 300, 30, 0.0, 1.0, 0.3, self._on_music_change)
        self.slider_sfx = Slider(panel_x + 150, start_y + spacing, 300, 30, 0.0, 1.0, 0.5, self._on_sfx_change)
        self.checkbox_fullscreen = Checkbox(panel_x + 20, start_y + spacing * 2, "Plein écran", False, self._on_fullscreen_change)

        self.widgets = [
            self.slider_music, self.slider_sfx, self.checkbox_fullscreen,
            Button(sw // 2 - 75, start_y + spacing * 3 + 30, 150, 45, "Retour", self._on_back),
        ]

    def _on_music_change(self, value: float):
        try:
            from client.audio import get_audio
            get_audio().set_music_volume(value)
        except:
            pass
        self.manager.set_option('music_volume', value)

    def _on_sfx_change(self, value: float):
        try:
            from client.audio import get_audio
            audio = get_audio()
            audio.set_sfx_volume(value)
            audio.play_ui_click()
        except:
            pass
        self.manager.set_option('sfx_volume', value)

    def _on_fullscreen_change(self, checked: bool):
        screen = pygame.display.get_surface()
        sw, sh = screen.get_size()

        if checked:
            pygame.display.set_mode((sw, sh), pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF)
        else:
            pygame.display.set_mode((1280, 720), pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF)

        self.manager.set_option('fullscreen', checked)
        new_screen = pygame.display.get_surface()
        self._rebuild_layout(new_screen.get_width(), new_screen.get_height())

    def _on_back(self):
        from client.ui.menu_manager import GameState
        # Retourne à l'écran précédent (MAIN_MENU ou PAUSED)
        if self.manager.previous_state:
            self.manager.change_state(self.manager.previous_state)
        else:
            self.manager.change_state(GameState.MAIN_MENU)

    def handle_event(self, event: pygame.event.Event):
        super().handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._on_back()
        elif event.type == pygame.VIDEORESIZE:
            self._rebuild_layout(event.w, event.h)

    def render(self, screen: pygame.Surface):
        screen.fill(Colors.BG_DARK)
        sw, sh = screen.get_size()
        panel_x = sw // 2 - 250
        start_y = sh // 3
        spacing = 80

        title = self.title_font.render("Options", True, Colors.TEXT)
        screen.blit(title, title.get_rect(center=(sw // 2, sh // 5)))

        for text, y in [("Volume Musique", start_y + 5), ("Volume Effets", start_y + spacing + 5)]:
            label = self.label_font.render(text, True, Colors.TEXT_DIM)
            screen.blit(label, (panel_x + 20, y))

        screen.blit(self.label_font.render(f"{int(self.slider_music.get_value() * 100)}%", True, Colors.TEXT), (panel_x + 470, start_y + 5))
        screen.blit(self.label_font.render(f"{int(self.slider_sfx.get_value() * 100)}%", True, Colors.TEXT), (panel_x + 470, start_y + spacing + 5))

        for widget in self.widgets:
            widget.render(screen)

        hint = self.label_font.render("Les options sont sauvegardées automatiquement", True, Colors.TEXT_DARK)
        screen.blit(hint, hint.get_rect(center=(sw // 2, sh - 50)))


class PauseScreen(BaseScreen):
    """Menu pause en jeu."""

    def __init__(self, manager: 'MenuManager'):
        super().__init__(manager)
        self.title_font = pygame.font.Font(None, 72)
        self.overlay = None
        self.game_screenshot = None

    def set_game_screenshot(self, screenshot: pygame.Surface):
        """Capture l'écran du jeu pour l'afficher en fond."""
        self.game_screenshot = screenshot.copy()

    def on_enter(self):
        screen = self.manager.screen
        self._rebuild_layout(screen.get_width(), screen.get_height())

    def _rebuild_layout(self, sw: int, sh: int):
        self.widgets.clear()

        self.overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 180))

        btn_width, btn_height, btn_spacing = 280, 50, 20
        center_x = sw // 2 - btn_width // 2
        start_y = sh // 2 - 50

        from client.ui.menu_manager import GameState

        self.widgets = [
            Button(center_x, start_y, btn_width, btn_height, "Reprendre",
                   lambda: self.manager.change_state(GameState.PLAYING, instant=True)),
            Button(center_x, start_y + btn_height + btn_spacing, btn_width, btn_height, "Options",
                   lambda: self.manager.change_state(GameState.OPTIONS)),
            Button(center_x, start_y + (btn_height + btn_spacing) * 2, btn_width, btn_height, "Déconnexion",
                   self._on_disconnect),
        ]

    def _on_disconnect(self):
        self.manager.set_option('disconnect_requested', True)
        from client.ui.menu_manager import GameState
        self.manager.change_state(GameState.MAIN_MENU, instant=True)

    def handle_event(self, event: pygame.event.Event):
        super().handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            from client.ui.menu_manager import GameState
            self.manager.change_state(GameState.PLAYING, instant=True)
        elif event.type == pygame.VIDEORESIZE:
            self._rebuild_layout(event.w, event.h)

    def render(self, screen: pygame.Surface):
        # Affiche la capture du jeu en fond
        if self.game_screenshot:
            screen.blit(self.game_screenshot, (0, 0))

        # Overlay semi-transparent
        if self.overlay:
            screen.blit(self.overlay, (0, 0))

        sw, sh = screen.get_size()

        title = self.title_font.render("PAUSE", True, Colors.PRIMARY)
        screen.blit(title, title.get_rect(center=(sw // 2, sh // 4)))

        for widget in self.widgets:
            widget.render(screen)