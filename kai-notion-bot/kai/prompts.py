from kai.schemas import Draft


def build_confirmation_text(draft: Draft) -> str:
    return (
        f"Кай понял это как: {draft.entry_kind.value}.\n"
        f"Предлагаю сохранить в: {draft.notion_target.value}.\n"
        f"Название: {draft.title}.\n"
        "Сохранить?"
    )
