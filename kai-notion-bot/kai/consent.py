from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def decision_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сохранить", callback_data=f"save:{draft_id}"),
                InlineKeyboardButton(text="Не сохранять", callback_data=f"cancel:{draft_id}"),
            ]
        ]
    )
