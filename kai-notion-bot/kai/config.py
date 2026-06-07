from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    telegram_bot_token: str = Field(min_length=1)
    notion_token: str = Field(min_length=1)
    notion_progress_db_id: str = Field(min_length=1)
    notion_notes_db_id: str = Field(min_length=1)
    notion_dreams_db_id: str = Field(min_length=1)
    notion_observations_db_id: str = Field(min_length=1)
    notion_physics_db_id: str = Field(min_length=1)
    notion_apv_db_id: str = Field(min_length=1)
    notion_daily_marks_db_id: str = Field(min_length=1)
    notion_activity_db_id: str = Field(min_length=1)
    notion_will_db_id: str = Field(min_length=1)
    llm_provider: str = Field(default="groq", min_length=1)
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="")
    llm_timeout_seconds: int = Field(default=30, ge=1, le=120)
    kai_profile_path: str = Field(default="data/kai_profile.json")
    kai_memory_db_path: str = Field(default="data/kai_memory.sqlite")
    kai_conversation_db_path: str = Field(default="data/kai_conversation.sqlite")
    kai_conversation_history_limit: int = Field(default=20, ge=1, le=200)
    obsidian_vault_path: str = Field(default="")
    obsidian_inbox_dir: str = Field(default="Входящие")
    obsidian_days_dir: str = Field(default="Дни")
    obsidian_dreams_dir: str = Field(default="Сны")
    obsidian_notes_dir: str = Field(default="Заметки")
    obsidian_observations_dir: str = Field(default="Наблюдения")
    obsidian_physics_dir: str = Field(default="Физика")
    obsidian_apv_dir: str = Field(default="АПВ")
    obsidian_tasks_dir: str = Field(default="Задачи")
    obsidian_patterns_dir: str = Field(default="Паттерны")
    obsidian_sources_dir: str = Field(default="Источники")
    obsidian_templates_dir: str = Field(default="Шаблоны")
    obsidian_attachments_dir: str = Field(default="Вложения")


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    load_dotenv()
    raw = {
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        "notion_token": os.getenv("NOTION_TOKEN", "").strip(),
        "notion_progress_db_id": os.getenv("NOTION_PROGRESS_DB_ID", "").strip(),
        "notion_notes_db_id": os.getenv("NOTION_NOTES_DB_ID", "").strip(),
        "notion_dreams_db_id": os.getenv("NOTION_DREAMS_DB_ID", "").strip(),
        "notion_observations_db_id": os.getenv("NOTION_OBSERVATIONS_DB_ID", "").strip(),
        "notion_physics_db_id": os.getenv("NOTION_PHYSICS_DB_ID", "").strip(),
        "notion_apv_db_id": os.getenv("NOTION_APV_DB_ID", "").strip(),
        "notion_daily_marks_db_id": os.getenv("NOTION_DAILY_MARKS_DB_ID", "").strip(),
        "notion_activity_db_id": os.getenv("NOTION_ACTIVITY_DB_ID", "").strip(),
        "notion_will_db_id": os.getenv("NOTION_WILL_DB_ID", "").strip(),
        "llm_provider": os.getenv("LLM_PROVIDER", "groq").strip(),
        "groq_api_key": os.getenv("GROQ_API_KEY", "").strip(),
        "groq_model": os.getenv("GROQ_MODEL", "").strip(),
        "llm_timeout_seconds": int(os.getenv("LLM_TIMEOUT_SECONDS", "30").strip() or "30"),
        "kai_profile_path": os.getenv("KAI_PROFILE_PATH", "data/kai_profile.json").strip(),
        "kai_memory_db_path": os.getenv("KAI_MEMORY_DB_PATH", "data/kai_memory.sqlite").strip(),
        "kai_conversation_db_path": os.getenv("KAI_CONVERSATION_DB_PATH", "data/kai_conversation.sqlite").strip(),
        "kai_conversation_history_limit": int(os.getenv("KAI_CONVERSATION_HISTORY_LIMIT", "20").strip() or "20"),
        "obsidian_vault_path": os.getenv("OBSIDIAN_VAULT_PATH", "").strip(),
        "obsidian_inbox_dir": os.getenv("OBSIDIAN_INBOX_DIR", "Входящие").strip(),
        "obsidian_days_dir": os.getenv("OBSIDIAN_DAYS_DIR", "Дни").strip(),
        "obsidian_dreams_dir": os.getenv("OBSIDIAN_DREAMS_DIR", "Сны").strip(),
        "obsidian_notes_dir": os.getenv("OBSIDIAN_NOTES_DIR", "Заметки").strip(),
        "obsidian_observations_dir": os.getenv("OBSIDIAN_OBSERVATIONS_DIR", "Наблюдения").strip(),
        "obsidian_physics_dir": os.getenv("OBSIDIAN_PHYSICS_DIR", "Физика").strip(),
        "obsidian_apv_dir": os.getenv("OBSIDIAN_APV_DIR", "АПВ").strip(),
        "obsidian_tasks_dir": os.getenv("OBSIDIAN_TASKS_DIR", "Задачи").strip(),
        "obsidian_patterns_dir": os.getenv("OBSIDIAN_PATTERNS_DIR", "Паттерны").strip(),
        "obsidian_sources_dir": os.getenv("OBSIDIAN_SOURCES_DIR", "Источники").strip(),
        "obsidian_templates_dir": os.getenv("OBSIDIAN_TEMPLATES_DIR", "Шаблоны").strip(),
        "obsidian_attachments_dir": os.getenv("OBSIDIAN_ATTACHMENTS_DIR", "Вложения").strip(),
    }
    try:
        return Settings.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeError(f"Ошибка конфигурации .env: {exc}") from exc
