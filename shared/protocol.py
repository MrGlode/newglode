from __future__ import annotations

import msgpack
import struct
import time

# Types de messages
MSG_AUTH = 1
MSG_AUTH_RESPONSE = 2
MSG_PLAYER_JOIN = 3
MSG_PLAYER_LEAVE = 4
MSG_PLAYER_MOVE = 5
MSG_CHUNK_REQUEST = 6
MSG_CHUNK_DATA = 7
MSG_ENTITY_UPDATE = 8
MSG_ENTITY_ADD = 9
MSG_ENTITY_REMOVE = 10
MSG_PLAYER_ACTION = 11  # Construire, miner, etc.
MSG_WORLD_TICK = 12
MSG_SYNC = 13
MSG_CHAT = 14

# Actions joueur
ACTION_BUILD = 1
ACTION_DESTROY = 2
ACTION_ROTATE = 3
ACTION_CONFIGURE = 4
ACTION_MINE = 5


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


def get_timestamp() -> float:
    return time.time() * 1000