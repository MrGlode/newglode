"""
Client réseau pour le jeu Factorio-like.
Gère la connexion au serveur et l'envoi/réception de messages.
"""

import socket
import time
from typing import TYPE_CHECKING, Optional

from shared.protocol import (
    pack_message, unpack_message, get_timestamp,
    MSG_AUTH, MSG_AUTH_RESPONSE, MSG_PLAYER_JOIN, MSG_PLAYER_LEAVE,
    MSG_PLAYER_MOVE, MSG_CHUNK_REQUEST, MSG_CHUNK_DATA,
    MSG_ENTITY_UPDATE, MSG_ENTITY_ADD, MSG_ENTITY_REMOVE,
    MSG_PLAYER_ACTION, MSG_SYNC,
    MSG_INVENTORY_UPDATE, MSG_INVENTORY_ACTION,
    ACTION_BUILD, ACTION_DESTROY, ACTION_CONFIGURE,
    INV_ACTION_PICKUP, INV_ACTION_DROP, INV_ACTION_TRANSFER_TO,
    INV_ACTION_TRANSFER_FROM, INV_ACTION_SWAP, INV_ACTION_CRAFT, INV_ACTION_SPLIT
)

if TYPE_CHECKING:
    from client.game import Game


class NetworkClient:
    """Client réseau pour communiquer avec le serveur."""

    def __init__(self, game: 'Game', host: str = 'localhost', port: int = 5555):
        self.game = game
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.buffer = b''
        self.connected = False

        # Stats
        self.bytes_received = 0
        self.bytes_sent = 0
        self.last_bandwidth_check = time.time()
        self.bandwidth = 0

    def connect(self):
        """Établit la connexion au serveur."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.connect((self.host, self.port))
        self.socket.setblocking(False)
        self.connected = True
        print(f"Connecté à {self.host}:{self.port}")

    def disconnect(self):
        """Ferme la connexion."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        self.game.on_disconnected()

    def send(self, msg_type: int, data: dict):
        """Envoie un message au serveur."""
        if not self.connected or not self.socket:
            return

        try:
            packed = pack_message(msg_type, data)
            self.socket.send(packed)
            self.bytes_sent += len(packed)
        except Exception as e:
            print(f"Erreur envoi: {e}")
            self.disconnect()

    def receive(self):
        """Reçoit et traite les messages du serveur."""
        if not self.connected or not self.socket:
            return

        try:
            data = self.socket.recv(65536)
            if not data:
                self.disconnect()
                return

            self.buffer += data
            self.bytes_received += len(data)

            # Traite tous les messages complets
            while True:
                msg, self.buffer = unpack_message(self.buffer)
                if msg is None:
                    break
                self.handle_message(msg)

            # Calcul bandwidth
            now = time.time()
            if now - self.last_bandwidth_check >= 1.0:
                self.bandwidth = self.bytes_received + self.bytes_sent
                self.bytes_received = 0
                self.bytes_sent = 0
                self.last_bandwidth_check = now

        except BlockingIOError:
            pass
        except Exception as e:
            print(f"Erreur réception: {e}")
            self.disconnect()

    def handle_message(self, msg: dict):
        """Traite un message reçu du serveur."""
        msg_type = msg['t']
        data = msg['d']

        if msg_type == MSG_AUTH_RESPONSE:
            if data['success']:
                self.game.on_authenticated(
                    data['player_id'],
                    data['x'],
                    data['y']
                )
            else:
                print("Échec authentification")
                self.disconnect()

        elif msg_type == MSG_PLAYER_JOIN:
            self.game.world_view.add_player(data)

        elif msg_type == MSG_PLAYER_LEAVE:
            self.game.world_view.remove_player(data['id'])

        elif msg_type == MSG_PLAYER_MOVE:
            self.game.world_view.update_player(data)

        elif msg_type == MSG_CHUNK_DATA:
            self.game.world_view.add_chunk(data)

        elif msg_type == MSG_ENTITY_UPDATE:
            self.game.world_view.update_entity(data)
            # Met à jour l'entité inspectée si c'est la même
            if self.game.inspected_entity and self.game.inspected_entity.get('id') == data.get('id'):
                self.game.inspected_entity = data

        elif msg_type == MSG_ENTITY_ADD:
            self.game.world_view.add_entity(data)

        elif msg_type == MSG_ENTITY_REMOVE:
            entity_id = data['id']
            self.game.world_view.remove_entity(entity_id)
            # Ferme l'inspection si l'entité inspectée est supprimée
            if self.game.inspected_entity and self.game.inspected_entity.get('id') == entity_id:
                self.game.inspected_entity = None

        elif msg_type == MSG_INVENTORY_UPDATE:
            self.game.on_inventory_update(data)

        elif msg_type == MSG_SYNC:
            # Synchronisation temps (pour l'instant on ignore)
            pass

    # ============================================
    # MÉTHODES D'ENVOI
    # ============================================

    def authenticate(self, name: str):
        """Envoie une demande d'authentification."""
        self.send(MSG_AUTH, {'name': name})

    def send_move(self, x: float, y: float):
        """Envoie la position du joueur."""
        self.send(MSG_PLAYER_MOVE, {'x': x, 'y': y})

    def request_chunk(self, cx: int, cy: int):
        """Demande les données d'un chunk."""
        self.send(MSG_CHUNK_REQUEST, {'cx': cx, 'cy': cy})

    def send_build(self, x: int, y: int, entity_type: int, direction: int = 0):
        """Envoie une demande de construction."""
        self.send(MSG_PLAYER_ACTION, {
            'action': ACTION_BUILD,
            'x': x,
            'y': y,
            'entity_type': int(entity_type),
            'direction': direction
        })

    def send_destroy(self, entity_id: int):
        """Envoie une demande de destruction."""
        self.send(MSG_PLAYER_ACTION, {
            'action': ACTION_DESTROY,
            'entity_id': entity_id,
            'x': 0,
            'y': 0
        })

    def send_set_recipe(self, entity_id: int, recipe: str):
        """Envoie une demande de configuration de recette."""
        self.send(MSG_PLAYER_ACTION, {
            'action': ACTION_CONFIGURE,
            'entity_id': entity_id,
            'recipe': recipe,
            'x': 0,
            'y': 0
        })

    # ============================================
    # MÉTHODES INVENTAIRE
    # ============================================

    def send_inventory_pickup(self, x: int, y: int):
        """Demande à ramasser les items à une position."""
        self.send(MSG_INVENTORY_ACTION, {
            'action': INV_ACTION_PICKUP,
            'x': x,
            'y': y
        })

    def send_inventory_mine(self, x: int, y: int):
        """Mine manuellement une ressource."""
        self.send(MSG_INVENTORY_ACTION, {
            'action': INV_ACTION_PICKUP,
            'x': x,
            'y': y,
            'mine': True
        })

    def send_inventory_drop(self, item: str, count: int):
        """Demande à lâcher des items."""
        self.send(MSG_INVENTORY_ACTION, {
            'action': INV_ACTION_DROP,
            'item': item,
            'count': count
        })

    def send_inventory_transfer_to(self, entity_id: int, item: str, count: int):
        """Transfère des items vers une entité."""
        self.send(MSG_INVENTORY_ACTION, {
            'action': INV_ACTION_TRANSFER_TO,
            'entity_id': entity_id,
            'item': item,
            'count': count
        })

    def send_inventory_transfer_from(self, entity_id: int, item: str, count: int):
        """Transfère des items depuis une entité."""
        self.send(MSG_INVENTORY_ACTION, {
            'action': INV_ACTION_TRANSFER_FROM,
            'entity_id': entity_id,
            'item': item,
            'count': count
        })

    def send_inventory_swap(self, slot1: int, slot2: int):
        """Échange deux slots de l'inventaire."""
        self.send(MSG_INVENTORY_ACTION, {
            'action': INV_ACTION_SWAP,
            'slot1': slot1,
            'slot2': slot2
        })

    def send_inventory_craft(self, recipe: str):
        """Demande à fabriquer un item."""
        self.send(MSG_INVENTORY_ACTION, {
            'action': INV_ACTION_CRAFT,
            'recipe': recipe
        })

    def send_inventory_split(self, from_slot: int, to_slot: int, count: int):
        self.send(MSG_INVENTORY_ACTION, {
            'action': INV_ACTION_SPLIT,
            'from_slot': from_slot,
            'to_slot': to_slot,
            'count': count
        })