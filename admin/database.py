import os
from pymongo import MongoClient
from typing import Optional, Dict, List, Any

class AdminDB:
    _instance: Optional['AdminDB'] = None

    def __init__(self, uri: str = None):
        self.url = uri or os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
        self.client = MongoClient(self.url)
        self.db = self.client['facto_admin']

        self.tiles = self.db['tiles']
        self.entities = self.db['entities']
        self.items = self.db['items']
        self.furnace_recipes = self.db['furnace_recipes']
        self.assembler_recipes = self.db['assembler_recipes']
        self.placement_rules = self.db['placement_rules']
        self.constants = self.db['constants']

    @classmethod
    def get_instance(cls, uri: str = None) -> 'AdminDB':
        if cls._instance is None:
            cls._instance = cls(uri)
        return cls._instance

    def init_default_data(self):
        if self.tiles.count_documents({}) == 0:
            self._init_tiles()
        if self.entities.count_documents({}) == 0:
            self._init_entities()
        if self.items.count_documents({}) == 0:
            self._init_items()
        if self.furnace_recipes.count_documents({}) == 0:
            self._init_furnace_recipes()
        if self.assembler_recipes.count_documents({}) == 0:
            self._init_assembler_recipes()
        if self.placement_rules.count_documents({}) == 0:
            self._init_placement_rules()
        if self.constants.count_documents({}) == 0:
            self._init_constants()

    def _init_tiles(self):
        tiles = [
            {'id': 0, 'name': 'VOID', 'color': [20, 20, 30], 'walkable': False, 'resource': None},
            {'id': 1, 'name': 'GRASS', 'color': [34, 139, 34], 'walkable': True, 'resource': None},
            {'id': 2, 'name': 'DIRT', 'color': [139, 90, 43], 'walkable': True, 'resource': None},
            {'id': 3, 'name': 'STONE', 'color': [128, 128, 128], 'walkable': True, 'resource': None},
            {'id': 4, 'name': 'WATER', 'color': [30, 144, 255], 'walkable': False, 'resource': None},
            {'id': 5, 'name': 'IRON_ORE', 'color': [160, 160, 180], 'walkable': True, 'resource': 'iron_ore'},
            {'id': 6, 'name': 'COPPER_ORE', 'color': [184, 115, 51], 'walkable': True, 'resource': 'copper_ore'},
            {'id': 7, 'name': 'GOLD_ORE', 'color': [255, 215, 0], 'walkable': True, 'resource': 'gold_ore'},
            {'id': 8, 'name': 'DIAMOND_ORE', 'color': [185, 242, 255], 'walkable': True, 'resource': 'diamond'},
            {'id': 9, 'name': 'BAUXITE_ORE', 'color': [205, 133, 63], 'walkable': True, 'resource': 'bauxite'},
            {'id': 10, 'name': 'TIN_ORE', 'color': [192, 192, 192], 'walkable': True, 'resource': 'tin_ore'},
            {'id': 11, 'name': 'URANIUM_ORE', 'color': [100, 255, 100], 'walkable': True, 'resource': 'uranium_ore'},
            {'id': 12, 'name': 'COAL', 'color': [40, 40, 40], 'walkable': True, 'resource': 'coal'}
        ]

        self.tiles.insert_many(tiles)

    def _init_entities(self):
        entities = [
            {'id': 0, 'name': 'PLAYER', 'display_name': 'Joueur', 'color': [255, 255, 255], 'has_direction': False, 'buffer_size': 0, 'speed': 5.0},
            {'id': 1, 'name': 'CONVEYOR', 'display_name': 'Convoyeur', 'color': [255, 200, 0], 'has_direction': True, 'buffer_size': 3, 'speed': 0.02},
            {'id': 2, 'name': 'MINER', 'display_name': 'Foreuse', 'color': [200, 100, 50], 'has_direction': True, 'buffer_size': 10, 'cooldown': 60},
            {'id': 3, 'name': 'FURNACE', 'display_name': 'Four', 'color': [255, 100, 0], 'has_direction': True, 'input_buffer_size': 10, 'output_buffer_size': 10, 'cooldown': 120},
            {'id': 4, 'name': 'ASSEMBLER', 'display_name': 'Assembleur', 'color': [100, 100, 200], 'has_direction': True, 'input_buffer_size': 10, 'output_buffer_size': 10},
            {'id': 5, 'name': 'CHEST', 'display_name': 'Coffre', 'color': [139, 90, 43], 'has_direction': False, 'buffer_size': 50},
            {'id': 6, 'name': 'INSERTER', 'display_name': 'Inserter', 'color': [150, 150, 150], 'has_direction': True, 'cooldown': 20, 'animation_speed': 0.05}
        ]

        self.entities.insert_many(entities)

    def _init_items(self):
        items = [
            # Ressources brutes
            {'name': 'iron_ore', 'display_name': 'Minerai de fer', 'color': [160, 160, 180], 'category': 'raw'},
            {'name': 'copper_ore', 'display_name': 'Minerai de cuivre', 'color': [184, 115, 51], 'category': 'raw'},
            {'name': 'coal', 'display_name': 'Charbon', 'color': [40, 40, 40], 'category': 'raw'},
            {'name': 'gold_ore', 'display_name': 'Minerai d\'or', 'color': [255, 215, 0], 'category': 'raw'},
            {'name': 'uranium_ore', 'display_name': 'Minerai d\'uranium', 'color': [100, 255, 100], 'category': 'raw'},
            {'name': 'tin_ore', 'display_name': 'Minerai d\'étain', 'color': [192, 192, 192], 'category': 'raw'},
            {'name': 'bauxite', 'display_name': 'Bauxite', 'color': [205, 133, 63], 'category': 'raw'},
            {'name': 'diamond', 'display_name': 'Diamant', 'color': [185, 242, 255], 'category': 'raw'},

            # Plaques (fondues)
            {'name': 'iron_plate', 'display_name': 'Plaque de fer', 'color': [200, 200, 210], 'category': 'plate'},
            {'name': 'copper_plate', 'display_name': 'Plaque de cuivre', 'color': [210, 140, 80], 'category': 'plate'},
            {'name': 'gold_plate', 'display_name': 'Plaque d\'or', 'color': [255, 223, 100], 'category': 'plate'},
            {'name': 'tin_plate', 'display_name': 'Plaque d\'étain', 'color': [210, 210, 210], 'category': 'plate'},
            {'name': 'carbon', 'display_name': 'Carbone', 'color': [60, 60, 60], 'category': 'plate'},

            # Composants intermédiaires
            {'name': 'copper_wire', 'display_name': 'Fil de cuivre', 'color': [230, 160, 100],
             'category': 'intermediate'},
            {'name': 'iron_gear', 'display_name': 'Engrenage', 'color': [180, 180, 190], 'category': 'intermediate'},
            {'name': 'circuit', 'display_name': 'Circuit', 'color': [50, 150, 50], 'category': 'intermediate'},
            {'name': 'advanced_circuit', 'display_name': 'Circuit avancé', 'color': [150, 50, 50],
             'category': 'intermediate'},

            # Science
            {'name': 'automation_science', 'display_name': 'Pack science auto.', 'color': [255, 100, 100],
             'category': 'science'},
        ]
        self.items.insert_many(items)

        def _init_furnace_recipes(self):
            """Initialise les recettes du four."""
            recipes = [
                {'input': 'iron_ore', 'output': 'iron_plate', 'count': 1, 'time': 120},
                {'input': 'copper_ore', 'output': 'copper_plate', 'count': 1, 'time': 120},
                {'input': 'gold_ore', 'output': 'gold_plate', 'count': 1, 'time': 180},
                {'input': 'tin_ore', 'output': 'tin_plate', 'count': 1, 'time': 120},
                {'input': 'coal', 'output': 'carbon', 'count': 1, 'time': 60},
            ]
            self.furnace_recipes.insert_many(recipes)

        def _init_assembler_recipes(self):
            """Initialise les recettes d'assemblage."""
            recipes = [
                {
                    'name': 'iron_gear',
                    'display_name': 'Engrenage',
                    'ingredients': {'iron_plate': 2},
                    'result': 'iron_gear',
                    'count': 1,
                    'time': 60
                },
                {
                    'name': 'copper_wire',
                    'display_name': 'Fil de cuivre',
                    'ingredients': {'copper_plate': 1},
                    'result': 'copper_wire',
                    'count': 2,
                    'time': 30
                },
                {
                    'name': 'circuit',
                    'display_name': 'Circuit',
                    'ingredients': {'iron_plate': 1, 'copper_wire': 3},
                    'result': 'circuit',
                    'count': 1,
                    'time': 90
                },
                {
                    'name': 'advanced_circuit',
                    'display_name': 'Circuit avancé',
                    'ingredients': {'circuit': 2, 'copper_wire': 4},
                    'result': 'advanced_circuit',
                    'count': 1,
                    'time': 180
                },
                {
                    'name': 'automation_science',
                    'display_name': 'Pack science auto.',
                    'ingredients': {'iron_gear': 1, 'circuit': 1},
                    'result': 'automation_science',
                    'count': 1,
                    'time': 120
                },
            ]
            self.assembler_recipes.insert_many(recipes)

        def _init_placement_rules(self):
            """Initialise les règles de placement."""
            rules = [
                {
                    'entity': 'MINER',
                    'allowed_tiles': ['IRON_ORE', 'COPPER_ORE', 'COAL', 'GOLD_ORE', 'URANIUM_ORE', 'TIN_ORE',
                                      'BAUXITE_ORE', 'DIAMOND_ORE'],
                    'forbidden_tiles': []
                },
                {
                    'entity': 'FURNACE',
                    'allowed_tiles': ['GRASS', 'DIRT', 'STONE'],
                    'forbidden_tiles': ['WATER']
                },
                {
                    'entity': 'ASSEMBLER',
                    'allowed_tiles': ['GRASS', 'DIRT', 'STONE'],
                    'forbidden_tiles': ['WATER']
                },
                {
                    'entity': 'CONVEYOR',
                    'allowed_tiles': [],  # Vide = tout sauf forbidden
                    'forbidden_tiles': ['WATER', 'VOID']
                },
                {
                    'entity': 'CHEST',
                    'allowed_tiles': [],
                    'forbidden_tiles': ['WATER', 'VOID']
                },
                {
                    'entity': 'INSERTER',
                    'allowed_tiles': [],
                    'forbidden_tiles': ['WATER', 'VOID']
                },
            ]
            self.placement_rules.insert_many(rules)

        def _init_constants(self):
            """Initialise les constantes du jeu."""
            constants = [
                {'key': 'CHUNK_SIZE', 'value': 32},
                {'key': 'TILE_SIZE', 'value': 64},
                {'key': 'WORLD_TICK_RATE', 'value': 60},
                {'key': 'NETWORK_TICK_RATE', 'value': 20},
                {'key': 'PLAYER_SPEED', 'value': 5.0},
                {'key': 'PLAYER_VIEW_DISTANCE', 'value': 3},
            ]
            self.constants.insert_many(constants)

        def close(self):
            """Ferme la connexion."""
            if self.client:
                self.client.close()

    # Fonctions utilitaires pour charger la config

    def get_admin_db() -> AdminDB:
        """Retourne l'instance singleton de la DB admin."""
        return AdminDB.get_instance()

    def load_tile_colors() -> Dict[int, tuple]:
        """Charge les couleurs des tiles."""
        db = get_admin_db()
        colors = {}
        for tile in db.tiles.find():
            colors[tile['id']] = tuple(tile['color'])
        return colors

    def load_entity_colors() -> Dict[int, tuple]:
        """Charge les couleurs des entités."""
        db = get_admin_db()
        colors = {}
        for entity in db.entities.find():
            colors[entity['id']] = tuple(entity['color'])
        return colors

    def load_entity_config() -> Dict[str, dict]:
        """Charge la configuration complète des entités."""
        db = get_admin_db()
        config = {}
        for entity in db.entities.find():
            config[entity['name']] = entity
        return config

    def load_item_colors() -> Dict[str, tuple]:
        """Charge les couleurs des items."""
        db = get_admin_db()
        colors = {}
        for item in db.items.find():
            colors[item['name']] = tuple(item['color'])
        return colors

    def load_furnace_recipes() -> Dict[str, dict]:
        """Charge les recettes du four."""
        db = get_admin_db()
        recipes = {}
        for recipe in db.furnace_recipes.find():
            recipes[recipe['input']] = {
                'output': recipe['output'],
                'count': recipe['count'],
                'time': recipe['time']
            }
        return recipes

    def load_assembler_recipes() -> Dict[str, dict]:
        """Charge les recettes d'assemblage."""
        db = get_admin_db()
        recipes = {}
        for recipe in db.assembler_recipes.find():
            recipes[recipe['name']] = {
                'display_name': recipe['display_name'],
                'ingredients': recipe['ingredients'],
                'result': recipe['result'],
                'count': recipe['count'],
                'time': recipe['time']
            }
        return recipes

    def load_placement_rules() -> Dict[str, dict]:
        """Charge les règles de placement."""
        db = get_admin_db()
        rules = {}
        for rule in db.placement_rules.find():
            rules[rule['entity']] = {
                'allowed_tiles': rule['allowed_tiles'],
                'forbidden_tiles': rule['forbidden_tiles']
            }
        return rules

    def load_tiles_by_name() -> Dict[str, dict]:
        """Charge les tiles indexées par nom."""
        db = get_admin_db()
        tiles = {}
        for tile in db.tiles.find():
            tiles[tile['name']] = tile
        return tiles

    def get_resource_for_tile(tile_id: int) -> Optional[str]:
        """Retourne la ressource associée à une tile."""
        db = get_admin_db()
        tile = db.tiles.find_one({'id': tile_id})
        if tile:
            return tile.get('resource')
        return None