import sqlite3
import os
from typing import Optional


class Database:
    def __init__(self, path: str = "data/bot.db"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS linked_accounts (
                    guild_id    TEXT NOT NULL,
                    discord_id  TEXT NOT NULL,
                    riot_name   TEXT NOT NULL,
                    riot_tag    TEXT NOT NULL,
                    region      TEXT NOT NULL DEFAULT 'ap',
                    linked_by   TEXT NOT NULL,
                    linked_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, discord_id)
                )
            """)
            conn.commit()

    # ── Link management ─────────────────────────────────────────────────────

    def link(self, guild_id: int, discord_id: int, riot_name: str,
             riot_tag: str, region: str, linked_by: int):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO linked_accounts (guild_id, discord_id, riot_name, riot_tag, region, linked_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, discord_id) DO UPDATE SET
                    riot_name = excluded.riot_name,
                    riot_tag  = excluded.riot_tag,
                    region    = excluded.region,
                    linked_by = excluded.linked_by,
                    linked_at = CURRENT_TIMESTAMP
            """, (str(guild_id), str(discord_id), riot_name, riot_tag, region, str(linked_by)))
            conn.commit()

    def unlink(self, guild_id: int, discord_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute("""
                DELETE FROM linked_accounts
                WHERE guild_id = ? AND discord_id = ?
            """, (str(guild_id), str(discord_id)))
            conn.commit()
            return cur.rowcount > 0

    def get_account(self, guild_id: int, discord_id: int) -> Optional[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute("""
                SELECT * FROM linked_accounts
                WHERE guild_id = ? AND discord_id = ?
            """, (str(guild_id), str(discord_id))).fetchone()

    def list_accounts(self, guild_id: int) -> list:
        with self._conn() as conn:
            return conn.execute("""
                SELECT * FROM linked_accounts
                WHERE guild_id = ?
                ORDER BY linked_at DESC
            """, (str(guild_id),)).fetchall()
