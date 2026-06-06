from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from kai.schemas import Draft, DraftStatus, EntryKind, NotionTarget


class DraftStorage:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                source_text TEXT NOT NULL,
                title TEXT NOT NULL,
                entry_kind TEXT NOT NULL,
                notion_target TEXT NOT NULL,
                created_date TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT
            )
            """
        )
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(drafts)").fetchall()}
        if "reason" not in columns:
            self.conn.execute("ALTER TABLE drafts ADD COLUMN reason TEXT")
        self.conn.commit()

    def create_draft(self, draft: Draft) -> Draft:
        cur = self.conn.execute(
            """
            INSERT INTO drafts (user_id, chat_id, source_text, title, entry_kind, notion_target, created_date, status, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft.user_id,
                draft.chat_id,
                draft.source_text,
                draft.title,
                draft.entry_kind.value,
                draft.notion_target.value,
                draft.created_date.isoformat(),
                draft.status.value,
                draft.reason,
            ),
        )
        self.conn.commit()
        draft.id = cur.lastrowid
        return draft

    def get_draft(self, draft_id: int) -> Draft | None:
        row = self.conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            return None
        return Draft(
            id=row["id"],
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            source_text=row["source_text"],
            title=row["title"],
            entry_kind=EntryKind(row["entry_kind"]),
            notion_target=NotionTarget(row["notion_target"]),
            created_date=date.fromisoformat(row["created_date"]),
            status=DraftStatus(row["status"]),
            reason=row["reason"],
        )

    def set_status(self, draft_id: int, status: DraftStatus) -> None:
        self.conn.execute("UPDATE drafts SET status = ? WHERE id = ?", (status.value, draft_id))
        self.conn.commit()
