"""
Serveur de jeu Factorio-like.
Gère les connexions clients, la simulation du monde et la synchronisation.
"""

import socket
import threading
import time
from typing import Dict
from dataclasses import dataclass, field

from shared.protocol import (
    pack_message, unpack_message, get_timestamp,
    MSG_AUTH, MSG_AUTH_RESPONSE, MSG_PLAYER_JOIN, MSG_PLAYER_LEAVE,
    MSG_PLAYER_MOVE, MSG_CHUNK_REQUEST, MSG_CHUNK_DATA,
    MSG_ENTITY_UPDATE, MSG_ENTITY_ADD, MSG_ENTITY_REMOVE,
    MSG_PLAYER_ACTION, MSG_WORLD_TICK, MSG_SYNC,
    MSG_INVENTORY_UPDATE, MSG_INVENTORY_ACTION,
    ACTION_BUILD, ACTION_DESTROY, ACTION_CONFIGURE,
    INV_ACTION_PICKUP, INV_ACTION_DROP, INV_ACTION_TRANSFER_TO,
    INV_ACTION_TRANSFER_FROM, INV_ACTION_SWAP, INV_ACTION_CRAFT
)
from shared.constants import (
    WORLD_TICK_RATE, WORLD_TICK_INTERVAL,
    NETWORK_TICK_RATE, NETWORK_TICK_INTERVAL,
    PLAYER_VIEW_DISTANCE
)
from shared.entities import EntityType, Direction
from shared.player import Player, Inventory
from server.world import World
from server.simulation import Simulation
from server.persistence import Persistence
from server.inventory_manager import InventoryManager


@dataclass
class ClientConnection:
    """Représente une connexion client."""
    conn: socket.socket
    addr: tuple
    player_id: int = 0
    authenticated: bool = False
    buffer: bytes = b''
    subscribed_chunks: set = field(default_factory=set)


