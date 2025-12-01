# Factorio-like - Documentation Technique

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Protocole réseau](#protocole-réseau)
4. [Système de chunks](#système-de-chunks)
5. [Entités et simulation](#entités-et-simulation)
6. [Rendu client](#rendu-client)
7. [Optimisations](#optimisations)
8. [Guide d'extension](#guide-dextension)

---

## Vue d'ensemble

### Description

Factorio-like est un jeu multijoueur 2D d'automatisation industrielle inspiré de [Factorio](https://factorio.com/) et [Shapez](https://shapez.io/). Les joueurs construisent des chaînes de production pour extraire, transformer et assembler des ressources.

### Technologies utilisées

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Langage | Python | 3.9+ |
| Rendu | Pygame / Pygame-ce | 2.x |
| Sérialisation | MessagePack | 1.x |
| Base de données | SQLite | 3.x |
| Réseau | TCP Sockets | - |

### Fonctionnalités principales

- **Multijoueur** : Serveur autoritaire, clients légers
- **Monde infini** : Génération procédurale par chunks
- **Simulation** : Miners, convoyeurs, fours, inserters, assembleurs
- **Persistance** : Sauvegarde SQLite (joueurs, chunks, entités)
- **Interface** : Minimap, inspection des machines, placement avec preview

---

## Architecture

### Structure des fichiers

```
factorio-like/
├── client/
│   ├── __init__.py
│   ├── main.py           # Point d'entrée client
│   ├── game.py           # Boucle principale, état du jeu
│   ├── renderer.py       # Rendu Pygame (monde, UI, minimap)
│   ├── network.py        # Communication serveur
│   ├── input_handler.py  # Gestion clavier/souris
│   └── world_view.py     # Vue locale du monde (chunks, entités)
├── server/
│   ├── __init__.py
│   ├── main.py           # Point d'entrée serveur, gestion clients
│   ├── world.py          # État du monde, joueurs, entités
│   ├── chunk.py          # Structure et génération des chunks
│   ├── simulation.py     # Logique des machines
│   └── persistence.py    # Sauvegarde SQLite
├── shared/
│   ├── __init__.py
│   ├── constants.py      # Constantes partagées
│   ├── protocol.py       # Messages réseau
│   ├── tiles.py          # Types de tiles
│   └── entities.py       # Types d'entités
└── saves/
    └── world.db          # Base de données SQLite
```

### Modèle client-serveur

```
┌─────────────┐         TCP          ┌─────────────┐
│   Client    │◄─────────────────────►│   Serveur   │
│  (Pygame)   │    MessagePack        │ (Autoritaire)│
└─────────────┘                       └─────────────┘
      │                                      │
      ▼                                      ▼
┌─────────────┐                       ┌─────────────┐
│ world_view  │                       │    World    │
│ (copie locale)                      │ (état réel) │
└─────────────┘                       └─────────────┘
```

**Principes** :
- Le serveur est **autoritaire** : il valide toutes les actions
- Le client ne fait que **prédire et afficher**
- Les modifications passent toujours par le serveur

> 📚 Référence : [Client-Server Game Architecture](https://www.gabrielgambetta.com/client-server-game-architecture.html)

---

## Protocole réseau

### Format des messages

Chaque message suit le format :

```
┌──────────────┬────────────────────┐
│ Taille (2B)  │ Payload MessagePack │
│ Big-endian   │ {t: type, d: data} │
└──────────────┴────────────────────┘
```

**Implémentation** (`shared/protocol.py`) :

```python
import msgpack
import struct

def pack_message(msg_type: int, data: dict) -> bytes:
    payload = msgpack.packb({'t': msg_type, 'd': data}, use_bin_type=True)
    return struct.pack('>H', len(payload)) + payload

def unpack_message(buffer: bytes) -> tuple[dict | None, bytes]:
    if len(buffer) < 2:
        return None, buffer
    
    msg_len = struct.unpack('>H', buffer[:2])[0]
    if len(buffer) < 2 + msg_len:
        return None, buffer
    
    payload = msgpack.unpackb(buffer[2:2 + msg_len], raw=False)
    return payload, buffer[2 + msg_len:]
```

### Types de messages

| Code | Nom | Direction | Description |
|------|-----|-----------|-------------|
| 1 | MSG_AUTH | C→S | Authentification joueur |
| 2 | MSG_AUTH_RESPONSE | S→C | Confirmation + position initiale |
| 3 | MSG_PLAYER_JOIN | S→C | Nouveau joueur connecté |
| 4 | MSG_PLAYER_LEAVE | S→C | Joueur déconnecté |
| 5 | MSG_PLAYER_MOVE | C↔S | Mise à jour position |
| 6 | MSG_CHUNK_REQUEST | C→S | Demande d'un chunk |
| 7 | MSG_CHUNK_DATA | S→C | Données d'un chunk |
| 8 | MSG_ENTITY_UPDATE | S→C | Mise à jour entité |
| 9 | MSG_ENTITY_ADD | S→C | Nouvelle entité |
| 10 | MSG_ENTITY_REMOVE | S→C | Suppression entité |
| 11 | MSG_PLAYER_ACTION | C→S | Action (build/destroy/configure) |
| 13 | MSG_SYNC | C↔S | Synchronisation temps |

### Optimisations réseau

- **TCP_NODELAY** : Désactive l'algorithme de Nagle pour réduire la latence
- **Tick rate séparé** : Monde à 60 UPS, réseau à 20 Hz
- **Delta compression** : Seules les entités modifiées sont envoyées

> 📚 Référence : [MessagePack](https://msgpack.org/)

---

## Système de chunks

### Structure

Le monde est divisé en **chunks** de 32×32 tiles.

```python
@dataclass
class Chunk:
    cx: int  # Coordonnées chunk
    cy: int
    tiles: List[List[TileType]]  # 32x32 tiles
    entities: Dict[int, Entity]   # Entités dans ce chunk
    dirty: bool = False           # Modifié depuis sauvegarde
```

### Génération procédurale

Chaque chunk est généré à partir d'un **seed** unique :

```python
def generate(self, world_seed: int):
    chunk_seed = hash((world_seed, self.cx, self.cy))
    rng = random.Random(chunk_seed)
    
    for y in range(CHUNK_SIZE):
        for x in range(CHUNK_SIZE):
            roll = rng.random()
            if roll < 0.02:
                self.tiles[y][x] = TileType.IRON_ORE
            elif roll < 0.04:
                self.tiles[y][x] = TileType.COPPER_ORE
            # ... etc
```

**Avantages** :
- Génération **déterministe** (même seed = même monde)
- Génération **à la demande** (lazy loading)
- **Infini** dans toutes les directions

### Conversion coordonnées

```python
def world_to_chunk(x: float, y: float) -> Tuple[int, int, int, int]:
    """Retourne (chunk_x, chunk_y, local_x, local_y)"""
    cx = int(x // CHUNK_SIZE)
    cy = int(y // CHUNK_SIZE)
    lx = int(x % CHUNK_SIZE)
    ly = int(y % CHUNK_SIZE)
    return cx, cy, lx, ly
```

> 📚 Référence : [Chunk-based World Storage](https://minecraft.fandom.com/wiki/Chunk)

---

## Entités et simulation

### Types d'entités

```python
class EntityType(IntEnum):
    PLAYER = 0
    CONVEYOR = 1
    MINER = 2
    FURNACE = 3
    ASSEMBLER = 4
    CHEST = 5
    INSERTER = 6
```

### Structure d'une entité

```python
@dataclass
class Entity:
    id: int
    entity_type: EntityType
    x: float
    y: float
    direction: Direction = Direction.NORTH
    data: Dict[str, Any] = field(default_factory=dict)
```

Le champ `data` contient l'état spécifique à chaque type :

| Type | Champs data |
|------|-------------|
| MINER | `output`, `cooldown` |
| CONVEYOR | `items` (avec `progress`) |
| FURNACE | `input`, `output`, `cooldown` |
| INSERTER | `held_item`, `progress`, `cooldown` |
| ASSEMBLER | `input`, `output`, `recipe`, `cooldown` |
| CHEST | `items` |

### Boucle de simulation

Le serveur exécute la simulation à **60 UPS** (Updates Per Second) :

```python
def world_loop(self):
    last_time = time.perf_counter()
    accumulator = 0.0

    while self.running:
        current_time = time.perf_counter()
        frame_time = current_time - last_time
        last_time = current_time
        accumulator += frame_time

        while accumulator >= WORLD_TICK_INTERVAL:
            self.simulation.tick()
            
            # Broadcast entités modifiées
            for entity in self.simulation.get_dirty_entities():
                cx, cy, _, _ = self.world.world_to_chunk(entity.x, entity.y)
                self.broadcast_to_chunk_subscribers(
                    (cx, cy), MSG_ENTITY_UPDATE, entity.to_dict()
                )
            
            accumulator -= WORLD_TICK_INTERVAL

        time.sleep(0.001)
```

> 📚 Référence : [Fix Your Timestep!](https://gafferongames.com/post/fix_your_timestep/)

### Simulation des machines

#### Miner (Foreuse)

```python
def update_miner(self, entity: Entity):
    # 1. Gère le cooldown
    cooldown = entity.data.get('cooldown', 0)
    if cooldown > 0:
        entity.data['cooldown'] = cooldown - 1
    
    output = entity.data.get('output', [])
    
    # 2. Éjecte vers l'entité devant
    if output:
        dx, dy = self.direction_to_delta(entity.direction)
        target = self.world.get_entity_at(entity.x + dx, entity.y + dy)
        if target and self.can_insert_into(target):
            self.insert_item_into(target, output.pop(0))
            self.mark_dirty(entity)
            self.mark_dirty(target)
    
    # 3. Extrait si cooldown terminé
    if cooldown <= 0:
        tile = self.world.get_tile(entity.x, entity.y)
        if tile in resource_map and len(output) < 10:
            output.append({'item': resource_map[tile]})
            entity.data['cooldown'] = 60  # 1 seconde
            self.mark_dirty(entity)
```

#### Conveyor (Convoyeur)

Les items sur un convoyeur ont une `progress` de 0.0 à 1.0 :

```python
def update_conveyor(self, entity: Entity):
    items = entity.data.get('items', [])
    speed = 0.02  # Tiles par tick
    
    for item in items:
        item['progress'] += speed
        
        if item['progress'] >= 1.0:
            # Transfert à l'entité suivante
            target = self.get_next_entity(entity)
            if target and self.can_insert_into(target):
                self.insert_item_into(target, item)
                items.remove(item)
            else:
                item['progress'] = 0.99  # Bloqué
```

#### Inserter

L'inserter prend **derrière** lui et dépose **devant** :

```
[Source] ← [Inserter→] → [Destination]
```

```python
def update_inserter(self, entity: Entity):
    dx, dy = self.direction_to_delta(entity.direction)
    
    source = self.world.get_entity_at(entity.x - dx, entity.y - dy)
    dest = self.world.get_entity_at(entity.x + dx, entity.y + dy)
    
    # Animation de transport
    if entity.data.get('held_item'):
        entity.data['progress'] += 0.05
        if entity.data['progress'] >= 1.0:
            self.insert_item_into(dest, entity.data['held_item'])
            entity.data['held_item'] = None
    else:
        # Prend un item si destination disponible
        if source and dest and self.can_insert_into(dest):
            item = self.extract_item_from(source)
            if item:
                entity.data['held_item'] = item
                entity.data['progress'] = 0.0
```

#### Assembler

Combine des items selon une **recette** :

```python
recipes = {
    'iron_gear': {
        'ingredients': {'iron_plate': 2},
        'result': 'iron_gear',
        'count': 1,
        'time': 60
    },
    'circuit': {
        'ingredients': {'iron_plate': 1, 'copper_wire': 3},
        'result': 'circuit',
        'count': 1,
        'time': 90
    },
}
```

---

## Rendu client

### Pipeline de rendu

```python
def render(self, game: 'Game'):
    self._chunks_rebuilt_this_frame = 0
    
    self.screen.fill((20, 20, 30))     # 1. Clear
    self.render_world(game)             # 2. Tiles (chunks cachés)
    self.render_entities(game)          # 3. Machines
    self.render_players(game)           # 4. Joueurs
    self.render_cursor(game)            # 5. Curseur construction
    self.render_minimap(game)           # 6. Minimap
    self.render_ui(game)                # 7. Interface
    
    if game.inspected_entity:
        self.render_inspection_panel(game)  # 8. Panneau inspection
    
    if game.show_debug:
        self.render_debug(game)         # 9. Debug (F3)
    
    pygame.display.flip()
```

### Système de coordonnées

```python
def world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
    """Monde → Écran"""
    rel_x = world_x - self.world_view.camera_x
    rel_y = world_y - self.world_view.camera_y
    
    screen_x = rel_x * self.tile_size + self.screen.get_width() // 2
    screen_y = rel_y * self.tile_size + self.screen.get_height() // 2
    
    return int(screen_x), int(screen_y)

def screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
    """Écran → Monde"""
    rel_x = screen_x - self.screen.get_width() // 2
    rel_y = screen_y - self.screen.get_height() // 2
    
    world_x = rel_x / self.tile_size + self.world_view.camera_x + 0.5
    world_y = rel_y / self.tile_size + self.world_view.camera_y + 0.5
    
    return world_x, world_y
```

### Cache des chunks

Chaque chunk est pré-rendu dans une surface Pygame :

```python
def get_chunk_surface(self, cx: int, cy: int) -> pygame.Surface:
    if (cx, cy) not in self._chunk_surfaces:
        chunk = self.world_view.chunks.get((cx, cy))
        if not chunk:
            return None

        # Toujours 32 pixels/tile (taille de base)
        surface = pygame.Surface((32 * 32, 32 * 32))
        
        for ty in range(32):
            for tx in range(32):
                tile_type = chunk['tiles'][ty][tx]
                color = self.TILE_COLORS.get(tile_type)
                x, y = tx * 32, ty * 32
                surface.fill(color, (x, y, 32, 32))
                # Bordure
                darker = tuple(max(0, c - 30) for c in color)
                pygame.draw.rect(surface, darker, (x, y, 32, 32), 1)
        
        self._chunk_surfaces[(cx, cy)] = surface
    
    return self._chunk_surfaces[(cx, cy)]
```

### Zoom avec cache scalé

Pour le zoom, on scale les surfaces cachées :

```python
def render_world(self, game: 'Game'):
    # Invalide le cache scalé si zoom changé
    if self._scaled_tile_size != self.tile_size:
        self._scaled_cache.clear()
        self._scaled_tile_size = self.tile_size
    
    for cx, cy in visible_chunks:
        surface = self.get_chunk_surface(cx, cy)
        
        # Scale avec cache si nécessaire
        if self.tile_size != 32:
            if (cx, cy) not in self._scaled_cache:
                target_size = 32 * self.tile_size
                self._scaled_cache[(cx, cy)] = pygame.transform.scale(
                    surface, (target_size, target_size)
                )
            surface = self._scaled_cache[(cx, cy)]
        
        self.screen.blit(surface, (screen_x, screen_y))
```

> 📚 Référence : [Pygame Display](https://www.pygame.org/docs/ref/display.html)

---

## Optimisations

### Résumé des optimisations

| Domaine | Technique | Gain |
|---------|-----------|------|
| Rendu | Cache chunks | ~100x moins de draw calls |
| Rendu | Cache zoom scalé | Pas de freeze au zoom |
| Réseau | MessagePack | ~50% plus compact que JSON |
| Réseau | TCP_NODELAY | Latence réduite |
| Réseau | Tick rate 20Hz | 3x moins de messages |
| Simulation | Dirty tracking | Broadcast uniquement si changement |
| Minimap | Échantillonnage | Affiche jusqu'à 256x256 tiles |

### Dirty tracking

Seules les entités modifiées sont broadcastées :

```python
class Simulation:
    def __init__(self, world: World):
        self.world = world
        self.dirty_entities: Set[int] = set()
    
    def mark_dirty(self, entity: Entity):
        self.dirty_entities.add(entity.id)
    
    def tick(self):
        self.dirty_entities.clear()
        # ... simulation ...
    
    def get_dirty_entities(self) -> List[Entity]:
        return [self.world.entities[id] for id in self.dirty_entities 
                if id in self.world.entities]
```

### Interpolation joueurs

Les autres joueurs sont interpolés pour un mouvement fluide :

```python
def update_players_interpolation(self, dt: float):
    speed = 10.0
    
    for player in self.other_players.values():
        dx = player['target_x'] - player['x']
        dy = player['target_y'] - player['y']
        
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            player['x'] = player['target_x']
            player['y'] = player['target_y']
        else:
            player['x'] += dx * min(1.0, speed * dt)
            player['y'] += dy * min(1.0, speed * dt)
```

> 📚 Référence : [Entity Interpolation](https://www.gabrielgambetta.com/entity-interpolation.html)

---

## Guide d'extension

### Ajouter un nouveau type de tile

1. **Définir le type** (`shared/tiles.py`) :
```python
class TileType(IntEnum):
    # ...
    URANIUM_ORE = 11
```

2. **Ajouter la couleur** (`client/renderer.py`) :
```python
TILE_COLORS = {
    # ...
    TileType.URANIUM_ORE: (100, 255, 100),
}
```

3. **Modifier la génération** (`server/chunk.py`) :
```python
if roll < 0.01:
    self.tiles[y][x] = TileType.URANIUM_ORE
```

### Ajouter une nouvelle entité

1. **Définir le type** (`shared/entities.py`) :
```python
class EntityType(IntEnum):
    # ...
    SPLITTER = 7
```

2. **Ajouter la couleur** (`client/renderer.py`) :
```python
ENTITY_COLORS = {
    # ...
    EntityType.SPLITTER: (200, 200, 50),
}
```

3. **Implémenter la logique** (`server/simulation.py`) :
```python
def update_entity(self, entity: Entity):
    # ...
    elif entity.entity_type == EntityType.SPLITTER:
        self.update_splitter(entity)

def update_splitter(self, entity: Entity):
    # Logique du splitter
    pass
```

4. **Ajouter à l'UI** (`client/renderer.py` et `client/input_handler.py`)

### Ajouter une nouvelle recette

Dans `server/simulation.py`, méthode `update_assembler` :

```python
recipes = {
    # ...
    'advanced_circuit': {
        'ingredients': {'circuit': 2, 'copper_wire': 4},
        'result': 'advanced_circuit',
        'count': 1,
        'time': 180
    },
}
```

### Ajouter une action joueur

1. **Définir l'action** (`shared/protocol.py`) :
```python
ACTION_ROTATE = 3
```

2. **Envoyer depuis le client** (`client/network.py`) :
```python
def send_rotate(self, entity_id: int):
    self.send(MSG_PLAYER_ACTION, {
        'action': ACTION_ROTATE,
        'entity_id': entity_id,
    })
```

3. **Gérer côté serveur** (`server/main.py`) :
```python
elif action == ACTION_ROTATE:
    entity = self.world.entities.get(data['entity_id'])
    if entity:
        entity.direction = Direction((entity.direction + 1) % 4)
        # Broadcast...
```

---

## Lancement

### Serveur

```bash
cd factorio-like
python -m server.main
```

### Client

```bash
cd factorio-like
python -m client.main
```

### Contrôles

| Touche | Action |
|--------|--------|
| ZQSD / Flèches | Déplacement |
| 1-6 | Sélectionner entité |
| R | Tourner |
| Clic gauche | Construire / Inspecter |
| Clic droit | Détruire / Fermer panneau |
| Molette | Zoom (map ou minimap) |
| F3 | Debug |
| Échap | Désélectionner / Fermer |

---

## Ressources externes

- [Pygame Documentation](https://www.pygame.org/docs/)
- [MessagePack Specification](https://github.com/msgpack/msgpack/blob/master/spec.md)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Game Programming Patterns](https://gameprogrammingpatterns.com/)
- [Factorio Friday Facts](https://factorio.com/blog/) - Inspirations techniques
- [Gabriel Gambetta - Fast-Paced Multiplayer](https://www.gabrielgambetta.com/client-server-game-architecture.html)
- [Glenn Fiedler - Game Networking](https://gafferongames.com/)

---

*Documentation générée pour le projet Factorio-like - Version 1.0*