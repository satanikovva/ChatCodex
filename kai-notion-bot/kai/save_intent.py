from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SaveIntent:
    should_save: bool
    mode: str  # current_message | recent_conversation | dream_with_analysis | analysis_only
    target: str | None  # dreams, notes, observations, physics, apv, tasks, patterns, inbox
    reply_hint: str | None = None


_SAVE_TRIGGERS = (
    "сохрани",
    "запиши",
    "зафиксируй",
)


def detect_save_intent(text: str) -> SaveIntent:
    normalized = " ".join(text.strip().lower().split())
    if not normalized or not any(trigger in normalized for trigger in _SAVE_TRIGGERS):
        return SaveIntent(should_save=False, mode="current_message", target=None)

    if "весь разговор" in normalized or "весь диалог" in normalized or "сохрани диалог" in normalized:
        return SaveIntent(True, "recent_conversation", "notes", "Сохраняю последние сообщения диалога.")

    if "наш анализ" in normalized:
        return SaveIntent(True, "analysis_only", "dreams", "Сохраняю последний разбор и связанный контекст.")

    if "сон" in normalized and ("с анализ" in normalized or "плюс анализ" in normalized or "и анализ" in normalized):
        return SaveIntent(True, "dream_with_analysis", "dreams", "Сохраняю сон вместе с анализом.")

    if "сохрани сон" in normalized or "запиши сон" in normalized or "зафиксируй сон" in normalized:
        return SaveIntent(True, "dream_with_analysis", "dreams", "Сохраняю сон вместе с анализом.")

    target = _detect_target(normalized)
    return SaveIntent(True, "current_message", target or "inbox", "Сохраняю явно указанное содержимое.")


def _detect_target(normalized: str) -> str | None:
    if "в физик" in normalized or "физику" in normalized:
        return "physics"
    if "в апв" in normalized or "в apv" in normalized:
        return "apv"
    if "в задач" in normalized or "задачи" in normalized:
        return "tasks"
    if "в сон" in normalized or "сны" in normalized:
        return "dreams"
    if "в наблюден" in normalized or "наблюдения" in normalized:
        return "observations"
    if "в паттерн" in normalized or "паттерны" in normalized:
        return "patterns"
    if "в замет" in normalized or "заметки" in normalized:
        return "notes"
    if "в обсидиан" in normalized or "в obsidian" in normalized:
        return "inbox"
    return None
