from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from kai.classifier import make_draft
from kai.config import load_settings
from kai.consent import decision_keyboard, dream_decision_keyboard
from kai.conversation import ConversationMemory
from kai.dream_analysis import analyze_dream, format_dream_analysis_for_telegram
from kai.llm_client import ask_llm
from kai.memory import KaiMemory
from kai.obsidian_saver import ObsidianSaver, get_obsidian_folder_label
from kai.notion_reader import NotionReader
from kai.profile import format_profile_for_prompt, load_profile
from kai.save_intent import SaveIntent, detect_save_intent
from kai.schemas import Draft, DraftStatus, EntryKind, NotionTarget
from kai.storage import DraftStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = load_settings()
BASE_DIR = Path(__file__).resolve().parents[1]
storage = DraftStorage(str(BASE_DIR / "data" / "kai.sqlite"))
kmemory = KaiMemory(str(BASE_DIR / settings.kai_memory_db_path))
cmemory = ConversationMemory(str(BASE_DIR / settings.kai_conversation_db_path))
notion_reader = NotionReader(settings)
dp = Dispatcher()

TARGET_MAP = {
    "progress": NotionTarget.PROGRESS,
    "notes": NotionTarget.NOTES,
    "dreams": NotionTarget.DREAMS,
    "observations": NotionTarget.OBSERVATIONS,
    "physics": NotionTarget.PHYSICS,
    "apv": NotionTarget.APV,
}

ENTRY_MAP = {
    "task": EntryKind.TASK,
    "note": EntryKind.NOTE,
    "dream": EntryKind.DREAM,
    "observation": EntryKind.OBSERVATION,
    "physics": EntryKind.PHYSICS,
    "apv": EntryKind.APV,
}


def _is_dream_draft(draft: Draft) -> bool:
    return draft.entry_kind == EntryKind.DREAM or draft.notion_target == NotionTarget.DREAMS


def _dream_action_text(draft: Draft) -> str:
    folder_label = get_obsidian_folder_label(draft, settings)
    return (
        "Что сделать со сном?\n"
        f"Папка: {folder_label}\n"
        f"Название: {draft.title}"
    )


def _save_offer_text(draft: Draft) -> str:
    folder_label = get_obsidian_folder_label(draft, settings)
    return (
        "Хочешь, сохраню это в Obsidian?\n"
        f"Папка: {folder_label}\n"
        f"Название: {draft.title}"
    )


def _analysis_context(chat_id: int) -> tuple[str, str, str]:
    profile = load_profile(str(BASE_DIR / settings.kai_profile_path))
    return (
        format_profile_for_prompt(profile),
        kmemory.format_for_prompt(limit=20),
        cmemory.format_recent_messages(chat_id=chat_id, limit=settings.kai_conversation_history_limit),
    )


