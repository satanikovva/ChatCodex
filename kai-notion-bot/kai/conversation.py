from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class ConversationMemory:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def add_message(self, chat_id: int, role: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO conversation_messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def get_recent_messages(self, chat_id: int, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, chat_id, role, content, created_at FROM conversation_messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def format_recent_messages(self, chat_id: int, limit: int = 20) -> str:
        msgs = self.get_recent_messages(chat_id=chat_id, limit=limit)
        if not msgs:
            return "(контекст пуст)"
        return "\n".join(f"{m['role']}: {m['content']}" for m in msgs)

    def trim_chat_history(self, chat_id: int, keep_last: int = 80) -> None:
        self.conn.execute(
            """
            DELETE FROM conversation_messages
            WHERE chat_id = ?
              AND id NOT IN (
                SELECT id FROM conversation_messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?
              )
            """,
            (chat_id, chat_id, keep_last),
        )
        self.conn.commit()
