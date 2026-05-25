from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from kai.config import load_settings


@dataclass(frozen=True)
class LLMDecision:
    reply: str
    should_offer_save: bool
    save_target: str | None
    entry_kind: str | None
    title: str | None
    text_to_save: str | None
    reason: str | None


SYSTEM_PROMPT = """Ты Кай, живой ИИ-помощник Алекс.
Ты не сортировщик заметок.
Ты сначала отвечаешь как нормальный собеседник: тепло, умно, живо, по-русски.
Ты можешь обсуждать физику, APV, сны, Notion, задачи, исследования, паттерны мышления.
Ты предлагаешь сохранить в Notion только если сообщение действительно содержит:
- задачу
- мысль
- инсайт
- сон
- наблюдение
- физическую гипотезу
- APV-эксперимент
- важный паттерн
Ты никогда не сохраняешь автоматически.
Ты не используешь жёсткие ключевые слова как основу поведения.
Ты возвращаешь только JSON.

JSON format:
{
"reply": "живой ответ пользователю",
"should_offer_save": true/false,
"save_target": "progress|notes|dreams|observations|physics|apv|null",
"entry_kind": "task|note|dream|observation|physics|apv|null",
"title": "короткое название 3-7 слов или null",
"text_to_save": "что сохранить или null",
"reason": "почему стоит сохранить или null"
}

Если это обычный разговор, should_offer_save=false.
Если пользователь спрашивает "как дела", "как ты", "что делаешь", "давай поговорим", просто ответь, без сохранения.
Если пользователь говорит "надо сделать..." или описывает сон/идею/гипотезу, ответь живо и предложи сохранить.
"""


def _fallback() -> LLMDecision:
    return LLMDecision(
        reply="Мой LLM-модуль сейчас недоступен, но Telegram/Notion-контур жив.",
        should_offer_save=False,
        save_target=None,
        entry_kind=None,
        title=None,
        text_to_save=None,
        reason=None,
    )


def ask_llm(user_text: str) -> LLMDecision:
    settings = load_settings()
    if settings.llm_provider.lower() != "groq" or not settings.groq_api_key or not settings.groq_model:
        return _fallback()

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)

        return LLMDecision(
            reply=str(data.get("reply") or "Я рядом."),
            should_offer_save=bool(data.get("should_offer_save", False)),
            save_target=data.get("save_target"),
            entry_kind=data.get("entry_kind"),
            title=data.get("title"),
            text_to_save=data.get("text_to_save"),
            reason=data.get("reason"),
        )
    except Exception:
        return _fallback()
