from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models import Category, Service


def categories_kb(categories: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        emoji = cat.emoji or "📁"
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} {cat.name}",
                callback_data=f"cat:{cat.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def services_kb(services: list, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for svc in services:
        builder.row(
            InlineKeyboardButton(
                text=f"{svc.name} — {svc.price_stars} ⭐",
                callback_data=f"svc:{svc.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ К категориям", callback_data="catalog"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def service_detail_kb(service_id: int, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Купить за Stars", callback_data=f"buy:{service_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"cat:{category_id}"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def order_actions_kb(order_number: str, can_pay: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_pay:
        builder.row(
            InlineKeyboardButton(text="💳 Оплатить Stars", callback_data=f"pay_order:{order_number}"),
        )
    builder.row(InlineKeyboardButton(text="◀️ Мои заказы", callback_data="my_orders"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()
