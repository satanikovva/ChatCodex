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
    }
    try:
        return Settings.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeError(f"Ошибка конфигурации .env: {exc}") from exc
