from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DetectedIntent:
    kind: str
    reply: str | None = None


SAVE_TRIGGERS = (
    "запиши",
    "сохрани",
    "зафиксируй",
    "добавь в obsidian",
    "добавь в дневник",
    "надо сделать",
    "нужно сделать",
    "задача",
    "план",
    "купить",
    "разобрать",
    "дописать",
    "приснилось",
    "был сон",
    "во сне",
    "осознанный сон",
    "идея:",
    "инсайт:",
    "поняла что",
    "мысль:",
    "гипотеза:",
    "апв",
    "эксперимент",
    "квант",
    "энтроп",
)


def _word_count(text: str) -> int:
    return len(re.findall(r"[\wа-яА-ЯёЁ-]+", text))


def detect_intent(text: str) -> DetectedIntent:
    normalized = text.strip().lower()

    if normalized in {"/help", "/start"} or any(x in normalized for x in ("что ты умеешь", "помощь")):
        return DetectedIntent(
            kind="help",
            reply="Я Кай. Могу предложить сохранить задачу, мысль, сон, наблюдение, физическую идею или APV-эксперимент в Obsidian. Пока сохраняю только после кнопки.",
        )

    if any(x in normalized for x in ("статус", "ты работаешь", "ты жив")):
        return DetectedIntent(kind="status", reply="Я на связи. Пока умею принимать текст, предлагать сохранение в Obsidian и ждать подтверждения.")

    if any(x in normalized for x in ("удали", "удалить", "сотри", "убери запись", "удали заметку")):
        return DetectedIntent(
            kind="command_delete",
            reply="Я пока не умею удалять записи автоматически. Если запись уже сохранена в Obsidian, удали Markdown-файл вручную.",
        )

    if any(x in normalized for x in ("отмена", "не сохраняй", "забудь", "не надо")):
        return DetectedIntent(kind="command_cancel", reply="Окей, не сохраняю.")

    if any(x in normalized for x in SAVE_TRIGGERS):
        return DetectedIntent(kind="save_candidate")

    chat_phrases = (
        "как дела", "как ты", "что делаешь", "что делал", "привет", "спасибо", "ок", "ясно", "понял", "поняла", "да", "нет", "поговорим", "давай обсудим",
    )
    if any(x in normalized for x in chat_phrases):
        return DetectedIntent(kind="chat")

    if "?" in normalized and not any(x in normalized for x in SAVE_TRIGGERS):
        return DetectedIntent(kind="chat")

    if _word_count(normalized) <= 5 and not any(x in normalized for x in SAVE_TRIGGERS):
        return DetectedIntent(kind="chat")

    return DetectedIntent(kind="chat")
