"""
Widgets UI réutilisables pour les menus.
Boutons, champs texte, sliders, labels.
"""

import pygame
from typing import Callable, Optional, Tuple


class Colors:
    """Palette de couleurs du jeu."""
    BG_DARK = (20, 22, 30)
    BG_PANEL = (35, 38, 48)
    BG_HOVER = (50, 55, 70)
    BG_ACTIVE = (60, 65, 85)

    PRIMARY = (255, 160, 50)      # Orange Factorio
    PRIMARY_HOVER = (255, 180, 80)
    PRIMARY_DARK = (200, 120, 30)

    TEXT = (240, 240, 240)
    TEXT_DIM = (150, 150, 160)
    TEXT_DARK = (100, 100, 110)

    SUCCESS = (80, 200, 80)
    ERROR = (200, 80, 80)

    BORDER = (80, 85, 100)
    BORDER_FOCUS = (255, 160, 50)


class Widget:
    """Classe de base pour tous les widgets."""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.rect = pygame.Rect(x, y, width, height)
        self.visible = True
        self.enabled = True
        self.focused = False
        self.hovered = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        return False

    def update(self, dt: float):
        pass

    def render(self, screen: pygame.Surface):
        pass

    def center_x(self, screen_width: int):
        self.rect.x = (screen_width - self.rect.width) // 2


class Label(Widget):
    """Label de texte simple."""

    def __init__(self, x: int, y: int, text: str, font_size: int = 24,
                 color: Tuple[int, int, int] = Colors.TEXT, centered: bool = False):
        self.font = pygame.font.Font(None, font_size)
        self.text = text
        self.color = color
        self.centered = centered
        surface = self.font.render(text, True, color)
        super().__init__(x, y, surface.get_width(), surface.get_height())

    def set_text(self, text: str):
        self.text = text
        surface = self.font.render(text, True, self.color)
        self.rect.width = surface.get_width()
        self.rect.height = surface.get_height()

    def render(self, screen: pygame.Surface):
        if not self.visible:
            return
        surface = self.font.render(self.text, True, self.color)
        x = self.rect.x - surface.get_width() // 2 if self.centered else self.rect.x
        screen.blit(surface, (x, self.rect.y))


class Button(Widget):
    """Bouton cliquable avec texte."""

    def __init__(self, x: int, y: int, width: int, height: int, text: str,
                 callback: Optional[Callable] = None, font_size: int = 28):
        super().__init__(x, y, width, height)
        self.text = text
        self.callback = callback
        self.font = pygame.font.Font(None, font_size)
        self.scale = 1.0
        self.target_scale = 1.0

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            self.target_scale = 1.05 if self.hovered else 1.0

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.scale = 0.95
                if self.callback:
                    self.callback()
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.scale = self.target_scale

        return False

    def update(self, dt: float):
        self.scale += (self.target_scale - self.scale) * 10 * dt

    def render(self, screen: pygame.Surface):
        if not self.visible:
            return

        if not self.enabled:
            bg_color, text_color, border_color = Colors.BG_PANEL, Colors.TEXT_DIM, Colors.BORDER
        elif self.hovered:
            bg_color, text_color, border_color = Colors.PRIMARY_HOVER, Colors.BG_DARK, Colors.PRIMARY
        else:
            bg_color, text_color, border_color = Colors.PRIMARY, Colors.BG_DARK, Colors.PRIMARY_DARK

        scaled_rect = self.rect.copy()
        if self.scale != 1.0:
            dw = int(self.rect.width * (self.scale - 1) / 2)
            dh = int(self.rect.height * (self.scale - 1) / 2)
            scaled_rect.inflate_ip(dw * 2, dh * 2)

        pygame.draw.rect(screen, bg_color, scaled_rect, border_radius=8)
        pygame.draw.rect(screen, border_color, scaled_rect, 2, border_radius=8)

        text_surface = self.font.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=scaled_rect.center)
        screen.blit(text_surface, text_rect)


