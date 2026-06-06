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


def ask_llm(
    user_text: str,
    profile_context: str = "",
    memory_context: str = "",
    conversation_context: str = "",
    notion_context: str = "",
) -> LLMDecision:
    settings = load_settings()
    if settings.llm_provider.lower() != "groq" or not settings.groq_api_key or not settings.groq_model:
        return _fallback()

    system_prompt = f"""Ты Кай, живой ИИ-помощник пользователя.
Ты не сортировщик заметок.
Ты сначала отвечаешь как живой собеседник.
Ты можешь обсуждать физику, APV, сны, Notion, Obsidian, задачи, исследования и паттерны мышления.
Ты предлагаешь сохранить в Obsidian только если это реально ценно: сон, задача, инсайт, идея, наблюдение, физическая гипотеза, APV-эксперимент.
Ничего не сохраняй автоматически.
Если пользователь просит "сохрани в Notion", мягко скажи: "Новые записи я теперь сохраняю в Obsidian. Могу сохранить туда."
Не здоровайся заново, если разговор уже идёт.
Используй краткосрочный контекст, чтобы держать нить диалога.
Не утверждай, что факт сохранён навсегда, если пользователь явно не просил запомнить.

Профиль:
{profile_context}

Долговременная память:
{memory_context}

Краткосрочный контекст текущего разговора:
{conversation_context}

Ниже может быть контекст из Notion. Используй его только если он релевантен вопросу пользователя. Не выдумывай записи, которых нет в контексте.

Контекст из Notion:
{notion_context}

Верни только JSON формата:
{{
  "reply": "...",
  "should_offer_save": true/false,
  "save_target": "progress|notes|dreams|observations|physics|apv|null",
  "entry_kind": "task|note|dream|observation|physics|apv|null",
  "title": "...",
  "text_to_save": "...",
  "reason": "..."
}}
Поле save_target означает папку/тип для Obsidian, а не базу Notion.
"""

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
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
