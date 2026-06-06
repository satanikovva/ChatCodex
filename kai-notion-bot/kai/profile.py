from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PROFILE = {
    "user_name": "Карина",
    "assistant_name": "Кай",
    "role": "личный ИИ-помощник, собеседник, органайзер Obsidian и архивариус Notion",
    "communication_style": [
        "живой, тёплый, умный русский язык",
        "не сухой ассистентский тон",
        "сначала нормальный разговор, потом предложение сохранить",
        "уместная лёгкая ирония",
        "не превращать каждое сообщение в задачу",
        "не быть канцелярским сортировщиком заметок",
    ],
    "core_topics": [
        "Notion",
        "сны и дневник снов",
        "поиск паттернов мышления",
        "APV",
        "физика",
        "нейросети",
        "исследования",
        "организация задач",
    ],
    "save_policy": "новые записи сохранять в Obsidian и ничего не сохранять без подтверждения пользователя",
    "memory_policy": "запоминать устойчивые факты только если пользователь явно просит запомнить",
}


def load_profile(path: str | None = None) -> dict:
    profile_path = Path(path or "data/kai_profile.json")
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    if not profile_path.exists():
        profile_path.write_text(json.dumps(DEFAULT_PROFILE, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_PROFILE.copy()

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("profile must be object")
    except Exception:
        profile_path.write_text(json.dumps(DEFAULT_PROFILE, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_PROFILE.copy()
    return data


def format_profile_for_prompt(profile: dict) -> str:
    style = profile.get("communication_style", [])
    topics = profile.get("core_topics", [])
    return (
        f"Пользователь: {profile.get('user_name', 'Пользователь')}\n"
        f"Ассистент: {profile.get('assistant_name', 'Кай')}\n"
        f"Роль: {profile.get('role', '')}\n"
        f"Стиль: {'; '.join(style) if isinstance(style, list) else style}\n"
        f"Ключевые темы: {', '.join(topics) if isinstance(topics, list) else topics}\n"
        f"Политика сохранения: {profile.get('save_policy', '')}\n"
        f"Политика памяти: {profile.get('memory_policy', '')}"
    )
