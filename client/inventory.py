"""
Interface d'inventaire pour le client.
Affiche l'inventaire du joueur et gère les interactions.
"""
from os.path import split
from time import sleep

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

        # Crafting panel
        self.CRAFTING_PANEL_WIDTH = 220
        self.RECIPE_HEIGHT = 70
        self.RECIPE_PADDING = 4

        # Crafting state
        self._craft_scroll_offset = 0
        self._hovered_recipe: Optional[str] = None
        self._craft_recipes: List[dict] = []

        # Sorting system
        self._sort_button_rect: Optional[pygame.Rect] = None
        self._sort_button_hovered = False

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
        inv_width = self.COLS * (self.SLOT_SIZE + self.SLOT_PADDING) + self.MARGIN * 2
        inv_height = self.ROWS * (self.SLOT_SIZE + self.SLOT_PADDING) + self.MARGIN * 2 + 40

        # Largeur totale = inventaire + espace + craft
        total_width = inv_width + 10 + self.CRAFTING_PANEL_WIDTH

        screen_w, screen_h = screen.get_size()

        # Centre l'ensemble
        start_x = (screen_w - total_width) // 2
        y = (screen_h - inv_height) // 2

        return pygame.Rect(start_x, y, inv_width, inv_height)

    def get_craft_panel_rect(self, screen: pygame.Surface) -> pygame.Rect:
        inv_rect = self.get_panel_rect(screen)

        return pygame.Rect(
            inv_rect.right + 10,
            inv_rect.y,
            self.CRAFTING_PANEL_WIDTH,
            inv_rect.height
        )

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
        craft_rect = self.get_craft_panel_rect(game.screen)

        if self._sort_button_rect and self._sort_button_rect.collidepoint(pos) and button == 1:
            self._request_sort(game)
            return True

        # Clic sur le panneau craft
        if craft_rect.collidepoint(pos):
            recipe_name = self._get_recipe_at_pos(pos, game.screen)
            if recipe_name:
                self._handle_craft_click(recipe_name, button, game)
            return True

        # Clic hors panneaux → fermer l'inventaire
        if not panel_rect.collidepoint(pos):
            self.close()
            return True

        slot_index = self.get_slot_at_pos(pos, panel_rect)

        if slot_index is not None:
            slot = self.slots[slot_index] if slot_index < len(self.slots) else None

            if slot and button == 1:  # Clic gauche = drag tout
                self._start_drag(slot_index, slot, split=False)
                return True

            elif slot and button == 3:  # Clic droit = drag la moitié
                self._start_drag(slot_index, slot, split=True)
                return True

        return True

    def _handle_craft_click(self, recipe_name: str, button: int, game: 'Game'):
        """Gère un clic sur une recette."""
        # Trouve la recette
        recipe = None
        for r in self._craft_recipes:
            if r['name'] == recipe_name:
                recipe = r
                break

        if not recipe or not recipe['can_craft']:
            # Recette non craftable - son feedback
            from client.audio import get_audio
            # get_audio().play_error()  # Si tu as un son d'erreur
            return

        # Détermine la quantité à crafter
        keys = pygame.key.get_pressed()
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        if shift_held:
            # Shift + clic = max
            count = recipe['max_craft']
        elif button == 3:
            # Clic droit = 5 (ou max si moins de 5 possibles)
            count = min(5, recipe['max_craft'])
        else:
            # Clic gauche = 1
            count = 1

        if count > 0 and game.network:
            game.network.send_inventory_craft(recipe_name, count)
            from client.audio import get_audio
            get_audio().play_ui_click()

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
            self._hovered_recipe = None
            self._sort_button_hovered = False
            return

        panel_rect = self.get_panel_rect(screen)
        self.hovered_slot = self.get_slot_at_pos(pos, panel_rect)

        # Vérifie le survol des recettes
        self._hovered_recipe = self._get_recipe_at_pos(pos, screen)

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

    def _update_craft_recipes(self):
        from admin.config import get_config
        config = get_config()

        self._craft_recipes = []

        for name, recipe in config.assembler_recipes.items():
            inventory_count = self._count_items_in_inventory()

            can_craft, missing, max_craft = self._check_recipe_craftable(recipe, inventory_count)

            self._craft_recipes.append({
                'name': name,
                'display_name': recipe.display_name,
                'ingredients': recipe.ingredients,
                'result': recipe.result,
                'result_count': recipe.count,
                'can_craft': can_craft,
                'missing': missing,
                'max_craft': max_craft
            })

    def _count_items_in_inventory(self) -> dict:
        counts = {}
        for slot in self.slots:
            if slot:
                item = slot.get('item', '')
                count = slot.get('count', 0)
                counts[item] = counts.get(item, 0) + count
        return counts

    def _check_recipe_craftable(self, recipe, inventory_count: dict) -> tuple:
        missing = {}
        max_craft = float('inf')

        for ingredient, needed in recipe.ingredients.items():
            have = inventory_count.get(ingredient, 0)

            if have < needed:
                missing[ingredient] = needed - have

            possible = have // needed
            max_craft = min(max_craft, possible)

        can_craft = len(missing) == 0 and max_craft > 0
        max_craft = int(max_craft) if max_craft != float('inf') else 0

        return can_craft, missing, max_craft

    def render(self, screen: pygame.Surface, game: 'Game'):
        """Affiche l'inventaire."""
        if not self.visible:
            return

            # Met à jour les recettes (cache invalidé quand l'inventaire change)
        self._update_craft_recipes()

        screen_size = screen.get_size()

        # Cache l'overlay
        if self._overlay_cache is None or self._overlay_size != screen_size:
            self._overlay_cache = pygame.Surface(screen_size, pygame.SRCALPHA)
            self._overlay_cache.fill((0, 0, 0, 128))
            self._overlay_size = screen_size

        screen.blit(self._overlay_cache, (0, 0))

        panel_rect = self.get_panel_rect(screen)

        # Panneau inventaire
        pygame.draw.rect(screen, self.BG_COLOR, panel_rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, panel_rect, 2)

        # Titre inventaire
        title = self.font.render("Inventaire", True, self.TEXT_COLOR)
        title_x = panel_rect.x + 15
        screen.blit(title, (title_x, panel_rect.y + 10))

        # Sorting
        self._render_sort_button(screen, panel_rect)

        # Slots
        for i in range(self.COLS * self.ROWS):
            self._render_slot(screen, i, panel_rect, game)

        # Panneau craft
        self._render_craft_panel(screen, game)

        # Instructions
        help_text = self.small_font.render(
            "Clic: x1 | Clic droit: x5 | Shift+Clic: Max",
            True, (150, 150, 150)
        )
        help_x = panel_rect.x + (panel_rect.width - help_text.get_width()) // 2
        screen.blit(help_text, (help_x, panel_rect.y + panel_rect.height - 25))

        # Item draggé
        self._render_dragged_item(screen, game)

        # Tooltip
        self._render_tooltip(screen, game)

    def _render_sort_button(self, screen: pygame.Surface, panel_rect: pygame.Rect):
        """Affiche le bouton de tri."""
        btn_width = 60
        btn_height = 24
        btn_x = panel_rect.right - btn_width - 15
        btn_y = panel_rect.y + 8

        self._sort_button_rect = pygame.Rect(btn_x, btn_y, btn_width, btn_height)

        # Couleur selon hover
        if self._sort_button_hovered:
            bg_color = (70, 90, 70)
            border_color = (120, 180, 120)
        else:
            bg_color = (50, 65, 50)
            border_color = (80, 120, 80)

        pygame.draw.rect(screen, bg_color, self._sort_button_rect)
        pygame.draw.rect(screen, border_color, self._sort_button_rect, 1)

        # Texte
        text = self.small_font.render("Trier", True, (200, 255, 200))
        text_x = btn_x + (btn_width - text.get_width()) // 2
        text_y = btn_y + (btn_height - text.get_height()) // 2
        screen.blit(text, (text_x, text_y))

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

    def _render_craft_panel(self, screen: pygame.Surface, game: 'Game'):
        """Affiche le panneau de craft."""
        craft_rect = self.get_craft_panel_rect(screen)

        # Fond du panneau
        pygame.draw.rect(screen, self.BG_COLOR, craft_rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, craft_rect, 2)

        # Titre
        title = self.font.render("Craft", True, self.TEXT_COLOR)
        title_x = craft_rect.x + (craft_rect.width - title.get_width()) // 2
        screen.blit(title, (title_x, craft_rect.y + 10))

        # Zone des recettes
        recipes_y = craft_rect.y + 40
        recipes_height = craft_rect.height - 50
        recipes_width = craft_rect.width - 10

        # Surface intermédiaire pour le scroll
        recipes_surface = pygame.Surface((recipes_width, recipes_height), pygame.SRCALPHA)
        recipes_surface.fill((0, 0, 0, 0))

        # Affiche chaque recette sur la surface intermédiaire
        y = -self._craft_scroll_offset
        for recipe in self._craft_recipes:
            # Ne dessine que si visible
            if y + self.RECIPE_HEIGHT > 0 and y < recipes_height:
                self._render_recipe(recipes_surface, recipe, 0, y, recipes_width, game)
            y += self.RECIPE_HEIGHT + self.RECIPE_PADDING

        # Blit la surface sur l'écran
        screen.blit(recipes_surface, (craft_rect.x + 5, recipes_y))

        # Scrollbar optionnelle
        self._render_scrollbar(screen, craft_rect, recipes_y, recipes_height)

    def _render_scrollbar(self, screen: pygame.Surface, craft_rect: pygame.Rect, recipes_y: int, recipes_height: int):
        """Affiche une scrollbar si nécessaire."""
        total_height = len(self._craft_recipes) * (self.RECIPE_HEIGHT + self.RECIPE_PADDING)

        if total_height <= recipes_height:
            return  # Pas besoin de scrollbar

        # Dimensions scrollbar
        scrollbar_width = 6
        scrollbar_x = craft_rect.right - scrollbar_width - 3

        # Hauteur du thumb proportionnelle
        thumb_height = max(20, int(recipes_height * (recipes_height / total_height)))

        # Position du thumb
        scroll_ratio = self._craft_scroll_offset / (total_height - recipes_height)
        thumb_y = recipes_y + int(scroll_ratio * (recipes_height - thumb_height))

        # Track (fond)
        track_rect = pygame.Rect(scrollbar_x, recipes_y, scrollbar_width, recipes_height)
        pygame.draw.rect(screen, (40, 40, 50), track_rect)

        # Thumb
        thumb_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)
        pygame.draw.rect(screen, (80, 80, 100), thumb_rect)

    def _render_recipe(self, surface: pygame.Surface, recipe: dict, x: int, y: int, width: int, game: 'Game'):
        """Affiche une recette individuelle."""
        rect = pygame.Rect(x, y, width, self.RECIPE_HEIGHT)

        # Couleur selon l'état
        if recipe['name'] == self._hovered_recipe:
            if recipe['can_craft']:
                bg_color = (40, 80, 40)
            else:
                bg_color = (80, 40, 40)
        else:
            if recipe['can_craft']:
                bg_color = (30, 60, 30)
            else:
                bg_color = (60, 30, 30)

        # Fond
        pygame.draw.rect(surface, bg_color, rect)
        pygame.draw.rect(surface, self.BORDER_COLOR, rect, 1)

        # Nom du résultat
        name_color = (255, 255, 255) if recipe['can_craft'] else (150, 150, 150)
        name_text = self.font.render(recipe['display_name'], True, name_color)
        surface.blit(name_text, (x + 5, y + 5))

        # Quantité produite
        if recipe['result_count'] > 1:
            count_text = self.small_font.render(f"x{recipe['result_count']}", True, self.COUNT_COLOR)
            surface.blit(count_text, (x + 10 + name_text.get_width(), y + 8))

        # Max craftable
        if recipe['can_craft']:
            max_text = self.small_font.render(f"Max: {recipe['max_craft']}", True, (150, 200, 150))
            surface.blit(max_text, (x + width - max_text.get_width() - 5, y + 5))

        # Ingrédients
        ing_y = y + 28
        inventory_count = self._count_items_in_inventory()

        for ingredient, needed in recipe['ingredients'].items():
            from admin.config import get_config
            config = get_config()
            item_config = config.items.get(ingredient)
            ing_name = item_config.display_name if item_config else ingredient.replace('_', ' ').title()

            have = inventory_count.get(ingredient, 0)
            if have >= needed:
                ing_color = (100, 255, 100)
                text = f"[OK] {needed} {ing_name}"
            else:
                ing_color = (255, 100, 100)
                text = f"[X] {needed} {ing_name} ({have})"

            ing_text = self.small_font.render(text, True, ing_color)
            surface.blit(ing_text, (x + 8, ing_y))
            ing_y += 15

    def _get_recipe_rect(self, index: int, craft_rect: pygame.Rect) -> pygame.Rect:
        recipes_y = craft_rect.y + 40
        y = recipes_y - self._craft_scroll_offset + index * (self.RECIPE_HEIGHT + self.RECIPE_PADDING)
        return pygame.Rect(craft_rect.x + 5, y, craft_rect.width - 10, self.RECIPE_HEIGHT)

    def _get_recipe_at_pos(self, pos: Tuple[int, int], screen: pygame.Surface) -> Optional[str]:
        craft_rect = self.get_craft_panel_rect(screen)

        if not craft_rect.collidepoint(pos):
            return None

        for i, recipe in enumerate(self._craft_recipes):
            rect = self._get_recipe_rect(i, craft_rect)
            if rect.collidepoint(pos):
                return recipe['name']

        return None

    def scroll_craft_panel(self, delta: int, screen: pygame.Surface):
        """Scroll le panneau de craft."""
        craft_rect = self.get_craft_panel_rect(screen)
        visible_height = craft_rect.height - 50  # Hauteur réelle de la zone recettes

        total_height = len(self._craft_recipes) * (self.RECIPE_HEIGHT + self.RECIPE_PADDING)

        max_scroll = max(0, total_height - visible_height)
        self._craft_scroll_offset = max(0, min(max_scroll, self._craft_scroll_offset + delta))

    def _request_sort(self, game: 'Game'):
        """Envoie une demande de tri au serveur."""
        if game.network:
            game.network.send_inventory_sort()
            from client.audio import get_audio
            get_audio().play_ui_click()

class InventorySlotData:
    """Données d'un slot pour le rendu."""
    def __init__(self, item: str = "", count: int = 0):
        self.item = item
        self.count = count

    def to_dict(self) -> dict:
        return {'item': self.item, 'count': self.count}