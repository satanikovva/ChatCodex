from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class KaiMemory:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                source_text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def add_memory(self, key: str, value: str, source_text: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT INTO memories (key, value, source_text, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                source_text = excluded.source_text,
                updated_at = excluded.updated_at
            """,
            (key, value, source_text, now, now),
        )
        self.conn.commit()

    def list_memories(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, key, value, source_text, created_at, updated_at FROM memories ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def format_for_prompt(self, limit: int = 20) -> str:
        items = self.list_memories(limit=limit)
        if not items:
            return "(память пуста)"
        return "\n".join(f"- {item['key']}: {item['value']}" for item in items)
