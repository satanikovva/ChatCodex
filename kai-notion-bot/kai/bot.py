from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message

from kai.classifier import make_draft
from kai.config import load_settings
from kai.consent import decision_keyboard
from kai.llm_client import ask_llm
from kai.notion_client import NotionSaver
from kai.prompts import build_saved_text
from kai.schemas import Draft, DraftStatus, EntryKind, NotionTarget
from kai.storage import DraftStorage


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
storage = DraftStorage(str(BASE_DIR / "data" / "kai.sqlite"))
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


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    if not message.text or not message.from_user:
        return

    decision = ask_llm(message.text)
    await message.answer(decision.reply)

    if not decision.should_offer_save:
        return

    draft: Draft
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
        )
    else:
        draft = make_draft(message.from_user.id, message.chat.id, decision.text_to_save or message.text)

    draft = storage.create_draft(draft)
    await message.answer(
        f"Хочешь, сохраню это в Notion?\nБаза: {draft.notion_target.value}\nНазвание: {draft.title}",
        reply_markup=decision_keyboard(draft.id or 0),
    )


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
        settings = load_settings()
        notion = NotionSaver(settings)
        notion.save_draft(draft)
    except Exception as exc:
        logger.exception("Ошибка сохранения в Notion")
        await callback.message.answer(f"Не удалось сохранить в Notion: {exc}")
        await callback.answer()
        return

    storage.set_status(draft_id, DraftStatus.SAVED)
    await callback.message.answer(build_saved_text(draft))
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
    settings = load_settings()
    bot = Bot(token=settings.telegram_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
