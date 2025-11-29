import socket
import time
from typing import TYPE_CHECKING, Optional

from shared.protocol import (
    pack_message, unpack_message, get_timestamp,
    MSG_AUTH, MSG_AUTH_RESPONSE, MSG_PLAYER_JOIN, MSG_PLAYER_LEAVE,
    MSG_PLAYER_MOVE, MSG_CHUNK_REQUEST, MSG_CHUNK_DATA,
    MSG_ENTITY_UPDATE, MSG_ENTITY_ADD, MSG_ENTITY_REMOVE,
    MSG_PLAYER_ACTION, MSG_SYNC,
    ACTION_BUILD, ACTION_DESTROY
)

if TYPE_CHECKING:
    from client.game import Game


class NetworkClient:
    def __init__(self, game: 'Game', host: str = 'localhost', port: int = 5555):
        self.game = game
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.buffer = b''
        self.connected = False

        # Stats
        self.bytes_received = 0
        self.last_bytes_check = time.perf_counter()
        self.bandwidth = 0

        # RTT
        self.rtt = 0.0
        self.last_sync = 0.0

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.connect((self.host, self.port))
            self.socket.setblocking(False)
            self.connected = True
            print(f"Connecté à {self.host}:{self.port}")
        except Exception as e:
            print(f"Erreur connexion: {e}")
            self.connected = False
            raise

    def disconnect(self):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        print("Déconnexion du serveur")
        self.game.on_disconnected()

    def send(self, msg_type: int, data: dict):
        if not self.connected:
            return
        try:
            self.socket.send(pack_message(msg_type, data))
        except Exception as e:
            print(f"Erreur envoi: {e}")
            self.disconnect()

    def receive(self):
        if not self.connected:
            return

        current_time = time.perf_counter()

        # Bandwidth calc
        if current_time - self.last_bytes_check >= 1.0:
            self.bandwidth = self.bytes_received
            self.bytes_received = 0
            self.last_bytes_check = current_time

        # Sync périodique
        if current_time - self.last_sync > 1.0:
            self.send(MSG_SYNC, {'client_time': get_timestamp()})
            self.last_sync = current_time

        try:
            data = self.socket.recv(8192)
            if not data:
                print("Serveur a fermé la connexion")
                self.disconnect()
                return

            self.bytes_received += len(data)
            self.buffer += data

            while True:
                msg, self.buffer = unpack_message(self.buffer)
                if msg is None:
                    break
                #print(f"Message reçu: type={msg['t']}")  # Debug
                self.handle_message(msg)

        except BlockingIOError:
            pass  # Normal, pas de données disponibles
        except ConnectionResetError:
            print("Connexion reset par le serveur")
            self.disconnect()
        except Exception as e:
            print(f"Erreur réception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.disconnect()

    def handle_message(self, msg: dict):
        msg_type = msg['t']
        data = msg['d']

        #print(f"Message reçu: type={msg_type}, data={data}")  # Debug

        if msg_type == MSG_AUTH_RESPONSE:
            if data['success']:
                self.game.on_authenticated(data['player_id'], data['x'], data['y'])
            else:
                print("Authentification échouée")
                self.disconnect()

        elif msg_type == MSG_CHUNK_DATA:
            self.game.world_view.add_chunk(data)

        elif msg_type == MSG_PLAYER_JOIN:
            #print(f"Joueur rejoint: {data}")  # Debug
            self.game.world_view.add_player(data['id'], data['name'], data['x'], data['y'])

        elif msg_type == MSG_PLAYER_LEAVE:
            #print(f"Joueur parti: {data}")  # Debug
            self.game.world_view.remove_player(data['id'])

        elif msg_type == MSG_PLAYER_MOVE:
            #print(f"Joueur bouge: {data}")  # Debug
            self.game.world_view.move_player(data['id'], data['x'], data['y'])

        elif msg_type == MSG_ENTITY_ADD:
            self.game.world_view.add_entity(data)

        elif msg_type == MSG_ENTITY_REMOVE:
            self.game.world_view.remove_entity(data['id'])

        elif msg_type == MSG_ENTITY_UPDATE:
            self.game.world_view.update_entity(data['id'], data)

        elif msg_type == MSG_SYNC:
            self.rtt = get_timestamp() - data['client_time']

    def authenticate(self, name: str):
        self.send(MSG_AUTH, {'name': name})

    def send_move(self, x: float, y: float):
        self.send(MSG_PLAYER_MOVE, {'x': x, 'y': y})

    def request_chunk(self, cx: int, cy: int):
        self.send(MSG_CHUNK_REQUEST, {'cx': cx, 'cy': cy})

    def send_build(self, x: int, y: int, entity_type: int, direction: int):
        self.send(MSG_PLAYER_ACTION, {
            'action': ACTION_BUILD,
            'x': x,
            'y': y,
            'entity_type': entity_type,
            'direction': direction
        })

    def send_destroy(self, entity_id: int):
        self.send(MSG_PLAYER_ACTION, {
            'action': ACTION_DESTROY,
            'entity_id': entity_id,
            'x': 0,
            'y': 0
        })