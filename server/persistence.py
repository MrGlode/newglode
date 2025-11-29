import json
import os
import sqlite3
from typing import Optional
from server.chunk import Chunk
from server.world import World, Player


class Persistence:
    def __init__(self, save_dir: str = "saves"):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.db_path = os.path.join(save_dir, "world.db")
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    cx INTEGER,
                    cy INTEGER,
                    data TEXT,
                    PRIMARY KEY (cx, cy)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS world_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    x REAL,
                    y REAL,
                    data TEXT
                )
            """)
            conn.commit()

    def save_chunk(self, chunk: Chunk):
        with sqlite3.connect(self.db_path) as conn:
            data = json.dumps(chunk.to_dict())
            conn.execute(
                "INSERT OR REPLACE INTO chunks (cx, cy, data) VALUES (?, ?, ?)",
                (chunk.cx, chunk.cy, data)
            )
            conn.commit()
        chunk.dirty = False

    def load_chunk(self, cx: int, cy: int) -> Optional[Chunk]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM chunks WHERE cx = ? AND cy = ?",
                (cx, cy)
            )
            row = cursor.fetchone()
            if row:
                return Chunk.from_dict(json.loads(row[0]))
        return None

    def save_world_meta(self, world: World):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO world_meta (key, value) VALUES (?, ?)",
                ("seed", str(world.seed))
            )
            conn.execute(
                "INSERT OR REPLACE INTO world_meta (key, value) VALUES (?, ?)",
                ("tick", str(world.tick))
            )
            conn.execute(
                "INSERT OR REPLACE INTO world_meta (key, value) VALUES (?, ?)",
                ("next_entity_id", str(world.next_entity_id))
            )
            conn.commit()

    def load_world_meta(self) -> dict:
        meta = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT key, value FROM world_meta")
            for row in cursor:
                meta[row[0]] = row[1]
        return meta

    def save_player(self, player: Player):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO players (id, name, x, y, data) VALUES (?, ?, ?, ?, ?)",
                (player.id, player.name, player.x, player.y, "{}")
            )
            conn.commit()

    def load_player(self, player_id: int) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT name, x, y, data FROM players WHERE id = ?",
                (player_id,)
            )
            row = cursor.fetchone()
            if row:
                return {'name': row[0], 'x': row[1], 'y': row[2], 'data': json.loads(row[3])}
        return None

    def save_all_dirty_chunks(self, world: World):
        """Sauvegarde tous les chunks modifiés."""
        with world.lock:
            for chunk in world.chunks.values():
                if chunk.dirty:
                    self.save_chunk(chunk)