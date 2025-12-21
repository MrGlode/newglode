"""
Interface d'inventaire pour le client.
Affiche l'inventaire du joueur et gère les interactions.
"""
from os.path import split

import pygame
from typing import Optional, List, Dict, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from client.game import Game


class InventoryUI:
    """Interface utilisateur pour l'inventaire."""

    COLS = 10  # Colonnes
    ROWS = 4   # Lignes
    SLOT_SIZE = 48  # Taille d'un slot en pixels
    SLOT_PADDING = 4  # Espacement entre slots
    MARGIN = 20  # Marge du panneau

    def __init__(self):
        self.visible = False
        self.slots: List[Optional[dict]] = [None] * (self.COLS * self.ROWS)
        self.selected_slot: Optional[int] = None  # Slot sélectionné pour déplacement
        self.hovered_slot: Optional[int] = None

        # Overlay cache
        self._overlay_cache: Optional[pygame.Surface] = None
        self._overlay_size: Tuple[int, int] = (0,0)

        # Drag & Drop
        self._dragging = False
        self._drag_slot: Optional[int] = None
        self._drag_item: Optional[dict] = None
        self._drag_pos: Tuple[int, int] = (0,0)
        self._drag_is_split: bool = False
        self._drag_remaining: Optional[dict] = None

        # Fonts
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)

        # Tooltips
        self._tooltip_font = pygame.font.Font(None, 20)
        self._hover_time: float = 0
        self._hover_delay: float = 0.3

        # Couleurs
        self.BG_COLOR = (30, 30, 40)
        self.BORDER_COLOR = (100, 100, 120)
        self.SLOT_COLOR = (50, 50, 60)
        self.SLOT_HOVER_COLOR = (70, 70, 80)
        self.SLOT_SELECTED_COLOR = (80, 100, 80)
        self.TEXT_COLOR = (255, 255, 255)
        self.COUNT_COLOR = (255, 255, 100)
        self.DRAG_COLOR = (40, 40, 50)

    def toggle(self):
        """Ouvre/ferme l'inventaire."""
        self.visible = not self.visible
        self.selected_slot = None

    def open(self):
        """Ouvre l'inventaire."""
        self.visible = True

    def close(self):
        """Ferme l'inventaire."""
        self.visible = False
        self.selected_slot = None

    def update_slots(self, slots_data: List[Optional[dict]]):
        """Met à jour les données des slots depuis le serveur."""
        self.slots = slots_data[:self.COLS * self.ROWS]
        # Complète avec des None si nécessaire
        while len(self.slots) < self.COLS * self.ROWS:
            self.slots.append(None)

    def get_panel_rect(self, screen: pygame.Surface) -> pygame.Rect:
        """Calcule le rectangle du panneau d'inventaire."""
        panel_width = self.COLS * (self.SLOT_SIZE + self.SLOT_PADDING) + self.MARGIN * 2
        panel_height = self.ROWS * (self.SLOT_SIZE + self.SLOT_PADDING) + self.MARGIN * 2 + 40  # +40 pour le titre

        screen_w, screen_h = screen.get_size()
        x = (screen_w - panel_width) // 2
        y = (screen_h - panel_height) // 2

        return pygame.Rect(x, y, panel_width, panel_height)

    def get_slot_rect(self, index: int, panel_rect: pygame.Rect) -> pygame.Rect:
        """Calcule le rectangle d'un slot."""
        col = index % self.COLS
        row = index // self.COLS

        x = panel_rect.x + self.MARGIN + col * (self.SLOT_SIZE + self.SLOT_PADDING)
        y = panel_rect.y + self.MARGIN + 40 + row * (self.SLOT_SIZE + self.SLOT_PADDING)  # +40 pour le titre

        return pygame.Rect(x, y, self.SLOT_SIZE, self.SLOT_SIZE)

    def get_slot_at_pos(self, pos: Tuple[int, int], panel_rect: pygame.Rect) -> Optional[int]:
        """Retourne l'index du slot à la position donnée, ou None."""
        for i in range(self.COLS * self.ROWS):
            slot_rect = self.get_slot_rect(i, panel_rect)
            if slot_rect.collidepoint(pos):
                return i
        return None

    def handle_mouse_down(self, pos: Tuple[int, int], button: int, game: 'Game') -> bool:
        if not self.visible:
            return False

        panel_rect = self.get_panel_rect(game.screen)

        if not panel_rect.collidepoint(pos):
            self.close()
            return True

        slot_index = self.get_slot_at_pos(pos, panel_rect)

        if slot_index is not None:
            slot = self.slots[slot_index] if slot_index < len(self.slots) else None

            if slot and button == 1:
                self._start_drag(slot_index, slot, split=False)
                return True
            elif slot and button == 3:
                self._start_drag(slot_index, slot, split=True)
                return True

        return True

    def handle_mouse_up(self, pos: Tuple[int, int], button: int, game: 'Game') -> bool:
        if not self.visible:
            return False

        if not self._dragging:
            return False

        if button not in (1, 3):
            return False

        panel_rect = self.get_panel_rect(game.screen)
        target_slot = self.get_slot_at_pos(pos, panel_rect)

        if target_slot is not None and target_slot != self._drag_slot:
            if game.network:
                if self._drag_is_split:
                    count = self._drag_item.get('count', 0)
                    game.network.send_inventory_split(self._drag_slot, target_slot, count)
                else:
                    game.network.send_inventory_swap(self._drag_slot, target_slot)

                from client.audio import get_audio
                get_audio().play_ui_click()

        self._end_drag()
        return True

    """
    def handle_click(self, pos: Tuple[int, int], button: int, game: 'Game') -> bool:

        # Gère un clic sur l'inventaire.
        # Retourne True si le clic a été consommé.

        if not self.visible:
            return False

        panel_rect = self.get_panel_rect(game.screen)

        # Vérifie si le clic est dans le panneau
        if not panel_rect.collidepoint(pos):
            return False

        slot_index = self.get_slot_at_pos(pos, panel_rect)

        if slot_index is not None:
            if button == 1:  # Clic gauche
                self._handle_left_click(slot_index, game)
            elif button == 3:  # Clic droit
                self._handle_right_click(slot_index, game)

        return True
    """

    def _handle_left_click(self, slot_index: int, game: 'Game'):
        # Gère le clic gauche sur un slot.

        slot = self.slots[slot_index]

        if self.selected_slot is None:
            # Sélectionne le slot s'il contient quelque chose
            if slot:
                self.selected_slot = slot_index
        else:
            # Échange ou fusionne avec le slot sélectionné
            if slot_index != self.selected_slot:
                # Envoie une demande d'échange au serveur
                if game.network:
                    game.network.send_inventory_swap(self.selected_slot, slot_index)
            self.selected_slot = None

    def _handle_right_click(self, slot_index: int, game: 'Game'):
        # Gère le clic droit sur un slot (prend la moitié).
        slot = self.slots[slot_index]

        if slot and game.inspected_entity:
            # Transfère vers l'entité inspectée
            entity_id = game.inspected_entity.get('id')
            item = slot.get('item')
            count = 1  # Transfère 1 par clic droit

            if game.network and entity_id and item:
                game.network.send_inventory_transfer_to(entity_id, item, count)

    def handle_mouse_motion(self, pos: Tuple[int, int], screen: pygame.Surface):
        """Met à jour le slot survolé."""
        if not self.visible:
            self.hovered_slot = None
            return

        panel_rect = self.get_panel_rect(screen)
        self.hovered_slot = self.get_slot_at_pos(pos, panel_rect)

        if self._dragging:
            self._drag_pos = pos

    def _start_drag(self, slot_index: int, slot: dict, split: bool):
        """Démarre un drag (complet ou split)."""
        item_name = slot.get('item', '')
        total_count = slot.get('count', 0)

        if split and total_count > 1:
            drag_count = (total_count + 1) // 2
            remaining_count = total_count - drag_count

            self._drag_item = {'item': item_name, 'count': drag_count}
            self._drag_remaining = {'item': item_name, 'count': remaining_count}
            self._drag_is_split = True
        else:
            self._drag_item = slot.copy()
            self._drag_remaining = None
            self._drag_is_split = False

        self._dragging = True
        self._drag_slot = slot_index
        self._drag_pos = pygame.mouse.get_pos()

    def _end_drag(self):
        self._dragging = False
        self._drag_slot = None
        self._drag_item = None
        self._drag_pos = (0,0)
        self._drag_is_split = False
        self._drag_remaining = None

    def render(self, screen: pygame.Surface, game: 'Game'):
        """Affiche l'inventaire."""
        if not self.visible:
            return

        panel_rect = self.get_panel_rect(screen)

        # Fond semi-transparent
        overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        screen.blit(overlay, (0, 0))

        # Panneau principal
        pygame.draw.rect(screen, self.BG_COLOR, panel_rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, panel_rect, 2)

        # Titre
        title = self.font.render("Inventaire", True, self.TEXT_COLOR)
        title_x = panel_rect.x + (panel_rect.width - title.get_width()) // 2
        screen.blit(title, (title_x, panel_rect.y + 10))

        # Slots
        for i in range(self.COLS * self.ROWS):
            self._render_slot(screen, i, panel_rect, game)

        # Instructions
        help_text = self.small_font.render("I/E: Fermer | Clic: Sélectionner | Clic droit: Transférer", True, (150, 150, 150))
        help_x = panel_rect.x + (panel_rect.width - help_text.get_width()) // 2
        screen.blit(help_text, (help_x, panel_rect.y + panel_rect.height - 25))

        self._render_dragged_item(screen, game)

        self._render_tooltip(screen, game)

    def _render_slot(self, screen: pygame.Surface, index: int, panel_rect: pygame.Rect, game: 'Game'):
        """Affiche un slot individuel."""
        slot_rect = self.get_slot_rect(index, panel_rect)
        slot = self.slots[index] if index < len(self.slots) else None

        # Couleur de fond selon l'état
        if index == self._drag_slot:
            color = self.DRAG_COLOR
        elif index == self.hovered_slot:
            color = self.SLOT_HOVER_COLOR
        else:
            color = self.SLOT_COLOR

        # Dessine le slot
        pygame.draw.rect(screen, color, slot_rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, slot_rect, 1)

        if index == self._drag_slot:
            # Slot source du drag
            if self._drag_is_split and self._drag_remaining:
                # Split : affiche ce qui RESTE (pas ce qu'on drag)
                self._render_item_in_slot(screen, self._drag_remaining, slot_rect, game)
            # else: drag complet → slot vide visuellement (rien à afficher)
        elif slot:
            # Slot normal
            self._render_item_in_slot(screen, slot, slot_rect, game)

    def _render_item_in_slot(self, screen: pygame.Surface, slot: dict, slot_rect: pygame.Rect, game: 'Game'):
        """Affiche un item dans un slot."""
        item_name = slot.get('item', '')
        count = slot.get('count', 0)

        # Couleur de l'item
        item_color = self._get_item_color(item_name, game)

        # Carré coloré représentant l'item
        item_rect = pygame.Rect(
            slot_rect.x + 8,
            slot_rect.y + 6,
            self.SLOT_SIZE - 16,
            self.SLOT_SIZE - 20
        )
        pygame.draw.rect(screen, item_color, item_rect)
        pygame.draw.rect(screen, (255, 255, 255), item_rect, 1)

        # Quantité
        if count > 1:
            count_text = self.small_font.render(str(count), True, self.COUNT_COLOR)
            count_x = slot_rect.x + self.SLOT_SIZE - count_text.get_width() - 4
            count_y = slot_rect.y + self.SLOT_SIZE - count_text.get_height() - 2

            shadow = self.small_font.render(str(count), True, (0, 0, 0))
            screen.blit(shadow, (count_x + 1, count_y + 1))
            screen.blit(count_text, (count_x, count_y))

    def _render_dragged_item(self, screen: pygame.Surface, game: 'Game'):
        """Affiche l'item en cours de drag sous le curseur."""
        if not self._dragging or not self._drag_item:
            return

        item_name = self._drag_item.get('item', '')
        count = self._drag_item.get('count', 0)
        item_color = self._get_item_color(item_name, game)

        # Taille de l'item draggé (légèrement plus grand)
        size = self.SLOT_SIZE - 8
        x = self._drag_pos[0] - size // 2
        y = self._drag_pos[1] - size // 2

        # Ombre
        shadow_rect = pygame.Rect(x + 4, y + 4, size, size)
        pygame.draw.rect(screen, (0, 0, 0, 100), shadow_rect)

        # Item
        item_rect = pygame.Rect(x, y, size, size)
        pygame.draw.rect(screen, item_color, item_rect)
        pygame.draw.rect(screen, (255, 255, 255), item_rect, 2)

        # Quantité
        if count > 1:
            count_text = self.small_font.render(str(count), True, self.COUNT_COLOR)
            count_x = x + size - count_text.get_width()
            count_y = y + size - count_text.get_height()

            shadow = self.small_font.render(str(count), True, (0, 0, 0))
            screen.blit(shadow, (count_x + 1, count_y + 1))
            screen.blit(count_text, (count_x, count_y))

    def _render_tooltip(self, screen: pygame.Surface, game: 'Game'):
        if self._dragging:
            return

        if self.hovered_slot is None:
            return

        slot = self.slots[self.hovered_slot] if self.hovered_slot < len(self.slots) else None
        if not slot:
            return

        item_name = slot.get('item', '')
        count = slot.get('count', 0)

        if not item_name:
            return

        from admin.config import get_config
        config = get_config()
        item_config = config.items.get(item_name)
        display_name = item_config.display_name if item_config else item_name.replace('_', ' ').title()

        text = f"{display_name}"
        if count > 1:
            text += f" (x{count})"

        text_surface = self._tooltip_font.render(text, True, (255,255,255))
        padding = 8

        tooltip_width = text_surface.get_width() + padding * 2
        tooltip_height = text_surface.get_height() + padding * 2

        mouse_x, mouse_y = pygame.mouse.get_pos()
        tooltip_x = mouse_x + 15
        tooltip_y = mouse_y - tooltip_height - 5

        screen_w, screen_h = screen.get_size()
        if tooltip_x + tooltip_width > screen_w:
            tooltip_x = mouse_x - tooltip_width - 10
        if tooltip_y < 0:
            tooltip_y = mouse_y + 20

        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)

        tooltip_surface = pygame.Surface((tooltip_width, tooltip_height), pygame.SRCALPHA)
        tooltip_surface.fill((20, 20, 30, 230))
        screen.blit(tooltip_surface, (tooltip_x, tooltip_y))

        pygame.draw.rect(screen, (100, 100, 120), tooltip_rect, 1)

        screen.blit(text_surface, (tooltip_x + padding, tooltip_y + padding))

    def _get_item_color(self, item_name: str, game: 'Game') -> Tuple[int, int, int]:
        """Récupère la couleur d'un item."""
        from admin.config import get_config
        config = get_config()
        return config.get_item_color(item_name)

    def render_hotbar(self, screen: pygame.Surface, game: 'Game'):
        """Affiche une barre rapide en bas de l'écran (premiers slots)."""
        if self.visible:
            return  # Pas de hotbar si l'inventaire est ouvert

        hotbar_slots = 10
        slot_size = 40
        padding = 4

        total_width = hotbar_slots * (slot_size + padding)
        screen_w, screen_h = screen.get_size()

        # Position (au-dessus de la toolbar existante)
        start_x = (screen_w - total_width) // 2
        start_y = screen_h - 80 - slot_size - 10  # Au-dessus de la toolbar

        # Fond
        bg_rect = pygame.Rect(start_x - 5, start_y - 5, total_width + 10, slot_size + 10)
        pygame.draw.rect(screen, (30, 30, 40, 200), bg_rect)
        pygame.draw.rect(screen, (80, 80, 100), bg_rect, 1)

        # Slots
        for i in range(hotbar_slots):
            slot_rect = pygame.Rect(
                start_x + i * (slot_size + padding),
                start_y,
                slot_size,
                slot_size
            )

            slot = self.slots[i] if i < len(self.slots) else None

            # Fond du slot
            pygame.draw.rect(screen, (50, 50, 60), slot_rect)
            pygame.draw.rect(screen, (80, 80, 100), slot_rect, 1)

            if slot:
                item_name = slot.get('item', '')
                count = slot.get('count', 0)

                # Item
                item_color = self._get_item_color(item_name, game)
                item_rect = pygame.Rect(
                    slot_rect.x + 6,
                    slot_rect.y + 4,
                    slot_size - 12,
                    slot_size - 16
                )
                pygame.draw.rect(screen, item_color, item_rect)
                pygame.draw.rect(screen, (255, 255, 255), item_rect, 1)

                # Quantité
                if count > 1:
                    count_text = self.small_font.render(str(count), True, self.COUNT_COLOR)
                    count_x = slot_rect.x + slot_size - count_text.get_width() - 3
                    count_y = slot_rect.y + slot_size - count_text.get_height() - 1

                    shadow = self.small_font.render(str(count), True, (0, 0, 0))
                    screen.blit(shadow, (count_x + 1, count_y + 1))
                    screen.blit(count_text, (count_x, count_y))


class InventorySlotData:
    """Données d'un slot pour le rendu."""
    def __init__(self, item: str = "", count: int = 0):
        self.item = item
        self.count = count

    def to_dict(self) -> dict:
        return {'item': self.item, 'count': self.count}