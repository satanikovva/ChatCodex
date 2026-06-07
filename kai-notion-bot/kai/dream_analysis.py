from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from kai.config import load_settings


@dataclass(frozen=True)
class DreamAnalysis:
    summary: str
    symbols: list[str] = field(default_factory=list)
    plot_dynamics: str = ""
    emotional_tone: str = ""
    body_layer: str = ""
    psychoanalytic_layer: str = ""
    jungian_layer: str = ""
    cognitive_layer: str = ""
    possible_patterns: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    obsidian_markdown: str = ""


def _fallback_analysis() -> DreamAnalysis:
    return DreamAnalysis(
        summary="Не смогла получить полноценный разбор: LLM-модуль анализа снов сейчас недоступен.",
        questions=["Попробуем разобрать этот сон позже, когда LLM снова будет доступен?"],
        obsidian_markdown="## Анализ\n\nLLM-модуль анализа снов был недоступен, поэтому структурированный анализ не создан.",
    )


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def analyze_dream(
    user_text: str,
    profile_context: str = "",
    memory_context: str = "",
    conversation_context: str = "",
) -> DreamAnalysis:
    settings = load_settings()
    if settings.llm_provider.lower() != "groq" or not settings.groq_api_key or not settings.groq_model:
        return _fallback_analysis()

    system_prompt = f"""Ты Кай, аналитик снов и паттернов мышления.
Ты не ставишь диагнозы.
Ты не утверждаешь мистические факты как истину.
Ты разбираешь сон как символическую, эмоциональную, телесную и сюжетную систему.
Ты различаешь факты сна, интерпретации, гипотезы и вопросы для уточнения.
Ты используешь профиль и память пользователя, если они даны.
Отвечай на русском.
Не уходи в общие красивые эпитеты.
Делай глубокий, но аккуратный анализ.

Требования к глубине:
- минимум 4 содержательных раздела;
- опирайся на конкретные детали сна;
- разбирай не только символы, но и динамику сюжета;
- покажи связи с психоанализом, Юнгом, когнитивной наукой и телесным опытом;
- не используй общие слова без связи с деталями;
- не ставь диагнозы.

Профиль:
{profile_context}

Долговременная память:
{memory_context}

Краткосрочный контекст текущего разговора:
{conversation_context}

Верни только JSON:
{{
  "summary": "ядро сна с опорой на детали",
  "symbols": ["символ + краткая привязка к детали сна"],
  "plot_dynamics": "как движется сюжет и напряжение",
  "emotional_tone": "эмоциональный тон",
  "body_layer": "телесный слой и моторика/ощущения",
  "psychoanalytic_layer": "психоаналитическая гипотеза без диагноза",
  "jungian_layer": "юнгианский/архетипический слой как гипотеза",
  "cognitive_layer": "когнитивно-нейронаучная гипотеза",
  "possible_patterns": ["возможный паттерн, не диагноз"],
  "questions": ["1-3 вопроса для уточнения"],
  "obsidian_markdown": "## Анализ\n..."
}}
"""

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.35,
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
        return DreamAnalysis(
            summary=str(data.get("summary") or ""),
            symbols=_as_str_list(data.get("symbols")),
            plot_dynamics=str(data.get("plot_dynamics") or ""),
            emotional_tone=str(data.get("emotional_tone") or ""),
            body_layer=str(data.get("body_layer") or ""),
            psychoanalytic_layer=str(data.get("psychoanalytic_layer") or ""),
            jungian_layer=str(data.get("jungian_layer") or ""),
            cognitive_layer=str(data.get("cognitive_layer") or ""),
            possible_patterns=_as_str_list(data.get("possible_patterns")),
            questions=_as_str_list(data.get("questions")),
            obsidian_markdown=str(data.get("obsidian_markdown") or "").strip(),
        )
    except Exception:
        return _fallback_analysis()


def format_dream_analysis_for_telegram(analysis: DreamAnalysis, max_length: int = 3500) -> str:
    symbols = "\n".join(f"   - {symbol}" for symbol in analysis.symbols) if analysis.symbols else "   - не выделены явно"
    patterns = "\n".join(f"   - {pattern}" for pattern in analysis.possible_patterns) if analysis.possible_patterns else "   - пока без уверенного паттерна"
    questions = "\n".join(f"   - {question}" for question in analysis.questions) if analysis.questions else "   - Что в этом сне сильнее всего осталось в теле/эмоции?"
    text = (
        "Разбор сна:\n\n"
        "1. Ядро сна\n"
        f"   {analysis.summary or 'Сон требует дополнительного уточнения.'}\n\n"
        "2. Символы и динамика\n"
        f"{symbols}\n"
        f"   Динамика: {analysis.plot_dynamics or 'не выделена.'}\n"
        f"   Эмоциональный тон: {analysis.emotional_tone or 'не выделен.'}\n\n"
        "3. Психоаналитический слой\n"
        f"   {analysis.psychoanalytic_layer or 'Недостаточно данных для аккуратной психоаналитической гипотезы.'}\n\n"
        "4. Юнгианский/архетипический слой\n"
        f"   {analysis.jungian_layer or 'Архетипический слой пока лучше держать как открытую гипотезу.'}\n\n"
        "5. Когнитивно-телесный слой\n"
        f"   {analysis.cognitive_layer or 'Когнитивный слой не выделен.'}\n"
        f"   Телесность: {analysis.body_layer or 'телесный слой не выделен.'}\n\n"
        "6. Возможные паттерны\n"
        f"{patterns}\n\n"
        "7. Вопросы\n"
        f"{questions}"
    )
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"