class TextInput(Widget):
    """Champ de saisie de texte."""

    def __init__(self, x: int, y: int, width: int, height: int,
                 placeholder: str = "", font_size: int = 24, max_length: int = 50):
        super().__init__(x, y, width, height)
        self.text = ""
        self.placeholder = placeholder
        self.font = pygame.font.Font(None, font_size)
        self.max_length = max_length
        self.cursor_visible = True
        self.cursor_timer = 0.0
        self.cursor_pos = 0

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            was_focused = self.focused
            self.focused = self.rect.collidepoint(event.pos)
            if self.focused:
                self.cursor_visible = True
                self.cursor_timer = 0
                self.cursor_pos = len(self.text)
            return self.focused or was_focused

        elif event.type == pygame.KEYDOWN and self.focused:
            if event.key == pygame.K_BACKSPACE:
                if self.cursor_pos > 0:
                    self.text = self.text[:self.cursor_pos-1] + self.text[self.cursor_pos:]
                    self.cursor_pos -= 1
            elif event.key == pygame.K_DELETE:
                if self.cursor_pos < len(self.text):
                    self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos+1:]
            elif event.key == pygame.K_LEFT:
                self.cursor_pos = max(0, self.cursor_pos - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
            elif event.key == pygame.K_HOME:
                self.cursor_pos = 0
            elif event.key == pygame.K_END:
                self.cursor_pos = len(self.text)
            elif event.key in (pygame.K_TAB, pygame.K_RETURN):
                return False  # Laisse passer
            elif event.unicode and len(self.text) < self.max_length:
                if event.unicode.isprintable():
                    self.text = self.text[:self.cursor_pos] + event.unicode + self.text[self.cursor_pos:]
                    self.cursor_pos += 1

            self.cursor_visible = True
            self.cursor_timer = 0
            return True

        return False

    def update(self, dt: float):
        if self.focused:
            self.cursor_timer += dt
            if self.cursor_timer >= 0.5:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0

    def render(self, screen: pygame.Surface):
        if not self.visible:
            return

        bg_color = Colors.BG_ACTIVE if self.focused else Colors.BG_PANEL
        border_color = Colors.BORDER_FOCUS if self.focused else Colors.BORDER

        pygame.draw.rect(screen, bg_color, self.rect, border_radius=6)
        pygame.draw.rect(screen, border_color, self.rect, 2, border_radius=6)

        if self.text:
            text_color, display_text = Colors.TEXT, self.text
        else:
            text_color, display_text = Colors.TEXT_DIM, self.placeholder

        text_surface = self.font.render(display_text, True, text_color)
        text_x = self.rect.x + 10
        text_y = self.rect.y + (self.rect.height - text_surface.get_height()) // 2

        clip_rect = pygame.Rect(self.rect.x + 10, self.rect.y, self.rect.width - 20, self.rect.height)
        old_clip = screen.get_clip()
        screen.set_clip(clip_rect)
        screen.blit(text_surface, (text_x, text_y))

        if self.focused and self.cursor_visible:
            cursor_x = text_x + self.font.size(self.text[:self.cursor_pos])[0] if self.text else text_x
            pygame.draw.line(screen, Colors.TEXT, (cursor_x, self.rect.y + 8), (cursor_x, self.rect.y + self.rect.height - 8), 2)

        screen.set_clip(old_clip)

    def get_text(self) -> str:
        return self.text

    def set_text(self, text: str):
        self.text = text[:self.max_length]
        self.cursor_pos = len(self.text)


class Slider(Widget):
    """Slider pour les options (volume, etc.)."""

    def __init__(self, x: int, y: int, width: int, height: int,
                 min_val: float = 0.0, max_val: float = 1.0, value: float = 0.5,
                 callback: Optional[Callable[[float], None]] = None):
        super().__init__(x, y, width, height)
        self.min_val = min_val
        self.max_val = max_val
        self.value = value
        self.callback = callback
        self.dragging = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self._update_value(event.pos[0])
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            if self.dragging:
                self._update_value(event.pos[0])
                return True

        return False

    def _update_value(self, mouse_x: int):
        track_x = self.rect.x + 10
        track_width = self.rect.width - 20
        ratio = max(0.0, min(1.0, (mouse_x - track_x) / track_width))
        self.value = self.min_val + ratio * (self.max_val - self.min_val)
        if self.callback:
            self.callback(self.value)

    def render(self, screen: pygame.Surface):
        if not self.visible:
            return

        track_rect = pygame.Rect(self.rect.x + 10, self.rect.y + self.rect.height // 2 - 4, self.rect.width - 20, 8)
        pygame.draw.rect(screen, Colors.BG_PANEL, track_rect, border_radius=4)

        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        filled_width = int(track_rect.width * ratio)
        filled_rect = pygame.Rect(track_rect.x, track_rect.y, filled_width, track_rect.height)
        pygame.draw.rect(screen, Colors.PRIMARY, filled_rect, border_radius=4)

        cursor_x = track_rect.x + filled_width
        cursor_radius = 12 if self.dragging or self.hovered else 10
        pygame.draw.circle(screen, Colors.PRIMARY, (cursor_x, self.rect.centery), cursor_radius)
        pygame.draw.circle(screen, Colors.TEXT, (cursor_x, self.rect.centery), cursor_radius, 2)

    def set_value(self, value: float):
        self.value = max(self.min_val, min(self.max_val, value))

    def get_value(self) -> float:
        return self.value


class Checkbox(Widget):
    """Case à cocher."""

    def __init__(self, x: int, y: int, text: str, checked: bool = False,
                 callback: Optional[Callable[[bool], None]] = None, font_size: int = 24):
        self.font = pygame.font.Font(None, font_size)
        text_surface = self.font.render(text, True, Colors.TEXT)
        self.box_size = 24
        width = self.box_size + 10 + text_surface.get_width()
        height = max(self.box_size, text_surface.get_height())

        super().__init__(x, y, width, height)
        self.text = text
        self.checked = checked
        self.callback = callback

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.checked = not self.checked
                if self.callback:
                    self.callback(self.checked)
                return True

        return False

    def render(self, screen: pygame.Surface):
        if not self.visible:
            return

        box_rect = pygame.Rect(self.rect.x, self.rect.y + (self.rect.height - self.box_size) // 2, self.box_size, self.box_size)
        bg_color = Colors.BG_HOVER if self.hovered else Colors.BG_PANEL
        border_color = Colors.PRIMARY if self.checked else Colors.BORDER

        pygame.draw.rect(screen, bg_color, box_rect, border_radius=4)
        pygame.draw.rect(screen, border_color, box_rect, 2, border_radius=4)

        if self.checked:
            points = [(box_rect.x + 5, box_rect.centery), (box_rect.x + self.box_size // 3, box_rect.y + self.box_size - 6), (box_rect.x + self.box_size - 5, box_rect.y + 5)]
            pygame.draw.lines(screen, Colors.PRIMARY, False, points, 3)

        text_color = Colors.TEXT if self.enabled else Colors.TEXT_DIM
        text_surface = self.font.render(self.text, True, text_color)
        screen.blit(text_surface, (self.rect.x + self.box_size + 10, self.rect.y + (self.rect.height - text_surface.get_height()) // 2))

    def set_checked(self, checked: bool):
        self.checked = checked