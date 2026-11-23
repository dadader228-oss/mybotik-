import logging
from functools import wraps
from typing import Callable, Any

from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


def admin_required(handler: Callable) -> Callable:
    @wraps(handler)
    async def wrapper(event: Message | CallbackQuery, *args, **kwargs):
        user_id = event.from_user.id if event.from_user else None
        if not user_id or not is_admin(user_id):
            if isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещён", show_alert=True)
            else:
                await event.answer("⛔ Доступ запрещён. Только для администраторов.")
            return
        return await handler(event, *args, **kwargs)
    return wrapper


def format_price_stars(amount: int) -> str:
    return f"{amount} ⭐"


def format_balance(amount: float) -> str:
    return f"{amount:.0f} ₽"


def safe_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in "._- ").strip()


def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