async def _send_typing(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")


def _save_draft_to_obsidian(draft: Draft) -> dict:
    obsidian = ObsidianSaver(settings)
    return obsidian.save_draft(draft)


TARGET_FOLDER_MAP = {
    "dreams": lambda: settings.obsidian_dreams_dir,
    "notes": lambda: settings.obsidian_notes_dir,
    "observations": lambda: settings.obsidian_observations_dir,
    "physics": lambda: settings.obsidian_physics_dir,
    "apv": lambda: settings.obsidian_apv_dir,
    "tasks": lambda: settings.obsidian_tasks_dir,
    "patterns": lambda: settings.obsidian_patterns_dir,
    "inbox": lambda: settings.obsidian_inbox_dir,
}


def _folder_for_save_target(target: str | None) -> str:
    getter = TARGET_FOLDER_MAP.get(target or "inbox", TARGET_FOLDER_MAP["inbox"])
    return getter()


def _format_messages(messages: list[dict]) -> str:
    if not messages:
        return "(контекст пуст)"
    return "\n".join(f"{message['role']}: {message['content']}" for message in messages)


def _last_user_message(messages: list[dict]) -> str | None:
    for message in reversed(messages):
        if message["role"] == "user" and message["content"].strip():
            return message["content"].strip()
    return None


def _last_dream_text(messages: list[dict]) -> str | None:
    dream_markers = ("присни", "снилось", "сон", "во сне")
    for message in reversed(messages):
        content = message["content"].strip()
        if message["role"] == "user" and any(marker in content.lower() for marker in dream_markers):
            return content
    return _last_user_message(messages)


def _last_analysis_text(messages: list[dict]) -> str | None:
    for message in reversed(messages):
        content = message["content"].strip()
        lowered = content.lower()
        if message["role"] == "assistant" and ("разбор сна" in lowered or "ядро сна" in lowered or "## анализ" in lowered):
            return content
    return None


def _title_from_text(text: str, fallback: str = "Запись Кая") -> str:
    words = [word.strip('.,!?;:()[]{}«»"') for word in text.split()]
    words = [word for word in words if word]
    if not words:
        return fallback
    return " ".join(words[:7])


def _strip_save_command(text: str) -> str:
    normalized = text.strip()
    for trigger in ("сохрани это", "запиши это", "сохрани", "запиши", "зафиксируй"):
        if normalized.lower().startswith(trigger):
            return normalized[len(trigger):].strip(" :—-\n")
    return normalized


def _is_only_save_routing_text(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    if not normalized:
        return True
    routing_phrases = {
        "это",
        "в obsidian",
        "в обсидиан",
        "в физику",
        "в физика",
        "в апв",
        "в apv",
        "в задачи",
        "в заметки",
        "в сны",
        "в наблюдения",
        "в паттерны",
    }
    return normalized in routing_phrases


def _obsidian_tags(*extra: str) -> list[str]:
    return ["kai", "telegram", *[tag for tag in extra if tag]]


def _build_dream_body(dream_text: str, analysis_markdown: str, context: str, folder: str) -> str:
    analysis = analysis_markdown.strip()
    if analysis.startswith("## Анализ"):
        analysis = analysis.removeprefix("## Анализ").strip()
    return (
        "## Текст сна\n\n"
        f"{dream_text.strip()}\n\n"
        "## Анализ\n\n"
        f"{analysis or 'Анализ пока не создан.'}\n\n"
        "## Контекст разговора\n\n"
        f"{context.strip()}\n\n"
        "## Метаданные\n\n"
        "- Тип: сон\n"
        f"- Папка: {folder}\n"
        "- Создано Каем: да"
    )


def _build_conversation_body(context: str, folder: str) -> str:
    return (
        "## Диалог\n\n"
        f"{context.strip()}\n\n"
        "## Метаданные\n\n"
        "- Тип: диалог\n"
        f"- Папка: {folder}\n"
        "- Создано Каем: да"
    )


def _build_simple_body(content: str, type_label: str, folder: str) -> str:
    return (
        "## Текст\n\n"
        f"{content.strip()}\n\n"
        "## Метаданные\n\n"
        f"- Тип: {type_label}\n"
        f"- Папка: {folder}\n"
        "- Создано Каем: да"
    )


def _type_for_target(target: str | None) -> str:
    return {
        "dreams": "сон",
        "physics": "физика",
        "apv": "апв",
        "tasks": "задача",
        "observations": "наблюдение",
        "patterns": "паттерн",
        "notes": "заметка",
        "inbox": "заметка",
    }.get(target or "inbox", "заметка")


def _is_dream_analysis_request(text: str) -> bool:
    normalized = text.lower()
    return "сон" in normalized and any(word in normalized for word in ("проанализ", "разбери", "разбор"))


async def _send_message_typing(message: Message) -> None:
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")


def _should_use_notion_context(text: str) -> bool:
    t = text.lower()
    triggers = (
        "что я писала про",
        "найди записи про",
        "были ли у меня сны про",
        "что у меня есть по",
        "какие паттерны",
        "что я отмечала",
        "посмотри в notion",
    )
    return any(x in t for x in triggers)


async def _handle_dream_analysis_request(message: Message, profile_context: str, memory_context: str, conversation_context: str, recent_messages: list[dict]) -> bool:
    if not _is_dream_analysis_request(message.text or ""):
        return False
    dream_text = _last_dream_text(recent_messages)
    if not dream_text:
        answer = "Я могу разобрать сон, но сначала пришли само описание сна — без него буду гадать по туману."
        cmemory.add_message(message.chat.id, "user", message.text or "")
        await message.answer(answer)
        cmemory.add_message(message.chat.id, "assistant", answer)
        return True

    cmemory.add_message(message.chat.id, "user", message.text or "")
    await _send_message_typing(message)
    analysis = analyze_dream(
        dream_text,
        profile_context=profile_context,
        memory_context=memory_context,
        conversation_context=conversation_context,
    )
    answer = format_dream_analysis_for_telegram(analysis)
    await message.answer(answer)
    cmemory.add_message(message.chat.id, "assistant", answer)
    cmemory.trim_chat_history(chat_id=message.chat.id, keep_last=80)
    return True


async def _handle_explicit_save(message: Message, intent: SaveIntent, profile_context: str, memory_context: str, conversation_context: str, recent_messages: list[dict]) -> bool:
    if not intent.should_save:
        return False

    cmemory.add_message(message.chat.id, "user", message.text or "")
    await _send_message_typing(message)

    try:
        saved = _save_explicit_content(message.text or "", intent, profile_context, memory_context, conversation_context, recent_messages)
    except Exception as exc:
        logger.exception("Ошибка explicit-save в Obsidian")
        answer = f"Не удалось сохранить в Obsidian: {exc}"
        await message.answer(answer)
        cmemory.add_message(message.chat.id, "assistant", answer)
        return True

    answer = f"Сохранил в Obsidian ✓\nПапка: {saved['folder']}\nФайл: {saved['path']}"
    await message.answer(answer)
    cmemory.add_message(message.chat.id, "assistant", answer)
    cmemory.trim_chat_history(chat_id=message.chat.id, keep_last=80)
    return True


def _save_explicit_content(command_text: str, intent: SaveIntent, profile_context: str, memory_context: str, conversation_context: str, recent_messages: list[dict]) -> dict:
    obsidian = ObsidianSaver(settings)
    context = _format_messages(recent_messages)

    if intent.mode == "recent_conversation":
        folder = _folder_for_save_target(intent.target or "notes")
        title = f"Диалог с Каем {date.today().isoformat()}"
        body = _build_conversation_body(context, folder)
        return obsidian.save_markdown(
            title=title,
            folder=folder,
            body=body,
            properties={"type": "диалог", "tags": _obsidian_tags("диалог")},
        )

    if intent.mode == "dream_with_analysis":
        folder = _folder_for_save_target("dreams")
        dream_text = _last_dream_text(recent_messages) or _strip_save_command(command_text)
        last_analysis = _last_analysis_text(recent_messages)
        if last_analysis:
            analysis_markdown = f"## Анализ\n\n{last_analysis}"
        else:
            analysis = analyze_dream(
                dream_text,
                profile_context=profile_context,
                memory_context=memory_context,
                conversation_context=conversation_context,
            )
            analysis_markdown = analysis.obsidian_markdown
        title = _title_from_text(dream_text, fallback="Сон")
        body = _build_dream_body(dream_text, analysis_markdown, context, folder)
        return obsidian.save_markdown(
            title=title,
            folder=folder,
            body=body,
            properties={"type": "сон", "tags": _obsidian_tags("сон")},
        )

    if intent.mode == "analysis_only":
        folder = _folder_for_save_target(intent.target or "dreams")
        analysis_text = _last_analysis_text(recent_messages) or "Анализ в текущем контексте не найден."
        dream_text = _last_dream_text(recent_messages) or "Связанный сон в текущем контексте не найден."
        body = _build_dream_body(dream_text, f"## Анализ\n\n{analysis_text}", context, folder)
        return obsidian.save_markdown(
            title="Анализ сна",
            folder=folder,
            body=body,
            properties={"type": "сон", "tags": _obsidian_tags("сон", "анализ")},
        )

    folder = _folder_for_save_target(intent.target)
    explicit_content = _strip_save_command(command_text)
    if _is_only_save_routing_text(explicit_content):
        explicit_content = _last_user_message(recent_messages) or command_text
    type_label = _type_for_target(intent.target)
    body = _build_simple_body(explicit_content, type_label, folder)
    return obsidian.save_markdown(
        title=_title_from_text(explicit_content),
        folder=folder,
        body=body,
        properties={"type": type_label, "tags": _obsidian_tags(type_label)},
    )


@dp.message(Command("recent"))
async def recent_cmd(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    target = parts[1].strip().lower() if len(parts) > 1 else "notes"
    pages = notion_reader.get_recent(target=target, limit=5)
    if not pages:
        await message.answer("Ничего не нашёл в этой базе.")
        return
    text = notion_reader.format_pages_for_prompt(pages)
    await message.answer(text[:3800])


@dp.message(Command("find"))
async def find_cmd(message: Message) -> None:
    query = (message.text or "").replace("/find", "", 1).strip()
    if not query:
        await message.answer("Напиши после /find, что искать.")
        return
    pages = notion_reader.search_text(query=query, limit=8)
    notion_context = notion_reader.format_pages_for_prompt(pages)
    profile = load_profile(str(BASE_DIR / settings.kai_profile_path))
    decision = ask_llm(
        f"Кратко перескажи, что найдено по запросу: {query}. Укажи, из каких баз это взято.",
        profile_context=format_profile_for_prompt(profile),
        memory_context=kmemory.format_for_prompt(limit=20),
        conversation_context=cmemory.format_recent_messages(chat_id=message.chat.id, limit=settings.kai_conversation_history_limit),
        notion_context=notion_context,
    )
    await message.answer(decision.reply)


@dp.message(Command("patterns"))
async def patterns_cmd(message: Message) -> None:
    pages = (
        notion_reader.get_recent("notes", 8)
        + notion_reader.get_recent("dreams", 8)
        + notion_reader.get_recent("observations", 8)
    )
    notion_context = notion_reader.format_pages_for_prompt(pages)
    profile = load_profile(str(BASE_DIR / settings.kai_profile_path))
    decision = ask_llm(
        "Найди 1-3 сильных повторяющихся паттерна. Разделяй факты и гипотезы. Начни с фразы: 'Вот что я вижу как возможные паттерны, не как окончательный диагноз.'",
        profile_context=format_profile_for_prompt(profile),
        memory_context=kmemory.format_for_prompt(limit=20),
        conversation_context=cmemory.format_recent_messages(chat_id=message.chat.id, limit=settings.kai_conversation_history_limit),
        notion_context=notion_context,
    )
    await message.answer(decision.reply)


@dp.message(Command("profile"))
async def profile_cmd(message: Message) -> None:
    profile = load_profile(str(BASE_DIR / settings.kai_profile_path))
    topics = ", ".join(profile.get("core_topics", []))
    await message.answer(
        f"Пользователь: {profile.get('user_name', '')}\n"
        f"Помощник: {profile.get('assistant_name', '')}\n"
        f"Темы: {topics}\n"
        f"Политика сохранения: {profile.get('save_policy', '')}"
    )


@dp.message(Command("remember"))
async def remember_cmd(message: Message) -> None:
    text = message.text or ""
    value = text.replace("/remember", "", 1).strip()
    if not value:
        await message.answer("Напиши после /remember, что запомнить.")
        return
    kmemory.add_memory(key="user_fact", value=value, source_text=text)
    await message.answer("Запомнил ✓")


@dp.message(Command("memory"))
async def memory_cmd(message: Message) -> None:
    items = kmemory.list_memories(limit=20)
    if not items:
        await message.answer("Память пока пуста.")
        return
    lines = [f"- {it['key']}: {it['value']}" for it in items]
    await message.answer("Последняя память:\n" + "\n".join(lines))


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    if not message.text or not message.from_user:
        return

    chat_id = message.chat.id
    recent_messages = cmemory.get_recent_messages(chat_id=chat_id, limit=30)
    profile = load_profile(str(BASE_DIR / settings.kai_profile_path))
    profile_context = format_profile_for_prompt(profile)
    memory_context = kmemory.format_for_prompt(limit=20)
    conversation_context = _format_messages(recent_messages[-settings.kai_conversation_history_limit:])

    save_intent = detect_save_intent(message.text)
    if await _handle_explicit_save(message, save_intent, profile_context, memory_context, conversation_context, recent_messages):
        return

    if await _handle_dream_analysis_request(message, profile_context, memory_context, conversation_context, recent_messages):
        return

    notion_context = ""
    if _should_use_notion_context(message.text):
        search_query = message.text
        pages = notion_reader.search_text(query=search_query, limit=8)
        notion_context = notion_reader.format_pages_for_prompt(pages)

    decision = ask_llm(
        message.text,
        profile_context=profile_context,
        memory_context=memory_context,
        conversation_context=conversation_context,
        notion_context=notion_context,
    )

    reply = decision.reply
    if decision.should_offer_save and "сохрани" not in reply.lower():
        reply = f"{reply}\n\nЕсли захочешь, скажи: ‘сохрани это’."

    cmemory.add_message(chat_id, "user", message.text)
    await message.answer(reply)
    cmemory.add_message(chat_id, "assistant", reply)
    cmemory.trim_chat_history(chat_id=chat_id, keep_last=80)


@dp.callback_query(F.data.startswith("save:"))
async def save_draft(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    draft_id = int(callback.data.split(":", maxsplit=1)[1])
    draft = storage.get_draft(draft_id)
    if draft is None:
        await callback.message.answer("Черновик не найден.")
        await callback.answer()
        return
    if draft.status != DraftStatus.PENDING:
        await callback.message.answer("Этот черновик уже обработан.")
        await callback.answer()
        return
    try:
        saved = _save_draft_to_obsidian(draft)
    except Exception as exc:
        logger.exception("Ошибка сохранения в Obsidian")
        await callback.message.answer(f"Не удалось сохранить в Obsidian: {exc}")
        await callback.answer()
        return
    storage.set_status(draft_id, DraftStatus.SAVED)
    await callback.message.answer(f"Сохранено в Obsidian ✓\nПапка: {saved['folder']}\nФайл: {saved['path']}")
    await callback.answer()


@dp.callback_query(F.data.startswith("analyze:"))
async def analyze_draft(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    draft_id = int(callback.data.split(":", maxsplit=1)[1])
    draft = storage.get_draft(draft_id)
    if draft is None:
        await callback.message.answer("Черновик не найден.")
        await callback.answer()
        return
    if not _is_dream_draft(draft):
        await callback.message.answer("Анализ снов доступен только для черновиков сна.")
        await callback.answer()
        return

    await _send_typing(callback)
    profile_context, memory_context, conversation_context = _analysis_context(draft.chat_id)
    analysis = analyze_dream(
        draft.source_text,
        profile_context=profile_context,
        memory_context=memory_context,
        conversation_context=conversation_context,
    )
    answer = format_dream_analysis_for_telegram(analysis)
    await callback.message.answer(answer)
    cmemory.add_message(draft.chat_id, "assistant", answer)
    await callback.answer()


@dp.callback_query(F.data.startswith("save_analyze:"))
async def save_analyzed_draft(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    draft_id = int(callback.data.split(":", maxsplit=1)[1])
    draft = storage.get_draft(draft_id)
    if draft is None:
        await callback.message.answer("Черновик не найден.")
        await callback.answer()
        return
    if draft.status != DraftStatus.PENDING:
        await callback.message.answer("Этот черновик уже обработан.")
        await callback.answer()
        return
    if not _is_dream_draft(draft):
        await callback.message.answer("Сохранение с анализом доступно только для снов.")
        await callback.answer()
        return

    await _send_typing(callback)
    profile_context, memory_context, conversation_context = _analysis_context(draft.chat_id)
    analysis = analyze_dream(
        draft.source_text,
        profile_context=profile_context,
        memory_context=memory_context,
        conversation_context=conversation_context,
    )
    draft.analysis_markdown = analysis.obsidian_markdown
    storage.set_analysis_markdown(draft_id, draft.analysis_markdown)
    try:
        saved = _save_draft_to_obsidian(draft)
    except Exception as exc:
        logger.exception("Ошибка сохранения сна с анализом в Obsidian")
        await callback.message.answer(f"Не удалось сохранить в Obsidian: {exc}")
        await callback.answer()
        return

    storage.set_status(draft_id, DraftStatus.SAVED)
    await callback.message.answer(f"Сохранено в Obsidian ✓\nПапка: {saved['folder']}\nФайл: {saved['path']}")
    await callback.answer()


@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_draft(callback: CallbackQuery) -> None:
    if not callback.data or not callback.message:
        await callback.answer()
        return
    draft_id = int(callback.data.split(":", maxsplit=1)[1])
    draft = storage.get_draft(draft_id)
    if draft is not None and draft.status == DraftStatus.PENDING:
        storage.set_status(draft_id, DraftStatus.CANCELLED)
    await callback.message.answer("Окей, не сохраняю.")
    await callback.answer()


async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
