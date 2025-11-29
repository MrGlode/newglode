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
    MSG_PLAYER_ACTION, MSG_WORLD_TICK, MSG_SYNC
)
from shared.constants import (
    WORLD_TICK_RATE, WORLD_TICK_INTERVAL,
    NETWORK_TICK_RATE, NETWORK_TICK_INTERVAL,
    PLAYER_VIEW_DISTANCE
)
from server.world import World
from server.simulation import Simulation
from server.persistence import Persistence


@dataclass
class ClientConnection:
    conn: socket.socket
    addr: tuple
    player_id: int = 0
    authenticated: bool = False
    buffer: bytes = b''
    subscribed_chunks: set = field(default_factory=set)


class GameServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.server.bind((host, port))
        self.server.listen()

        self.clients: Dict[int, ClientConnection] = {}
        self.lock = threading.RLock()
        self.next_client_id = 0

        # Monde
        self.persistence = Persistence()
        self.world = self.load_or_create_world()
        self.simulation = Simulation(self.world)

        self.running = True

    def load_or_create_world(self) -> World:
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
        msg_type = msg['t']
        data = msg['d']
        client = self.clients.get(client_id)

        if not client:
            return

        print(f"Message de client {client_id}: type={msg_type}")  # Debug

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
        name = data.get('name', f'Player{client_id}')

        with self.lock:
            client = self.clients[client_id]
            client.authenticated = True
            client.player_id = client_id

            # Charge ou crée le joueur
            player_data = self.persistence.load_player(client_id)
            if player_data:
                player = self.world.add_player(client_id, player_data['name'])
                player.x = player_data['x']
                player.y = player_data['y']
            else:
                player = self.world.add_player(client_id, name)

            # Envoie la confirmation au nouveau joueur
            self.send_to(client_id, MSG_AUTH_RESPONSE, {
                'success': True,
                'player_id': client_id,
                'x': player.x,
                'y': player.y,
                'tick': self.world.tick
            })

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
        x = data['x']
        y = data['y']

        self.world.move_player(client_id, x, y)

        # Met à jour les chunks souscrits
        self.update_chunk_subscriptions(client_id)

        # Broadcast aux autres joueurs proches
        self.broadcast_except(client_id, MSG_PLAYER_MOVE, {
            'id': client_id,
            'x': x,
            'y': y
        })

    def handle_chunk_request(self, client_id: int, data: dict):
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
        from shared.protocol import ACTION_BUILD, ACTION_DESTROY
        from shared.entities import EntityType, Direction

        action = data['action']
        x = data['x']
        y = data['y']

        if action == ACTION_BUILD:
            entity_type = EntityType(data['entity_type'])
            direction = Direction(data.get('direction', 0))

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
        try:
            client = self.clients.get(client_id)
            if client:
                client.conn.send(pack_message(msg_type, data))
        except Exception:
            self.disconnect_client(client_id)

    def broadcast(self, msg_type: int, data: dict):
        for client_id in list(self.clients.keys()):
            self.send_to(client_id, msg_type, data)

    def broadcast_except(self, exclude_id: int, msg_type: int, data: dict):
        for client_id in list(self.clients.keys()):
            if client_id != exclude_id:
                self.send_to(client_id, msg_type, data)

    def disconnect_client(self, client_id: int):
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
                        self.persistence.save_player(player)
                    self.world.remove_player(client_id)
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
                    print(f"Entity {entity.id} dirty: {entity.data}")
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
        print("Sauvegarde du monde...")
        self.persistence.save_world_meta(self.world)
        self.persistence.save_all_dirty_chunks(self.world)
        for player in self.world.players.values():
            self.persistence.save_player(player)
        print("Sauvegarde terminée")

    def run(self):
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