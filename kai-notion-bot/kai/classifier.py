from __future__ import annotations

from datetime import date
import re

from kai.schemas import Draft, EntryKind, NotionTarget


RULES: list[tuple[EntryKind, NotionTarget, tuple[str, ...]]] = [
    (EntryKind.DREAM, NotionTarget.DREAMS, ("сон", "приснилось", "во сне", "осознанный сон")),
    (EntryKind.APV, NotionTarget.APV, ("апв", "нейросеть", "активация", "alpha", "baseline", "датасет", "эксперимент")),
    (EntryKind.PHYSICS, NotionTarget.PHYSICS, ("физика", "энтропия", "квант", "формула", "гипотеза", "информационная физика")),
    (EntryKind.TASK, NotionTarget.PROGRESS, ("надо", "сделать", "задача", "план", "купить", "разобрать", "дописать")),
    (EntryKind.OBSERVATION, NotionTarget.OBSERVATIONS, ("наблюдение", "паттерн", "чит-код", "система", "реальность", "р1", "р2", "р3")),
    (EntryKind.NOTE, NotionTarget.NOTES, ("идея", "мысль", "инсайт", "заметка", "поняла")),
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def make_short_title(text: str) -> str:
    words = re.findall(r"[\wа-яА-ЯёЁ-]+", text)
    if not words:
        return "Новая заметка"
    count = min(7, max(3, len(words)))
    return " ".join(words[:count]).strip().capitalize()


def classify_text(text: str) -> tuple[EntryKind, NotionTarget]:
    normalized = _normalize(text)
    for kind, target, keywords in RULES:
        if any(keyword in normalized for keyword in keywords):
            return kind, target
    return EntryKind.NOTE, NotionTarget.NOTES


def make_draft(user_id: int, chat_id: int, text: str) -> Draft:
    kind, target = classify_text(text)
    return Draft(
        id=None,
        user_id=user_id,
        chat_id=chat_id,
        source_text=text,
        title=make_short_title(text),
        entry_kind=kind,
        notion_target=target,
        created_date=date.today(),
    )
