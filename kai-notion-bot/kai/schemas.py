from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class DraftStatus(str, Enum):
    PENDING = "pending"
    SAVED = "saved"
    CANCELLED = "cancelled"


class EntryKind(str, Enum):
    DREAM = "сон"
    TASK = "задача"
    NOTE = "заметка"
    OBSERVATION = "наблюдение"
    PHYSICS = "физическая идея"
    APV = "APV-эксперимент"


class NotionTarget(str, Enum):
    PROGRESS = "🧠 Мой прогресс"
    NOTES = "👽 Записи"
    DREAMS = "🌙 Дневник снов"
    OBSERVATIONS = "📓 Журнал наблюдений"
    PHYSICS = "🔬 Физика — Идеи"
    APV = "🤾‍♀️ АПВ дневник нейросети"


@dataclass(slots=True)
class Draft:
    id: int | None
    user_id: int
    chat_id: int
    source_text: str
    title: str
    entry_kind: EntryKind
    notion_target: NotionTarget
    created_date: date
    status: DraftStatus = DraftStatus.PENDING
    reason: str | None = None
    analysis_markdown: str | None = None
