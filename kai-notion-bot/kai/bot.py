from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from kai.agent import AgentDecision, plan_agent_action
from kai.config import load_settings
from kai.conversation import ConversationMemory
from kai.dream_analysis import analyze_dream, format_dream_analysis_for_telegram
from kai.llm_client import ask_llm
from kai.memory import KaiMemory
from kai.notion_reader import NotionReader
from kai.obsidian_saver import ObsidianSaver
from kai.obsidian_tools import ObsidianTools
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
obsidian_tools = ObsidianTools(settings)
dp = Dispatcher()


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


def _title_from_text(text: str, fallback: str = "Заметка Кая") -> str:
    words = [word.strip('.,!?;:()[]{}«»"') for word in text.split()]
    words = [word for word in words if word]
    if not words:
        return fallback
    return " ".join(words[:7])


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
    return any(trigger in t for trigger in triggers)


def _is_dream_draft(draft: Draft) -> bool:
    return draft.entry_kind == EntryKind.DREAM or draft.notion_target == NotionTarget.DREAMS


async def _send_message_typing(message: Message) -> None:
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")


async def _send_callback_typing(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")


def _analysis_context(chat_id: int) -> tuple[str, str, str]:
    profile = load_profile(str(BASE_DIR / settings.kai_profile_path))
    return (
        format_profile_for_prompt(profile),
        kmemory.format_for_prompt(limit=20),
        cmemory.format_recent_messages(chat_id=chat_id, limit=settings.kai_conversation_history_limit),
    )


def _tool_result_text(tool_name: str, result: Any) -> str:
    if tool_name in {"create_note", "save_conversation", "save_dream_with_analysis"}:
        return f"Готово ✓\nПапка: {result['folder']}\nФайл: {result['path']}"
    if tool_name == "append_note":
        return f"Готово ✓\nДописал в файл: {result['path']}"
    if tool_name in {"search_notes", "list_recent"}:
        if not result:
            return "Ничего не нашёл в Obsidian."
        lines = ["Нашёл в Obsidian:"]
        for item in result:
            snippet = f" — {item['snippet']}" if item.get("snippet") else ""
            lines.append(f"- {item.get('title', 'Без названия')}\n  {item.get('path', '')}{snippet}")
        return "\n".join(lines)[:3800]
    if tool_name == "read_note":
        content = result.get("content", "")
        return f"Прочитал: {result.get('title', 'заметка')}\nФайл: {result.get('path', '')}\n\n{content[:3200]}"
    return f"Готово ✓\n{result}"


def _execute_tool(decision: AgentDecision, user_text: str, recent_messages: list[dict], conversation_context: str, profile_context: str, memory_context: str) -> tuple[str, Any]:
    tool_name = decision.tool_name or ""
    args = decision.tool_args or {}

    if tool_name == "create_note":
        content = str(args.get("content") or _last_user_message(recent_messages) or user_text)
        return tool_name, obsidian_tools.create_note(
            folder=str(args.get("folder") or settings.obsidian_notes_dir),
            title=str(args.get("title") or _title_from_text(content)),
            content=content,
            properties=args.get("properties") if isinstance(args.get("properties"), dict) else None,
        )

    if tool_name == "search_notes":
        folders = args.get("folders") if isinstance(args.get("folders"), list) else None
        return tool_name, obsidian_tools.search_notes(
            query=str(args.get("query") or user_text),
            folders=folders,
            limit=int(args.get("limit") or 10),
        )

    if tool_name == "read_note":
        return tool_name, obsidian_tools.read_note(path=str(args.get("path") or ""))

    if tool_name == "append_note":
        return tool_name, obsidian_tools.append_note(
            path=str(args.get("path") or ""),
            content=str(args.get("content") or user_text),
            heading=str(args["heading"]) if args.get("heading") else None,
        )

    if tool_name == "save_conversation":
        messages = [*recent_messages, {"role": "user", "content": user_text}]
        return tool_name, obsidian_tools.save_conversation(
            title=str(args.get("title") or "Диалог с Каем"),
            messages=messages,
            folder=str(args.get("folder") or settings.obsidian_notes_dir),
        )

    if tool_name == "save_dream_with_analysis":
        dream_text = str(args.get("dream_text") or _last_dream_text(recent_messages) or user_text)
        analysis_markdown = str(args.get("analysis_markdown") or "").strip()
        if not analysis_markdown:
            analysis = analyze_dream(
                dream_text,
                profile_context=profile_context,
                memory_context=memory_context,
                conversation_context=conversation_context,
            )
            analysis_markdown = analysis.obsidian_markdown
        return tool_name, obsidian_tools.save_dream_with_analysis(
            title=str(args.get("title") or _title_from_text(dream_text, fallback="Сон")),
            dream_text=dream_text,
            analysis_markdown=analysis_markdown,
            conversation_context=conversation_context,
        )

    if tool_name == "list_recent":
        return tool_name, obsidian_tools.list_recent(
            folder=str(args.get("folder") or settings.obsidian_notes_dir),
            limit=int(args.get("limit") or 5),
        )

    raise RuntimeError(f"Неизвестный инструмент: {tool_name}")


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

    obsidian_context = ""
    if _should_use_notion_context(message.text):
        pages = notion_reader.search_text(query=message.text, limit=8)
        obsidian_context = notion_reader.format_pages_for_prompt(pages)

    decision = plan_agent_action(
        message.text,
        profile_context=profile_context,
        memory_context=memory_context,
        conversation_context=conversation_context,
        obsidian_context=obsidian_context,
    )

    cmemory.add_message(chat_id, "user", message.text)
    sent_replies: list[str] = []

    if decision.reply:
        await message.answer(decision.reply)
        sent_replies.append(decision.reply)

    if decision.needs_tool:
        if not decision.tool_name or decision.confidence < 0.65:
            fallback = decision.reply or "Я не до конца уверен, какое действие выполнить. Уточни, пожалуйста, что именно сделать в Obsidian."
            if not sent_replies:
                await message.answer(fallback)
                sent_replies.append(fallback)
        else:
            await _send_message_typing(message)
            try:
                tool_name, result = _execute_tool(
                    decision,
                    user_text=message.text,
                    recent_messages=recent_messages,
                    conversation_context=conversation_context,
                    profile_context=profile_context,
                    memory_context=memory_context,
                )
                tool_reply = _tool_result_text(tool_name, result)
            except Exception as exc:
                logger.exception("Ошибка Obsidian tool call")
                tool_reply = f"Не смог выполнить действие в Obsidian: {exc}"
            await message.answer(tool_reply)
            sent_replies.append(tool_reply)

    if not sent_replies:
        fallback = "Я здесь. Дай мне чуть больше контекста — и я нормально разберу, что ты хочешь сделать."
        await message.answer(fallback)
        sent_replies.append(fallback)

    for reply in sent_replies:
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
        saved = ObsidianSaver(settings).save_draft(draft)
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

    await _send_callback_typing(callback)
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

    await _send_callback_typing(callback)
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
        saved = ObsidianSaver(settings).save_draft(draft)
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
