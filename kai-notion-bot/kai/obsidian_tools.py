from __future__ import annotations

from datetime import date
from pathlib import Path

from kai.config import Settings
from kai.obsidian_saver import ObsidianSaver


class ObsidianTools:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.saver = ObsidianSaver(settings)
        self.vault_path = Path(settings.obsidian_vault_path).expanduser()

    def create_note(self, folder: str, title: str, content: str, properties: dict | None = None) -> dict:
        resolved_folder = self.resolve_folder(folder)
        body = content.strip() or "(пустая заметка)"
        return self.saver.save_markdown(
            title=title.strip() or "Заметка Кая",
            folder=resolved_folder,
            body=body,
            properties=properties or {"type": "заметка", "tags": ["kai", "telegram"]},
        )

    def search_notes(self, query: str, folders: list[str] | None = None, limit: int = 10) -> list[dict]:
        query_text = query.strip().lower()
        if not query_text:
            return []
        roots = [self.vault_path / self.resolve_folder(folder) for folder in folders] if folders else [self.vault_path]
        results: list[dict] = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                try:
                    content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                lowered = content.lower()
                title = path.stem
                title_lowered = title.lower()
                score = 0
                if query_text in title_lowered:
                    score += 5
                if query_text in lowered:
                    score += 2 + lowered.count(query_text)
                if score <= 0:
                    continue
                results.append(
                    {
                        "title": title,
                        "path": str(path),
                        "snippet": _snippet(content, query_text),
                        "score": score,
                    }
                )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def read_note(self, path: str) -> dict:
        note_path = self._safe_path(path)
        content = note_path.read_text(encoding="utf-8")
        return {"title": note_path.stem, "content": content, "path": str(note_path)}

    def append_note(self, path: str, content: str, heading: str | None = None) -> dict:
        note_path = self._safe_path(path)
        addition = content.strip()
        if heading:
            addition = f"\n\n## {heading.strip()}\n\n{addition}"
        else:
            addition = f"\n\n{addition}"
        with note_path.open("a", encoding="utf-8") as file:
            file.write(addition)
        return {"path": str(note_path)}

    def save_conversation(self, title: str, messages: list[dict], folder: str = "Заметки") -> dict:
        resolved_folder = self.resolve_folder(folder)
        lines = [f"{message.get('role', 'unknown')}: {message.get('content', '')}" for message in messages]
        body = (
            "## Диалог\n\n"
            + "\n".join(lines)
            + "\n\n## Метаданные\n\n"
            + "- Тип: диалог\n"
            + f"- Папка: {resolved_folder}\n"
            + "- Создано Каем: да"
        )
        return self.saver.save_markdown(
            title=title.strip() or f"Диалог с Каем {date.today().isoformat()}",
            folder=resolved_folder,
            body=body,
            properties={"type": "диалог", "tags": ["kai", "telegram", "диалог"]},
        )

    def save_dream_with_analysis(
        self,
        title: str,
        dream_text: str,
        analysis_markdown: str,
        conversation_context: str,
    ) -> dict:
        folder = self.settings.obsidian_dreams_dir
        analysis = analysis_markdown.strip()
        if analysis.startswith("## Анализ"):
            analysis = analysis.removeprefix("## Анализ").strip()
        body = (
            "## Текст сна\n\n"
            f"{dream_text.strip()}\n\n"
            "## Анализ\n\n"
            f"{analysis}\n\n"
            "## Контекст разговора\n\n"
            f"{conversation_context.strip()}\n\n"
            "## Метаданные\n\n"
            "- Тип: сон\n"
            f"- Папка: {folder}\n"
            "- Создано Каем: да"
        )
        return self.saver.save_markdown(
            title=title.strip() or "Сон",
            folder=folder,
            body=body,
            properties={"type": "сон", "tags": ["kai", "telegram", "сон"]},
        )

    def list_recent(self, folder: str, limit: int = 5) -> list[dict]:
        folder_path = self.vault_path / self.resolve_folder(folder)
        if not folder_path.exists():
            return []
        paths = sorted(folder_path.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        return [{"title": path.stem, "path": str(path)} for path in paths[:limit]]

    def resolve_folder(self, folder: str | None) -> str:
        normalized = (folder or "").strip().lower()
        mapping = {
            "": self.settings.obsidian_inbox_dir,
            "inbox": self.settings.obsidian_inbox_dir,
            "входящие": self.settings.obsidian_inbox_dir,
            "notes": self.settings.obsidian_notes_dir,
            "заметки": self.settings.obsidian_notes_dir,
            "dreams": self.settings.obsidian_dreams_dir,
            "сны": self.settings.obsidian_dreams_dir,
            "tasks": self.settings.obsidian_tasks_dir,
            "задачи": self.settings.obsidian_tasks_dir,
            "observations": self.settings.obsidian_observations_dir,
            "наблюдения": self.settings.obsidian_observations_dir,
            "physics": self.settings.obsidian_physics_dir,
            "физика": self.settings.obsidian_physics_dir,
            "apv": self.settings.obsidian_apv_dir,
            "апв": self.settings.obsidian_apv_dir,
            "patterns": self.settings.obsidian_patterns_dir,
            "паттерны": self.settings.obsidian_patterns_dir,
            "sources": self.settings.obsidian_sources_dir,
            "источники": self.settings.obsidian_sources_dir,
        }
        return mapping.get(normalized, folder or self.settings.obsidian_inbox_dir)

    def _safe_path(self, path: str) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.vault_path / candidate
        resolved_vault = self.vault_path.resolve()
        resolved_candidate = candidate.resolve()
        if resolved_vault not in resolved_candidate.parents and resolved_candidate != resolved_vault:
            raise RuntimeError("Нельзя читать или изменять файл вне Obsidian vault")
        if not resolved_candidate.exists():
            raise FileNotFoundError(str(resolved_candidate))
        return resolved_candidate


def _snippet(content: str, query: str, radius: int = 90) -> str:
    lowered = content.lower()
    index = lowered.find(query)
    if index < 0:
        return content[: radius * 2].strip()
    start = max(index - radius, 0)
    end = min(index + len(query) + radius, len(content))
    return content[start:end].replace("\n", " ").strip()
