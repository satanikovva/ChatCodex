from __future__ import annotations

from notion_client import Client

from kai.config import Settings
from kai.schemas import Draft, NotionTarget


def status_prop(name: str) -> dict:
    return {"status": {"name": name}}


def select_prop(name: str) -> dict:
    return {"select": {"name": name}}


class NotionSaver:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = Client(auth=settings.notion_token)

    def save_draft(self, draft: Draft) -> None:
        database_id = self._get_database_id(draft.notion_target)
        properties = self._build_properties(draft)
        self.client.pages.create(parent={"database_id": database_id}, properties=properties)

    def _get_database_id(self, target: NotionTarget) -> str:
        mapping = {
            NotionTarget.PROGRESS: self.settings.notion_progress_db_id,
            NotionTarget.NOTES: self.settings.notion_notes_db_id,
            NotionTarget.DREAMS: self.settings.notion_dreams_db_id,
            NotionTarget.OBSERVATIONS: self.settings.notion_observations_db_id,
            NotionTarget.PHYSICS: self.settings.notion_physics_db_id,
            NotionTarget.APV: self.settings.notion_apv_db_id,
        }
        return mapping[target]

    def _build_properties(self, draft: Draft) -> dict:
        date_str = draft.created_date.isoformat()
        if draft.notion_target == NotionTarget.PROGRESS:
            return {
                "Задача / мысль": {"title": [{"text": {"content": draft.title}}]},
                "Статус": status_prop("🌀 В процессе"),
                "Энергия": select_prop("🟢 Лёгкая"),
                "Заметка": {"rich_text": [{"text": {"content": draft.source_text}}]},
            }
        if draft.notion_target == NotionTarget.NOTES:
            return {
                "Название": {"title": [{"text": {"content": draft.title}}]},
                "Тип": select_prop("Заметка"),
                "Дата": {"date": {"start": date_str}},
                "Текст": {"rich_text": [{"text": {"content": draft.source_text}}]},
                "Сохранить ⭐": {"checkbox": False},
            }
        if draft.notion_target == NotionTarget.DREAMS:
            return {
                "Сон": {"title": [{"text": {"content": draft.title}}]},
                "Дата": {"date": {"start": date_str}},
                "Краткое резюме": {"rich_text": [{"text": {"content": draft.source_text}}]},
                "Осознанность": select_prop("Нет"),
            }
        if draft.notion_target == NotionTarget.OBSERVATIONS:
            return {
                "Наблюдение": {"title": [{"text": {"content": draft.title}}]},
                "Дата": {"date": {"start": date_str}},
                "Опыт / событие": {"rich_text": [{"text": {"content": draft.source_text}}]},
            }
        if draft.notion_target == NotionTarget.PHYSICS:
            return {
                "Идея": {"title": [{"text": {"content": draft.title}}]},
                "Тип": select_prop("💡 Гипотеза"),
                "Тема": select_prop("Другое"),
                "Статус": select_prop("Черновик"),
                "Контент": {"rich_text": [{"text": {"content": draft.source_text}}]},
            }
        return {
            "Эксперимент": {"title": [{"text": {"content": draft.title}}]},
            "Дата": {"date": {"start": date_str}},
            "Статус": select_prop("🗒️ Запланировано"),
            "Результат": {"rich_text": [{"text": {"content": draft.source_text}}]},
        }
