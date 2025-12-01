from typing import List, Dict, Set, Optional
from shared.entities import Entity, EntityType, Direction
from shared.constants import WORLD_TICK_INTERVAL
from server.world import World
from admin.config import get_config


class Simulation:
    """Gère la logique du monde : machines, convoyeurs, etc."""

    def __init__(self, world: World):
        self.world = world
        self.dirty_entities: Set[int] = set()

    def tick(self):
        """Exécute un tick de simulation."""
        self.dirty_entities.clear()

        with self.world.lock:
            self.world.tick += 1

            # Simule toutes les entités des chunks chargés
            for chunk in self.world.chunks.values():
                for entity in list(chunk.entities.values()):
                    self.update_entity(entity)

    def mark_dirty(self, entity: Entity):
        """Marque une entité comme modifiée."""
        self.dirty_entities.add(entity.id)

    def get_dirty_entities(self) -> List[Entity]:
        """Retourne les entités modifiées depuis le dernier tick."""
        entities = []
        for entity_id in self.dirty_entities:
            if entity_id in self.world.entities:
                entities.append(self.world.entities[entity_id])
        return entities

    def update_entity(self, entity: Entity):
        """Met à jour une entité selon son type."""
        if entity.entity_type == EntityType.CONVEYOR:
            self.update_conveyor(entity)
        elif entity.entity_type == EntityType.MINER:
            self.update_miner(entity)
        elif entity.entity_type == EntityType.FURNACE:
            self.update_furnace(entity)
        elif entity.entity_type == EntityType.ASSEMBLER:
            self.update_assembler(entity)
        elif entity.entity_type == EntityType.INSERTER:
            self.update_inserter(entity)

    def update_conveyor(self, entity: Entity):
        """Déplace les items sur le convoyeur."""
        config = get_config()
        conveyor_config = config.entities_by_name.get('CONVEYOR')

        items = entity.data.get('items', [])
        if not items:
            return

        speed = conveyor_config.speed if conveyor_config else 0.02
        direction = entity.direction
        dx, dy = self.direction_to_delta(direction)

        new_items = []
        changed = False

        for item in items:
            item['progress'] += speed
            changed = True

            if item['progress'] >= 1.0:
                # Item sort du convoyeur, cherche la cible
                target_x = entity.x + dx
                target_y = entity.y + dy

                target_entity = self.world.get_entity_at(int(target_x), int(target_y))
                transferred = False

                if target_entity:
                    if target_entity.entity_type == EntityType.CONVEYOR:
                        target_items = target_entity.data.get('items', [])
                        max_items = config.entities_by_name.get('CONVEYOR').buffer_size if config.entities_by_name.get(
                            'CONVEYOR') else 3
                        if len(target_items) < max_items:
                            target_items.append({'item': item['item'], 'progress': 0.0})
                            target_entity.data['items'] = target_items
                            transferred = True
                            self.mark_dirty(target_entity)

                    elif target_entity.entity_type == EntityType.CHEST:
                        chest_items = target_entity.data.get('items', [])
                        max_items = config.entities_by_name.get('CHEST').buffer_size if config.entities_by_name.get(
                            'CHEST') else 50
                        if len(chest_items) < max_items:
                            chest_items.append({'item': item['item']})
                            target_entity.data['items'] = chest_items
                            transferred = True
                            self.mark_dirty(target_entity)

                    elif target_entity.entity_type == EntityType.FURNACE:
                        furnace_input = target_entity.data.get('input', [])
                        max_items = config.entities_by_name.get(
                            'FURNACE').input_buffer_size if config.entities_by_name.get('FURNACE') else 10
                        if len(furnace_input) < max_items:
                            furnace_input.append({'item': item['item']})
                            target_entity.data['input'] = furnace_input
                            transferred = True
                            self.mark_dirty(target_entity)

                    elif target_entity.entity_type == EntityType.ASSEMBLER:
                        assembler_input = target_entity.data.get('input', [])
                        max_items = config.entities_by_name.get(
                            'ASSEMBLER').input_buffer_size if config.entities_by_name.get('ASSEMBLER') else 10
                        if len(assembler_input) < max_items:
                            assembler_input.append({'item': item['item']})
                            target_entity.data['input'] = assembler_input
                            transferred = True
                            self.mark_dirty(target_entity)

                if not transferred:
                    item['progress'] = 0.99
                    new_items.append(item)
            else:
                new_items.append(item)

        entity.data['items'] = new_items
        if changed:
            self.mark_dirty(entity)

    def update_miner(self, entity: Entity):
        """Extrait des ressources du sol et éjecte vers la sortie."""
        config = get_config()
        miner_config = config.entities_by_name.get('MINER')

        cooldown = entity.data.get('cooldown', 0)
        if cooldown > 0:
            entity.data['cooldown'] = cooldown - 1

        output = entity.data.get('output', [])
        buffer_size = miner_config.buffer_size if miner_config else 10
        miner_cooldown = miner_config.cooldown if miner_config else 60

        # Essaie d'éjecter un item
        if output:
            dx, dy = self.direction_to_delta(entity.direction)
            target_x = entity.x + dx
            target_y = entity.y + dy

            target_entity = self.world.get_entity_at(int(target_x), int(target_y))

            if target_entity:
                transferred = False

                if target_entity.entity_type == EntityType.CONVEYOR:
                    items = target_entity.data.get('items', [])
                    max_items = config.entities_by_name.get('CONVEYOR').buffer_size if config.entities_by_name.get(
                        'CONVEYOR') else 3
                    if len(items) < max_items:
                        items.append({'item': output[0]['item'], 'progress': 0.0})
                        target_entity.data['items'] = items
                        transferred = True
                        self.mark_dirty(target_entity)

                elif target_entity.entity_type == EntityType.CHEST:
                    chest_items = target_entity.data.get('items', [])
                    max_items = config.entities_by_name.get('CHEST').buffer_size if config.entities_by_name.get(
                        'CHEST') else 50
                    if len(chest_items) < max_items:
                        chest_items.append({'item': output[0]['item']})
                        target_entity.data['items'] = chest_items
                        transferred = True
                        self.mark_dirty(target_entity)

                elif target_entity.entity_type == EntityType.FURNACE:
                    furnace_input = target_entity.data.get('input', [])
                    max_items = config.entities_by_name.get('FURNACE').input_buffer_size if config.entities_by_name.get(
                        'FURNACE') else 10
                    if len(furnace_input) < max_items:
                        furnace_input.append({'item': output[0]['item']})
                        target_entity.data['input'] = furnace_input
                        transferred = True
                        self.mark_dirty(target_entity)

                if transferred:
                    output.pop(0)
                    entity.data['output'] = output
                    self.mark_dirty(entity)

        # Extraction si cooldown terminé
        if cooldown <= 0:
            tile = self.world.get_tile(entity.x, entity.y)
            resource = config.get_resource_for_tile(int(tile))

            if resource and len(output) < buffer_size:
                output.append({'item': resource, 'progress': 0})
                entity.data['output'] = output
                entity.data['cooldown'] = miner_cooldown
                self.mark_dirty(entity)

    def update_furnace(self, entity: Entity):
        """Fond les minerais en plaques."""
        config = get_config()
        furnace_config = config.entities_by_name.get('FURNACE')

        cooldown = entity.data.get('cooldown', 0)

        if cooldown > 0:
            entity.data['cooldown'] = cooldown - 1

        input_items = entity.data.get('input', [])
        output_items = entity.data.get('output', [])

        output_buffer_size = furnace_config.output_buffer_size if furnace_config else 10

        # Éjecte les items produits
        if output_items:
            dx, dy = self.direction_to_delta(entity.direction)
            target_x = entity.x + dx
            target_y = entity.y + dy

            target_entity = self.world.get_entity_at(int(target_x), int(target_y))

            if target_entity:
                transferred = False

                if target_entity.entity_type == EntityType.CONVEYOR:
                    items = target_entity.data.get('items', [])
                    max_items = config.entities_by_name.get('CONVEYOR').buffer_size if config.entities_by_name.get(
                        'CONVEYOR') else 3
                    if len(items) < max_items:
                        items.append({'item': output_items[0]['item'], 'progress': 0.0})
                        target_entity.data['items'] = items
                        transferred = True
                        self.mark_dirty(target_entity)

                elif target_entity.entity_type == EntityType.CHEST:
                    chest_items = target_entity.data.get('items', [])
                    max_items = config.entities_by_name.get('CHEST').buffer_size if config.entities_by_name.get(
                        'CHEST') else 50
                    if len(chest_items) < max_items:
                        chest_items.append({'item': output_items[0]['item']})
                        target_entity.data['items'] = chest_items
                        transferred = True
                        self.mark_dirty(target_entity)

                if transferred:
                    output_items.pop(0)
                    entity.data['output'] = output_items
                    self.mark_dirty(entity)

        # Transforme si cooldown terminé
        if cooldown <= 0 and input_items and len(output_items) < output_buffer_size:
            item = input_items[0]
            item_type = item.get('item', '')

            recipe = config.furnace_recipes.get(item_type)

            if recipe:
                input_items.pop(0)
                for _ in range(recipe.count):
                    output_items.append({'item': recipe.output})
                entity.data['input'] = input_items
                entity.data['output'] = output_items
                entity.data['cooldown'] = recipe.time
                self.mark_dirty(entity)

    def update_assembler(self, entity: Entity):
        """Assemble des items selon une recette."""
        config = get_config()
        assembler_config = config.entities_by_name.get('ASSEMBLER')

        cooldown = entity.data.get('cooldown', 0)

        if cooldown > 0:
            entity.data['cooldown'] = cooldown - 1
            return

        input_items = entity.data.get('input', [])
        output_items = entity.data.get('output', [])
        selected_recipe = entity.data.get('recipe', None)

        output_buffer_size = assembler_config.output_buffer_size if assembler_config else 10

        # Si pas de recette sélectionnée, ne fait rien
        if not selected_recipe:
            return

        recipe = config.assembler_recipes.get(selected_recipe)
        if not recipe:
            return

        # Éjecte les items produits d'abord
        if output_items:
            dx, dy = self.direction_to_delta(entity.direction)
            target_x = entity.x + dx
            target_y = entity.y + dy

            target_entity = self.world.get_entity_at(int(target_x), int(target_y))

            if target_entity:
                transferred = False

                if target_entity.entity_type == EntityType.CONVEYOR:
                    items = target_entity.data.get('items', [])
                    max_items = config.entities_by_name.get('CONVEYOR').buffer_size if config.entities_by_name.get(
                        'CONVEYOR') else 3
                    if len(items) < max_items:
                        items.append({'item': output_items[0]['item'], 'progress': 0.0})
                        target_entity.data['items'] = items
                        transferred = True
                        self.mark_dirty(target_entity)

                elif target_entity.entity_type == EntityType.CHEST:
                    chest_items = target_entity.data.get('items', [])
                    max_items = config.entities_by_name.get('CHEST').buffer_size if config.entities_by_name.get(
                        'CHEST') else 50
                    if len(chest_items) < max_items:
                        chest_items.append({'item': output_items[0]['item']})
                        target_entity.data['items'] = chest_items
                        transferred = True
                        self.mark_dirty(target_entity)

                if transferred:
                    output_items.pop(0)
                    entity.data['output'] = output_items
                    self.mark_dirty(entity)

        # Buffer de sortie plein ?
        if len(output_items) >= output_buffer_size:
            return

        # Compte les items en input
        input_counts = {}
        for item in input_items:
            item_name = item.get('item', '')
            input_counts[item_name] = input_counts.get(item_name, 0) + 1

        # Vérifie si on a tous les ingrédients
        can_craft = True
        for ingredient, needed in recipe.ingredients.items():
            if input_counts.get(ingredient, 0) < needed:
                can_craft = False
                break

        if not can_craft:
            return

        # Consomme les ingrédients
        for ingredient, needed in recipe.ingredients.items():
            removed = 0
            new_input = []
            for item in input_items:
                if item.get('item') == ingredient and removed < needed:
                    removed += 1
                else:
                    new_input.append(item)
            input_items = new_input

        entity.data['input'] = input_items

        # Produit le résultat
        for _ in range(recipe.count):
            output_items.append({'item': recipe.result})

        entity.data['output'] = output_items
        entity.data['cooldown'] = recipe.time
        self.mark_dirty(entity)

    def update_inserter(self, entity: Entity):
        """Transfère des items entre entités."""
        config = get_config()
        inserter_config = config.entities_by_name.get('INSERTER')

        cooldown = entity.data.get('cooldown', 0)
        held_item = entity.data.get('held_item', None)
        progress = entity.data.get('progress', 0.0)

        animation_speed = inserter_config.animation_speed if inserter_config else 0.05
        inserter_cooldown = inserter_config.cooldown if inserter_config else 20

        direction = entity.direction
        dx, dy = self.direction_to_delta(direction)

        # Source = derrière l'inserter
        source_x = entity.x - dx
        source_y = entity.y - dy
        source_entity = self.world.get_entity_at(int(source_x), int(source_y))

        # Destination = devant l'inserter
        dest_x = entity.x + dx
        dest_y = entity.y + dy
        dest_entity = self.world.get_entity_at(int(dest_x), int(dest_y))

        # Si on tient un item, on continue l'animation
        if held_item:
            # Vérifie que la destination existe toujours et peut recevoir
            if not dest_entity:
                # Pas de destination - remet l'item dans la source
                if source_entity:
                    self.insert_item_into(source_entity, held_item)
                    self.mark_dirty(source_entity)
                entity.data['held_item'] = None
                entity.data['progress'] = 0.0
                entity.data['cooldown'] = inserter_cooldown
                self.mark_dirty(entity)
                return

            progress += animation_speed
            entity.data['progress'] = progress
            self.mark_dirty(entity)

            # Animation terminée - dépose l'item
            if progress >= 1.0:
                if self.insert_item_into(dest_entity, held_item):
                    self.mark_dirty(dest_entity)
                else:
                    # Destination pleine - remet l'item dans la source
                    if source_entity:
                        self.insert_item_into(source_entity, held_item)
                        self.mark_dirty(source_entity)

                entity.data['held_item'] = None
                entity.data['progress'] = 0.0
                entity.data['cooldown'] = inserter_cooldown
                self.mark_dirty(entity)
            return

        # Cooldown avant de prendre un nouvel item
        if cooldown > 0:
            entity.data['cooldown'] = cooldown - 1
            return

        # Ne prend un item que si la destination existe et peut recevoir
        if not source_entity or not dest_entity:
            return

        # Vérifie que la destination peut recevoir avant de prendre
        if not self.can_insert_into(dest_entity):
            return

        # Prend un item de la source
        item = self.extract_item_from(source_entity)
        if item:
            entity.data['held_item'] = item
            entity.data['progress'] = 0.0
            self.mark_dirty(entity)
            self.mark_dirty(source_entity)

    def extract_item_from(self, entity: Entity) -> Optional[dict]:
        """Extrait un item d'une entité. Retourne l'item ou None."""
        data = entity.data

        if entity.entity_type == EntityType.CHEST:
            items = data.get('items', [])
            if items:
                return items.pop(0)

        elif entity.entity_type == EntityType.FURNACE:
            output = data.get('output', [])
            if output:
                return output.pop(0)

        elif entity.entity_type == EntityType.MINER:
            output = data.get('output', [])
            if output:
                return output.pop(0)

        elif entity.entity_type == EntityType.ASSEMBLER:
            output = data.get('output', [])
            if output:
                return output.pop(0)

        elif entity.entity_type == EntityType.CONVEYOR:
            items = data.get('items', [])
            # Prend seulement les items en fin de convoyeur
            for i, item in enumerate(items):
                if item.get('progress', 0) >= 0.9:
                    return items.pop(i)

        return None

    def insert_item_into(self, entity: Entity, item: dict) -> bool:
        """Insère un item dans une entité. Retourne True si réussi."""
        config = get_config()
        data = entity.data

        if entity.entity_type == EntityType.CHEST:
            items = data.get('items', [])
            max_items = config.entities_by_name.get('CHEST').buffer_size if config.entities_by_name.get('CHEST') else 50
            if len(items) < max_items:
                items.append(item)
                data['items'] = items
                return True

        elif entity.entity_type == EntityType.FURNACE:
            input_items = data.get('input', [])
            max_items = config.entities_by_name.get('FURNACE').input_buffer_size if config.entities_by_name.get(
                'FURNACE') else 10
            if len(input_items) < max_items:
                input_items.append(item)
                data['input'] = input_items
                return True

        elif entity.entity_type == EntityType.ASSEMBLER:
            input_items = data.get('input', [])
            max_items = config.entities_by_name.get('ASSEMBLER').input_buffer_size if config.entities_by_name.get(
                'ASSEMBLER') else 10
            if len(input_items) < max_items:
                input_items.append(item)
                data['input'] = input_items
                return True

        elif entity.entity_type == EntityType.CONVEYOR:
            items = data.get('items', [])
            max_items = config.entities_by_name.get('CONVEYOR').buffer_size if config.entities_by_name.get(
                'CONVEYOR') else 3
            if len(items) < max_items:
                item['progress'] = 0.0
                items.append(item)
                data['items'] = items
                return True

        return False

    def can_insert_into(self, entity: Entity) -> bool:
        """Vérifie si une entité peut recevoir un item."""
        config = get_config()
        data = entity.data

        if entity.entity_type == EntityType.CHEST:
            items = data.get('items', [])
            max_items = config.entities_by_name.get('CHEST').buffer_size if config.entities_by_name.get('CHEST') else 50
            return len(items) < max_items

        elif entity.entity_type == EntityType.FURNACE:
            input_items = data.get('input', [])
            max_items = config.entities_by_name.get('FURNACE').input_buffer_size if config.entities_by_name.get(
                'FURNACE') else 10
            return len(input_items) < max_items

        elif entity.entity_type == EntityType.ASSEMBLER:
            input_items = data.get('input', [])
            max_items = config.entities_by_name.get('ASSEMBLER').input_buffer_size if config.entities_by_name.get(
                'ASSEMBLER') else 10
            return len(input_items) < max_items

        elif entity.entity_type == EntityType.CONVEYOR:
            items = data.get('items', [])
            max_items = config.entities_by_name.get('CONVEYOR').buffer_size if config.entities_by_name.get(
                'CONVEYOR') else 3
            return len(items) < max_items

        return False

    @staticmethod
    def direction_to_delta(direction: Direction) -> tuple:
        deltas = {
            Direction.NORTH: (0, -1),
            Direction.EAST: (1, 0),
            Direction.SOUTH: (0, 1),
            Direction.WEST: (-1, 0)
        }
        return deltas.get(direction, (0, 0))