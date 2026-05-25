from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, Message

from kai.classifier import make_draft
from kai.config import load_settings
from kai.consent import decision_keyboard
from kai.intents import Intent, detect_intent
from kai.notion_client import NotionSaver
from kai.prompts import build_confirmation_text
from kai.schemas import DraftStatus
from kai.storage import DraftStorage


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
storage = DraftStorage(str(BASE_DIR / "data" / "kai.sqlite"))
dp = Dispatcher()


def build_intent_reply(intent: Intent) -> str:
    if intent == Intent.SMALLTALK:
        return "Я тут ✨ Готова помочь, когда захочешь что-то сохранить."
    if intent == Intent.DELETE_REQUEST:
        return (
            "Я пока не умею удалять записи из Notion автоматически. "
            "Но могу научиться: на следующем шаге добавим удаление последней сохранённой записи. "
            "Сейчас удали её вручную в Notion, если она уже сохранена."
        )
    if intent == Intent.STATUS_REQUEST:
        return "Я на связи. Пока умею принимать текст, предлагать сохранение в Notion и ждать подтверждения."
    if intent == Intent.HELP_REQUEST:
        return (
            "Я Кай. Могу предложить сохранить задачу, мысль, сон, наблюдение, "
            "физическую идею или APV-эксперимент в Notion. Пока сохраняю только после кнопки."
        )
    if intent == Intent.CANCEL_REQUEST:
        return "Окей, не сохраняю."
    return ""


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    if not message.text or not message.from_user:
        return

    intent = detect_intent(message.text)
    if intent != Intent.SAVE_CANDIDATE:
        await message.answer(build_intent_reply(intent))
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
