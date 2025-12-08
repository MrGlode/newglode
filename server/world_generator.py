import math
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import IntEnum, auto

from shared.constants import CHUNK_SIZE
from shared.tiles import TileType


class SimplexNoise:
    GRAD3 = [
        (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
        (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
        (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1)
    ]

    F2 = 0.5 * (math.sqrt(3.0) - 1.0)
    G2 = (3.0 - math.sqrt(3.0)) / 6.0

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.perm = self._generate_permutation(seed)

    def _generate_permutation(self, seed: int) -> List[int]:
        rng = random.Random(seed)
        perm = list(range(256))
        rng.shuffle(perm)
        return perm + perm

    def _dot2(self, g: Tuple[int, int, int], x: float, y: float) -> float:
        return g[0] * x + g[1] * y

    def noise2d(self, x: float, y: float) -> float:
        s = (x + y) * self.F2
        i = math.floor(x + s)
        j = math.floor(y + s)

        t = (i + j) * self.G2
        X0 = i - t
        Y0 = j - t
        x0 = x - X0
        y0 = y - Y0

        if x0 > y0:
            i1, j1 = 1, 0
        else:
            i1, j1 = 0, 1

        x1 = x0 - i1 + self.G2
        y1 = y0 - j1 + self.G2
        x2 = x0 - 1.0 + 2.0 * self.G2
        y2 = y0 - 1.0 + 2.0 * self.G2

        ii = i & 255
        jj = j & 255

        gi0 = self.perm[ii + self.perm[jj]] % 12
        gi1 = self.perm[ii + i1 + self.perm[jj + j1]] % 12
        gi2 = self.perm[ii + 1 + self.perm[jj + 1]] % 12

        n0 = n1 = n2 = 0.0

        t0 = 0.5 - x0 * x0 - y0 * y0
        if t0 >= 0:
            t0 *= t0
            n0 = t0 * t0 * self._dot2(self.GRAD3[gi0], x0, y0)

        t1 = 0.5 - x1 * x1 - y1 * y1
        if t1 >= 0:
            t1 *= t1
            n1 = t1 * t1 * self._dot2(self.GRAD3[gi1], x1, y1)

        t2 = 0.5 - x2 * x2 - y2 * y2
        if t2 >= 0:
            t2 *= t2
            n2 = t2 * t2 * self._dot2(self.GRAD3[gi2], x2, y2)

        return 70.0 * (n0 + n1 + n2)

    def octave_noise2d(self, x: float, y: float, octaves: int = 4, persistence: float = 0.5,
                       lacunarity: float = 2.0) -> float:
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0

        for _ in range(octaves):
            total += self.noise2d(x * frequency, y * frequency) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= lacunarity

        return total / max_value


class Biome(IntEnum):
    OCEAN = auto()
    LAKE = auto()
    BEACH = auto()
    PLAINS = auto()
    FOREST = auto()
    DESERT = auto()
    SWAMP = auto()
    MOUNTAINS = auto()
    TUNDRA = auto()


@dataclass
class BiomeConfig:
    name: str
    base_tile: TileType
    secondary_tile: Optional[TileType] = None
    secondary_chance: float = 0.0
    tree_density: float = 0.0
    rock_density: float = 0.0
    resources: Dict[TileType, float] = field(default_factory=dict)


# Configuration des biomes
BIOME_CONFIGS: Dict[Biome, BiomeConfig] = {
    Biome.OCEAN: BiomeConfig(
        name="Ocean",
        base_tile=TileType.WATER,
    ),
    Biome.LAKE: BiomeConfig(
        name="Lake",
        base_tile=TileType.WATER,
    ),
    Biome.BEACH: BiomeConfig(
        name="Beach",
        base_tile=TileType.DIRT,
        secondary_tile=TileType.GRASS,
        secondary_chance=0.1,
    ),
    Biome.PLAINS: BiomeConfig(
        name="Plains",
        base_tile=TileType.GRASS,
        secondary_tile=TileType.DIRT,
        secondary_chance=0.05,
        resources={
            TileType.IRON_ORE: 0.008,
            TileType.COPPER_ORE: 0.006,
            TileType.COAL: 0.004,
        }
    ),
    Biome.FOREST: BiomeConfig(
        name="Forest",
        base_tile=TileType.GRASS,
        tree_density=0.3,
        resources={
            TileType.IRON_ORE: 0.005,
            TileType.COPPER_ORE: 0.008,
        }
    ),
    Biome.DESERT: BiomeConfig(
        name="Desert",
        base_tile=TileType.DIRT,
        secondary_tile=TileType.STONE,
        secondary_chance=0.1,
        resources={
            TileType.COPPER_ORE: 0.01,
            TileType.GOLD_ORE: 0.003,
            TileType.BAUXITE_ORE: 0.005,
        }
    ),
    Biome.SWAMP: BiomeConfig(
        name="Swamp",
        base_tile=TileType.GRASS,
        secondary_tile=TileType.WATER,
        secondary_chance=0.15,
        resources={
            TileType.COAL: 0.012,
            TileType.TIN_ORE: 0.006,
        }
    ),
    Biome.MOUNTAINS: BiomeConfig(
        name="Mountains",
        base_tile=TileType.STONE,
        secondary_tile=TileType.DIRT,
        secondary_chance=0.1,
        rock_density=0.2,
        resources={
            TileType.IRON_ORE: 0.015,
            TileType.COAL: 0.01,
            TileType.URANIUM_ORE: 0.002,
            TileType.DIAMOND_ORE: 0.001,
        }
    ),
    Biome.TUNDRA: BiomeConfig(
        name="Tundra",
        base_tile=TileType.STONE,
        secondary_tile=TileType.GRASS,
        secondary_chance=0.2,
        resources={
            TileType.IRON_ORE: 0.01,
            TileType.TIN_ORE: 0.008,
        }
    ),
}


@dataclass
class ResourcePatch:
    center_x: float
    center_y: float
    resource_type: TileType
    radius: float
    richness: float
    shape_seed: int
    noise_strength: float = 0.15  # Force du bruit de forme


class ResourcePatchGenerator:
    def __init__(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)
        self.noise = SimplexNoise(seed + 1000)

        self._patch_cache: Dict[Tuple[int, int], List[ResourcePatch]] = {}

        # Configuration des ressources - patches plus gros et cohérents
        self.resource_configs = {
            TileType.IRON_ORE: {
                'frequency': 0.0005,
                'min_radius': 8,
                'max_radius': 20,
                'min_richness': 0.6,
                'max_richness': 1.0,
                'noise_strength': 0.15,
            },
            TileType.COPPER_ORE: {
                'frequency': 0.0004,
                'min_radius': 8,
                'max_radius': 18,
                'min_richness': 0.5,
                'max_richness': 0.95,
                'noise_strength': 0.15,
            },
            TileType.COAL: {
                'frequency': 0.00035,
                'min_radius': 7,
                'max_radius': 16,
                'min_richness': 0.5,
                'max_richness': 0.9,
                'noise_strength': 0.12,
            },
            TileType.GOLD_ORE: {
                'frequency': 0.00015,
                'min_radius': 4,
                'max_radius': 10,
                'min_richness': 0.4,
                'max_richness': 0.7,
                'noise_strength': 0.2,
            },
            TileType.URANIUM_ORE: {
                'frequency': 0.00008,
                'min_radius': 3,
                'max_radius': 8,
                'min_richness': 0.3,
                'max_richness': 0.6,
                'noise_strength': 0.25,
            },
            TileType.DIAMOND_ORE: {
                'frequency': 0.00004,
                'min_radius': 2,
                'max_radius': 5,
                'min_richness': 0.2,
                'max_richness': 0.5,
                'noise_strength': 0.2,
            },
            TileType.BAUXITE_ORE: {
                'frequency': 0.00025,
                'min_radius': 6,
                'max_radius': 14,
                'min_richness': 0.5,
                'max_richness': 0.8,
                'noise_strength': 0.15,
            },
            TileType.TIN_ORE: {
                'frequency': 0.0003,
                'min_radius': 5,
                'max_radius': 12,
                'min_richness': 0.5,
                'max_richness': 0.85,
                'noise_strength': 0.15,
            }
        }

    def _get_region_key(self, world_x: float, world_y: float, region_size: int = 128) -> Tuple[int, int]:
        return (int(world_x // region_size), int(world_y // region_size))

    def _generate_patches_for_region(self, region_x: int, region_y: int, region_size: int = 128) -> List[ResourcePatch]:
        patches = []
        region_seed = hash((self.seed, region_x, region_y, "patches"))
        rng = random.Random(region_seed)

        world_x = region_x * region_size
        world_y = region_y * region_size

        for resource_type, config in self.resource_configs.items():
            area = region_size * region_size
            expected_patches = config['frequency'] * area

            num_patches = int(expected_patches)
            if rng.random() < (expected_patches - num_patches):
                num_patches += 1

            for _ in range(num_patches):
                patch = ResourcePatch(
                    center_x=world_x + rng.random() * region_size,
                    center_y=world_y + rng.random() * region_size,
                    resource_type=resource_type,
                    radius=rng.uniform(config['min_radius'], config['max_radius']),
                    richness=rng.uniform(config['min_richness'], config['max_richness']),
                    shape_seed=rng.randint(0, 1000000),
                    noise_strength=config.get('noise_strength', 0.15),
                )
                patches.append(patch)

        return patches

    def get_patches_near(self, world_x: float, world_y: float, radius: float = 64) -> List[ResourcePatch]:
        region_size = 128
        patches = []

        for dx in range(-1, 2):
            for dy in range(-1, 2):
                rx = int(world_x // region_size) + dx
                ry = int(world_y // region_size) + dy
                key = (rx, ry)

                if key not in self._patch_cache:
                    self._patch_cache[key] = self._generate_patches_for_region(rx, ry, region_size)

                patches.extend(self._patch_cache[key])

        return patches

    def get_resource_at(self, world_x: float, world_y: float, biome: Biome) -> Optional[TileType]:
        """
        Vérifie si une position contient une ressource.
        En cas de chevauchement, le patch le plus "dominant" gagne.
        """
        if biome in (Biome.OCEAN, Biome.LAKE):
            return None

        patches = self.get_patches_near(world_x, world_y)

        best_patch = None
        best_score = -1.0  # Score = proximité relative au centre (1 = centre, 0 = bord)

        for patch in patches:
            dx = world_x - patch.center_x
            dy = world_y - patch.center_y
            distance = math.sqrt(dx * dx + dy * dy)

            # Bruit de forme pour des bords irréguliers
            shape_noise = self.noise.noise2d(world_x * 0.1, world_y * 0.1)
            effective_radius = patch.radius * (1 + shape_noise * patch.noise_strength)

            if distance < effective_radius:
                # Score : plus on est proche du centre, plus le score est élevé
                score = 1 - (distance / effective_radius)

                if score > best_score:
                    best_score = score
                    best_patch = patch

        # Aucun patch trouvé
        if best_patch is None:
            return None

        # Appliquer la densité pour le patch gagnant
        normalized_dist = 1 - best_score
        density = best_patch.richness * (1 - normalized_dist * 0.7)

        # Petit bruit de détail
        detail_noise = self.noise.noise2d(world_x * 0.5, world_y * 0.5)
        density *= (0.85 + 0.15 * detail_noise)

        if random.Random(hash((world_x, world_y, best_patch.shape_seed))).random() < density:
            return best_patch.resource_type

        return None


class WorldGenerator:

    def __init__(self, seed: int):
        self.seed = seed

        self.elevation_noise = SimplexNoise(seed)
        self.moisture_noise = SimplexNoise(seed + 1)
        self.temperature_noise = SimplexNoise(seed + 2)
        self.detail_noise = SimplexNoise(seed + 3)

        self.resource_generator = ResourcePatchGenerator(seed)

        # Paramètres terrain
        self.sea_level = -0.15
        self.beach_threshold = 0.05
        self.mountain_threshold = 0.55

        # Échelles de bruit
        self.elevation_scale = 0.004
        self.moisture_scale = 0.012
        self.temperature_scale = 0.008
        self.detail_scale = 0.08

    def get_elevation(self, world_x: float, world_y: float) -> float:
        base = self.elevation_noise.octave_noise2d(
            world_x * self.elevation_scale,
            world_y * self.elevation_scale,
            octaves=6,
            persistence=0.5,
            lacunarity=2.0
        )

        # Détail réduit pour moins de fragmentation
        detail = self.detail_noise.noise2d(
            world_x * self.detail_scale,
            world_y * self.detail_scale
        ) * 0.03

        elevation = base + detail

        # Zone de départ garantie
        dist_from_spawn = math.sqrt(world_x * world_x + world_y * world_y)
        spawn_radius = 250
        if dist_from_spawn < spawn_radius:
            spawn_boost = 0.5 * (1 - dist_from_spawn / spawn_radius) ** 2
            elevation += spawn_boost

        return elevation

    def get_moisture(self, world_x: float, world_y: float) -> float:
        noise = self.moisture_noise.octave_noise2d(
            world_x * self.moisture_scale,
            world_y * self.moisture_scale,
            octaves=4,
            persistence=0.6
        )
        return (noise + 1) / 2

    def get_temperature(self, world_x: float, world_y: float) -> float:
        noise = self.temperature_noise.octave_noise2d(
            world_x * self.temperature_scale,
            world_y * self.temperature_scale,
            octaves=3,
            persistence=0.5
        )
        return (noise + 1) / 2

    def get_biome(self, elevation: float, moisture: float, temperature: float) -> Biome:
        if elevation < self.sea_level - 0.15:
            return Biome.OCEAN

        if elevation < self.sea_level:
            return Biome.LAKE

        if elevation < self.sea_level + self.beach_threshold:
            return Biome.BEACH

        if elevation > self.mountain_threshold:
            if temperature < 0.3:
                return Biome.TUNDRA
            return Biome.MOUNTAINS

        if moisture > 0.7:
            if temperature < 0.4:
                return Biome.SWAMP
            return Biome.FOREST

        if moisture < 0.3:
            if temperature > 0.6:
                return Biome.DESERT
            return Biome.PLAINS

        if temperature < 0.3:
            return Biome.TUNDRA

        return Biome.PLAINS

    def get_tile_at(self, world_x: float, world_y: float) -> TileType:
        elevation = self.get_elevation(world_x, world_y)
        moisture = self.get_moisture(world_x, world_y)
        temperature = self.get_temperature(world_x, world_y)
        biome = self.get_biome(elevation, moisture, temperature)

        config = BIOME_CONFIGS[biome]

        # Vérifier les ressources
        resource = self.resource_generator.get_resource_at(world_x, world_y, biome)
        if resource:
            return resource

        tile = config.base_tile

        if config.secondary_tile and config.secondary_chance > 0:
            detail = self.detail_noise.noise2d(world_x * 0.2, world_y * 0.2)
            if (detail + 1) / 2 < config.secondary_chance:
                tile = config.secondary_tile

        return tile

    def generate_chunk_tiles(self, cx: int, cy: int) -> List[List[TileType]]:
        tiles = [[TileType.VOID] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]

        base_x = cx * CHUNK_SIZE
        base_y = cy * CHUNK_SIZE

        for local_y in range(CHUNK_SIZE):
            for local_x in range(CHUNK_SIZE):
                world_x = base_x + local_x
                world_y = base_y + local_y
                tiles[local_y][local_x] = self.get_tile_at(world_x, world_y)

        return tiles

    def get_spawn_point(self) -> Tuple[float, float]:
        for radius in range(0, 100, 5):
            for angle in range(0, 360, 15):
                x = radius * math.cos(math.radians(angle))
                y = radius * math.sin(math.radians(angle))

                elevation = self.get_elevation(x, y)
                if self.sea_level + 0.1 < elevation < self.mountain_threshold:
                    return x, y

        return 0.0, 0.0


_generator_instance: Optional[WorldGenerator] = None


def get_world_generator(seed: int) -> WorldGenerator:
    global _generator_instance

    if _generator_instance is None or _generator_instance.seed != seed:
        _generator_instance = WorldGenerator(seed)

    return _generator_instance