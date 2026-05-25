from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    SAVE_CANDIDATE = "save_candidate"
    SMALLTALK = "smalltalk"
    DELETE_REQUEST = "delete_request"
    STATUS_REQUEST = "status_request"
    HELP_REQUEST = "help_request"
    CANCEL_REQUEST = "cancel_request"


def detect_intent(text: str) -> Intent:
    normalized = text.strip().lower()

    if normalized in {"/start", "/help"} or any(
        phrase in normalized for phrase in ("что ты умеешь", "помощь")
    ):
        return Intent.HELP_REQUEST

    if any(phrase in normalized for phrase in ("как дела?", "ты работаешь?", "статус", "ты жив?")):
        return Intent.STATUS_REQUEST

    if any(
        phrase in normalized
        for phrase in (
            "удали",
            "удалить",
            "сотри",
            "убери запись",
            "удали заметку",
            "я уже записала",
            "не надо сохранять",
        )
    ):
        return Intent.DELETE_REQUEST

    if any(phrase in normalized for phrase in ("отмена", "не сохраняй", "забудь", "не надо")):
        return Intent.CANCEL_REQUEST

    if any(
        phrase in normalized
        for phrase in ("привет", "как дела", "что делаешь", "ты тут", "спасибо", "ок", "поняла", "ясно")
    ):
        return Intent.SMALLTALK

    return Intent.SAVE_CANDIDATE
