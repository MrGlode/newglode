"""
Classe Player avec système d'inventaire.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class InventorySlot:
    """Un slot d'inventaire contenant un type d'item et une quantité."""
    item: str  # Nom de l'item (ex: 'iron_ore', 'iron_plate')
    count: int  # Quantité

    def to_dict(self) -> dict:
        return {'item': self.item, 'count': self.count}

    @staticmethod
    def from_dict(data: dict) -> 'InventorySlot':
        return InventorySlot(item=data['item'], count=data['count'])


class Inventory:
    """Inventaire du joueur avec slots empilables."""

    MAX_SLOTS = 40  # 4 lignes x 10 colonnes
    MAX_STACK = 100  # Stack max par slot

    def __init__(self):
        self.slots: List[Optional[InventorySlot]] = [None] * self.MAX_SLOTS

    def add_item(self, item: str, count: int = 1) -> int:
        """
        Ajoute des items à l'inventaire.
        Retourne le nombre d'items qui n'ont pas pu être ajoutés (overflow).
        """
        remaining = count

        # D'abord, essaie de compléter les stacks existants
        for i, slot in enumerate(self.slots):
            if remaining <= 0:
                break
            if slot and slot.item == item and slot.count < self.MAX_STACK:
                space = self.MAX_STACK - slot.count
                to_add = min(space, remaining)
                slot.count += to_add
                remaining -= to_add

        # Ensuite, utilise les slots vides
        for i, slot in enumerate(self.slots):
            if remaining <= 0:
                break
            if slot is None:
                to_add = min(self.MAX_STACK, remaining)
                self.slots[i] = InventorySlot(item=item, count=to_add)
                remaining -= to_add

        return remaining  # Retourne ce qui n'a pas pu être ajouté

    def remove_item(self, item: str, count: int = 1) -> int:
        """
        Retire des items de l'inventaire.
        Retourne le nombre d'items effectivement retirés.
        """
        to_remove = count
        removed = 0

        # Parcourt les slots en sens inverse (vide les derniers d'abord)
        for i in range(len(self.slots) - 1, -1, -1):
            if to_remove <= 0:
                break
            slot = self.slots[i]
            if slot and slot.item == item:
                take = min(slot.count, to_remove)
                slot.count -= take
                to_remove -= take
                removed += take

                # Supprime le slot s'il est vide
                if slot.count <= 0:
                    self.slots[i] = None

        return removed

    def has_item(self, item: str, count: int = 1) -> bool:
        """Vérifie si l'inventaire contient au moins 'count' items."""
        return self.count_item(item) >= count

    def count_item(self, item: str) -> int:
        """Compte le nombre total d'un item dans l'inventaire."""
        total = 0
        for slot in self.slots:
            if slot and slot.item == item:
                total += slot.count
        return total

    def get_all_items(self) -> Dict[str, int]:
        """Retourne un dictionnaire de tous les items et leurs quantités."""
        items = {}
        for slot in self.slots:
            if slot:
                items[slot.item] = items.get(slot.item, 0) + slot.count
        return items

    def is_full(self) -> bool:
        """Vérifie si l'inventaire est plein (aucun slot vide)."""
        return all(slot is not None for slot in self.slots)

    def get_free_slots(self) -> int:
        """Retourne le nombre de slots libres."""
        return sum(1 for slot in self.slots if slot is None)

    def swap_slots(self, index1: int, index2: int):
        """Échange deux slots."""
        if 0 <= index1 < self.MAX_SLOTS and 0 <= index2 < self.MAX_SLOTS:
            self.slots[index1], self.slots[index2] = self.slots[index2], self.slots[index1]

    def to_dict(self) -> dict:
        """Sérialise l'inventaire."""
        return {
            'slots': [slot.to_dict() if slot else None for slot in self.slots]
        }

    @staticmethod
    def from_dict(data: dict) -> 'Inventory':
        """Désérialise l'inventaire."""
        inv = Inventory()
        slots_data = data.get('slots', [])
        for i, slot_data in enumerate(slots_data):
            if i < inv.MAX_SLOTS and slot_data:
                inv.slots[i] = InventorySlot.from_dict(slot_data)
        return inv


@dataclass
class Player:
    """Représente un joueur dans le jeu."""
    id: int
    name: str
    x: float = 0.0
    y: float = 0.0
    inventory: Inventory = field(default_factory=Inventory)

    # Stats optionnelles pour le futur
    health: int = 100
    max_health: int = 100

    def to_dict(self) -> dict:
        """Sérialise le joueur."""
        return {
            'id': self.id,
            'name': self.name,
            'x': self.x,
            'y': self.y,
            'inventory': self.inventory.to_dict(),
            'health': self.health,
            'max_health': self.max_health
        }

    @staticmethod
    def from_dict(data: dict) -> 'Player':
        """Désérialise le joueur."""
        player = Player(
            id=data['id'],
            name=data['name'],
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
            health=data.get('health', 100),
            max_health=data.get('max_health', 100)
        )
        if 'inventory' in data:
            player.inventory = Inventory.from_dict(data['inventory'])
        return player

    def pickup_item(self, item: str, count: int = 1) -> int:
        """Ramasse des items. Retourne le nombre non ramassé."""
        return self.inventory.add_item(item, count)

    def drop_item(self, item: str, count: int = 1) -> int:
        """Lâche des items. Retourne le nombre effectivement lâché."""
        return self.inventory.remove_item(item, count)

    def can_craft(self, ingredients: Dict[str, int]) -> bool:
        """Vérifie si le joueur peut fabriquer une recette."""
        for item, needed in ingredients.items():
            if not self.inventory.has_item(item, needed):
                return False
        return True

    def craft(self, ingredients: Dict[str, int], result: str, count: int = 1) -> bool:
        """
        Fabrique un item. Consomme les ingrédients et ajoute le résultat.
        Retourne True si réussi.
        """
        if not self.can_craft(ingredients):
            return False

        # Consomme les ingrédients
        for item, needed in ingredients.items():
            self.inventory.remove_item(item, needed)

        # Ajoute le résultat
        overflow = self.inventory.add_item(result, count)

        # Si overflow, on a un problème (ne devrait pas arriver si on vérifie avant)
        return overflow == 0