class GameServer:
    """Serveur de jeu principal."""

    def __init__(self, host='0.0.0.0', port=5555):
        # Charge la configuration depuis MongoDB
        self._load_config()

        # Socket serveur
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.server.bind((host, port))
        self.server.listen()

        # Clients connectés
        self.clients: Dict[int, ClientConnection] = {}
        self.lock = threading.RLock()
        self.next_client_id = 0

        # Monde et simulation
        self.persistence = Persistence()
        self.world = self.load_or_create_world()
        self.simulation = Simulation(self.world)
        self.inventory_manager = InventoryManager(self.world)

        self.running = True

    def _load_config(self):
        """Charge la configuration depuis MongoDB ou utilise les valeurs par défaut."""
        from admin.config import get_config

        config = get_config()
        try:
            config.load_from_mongodb()
            print("Configuration chargée depuis MongoDB")
        except Exception as e:
            print(f"MongoDB non disponible ({e}), utilisation des valeurs par défaut")
            config.load_defaults()

    def load_or_create_world(self) -> World:
        """Charge le monde depuis la base de données ou en crée un nouveau."""
        meta = self.persistence.load_world_meta()
        if meta:
            world = World(seed=int(meta.get('seed', 12345)))
            world.tick = int(meta.get('tick', 0))
            world.next_entity_id = int(meta.get('next_entity_id', 1))
            print(f"Monde chargé - Tick: {world.tick}, Seed: {world.seed}")
        else:
            world = World(seed=12345)
            print(f"Nouveau monde créé - Seed: {world.seed}")
        return world

    def accept_connections(self):
        """Boucle d'acceptation des nouvelles connexions."""
        while self.running:
            try:
                conn, addr = self.server.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                conn.setblocking(False)

                with self.lock:
                    self.next_client_id += 1
                    client_id = self.next_client_id
                    self.clients[client_id] = ClientConnection(conn, addr)

                print(f"Connexion de {addr}")

            except Exception as e:
                if self.running:
                    print(f"Erreur accept: {e}")

    def receive_from_clients(self):
        """Reçoit et traite les messages de tous les clients."""
        with self.lock:
            disconnected = []

            for client_id, client in self.clients.items():
                try:
                    data = client.conn.recv(4096)
                    if not data:
                        print(f"Client {client_id}: connexion fermée (pas de données)")
                        disconnected.append(client_id)
                        continue

                    client.buffer += data

                    while True:
                        msg, client.buffer = unpack_message(client.buffer)
                        if msg is None:
                            break
                        self.handle_message(client_id, msg)

                except BlockingIOError:
                    pass
                except Exception as e:
                    print(f"Client {client_id}: erreur {type(e).__name__}: {e}")
                    disconnected.append(client_id)

            for client_id in disconnected:
                self.disconnect_client(client_id)

    def handle_message(self, client_id: int, msg: dict):
        """Traite un message reçu d'un client."""
        msg_type = msg['t']
        data = msg['d']
        client = self.clients.get(client_id)

        if not client:
            return

        try:
            if msg_type == MSG_AUTH:
                self.handle_auth(client_id, data)

            elif msg_type == MSG_PLAYER_MOVE:
                if client.authenticated:
                    self.handle_player_move(client_id, data)

            elif msg_type == MSG_CHUNK_REQUEST:
                if client.authenticated:
                    self.handle_chunk_request(client_id, data)

            elif msg_type == MSG_PLAYER_ACTION:
                if client.authenticated:
                    self.handle_player_action(client_id, data)

            elif msg_type == MSG_INVENTORY_ACTION:
                if client.authenticated:
                    self.handle_inventory_action(client_id, data)

            elif msg_type == MSG_SYNC:
                self.send_to(client_id, MSG_SYNC, {
                    'server_time': get_timestamp(),
                    'client_time': data['client_time'],
                    'tick': self.world.tick
                })

        except Exception as e:
            print(f"Erreur handle_message: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    def handle_auth(self, client_id: int, data: dict):
        """Gère l'authentification d'un client."""
        name = data.get('name', f'Player{client_id}')

        with self.lock:
            client = self.clients[client_id]
            client.authenticated = True
            client.player_id = client_id

            # Charge ou crée le joueur
            player_data = self.persistence.load_player(client_id)
            if player_data:
                player = Player(
                    id=client_id,
                    name=player_data.get('name', name),
                    x=player_data.get('x', 0.0),
                    y=player_data.get('y', 0.0)
                )
                # Charge l'inventaire si présent
                if 'inventory' in player_data:
                    player.inventory = Inventory.from_dict(player_data['inventory'])
                self.world.players[client_id] = player
            else:
                player = Player(id=client_id, name=name)
                self.world.players[client_id] = player

            # Envoie la confirmation au nouveau joueur
            self.send_to(client_id, MSG_AUTH_RESPONSE, {
                'success': True,
                'player_id': client_id,
                'x': player.x,
                'y': player.y,
                'tick': self.world.tick
            })

            # Envoie l'inventaire initial
            self.send_inventory_update(client_id)

            # Envoie la liste des joueurs existants au nouveau client
            for other_id, other_player in self.world.players.items():
                if other_id != client_id:
                    self.send_to(client_id, MSG_PLAYER_JOIN, {
                        'id': other_id,
                        'name': other_player.name,
                        'x': other_player.x,
                        'y': other_player.y
                    })

            # Notifie les autres joueurs du nouveau venu
            self.broadcast_except(client_id, MSG_PLAYER_JOIN, {
                'id': client_id,
                'name': name,
                'x': player.x,
                'y': player.y
            })

        print(f"Joueur {name} (ID: {client_id}) authentifié")

    def handle_player_move(self, client_id: int, data: dict):
        """Gère le mouvement d'un joueur."""
        x = data['x']
        y = data['y']

        player = self.world.players.get(client_id)
        if player:
            player.x = x
            player.y = y

        # Met à jour les chunks souscrits
        self.update_chunk_subscriptions(client_id)

        # Broadcast aux autres joueurs proches
        self.broadcast_except(client_id, MSG_PLAYER_MOVE, {
            'id': client_id,
            'x': x,
            'y': y
        })

    def handle_chunk_request(self, client_id: int, data: dict):
        """Gère la demande d'un chunk par un client."""
        cx = data['cx']
        cy = data['cy']

        # Vérifie d'abord si le chunk est en DB
        chunk = self.persistence.load_chunk(cx, cy)
        if chunk:
            self.world.chunks[(cx, cy)] = chunk
        else:
            chunk = self.world.get_chunk(cx, cy)

        self.send_to(client_id, MSG_CHUNK_DATA, chunk.to_dict())

        # Ajoute aux chunks souscrits
        with self.lock:
            client = self.clients.get(client_id)
            if client:
                client.subscribed_chunks.add((cx, cy))

    def handle_player_action(self, client_id: int, data: dict):
        """Gère les actions de construction/destruction."""
        from admin.config import get_config

        config = get_config()
        action = data['action']
        x = data['x']
        y = data['y']

        if action == ACTION_BUILD:
            entity_type = EntityType(data['entity_type'])
            direction = Direction(data.get('direction', 0))

            # Vérifie la tile
            tile = self.world.get_tile(x, y)
            tile_id = int(tile)

            # Récupère le nom de la tile et de l'entité
            tile_config = config.tiles.get(tile_id)
            tile_name = tile_config.name if tile_config else 'VOID'

            entity_config = config.entities.get(int(entity_type))
            entity_name = entity_config.name if entity_config else None

            # Vérifie les règles de placement
            if entity_name and not config.can_place_entity(entity_name, tile_name):
                return

            # Vérifie qu'il n'y a pas déjà une entité
            existing = self.world.get_entity_at(x, y)
            if existing:
                return

            entity = self.world.create_entity(entity_type, x, y, direction=direction)

            # Broadcast à tous les joueurs qui ont ce chunk
            cx, cy, _, _ = self.world.world_to_chunk(x, y)
            self.broadcast_to_chunk_subscribers((cx, cy), MSG_ENTITY_ADD, entity.to_dict())

        elif action == ACTION_DESTROY:
            entity_id = data['entity_id']
            entity = self.world.remove_entity(entity_id)

            if entity:
                cx, cy, _, _ = self.world.world_to_chunk(entity.x, entity.y)
                self.broadcast_to_chunk_subscribers((cx, cy), MSG_ENTITY_REMOVE, {'id': entity_id})

        elif action == ACTION_CONFIGURE:
            entity_id = data['entity_id']
            recipe = data.get('recipe', None)

            entity = self.world.entities.get(entity_id)
            if entity:
                entity.data['recipe'] = recipe
                cx, cy, _, _ = self.world.world_to_chunk(entity.x, entity.y)
                self.broadcast_to_chunk_subscribers((cx, cy), MSG_ENTITY_UPDATE, entity.to_dict())

    def handle_inventory_action(self, client_id: int, data: dict):
        """Gère les actions d'inventaire."""
        player = self.world.players.get(client_id)
        if not player:
            return

        action = data.get('action')

        if action == INV_ACTION_PICKUP:
            # Ramasse les items proches
            x = data.get('x', int(player.x))
            y = data.get('y', int(player.y))
            mine = data.get('mine', False)

            if mine:
                # Minage manuel (plus lent)
                item = self.inventory_manager.mine_resource(player, x, y)
                if item:
                    self.send_inventory_update(client_id)
            else:
                # Ramassage normal
                if self.inventory_manager.pickup_from_ground(player, x, y):
                    self.send_inventory_update(client_id)

        elif action == INV_ACTION_DROP:
            item = data.get('item')
            count = data.get('count', 1)
            # Lâche les items (pour l'instant on les perd, TODO: créer entité au sol)
            dropped = player.drop_item(item, count)
            if dropped > 0:
                self.send_inventory_update(client_id)

        elif action == INV_ACTION_TRANSFER_TO:
            entity_id = data.get('entity_id')
            item = data.get('item')
            count = data.get('count', 1)

            transferred = self.inventory_manager.transfer_to_entity(player, entity_id, item, count)
            if transferred > 0:
                self.send_inventory_update(client_id)
                # Met aussi à jour l'entité
                entity = self.world.entities.get(entity_id)
                if entity:
                    cx, cy, _, _ = self.world.world_to_chunk(entity.x, entity.y)
                    self.broadcast_to_chunk_subscribers((cx, cy), MSG_ENTITY_UPDATE, entity.to_dict())

        elif action == INV_ACTION_TRANSFER_FROM:
            entity_id = data.get('entity_id')
            item = data.get('item')
            count = data.get('count', 1)

            transferred = self.inventory_manager.transfer_from_entity(player, entity_id, item, count)
            if transferred > 0:
                self.send_inventory_update(client_id)
                # Met aussi à jour l'entité
                entity = self.world.entities.get(entity_id)
                if entity:
                    cx, cy, _, _ = self.world.world_to_chunk(entity.x, entity.y)
                    self.broadcast_to_chunk_subscribers((cx, cy), MSG_ENTITY_UPDATE, entity.to_dict())

        elif action == INV_ACTION_SWAP:
            slot1 = data.get('slot1')
            slot2 = data.get('slot2')

            if slot1 is not None and slot2 is not None:
                player.inventory.swap_slots(slot1, slot2)
                self.send_inventory_update(client_id)

        elif action == INV_ACTION_CRAFT:
            recipe = data.get('recipe')

            if self.inventory_manager.craft_item(player, recipe):
                self.send_inventory_update(client_id)

    def send_inventory_update(self, client_id: int):
        """Envoie l'inventaire complet au client."""
        player = self.world.players.get(client_id)
        if not player:
            return

        self.send_to(client_id, MSG_INVENTORY_UPDATE, player.inventory.to_dict())

    def update_chunk_subscriptions(self, client_id: int):
        """Met à jour les chunks auxquels un client est souscrit."""
        with self.lock:
            client = self.clients.get(client_id)
            player = self.world.players.get(client_id)

            if not client or not player:
                return

            needed_chunks = self.world.get_chunks_around(player.x, player.y)
            current_chunks = client.subscribed_chunks

            # Nouveaux chunks à envoyer
            new_chunks = needed_chunks - current_chunks
            for cx, cy in new_chunks:
                chunk = self.persistence.load_chunk(cx, cy)
                if chunk:
                    self.world.chunks[(cx, cy)] = chunk
                else:
                    chunk = self.world.get_chunk(cx, cy)
                self.send_to(client_id, MSG_CHUNK_DATA, chunk.to_dict())

            # Chunks à désouscrire
            old_chunks = current_chunks - needed_chunks

            client.subscribed_chunks = needed_chunks

    def broadcast_to_chunk_subscribers(self, chunk_key: tuple, msg_type: int, data: dict):
        """Envoie un message à tous les clients souscris à un chunk."""
        with self.lock:
            for client_id, client in self.clients.items():
                if chunk_key in client.subscribed_chunks:
                    self.send_to(client_id, msg_type, data)

    def send_to(self, client_id: int, msg_type: int, data: dict):
        """Envoie un message à un client spécifique."""
        try:
            client = self.clients.get(client_id)
            if client:
                client.conn.send(pack_message(msg_type, data))
        except Exception:
            self.disconnect_client(client_id)

    def broadcast(self, msg_type: int, data: dict):
        """Envoie un message à tous les clients."""
        for client_id in list(self.clients.keys()):
            self.send_to(client_id, msg_type, data)

    def broadcast_except(self, exclude_id: int, msg_type: int, data: dict):
        """Envoie un message à tous les clients sauf un."""
        for client_id in list(self.clients.keys()):
            if client_id != exclude_id:
                self.send_to(client_id, msg_type, data)

    def disconnect_client(self, client_id: int):
        """Déconnecte un client proprement."""
        with self.lock:
            client = self.clients.pop(client_id, None)
            if client:
                try:
                    client.conn.close()
                except:
                    pass

                if client.authenticated:
                    player = self.world.players.get(client_id)
                    if player:
                        # Sauvegarde le joueur avec son inventaire
                        self.persistence.save_player(player)
                    self.world.players.pop(client_id, None)
                    self.broadcast(MSG_PLAYER_LEAVE, {'id': client_id})

        print(f"Client {client_id} déconnecté")

    def world_loop(self):
        """Boucle de simulation du monde."""
        last_time = time.perf_counter()
        accumulator = 0.0

        while self.running:
            current_time = time.perf_counter()
            frame_time = current_time - last_time
            last_time = current_time

            accumulator += frame_time

            while accumulator >= WORLD_TICK_INTERVAL:
                self.simulation.tick()

                # Broadcast les entités modifiées
                for entity in self.simulation.get_dirty_entities():
                    cx, cy, _, _ = self.world.world_to_chunk(entity.x, entity.y)
                    self.broadcast_to_chunk_subscribers((cx, cy), MSG_ENTITY_UPDATE, entity.to_dict())

                accumulator -= WORLD_TICK_INTERVAL

            time.sleep(0.001)

    def network_loop(self):
        """Boucle réseau."""
        last_time = time.perf_counter()
        last_save = time.perf_counter()

        while self.running:
            current_time = time.perf_counter()

            self.receive_from_clients()

            # Sauvegarde périodique (toutes les 30 secondes)
            if current_time - last_save > 30.0:
                self.save_world()
                last_save = current_time

            time.sleep(NETWORK_TICK_INTERVAL)

    def save_world(self):
        """Sauvegarde le monde et les joueurs."""
        print("Sauvegarde du monde...")
        self.persistence.save_world_meta(self.world)
        self.persistence.save_all_dirty_chunks(self.world)
        for player in self.world.players.values():
            self.persistence.save_player(player)
        print("Sauvegarde terminée")

    def run(self):
        """Lance le serveur."""
        print(f"Serveur démarré sur le port 5555")
        print(f"World tick rate: {WORLD_TICK_RATE} UPS")
        print(f"Network tick rate: {NETWORK_TICK_RATE} Hz")

        accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
        accept_thread.start()

        world_thread = threading.Thread(target=self.world_loop, daemon=True)
        world_thread.start()

        try:
            self.network_loop()
        except KeyboardInterrupt:
            print("\nArrêt du serveur...")
            self.running = False
            self.save_world()


if __name__ == '__main__':
    GameServer().run()