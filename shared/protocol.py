"""
Protocole réseau pour le jeu Factorio-like.
Définit les types de messages et les fonctions de sérialisation.
"""

import time
import msgpack
from typing import Tuple, Optional

# ============================================
# TYPES DE MESSAGES
# ============================================

# Authentification
MSG_AUTH = 1  # Client -> Serveur : demande d'authentification
MSG_AUTH_RESPONSE = 2  # Serveur -> Client : réponse d'authentification

# Joueurs
MSG_PLAYER_JOIN = 3  # Serveur -> Client : un joueur rejoint
MSG_PLAYER_LEAVE = 4  # Serveur -> Client : un joueur quitte
MSG_PLAYER_MOVE = 5  # Bidirectionnel : mouvement joueur

# Monde
MSG_CHUNK_REQUEST = 6  # Client -> Serveur : demande un chunk
MSG_CHUNK_DATA = 7  # Serveur -> Client : données d'un chunk

# Entités
MSG_ENTITY_UPDATE = 8  # Serveur -> Client : mise à jour d'une entité
MSG_ENTITY_ADD = 9  # Serveur -> Client : nouvelle entité
MSG_ENTITY_REMOVE = 10  # Serveur -> Client : entité supprimée

# Actions
MSG_PLAYER_ACTION = 11  # Client -> Serveur : action du joueur

# Synchronisation
MSG_WORLD_TICK = 12  # Serveur -> Client : tick du monde
MSG_SYNC = 13  # Bidirectionnel : synchronisation temps

# Inventaire
MSG_INVENTORY_UPDATE = 20  # Serveur -> Client : mise à jour inventaire complet
MSG_INVENTORY_ACTION = 21  # Client -> Serveur : action sur inventaire

# ============================================
# TYPES D'ACTIONS (MSG_PLAYER_ACTION)
# ============================================

ACTION_BUILD = 1  # Construire une entité
ACTION_DESTROY = 2  # Détruire une entité
ACTION_CONFIGURE = 3  # Configurer une entité (ex: recette assembleur)

# ============================================
# ACTIONS D'INVENTAIRE (MSG_INVENTORY_ACTION)
# ============================================

INV_ACTION_PICKUP = 1  # Ramasser items au sol / depuis entité
INV_ACTION_DROP = 2  # Lâcher items au sol
INV_ACTION_TRANSFER_TO = 3  # Transférer vers une entité (chest, furnace...)
INV_ACTION_TRANSFER_FROM = 4  # Transférer depuis une entité
INV_ACTION_SWAP = 5  # Échanger deux slots d'inventaire
INV_ACTION_CRAFT = 6  # Fabriquer un item manuellement
INV_ACTION_SPLIT = 7
INV_ACTION_SORT = 8

# ============================================
# FONCTIONS DE SÉRIALISATION
# ============================================

def pack_message(msg_type: int, data: dict) -> bytes:
    """
    Emballe un message pour l'envoi réseau.
    Format: [longueur (4 bytes)] [msgpack(type + data)]
    """
    message = {'t': msg_type, 'd': data}
    packed = msgpack.packb(message, use_bin_type=True)
    length = len(packed)
    return length.to_bytes(4, 'big') + packed


def unpack_message(buffer: bytes) -> Tuple[Optional[dict], bytes]:
    """
    Déballe un message depuis le buffer.
    Retourne (message, buffer_restant) ou (None, buffer) si incomplet.
    """
    if len(buffer) < 4:
        return None, buffer

    length = int.from_bytes(buffer[:4], 'big')

    if len(buffer) < 4 + length:
        return None, buffer

    try:
        message = msgpack.unpackb(buffer[4:4 + length], raw=False)
        return message, buffer[4 + length:]
    except Exception:
        # Message corrompu, on skip
        return None, buffer[4 + length:]


def get_timestamp() -> int:
    """Retourne le timestamp actuel en millisecondes."""
    return int(time.time() * 1000)