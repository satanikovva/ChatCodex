from __future__ import annotations

import asyncio
import logging
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
    profile = load_profile(str(BASE_DIR / settings.kai_profile_path))
    profile_context = format_profile_for_prompt(profile)
    memory_context = kmemory.format_for_prompt(limit=20)
    conversation_context = cmemory.format_recent_messages(chat_id=chat_id, limit=settings.kai_conversation_history_limit)

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

    cmemory.add_message(chat_id, "user", message.text)
    await message.answer(decision.reply)
    cmemory.add_message(chat_id, "assistant", decision.reply)

    if decision.should_offer_save:
        mapped_target = TARGET_MAP.get((decision.save_target or "").lower())
        mapped_entry = ENTRY_MAP.get((decision.entry_kind or "").lower())
        if mapped_target and mapped_entry:
            fallback = make_draft(message.from_user.id, message.chat.id, message.text)
            draft = Draft(
                id=None,
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                source_text=decision.text_to_save or message.text,
                title=decision.title or fallback.title,
                entry_kind=mapped_entry,
                notion_target=mapped_target,
                created_date=fallback.created_date,
                status=DraftStatus.PENDING,
                reason=decision.reason,
            )
        else:
            draft = make_draft(message.from_user.id, message.chat.id, decision.text_to_save or message.text)
            draft.reason = decision.reason

        draft = storage.create_draft(draft)
        if _is_dream_draft(draft):
            save_msg = _dream_action_text(draft)
            await message.answer(save_msg, reply_markup=dream_decision_keyboard(draft.id or 0))
        else:
            save_msg = _save_offer_text(draft)
            await message.answer(save_msg, reply_markup=decision_keyboard(draft.id or 0))
        cmemory.add_message(chat_id, "assistant", save_msg)

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
