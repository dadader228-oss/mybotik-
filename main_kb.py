from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🛒 Каталог услуг", callback_data="catalog"),
        InlineKeyboardButton(text="💰 Мой баланс", callback_data="balance"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders"),
        InlineKeyboardButton(text="✍️ Индивидуальный заказ", callback_data="custom_order"),
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Портфолио", callback_data="portfolio"),
        InlineKeyboardButton(text="🎟 Промокоды", callback_data="promo"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Отзывы", callback_data="reviews"),
        InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral"),
    )
    builder.row(
        InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel"),
        )
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


def confirm_kb(confirm_data: str, cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data),
        InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data),
    )
    return builder.as_markup()
