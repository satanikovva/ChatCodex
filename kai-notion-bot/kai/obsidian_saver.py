from __future__ import annotations

import re
from pathlib import Path

from kai.config import Settings
from kai.schemas import Draft, EntryKind, NotionTarget

INVALID_FILENAME_CHARS = r'<>:"/\\|?*'


class ObsidianSaver:
    def __init__(self, settings: Settings) -> None:
        if not settings.obsidian_vault_path:
            raise RuntimeError("OBSIDIAN_VAULT_PATH не задан")
        self.settings = settings
        self.vault_path = Path(settings.obsidian_vault_path).expanduser()

    def save_draft(self, draft: Draft) -> dict:
        folder = get_obsidian_folder_label(draft, self.settings)
        folder_path = self.vault_path / folder
        folder_path.mkdir(parents=True, exist_ok=True)

        safe_title = safe_filename(draft.title)
        date_prefix = draft.created_date.isoformat()
        path = self._next_available_path(folder_path, f"{date_prefix} - {safe_title}")
        path.write_text(self._render_markdown(draft, folder), encoding="utf-8")
        return {"path": str(path), "folder": folder, "title": draft.title}

    def _next_available_path(self, folder_path: Path, stem: str) -> Path:
        candidate = folder_path / f"{stem}.md"
        counter = 2
        while candidate.exists():
            candidate = folder_path / f"{stem} {counter}.md"
            counter += 1
        return candidate

    def _render_markdown(self, draft: Draft, folder: str) -> str:
        escaped_title = draft.title.replace('"', '\\"')
        type_label = obsidian_type_label(draft)
        return (
            "---\n"
            f"type: {type_label}\n"
            f'title: "{escaped_title}"\n'
            f"date: {draft.created_date.isoformat()}\n"
            "source: telegram\n"
            "created_by: kai\n"
            "tags:\n"
            "  - kai\n"
            "  - telegram\n"
            "---\n\n"
            f"# {draft.title}\n\n"
            "## Текст\n\n"
            f"{draft.source_text}\n\n"
            "## Метаданные\n\n"
            f"- Тип: {type_label}\n"
            f"- Папка: {folder}\n"
            "- Создано Каем: да\n"
        )


def get_obsidian_folder_label(draft: Draft, settings: Settings) -> str:
    if draft.entry_kind == EntryKind.DREAM or draft.notion_target == NotionTarget.DREAMS:
        return settings.obsidian_dreams_dir
    if draft.entry_kind == EntryKind.NOTE or draft.notion_target == NotionTarget.NOTES:
        return settings.obsidian_notes_dir
    if draft.entry_kind == EntryKind.TASK or draft.notion_target == NotionTarget.PROGRESS:
        return settings.obsidian_tasks_dir
    if draft.entry_kind == EntryKind.OBSERVATION or draft.notion_target == NotionTarget.OBSERVATIONS:
        return settings.obsidian_observations_dir
    if draft.entry_kind == EntryKind.PHYSICS or draft.notion_target == NotionTarget.PHYSICS:
        return settings.obsidian_physics_dir
    if draft.entry_kind == EntryKind.APV or draft.notion_target == NotionTarget.APV:
        return settings.obsidian_apv_dir
    return settings.obsidian_inbox_dir


def obsidian_type_label(draft: Draft) -> str:
    if draft.entry_kind == EntryKind.DREAM or draft.notion_target == NotionTarget.DREAMS:
        return "сон"
    if draft.entry_kind == EntryKind.NOTE or draft.notion_target == NotionTarget.NOTES:
        return "заметка"
    if draft.entry_kind == EntryKind.TASK or draft.notion_target == NotionTarget.PROGRESS:
        return "задача"
    if draft.entry_kind == EntryKind.OBSERVATION or draft.notion_target == NotionTarget.OBSERVATIONS:
        return "наблюдение"
    if draft.entry_kind == EntryKind.PHYSICS or draft.notion_target == NotionTarget.PHYSICS:
        return "физика"
    if draft.entry_kind == EntryKind.APV or draft.notion_target == NotionTarget.APV:
        return "апв"
    return "заметка"


def safe_filename(title: str, max_length: int = 90) -> str:
    translation = str.maketrans({char: " " for char in INVALID_FILENAME_CHARS})
    cleaned = title.translate(translation)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    if not cleaned:
        cleaned = "Без названия"
    return cleaned[:max_length].rstrip()
