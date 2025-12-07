"""
Gestionnaire d'inventaire côté serveur.
Gère les transferts, le ramassage et le craft.
"""

from typing import Optional, TYPE_CHECKING
from shared.player import Player, Inventory
from shared.entities import EntityType

if TYPE_CHECKING:
    from server.world import World


class InventoryManager:
    """Gère toutes les opérations d'inventaire."""

    def __init__(self, world: 'World'):
        self.world = world

    def pickup_from_ground(self, player: Player, x: int, y: int, radius: float = 1.5) -> bool:
        """
        Ramasse les items au sol autour d'une position.
        Pour l'instant, on ramasse depuis les entités "droppées" ou les convoyeurs.
        Retourne True si quelque chose a été ramassé.
        """
        picked = False

        # Cherche les entités proches
        for entity in list(self.world.entities.values()):
            dx = entity.x - x
            dy = entity.y - y
            distance = (dx * dx + dy * dy) ** 0.5

            if distance > radius:
                continue

            # Ramasse depuis les convoyeurs
            if entity.entity_type == EntityType.CONVEYOR:
                items = entity.data.get('items', [])
                for item in items[:]:  # Copie pour itérer
                    overflow = player.pickup_item(item.get('item', ''), 1)
                    if overflow == 0:
                        items.remove(item)
                        picked = True
                entity.data['items'] = items

            # Ramasse depuis les chests
            elif entity.entity_type == EntityType.CHEST:
                items = entity.data.get('items', [])
                for item in items[:]:
                    overflow = player.pickup_item(item.get('item', ''), 1)
                    if overflow == 0:
                        items.remove(item)
                        picked = True
                    else:
                        break  # Inventaire plein
                entity.data['items'] = items

        return picked

    def transfer_to_entity(self, player: Player, entity_id: int, item: str, count: int) -> int:
        """
        Transfère des items du joueur vers une entité.
        Retourne le nombre d'items effectivement transférés.
        """
        entity = self.world.entities.get(entity_id)
        if not entity:
            return 0

        # Vérifie que le joueur a les items
        available = player.inventory.count_item(item)
        to_transfer = min(count, available)

        if to_transfer <= 0:
            return 0

        transferred = 0

        if entity.entity_type == EntityType.CHEST:
            items = entity.data.get('items', [])
            max_items = 50  # TODO: depuis config

            for _ in range(to_transfer):
                if len(items) >= max_items:
                    break
                items.append({'item': item})
                transferred += 1

            entity.data['items'] = items

        elif entity.entity_type == EntityType.FURNACE:
            input_items = entity.data.get('input', [])
            max_items = 10  # TODO: depuis config

            for _ in range(to_transfer):
                if len(input_items) >= max_items:
                    break
                input_items.append({'item': item})
                transferred += 1

            entity.data['input'] = input_items

        elif entity.entity_type == EntityType.ASSEMBLER:
            input_items = entity.data.get('input', [])
            max_items = 10  # TODO: depuis config

            for _ in range(to_transfer):
                if len(input_items) >= max_items:
                    break
                input_items.append({'item': item})
                transferred += 1

            entity.data['input'] = input_items

        # Retire les items du joueur
        if transferred > 0:
            player.inventory.remove_item(item, transferred)

        return transferred

    def transfer_from_entity(self, player: Player, entity_id: int, item: str, count: int) -> int:
        """
        Transfère des items d'une entité vers le joueur.
        Retourne le nombre d'items effectivement transférés.
        """
        entity = self.world.entities.get(entity_id)
        if not entity:
            return 0

        transferred = 0

        if entity.entity_type == EntityType.CHEST:
            items = entity.data.get('items', [])

            for _ in range(count):
                # Trouve un item correspondant
                found_idx = None
                for idx, slot in enumerate(items):
                    if slot.get('item') == item:
                        found_idx = idx
                        break

                if found_idx is None:
                    break

                # Essaie d'ajouter au joueur
                overflow = player.pickup_item(item, 1)
                if overflow == 0:
                    items.pop(found_idx)
                    transferred += 1
                else:
                    break  # Inventaire plein

            entity.data['items'] = items

        elif entity.entity_type == EntityType.FURNACE:
            output_items = entity.data.get('output', [])

            for _ in range(count):
                found_idx = None
                for idx, slot in enumerate(output_items):
                    if slot.get('item') == item:
                        found_idx = idx
                        break

                if found_idx is None:
                    break

                overflow = player.pickup_item(item, 1)
                if overflow == 0:
                    output_items.pop(found_idx)
                    transferred += 1
                else:
                    break

            entity.data['output'] = output_items

        elif entity.entity_type == EntityType.ASSEMBLER:
            output_items = entity.data.get('output', [])

            for _ in range(count):
                found_idx = None
                for idx, slot in enumerate(output_items):
                    if slot.get('item') == item:
                        found_idx = idx
                        break

                if found_idx is None:
                    break

                overflow = player.pickup_item(item, 1)
                if overflow == 0:
                    output_items.pop(found_idx)
                    transferred += 1
                else:
                    break

            entity.data['output'] = output_items

        elif entity.entity_type == EntityType.MINER:
            output_items = entity.data.get('output', [])

            for _ in range(count):
                found_idx = None
                for idx, slot in enumerate(output_items):
                    if slot.get('item') == item:
                        found_idx = idx
                        break

                if found_idx is None:
                    break

                overflow = player.pickup_item(item, 1)
                if overflow == 0:
                    output_items.pop(found_idx)
                    transferred += 1
                else:
                    break

            entity.data['output'] = output_items

        return transferred

    def craft_item(self, player: Player, recipe_name: str) -> bool:
        """
        Fabrique un item manuellement.
        Retourne True si le craft a réussi.
        """
        from admin.config import get_config

        config = get_config()
        recipe = config.assembler_recipes.get(recipe_name)

        if not recipe:
            return False

        # Vérifie les ingrédients
        if not player.can_craft(recipe.ingredients):
            return False

        # Vérifie qu'il y a de la place pour le résultat
        # (Simplifié: on vérifie juste qu'il y a un slot libre ou un stack existant)

        # Effectue le craft
        return player.craft(recipe.ingredients, recipe.result, recipe.count)

    def mine_resource(self, player: Player, x: int, y: int) -> Optional[str]:
        """
        Mine une ressource à la main (lent).
        Retourne le nom de l'item miné ou None.
        """
        from admin.config import get_config

        config = get_config()
        tile = self.world.get_tile(x, y)
        resource = config.get_resource_for_tile(int(tile))

        if resource:
            overflow = player.pickup_item(resource, 1)
            if overflow == 0:
                return resource

        return None