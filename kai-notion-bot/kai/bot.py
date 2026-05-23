from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from kai.classifier import make_draft
from kai.config import load_settings
from kai.consent import decision_keyboard
from kai.notion_client import NotionSaver
from kai.prompts import build_confirmation_text
from kai.schemas import DraftStatus
from kai.storage import DraftStorage


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
storage = DraftStorage(str(BASE_DIR / "data" / "kai.sqlite"))
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer("Привет! Я Кай. Отправь текст, и я предложу сохранить его в Notion.")


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    if not message.text or not message.from_user:
        return
    draft = make_draft(message.from_user.id, message.chat.id, message.text)
    draft = storage.create_draft(draft)
    await message.answer(build_confirmation_text(draft), reply_markup=decision_keyboard(draft.id or 0))


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
    await callback.message.answer("Сохранено в Notion ✅")
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
