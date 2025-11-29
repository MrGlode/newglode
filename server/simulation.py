from typing import List, Dict
from shared.entities import Entity, EntityType, Direction
from shared.constants import WORLD_TICK_INTERVAL
from server.world import World


class Simulation:
    """Gère la logique du monde : machines, convoyeurs, etc."""

    def __init__(self, world: World):
        self.world = world

    def tick(self):
        """Exécute un tick de simulation."""
        with self.world.lock:
            self.world.tick += 1

            # Simule toutes les entités des chunks chargés
            for chunk in self.world.chunks.values():
                for entity in list(chunk.entities.values()):
                    self.update_entity(entity)

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
        items = entity.data.get('items', [])
        if not items:
            return

        speed = 0.05  # Tiles par tick
        direction = entity.direction

        dx, dy = self.direction_to_delta(direction)

        new_items = []
        for item in items:
            item['progress'] += speed
            if item['progress'] >= 1.0:
                # Item sort du convoyeur, cherche le suivant
                next_x = entity.x + dx
                next_y = entity.y + dy
                # TODO: transférer à l'entité suivante
            else:
                new_items.append(item)

        entity.data['items'] = new_items

    def update_miner(self, entity: Entity):
        """Extrait des ressources du sol."""
        cooldown = entity.data.get('cooldown', 0)
        if cooldown > 0:
            entity.data['cooldown'] = cooldown - 1
            return

        # Vérifie la tuile sous le miner
        tile = self.world.get_tile(entity.x, entity.y)

        from shared.tiles import TileType
        resource_map = {
            TileType.IRON_ORE: 'iron_ore',
            TileType.COPPER_ORE: 'copper_ore',
            TileType.COAL: 'coal'
        }

        if tile in resource_map:
            output = entity.data.get('output', [])
            if len(output) < 10:  # Buffer max
                output.append({'item': resource_map[tile], 'progress': 0})
                entity.data['output'] = output
                entity.data['cooldown'] = 60  # 1 seconde à 60 UPS

    def update_furnace(self, entity: Entity):
        """Fond les minerais."""
        cooldown = entity.data.get('cooldown', 0)
        if cooldown > 0:
            entity.data['cooldown'] = cooldown - 1
            return

        input_items = entity.data.get('input', [])
        fuel = entity.data.get('fuel', 0)
        output = entity.data.get('output', [])

        if not input_items or fuel <= 0 or len(output) >= 10:
            return

        recipes = {
            'iron_ore': 'iron_plate',
            'copper_ore': 'copper_plate'
        }

        item = input_items[0]
        if item['item'] in recipes:
            input_items.pop(0)
            output.append({'item': recipes[item['item']]})
            entity.data['fuel'] = fuel - 1
            entity.data['cooldown'] = 120  # 2 secondes
            entity.data['input'] = input_items
            entity.data['output'] = output

    def update_assembler(self, entity: Entity):
        """Assemble des items selon une recette."""
        # TODO: implémenter les recettes d'assemblage
        pass

    def update_inserter(self, entity: Entity):
        """Transfère des items entre entités."""
        # TODO: implémenter la logique inserter
        pass

    @staticmethod
    def direction_to_delta(direction: Direction) -> tuple:
        deltas = {
            Direction.NORTH: (0, -1),
            Direction.EAST: (1, 0),
            Direction.SOUTH: (0, 1),
            Direction.WEST: (-1, 0)
        }
        return deltas.get(direction, (0, 0))