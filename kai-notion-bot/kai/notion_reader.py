from __future__ import annotations

from typing import Any

from notion_client import Client

from kai.config import Settings

DB_META = {
    "progress": ("🧠 Мой прогресс", "notion_progress_db_id"),
    "notes": ("👽 Записи", "notion_notes_db_id"),
    "dreams": ("🌙 Дневник снов", "notion_dreams_db_id"),
    "observations": ("📓 Журнал наблюдений", "notion_observations_db_id"),
    "physics": ("🔬 Физика — Идеи", "notion_physics_db_id"),
    "apv": ("🤾‍♀️ АПВ дневник нейросети", "notion_apv_db_id"),
}


class NotionReader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = Client(auth=settings.notion_token)

    def get_recent(self, target: str, limit: int = 5) -> list[dict]:
        targets = list(DB_META.keys()) if target == "all" else [target]
        pages: list[dict] = []
        for t in targets:
            if t not in DB_META:
                continue
            pages.extend(self._query_recent_for_target(t, limit))
        return pages[:limit] if target == "all" else pages

    def _query_recent_for_target(self, target: str, limit: int) -> list[dict]:
        db_label, db_field = DB_META[target]
        db_id = getattr(self.settings, db_field)
        try:
            resp = self.client.databases.query(
                database_id=db_id,
                page_size=limit,
                sorts=[{"property": "Дата", "direction": "descending"}],
            )
        except Exception:
            resp = self.client.databases.query(database_id=db_id, page_size=limit)
        return [self._normalize_page(db_label, item) for item in resp.get("results", [])]

    def search_text(self, query: str, limit: int = 8) -> list[dict]:
        q = query.strip().lower()
        if not q:
            return []

        collected: list[tuple[int, dict]] = []
        for target in ("notes", "dreams", "observations", "physics", "apv", "progress"):
            for page in self._query_recent_for_target(target, 20):
                score = self._score_page(page, q)
                if score > 0:
                    collected.append((score, page))

        collected.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in collected[:limit]]

    def _score_page(self, page: dict, query: str) -> int:
        score = 0
        if query in (page.get("title") or "").lower():
            score += 3
        if query in (page.get("summary") or "").lower():
            score += 2
        if query in (page.get("properties_text") or "").lower():
            score += 1
        return score

    def _normalize_page(self, db_label: str, page: dict[str, Any]) -> dict:
        props = page.get("properties", {})
        title = self._extract_title(props)
        summary = self._extract_summary(props)
        properties_text = self._properties_to_text(props)
        date_value = self._extract_date(props)
        return {
            "database": db_label,
            "title": title,
            "date": date_value,
            "summary": summary,
            "properties_text": properties_text,
            "url": page.get("url", ""),
        }

    def _extract_title(self, props: dict) -> str:
        for value in props.values():
            if value.get("type") == "title":
                arr = value.get("title", [])
                return "".join(x.get("plain_text", "") for x in arr).strip()
        return "Без названия"

    def _extract_summary(self, props: dict) -> str:
        for value in props.values():
            if value.get("type") == "rich_text":
                arr = value.get("rich_text", [])
                text = "".join(x.get("plain_text", "") for x in arr).strip()
                if text:
                    return text[:400]
        return ""

    def _extract_date(self, props: dict) -> str:
        if "Дата" in props and props["Дата"].get("type") == "date":
            date_obj = props["Дата"].get("date") or {}
            return date_obj.get("start", "")
        for value in props.values():
            if value.get("type") == "date":
                date_obj = value.get("date") or {}
                return date_obj.get("start", "")
        return ""

    def _properties_to_text(self, props: dict) -> str:
        parts: list[str] = []
        for name, value in props.items():
            ptype = value.get("type")
            rendered = self._render_property(value, ptype)
            if rendered:
                parts.append(f"{name}: {rendered}")
        return " | ".join(parts)

    def _render_property(self, value: dict, ptype: str | None) -> str:
        if ptype == "title":
            return "".join(x.get("plain_text", "") for x in value.get("title", [])).strip()
        if ptype == "rich_text":
            return "".join(x.get("plain_text", "") for x in value.get("rich_text", [])).strip()
        if ptype == "select":
            return (value.get("select") or {}).get("name", "")
        if ptype == "status":
            return (value.get("status") or {}).get("name", "")
        if ptype == "multi_select":
            return ", ".join(x.get("name", "") for x in value.get("multi_select", []))
        if ptype == "date":
            return (value.get("date") or {}).get("start", "")
        if ptype == "number":
            n = value.get("number")
            return "" if n is None else str(n)
        if ptype == "checkbox":
            return "true" if value.get("checkbox") else "false"
        if ptype == "url":
            return value.get("url") or ""
        if ptype == "relation":
            return f"relations:{len(value.get('relation', []))}"
        return ""

    def format_pages_for_prompt(self, pages: list[dict]) -> str:
        if not pages:
            return "(ничего не найдено)"
        lines = []
        for p in pages:
            lines.append(
                f"[{p.get('database','')}] {p.get('title','')} | {p.get('date','')} | {p.get('summary','')} | {p.get('properties_text','')}"
            )
        return "\n".join(lines)
