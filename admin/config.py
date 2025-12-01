"""
GameConfig - Configuration centralisée du jeu.
Charge les données depuis MongoDB au démarrage.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TileConfig:
    id: int
    name: str
    color: Tuple[int, int, int]
    walkable: bool
    resource: Optional[str]


@dataclass
class EntityConfig:
    id: int
    name: str
    display_name: str
    color: Tuple[int, int, int]
    has_direction: bool
    buffer_size: int = 0
    input_buffer_size: int = 0
    output_buffer_size: int = 0
    cooldown: int = 0
    speed: float = 0.0
    animation_speed: float = 0.0


@dataclass
class ItemConfig:
    name: str
    display_name: str
    color: Tuple[int, int, int]
    category: str


@dataclass
class FurnaceRecipe:
    input: str
    output: str
    count: int
    time: int


@dataclass
class AssemblerRecipe:
    name: str
    display_name: str
    ingredients: Dict[str, int]
    result: str
    count: int
    time: int


@dataclass
class PlacementRule:
    entity: str
    allowed_tiles: List[str]
    forbidden_tiles: List[str]


class GameConfig:
    """Configuration globale du jeu, chargée depuis MongoDB."""

    _instance: Optional['GameConfig'] = None

    def __init__(self):
        # Tiles
        self.tiles: Dict[int, TileConfig] = {}
        self.tiles_by_name: Dict[str, TileConfig] = {}
        self.tile_colors: Dict[int, Tuple[int, int, int]] = {}

        # Entités
        self.entities: Dict[int, EntityConfig] = {}
        self.entities_by_name: Dict[str, EntityConfig] = {}
        self.entity_colors: Dict[int, Tuple[int, int, int]] = {}

        # Items
        self.items: Dict[str, ItemConfig] = {}
        self.item_colors: Dict[str, Tuple[int, int, int]] = {}

        # Recettes
        self.furnace_recipes: Dict[str, FurnaceRecipe] = {}
        self.assembler_recipes: Dict[str, AssemblerRecipe] = {}

        # Règles de placement
        self.placement_rules: Dict[str, PlacementRule] = {}

        # Constantes
        self.constants: Dict[str, any] = {}

        # Flag de chargement
        self._loaded = False

    @classmethod
    def get_instance(cls) -> 'GameConfig':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_from_mongodb(self, mongo_uri: str = None):
        """Charge toute la configuration depuis MongoDB."""
        from admin.database import AdminDB

        db = AdminDB.get_instance(mongo_uri)
        db.init_default_data()

        self._load_tiles(db)
        self._load_entities(db)
        self._load_items(db)
        self._load_furnace_recipes(db)
        self._load_assembler_recipes(db)
        self._load_placement_rules(db)
        self._load_constants(db)

        self._loaded = True
        print(f"Configuration chargée: {len(self.tiles)} tiles, {len(self.entities)} entités, "
              f"{len(self.items)} items, {len(self.furnace_recipes)} recettes four, "
              f"{len(self.assembler_recipes)} recettes assembleur")

    def load_defaults(self):
        """Charge les valeurs par défaut (sans MongoDB)."""
        self._load_default_tiles()
        self._load_default_entities()
        self._load_default_items()
        self._load_default_furnace_recipes()
        self._load_default_assembler_recipes()
        self._load_default_placement_rules()
        self._load_default_constants()

        self._loaded = True
        print("Configuration par défaut chargée (sans MongoDB)")

    def _load_tiles(self, db):
        for doc in db.tiles.find():
            tile = TileConfig(
                id=doc['id'],
                name=doc['name'],
                color=tuple(doc['color']),
                walkable=doc['walkable'],
                resource=doc.get('resource')
            )
            self.tiles[tile.id] = tile
            self.tiles_by_name[tile.name] = tile
            self.tile_colors[tile.id] = tile.color

    def _load_entities(self, db):
        for doc in db.entities.find():
            entity = EntityConfig(
                id=doc['id'],
                name=doc['name'],
                display_name=doc['display_name'],
                color=tuple(doc['color']),
                has_direction=doc['has_direction'],
                buffer_size=doc.get('buffer_size', 0),
                input_buffer_size=doc.get('input_buffer_size', 0),
                output_buffer_size=doc.get('output_buffer_size', 0),
                cooldown=doc.get('cooldown', 0),
                speed=doc.get('speed', 0.0),
                animation_speed=doc.get('animation_speed', 0.0)
            )
            self.entities[entity.id] = entity
            self.entities_by_name[entity.name] = entity
            self.entity_colors[entity.id] = entity.color

    def _load_items(self, db):
        for doc in db.items.find():
            item = ItemConfig(
                name=doc['name'],
                display_name=doc['display_name'],
                color=tuple(doc['color']),
                category=doc['category']
            )
            self.items[item.name] = item
            self.item_colors[item.name] = item.color

    def _load_furnace_recipes(self, db):
        for doc in db.furnace_recipes.find():
            recipe = FurnaceRecipe(
                input=doc['input'],
                output=doc['output'],
                count=doc['count'],
                time=doc['time']
            )
            self.furnace_recipes[recipe.input] = recipe

    def _load_assembler_recipes(self, db):
        for doc in db.assembler_recipes.find():
            recipe = AssemblerRecipe(
                name=doc['name'],
                display_name=doc['display_name'],
                ingredients=doc['ingredients'],
                result=doc['result'],
                count=doc['count'],
                time=doc['time']
            )
            self.assembler_recipes[recipe.name] = recipe

    def _load_placement_rules(self, db):
        for doc in db.placement_rules.find():
            rule = PlacementRule(
                entity=doc['entity'],
                allowed_tiles=doc['allowed_tiles'],
                forbidden_tiles=doc['forbidden_tiles']
            )
            self.placement_rules[rule.entity] = rule

    def _load_constants(self, db):
        for doc in db.constants.find():
            self.constants[doc['key']] = doc['value']

    # Valeurs par défaut (fallback sans MongoDB)

    def _load_default_tiles(self):
        defaults = [
            (0, 'VOID', (20, 20, 30), False, None),
            (1, 'GRASS', (34, 139, 34), True, None),
            (2, 'DIRT', (139, 90, 43), True, None),
            (3, 'STONE', (128, 128, 128), True, None),
            (4, 'WATER', (30, 144, 255), False, None),
            (5, 'IRON_ORE', (160, 160, 180), True, 'iron_ore'),
            (6, 'COPPER_ORE', (184, 115, 51), True, 'copper_ore'),
            (7, 'GOLD_ORE', (255, 215, 0), True, 'gold_ore'),
            (8, 'DIAMOND_ORE', (185, 242, 255), True, 'diamond'),
            (9, 'BAUXITE_ORE', (205, 133, 63), True, 'bauxite'),
            (10, 'TIN_ORE', (192, 192, 192), True, 'tin_ore'),
            (11, 'URANIUM_ORE', (100, 255, 100), True, 'uranium_ore'),
            (12, 'COAL', (40, 40, 40), True, 'coal'),
        ]
        for id, name, color, walkable, resource in defaults:
            tile = TileConfig(id, name, color, walkable, resource)
            self.tiles[id] = tile
            self.tiles_by_name[name] = tile
            self.tile_colors[id] = color

    def _load_default_entities(self):
        defaults = [
            (0, 'PLAYER', 'Joueur', (255, 255, 255), False, 0, 0, 0, 0, 5.0, 0.0),
            (1, 'CONVEYOR', 'Convoyeur', (255, 200, 0), True, 3, 0, 0, 0, 0.02, 0.0),
            (2, 'MINER', 'Foreuse', (200, 100, 50), True, 10, 0, 0, 60, 0.0, 0.0),
            (3, 'FURNACE', 'Four', (255, 100, 0), True, 0, 10, 10, 120, 0.0, 0.0),
            (4, 'ASSEMBLER', 'Assembleur', (100, 100, 200), True, 0, 10, 10, 0, 0.0, 0.0),
            (5, 'CHEST', 'Coffre', (139, 90, 43), False, 50, 0, 0, 0, 0.0, 0.0),
            (6, 'INSERTER', 'Inserter', (150, 150, 150), True, 0, 0, 0, 20, 0.0, 0.05),
        ]
        for id, name, display, color, has_dir, buf, in_buf, out_buf, cd, spd, anim in defaults:
            entity = EntityConfig(id, name, display, color, has_dir, buf, in_buf, out_buf, cd, spd, anim)
            self.entities[id] = entity
            self.entities_by_name[name] = entity
            self.entity_colors[id] = color

    def _load_default_items(self):
        defaults = [
            ('iron_ore', 'Minerai de fer', (160, 160, 180), 'raw'),
            ('copper_ore', 'Minerai de cuivre', (184, 115, 51), 'raw'),
            ('coal', 'Charbon', (40, 40, 40), 'raw'),
            ('iron_plate', 'Plaque de fer', (200, 200, 210), 'plate'),
            ('copper_plate', 'Plaque de cuivre', (210, 140, 80), 'plate'),
            ('carbon', 'Carbone', (60, 60, 60), 'plate'),
            ('copper_wire', 'Fil de cuivre', (230, 160, 100), 'intermediate'),
            ('iron_gear', 'Engrenage', (180, 180, 190), 'intermediate'),
            ('circuit', 'Circuit', (50, 150, 50), 'intermediate'),
            ('advanced_circuit', 'Circuit avancé', (150, 50, 50), 'intermediate'),
            ('automation_science', 'Pack science auto.', (255, 100, 100), 'science'),
        ]
        for name, display, color, category in defaults:
            item = ItemConfig(name, display, color, category)
            self.items[name] = item
            self.item_colors[name] = color

    def _load_default_furnace_recipes(self):
        defaults = [
            ('iron_ore', 'iron_plate', 1, 120),
            ('copper_ore', 'copper_plate', 1, 120),
            ('coal', 'carbon', 1, 60),
        ]
        for input, output, count, time in defaults:
            recipe = FurnaceRecipe(input, output, count, time)
            self.furnace_recipes[input] = recipe

    def _load_default_assembler_recipes(self):
        defaults = [
            ('iron_gear', 'Engrenage', {'iron_plate': 2}, 'iron_gear', 1, 60),
            ('copper_wire', 'Fil de cuivre', {'copper_plate': 1}, 'copper_wire', 2, 30),
            ('circuit', 'Circuit', {'iron_plate': 1, 'copper_wire': 3}, 'circuit', 1, 90),
            ('automation_science', 'Pack science', {'iron_gear': 1, 'circuit': 1}, 'automation_science', 1, 120),
        ]
        for name, display, ingredients, result, count, time in defaults:
            recipe = AssemblerRecipe(name, display, ingredients, result, count, time)
            self.assembler_recipes[name] = recipe

    def _load_default_placement_rules(self):
        defaults = [
            ('MINER', ['IRON_ORE', 'COPPER_ORE', 'COAL'], []),
            ('FURNACE', ['GRASS', 'DIRT', 'STONE'], ['WATER']),
            ('ASSEMBLER', ['GRASS', 'DIRT', 'STONE'], ['WATER']),
            ('CONVEYOR', [], ['WATER', 'VOID']),
            ('CHEST', [], ['WATER', 'VOID']),
            ('INSERTER', [], ['WATER', 'VOID']),
        ]
        for entity, allowed, forbidden in defaults:
            rule = PlacementRule(entity, allowed, forbidden)
            self.placement_rules[entity] = rule

    def _load_default_constants(self):
        self.constants = {
            'CHUNK_SIZE': 32,
            'TILE_SIZE': 64,
            'WORLD_TICK_RATE': 60,
            'NETWORK_TICK_RATE': 20,
            'PLAYER_SPEED': 5.0,
            'PLAYER_VIEW_DISTANCE': 3,
        }

    # Méthodes utilitaires

    def get_tile_color(self, tile_id: int) -> Tuple[int, int, int]:
        """Retourne la couleur d'une tile."""
        return self.tile_colors.get(tile_id, (100, 100, 100))

    def get_entity_color(self, entity_id: int) -> Tuple[int, int, int]:
        """Retourne la couleur d'une entité."""
        return self.entity_colors.get(entity_id, (200, 200, 200))

    def get_item_color(self, item_name: str) -> Tuple[int, int, int]:
        """Retourne la couleur d'un item."""
        return self.item_colors.get(item_name, (150, 150, 150))

    def get_resource_for_tile(self, tile_id: int) -> Optional[str]:
        """Retourne la ressource associée à une tile."""
        tile = self.tiles.get(tile_id)
        if tile:
            return tile.resource
        return None

    def can_place_entity(self, entity_name: str, tile_name: str) -> bool:
        """Vérifie si une entité peut être placée sur une tile."""
        rule = self.placement_rules.get(entity_name)
        if not rule:
            return True

        # Vérifie les tiles interdites
        if tile_name in rule.forbidden_tiles:
            return False

        # Si allowed_tiles est vide, tout est permis (sauf forbidden)
        if not rule.allowed_tiles:
            return True

        # Sinon, doit être dans allowed_tiles
        return tile_name in rule.allowed_tiles

    def get_entity_display_name(self, entity_id: int) -> str:
        """Retourne le nom d'affichage d'une entité."""
        entity = self.entities.get(entity_id)
        if entity:
            return entity.display_name
        return "Inconnu"

    def get_assembler_recipe_names(self) -> List[str]:
        """Retourne la liste des noms de recettes assembleur."""
        return list(self.assembler_recipes.keys())


# Fonction globale pour accéder à la config
def get_config() -> GameConfig:
    """Retourne l'instance singleton de la configuration."""
    return GameConfig.get_instance()