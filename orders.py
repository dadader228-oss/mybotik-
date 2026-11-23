import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from db import get_session
from user_service import get_user_by_telegram_id
from order_service import get_user_orders, get_order_by_number, status_label
from main_kb import main_menu_kb, back_to_menu_kb
from catalog_kb import order_actions_kb
from helpers import is_admin, truncate

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("orders"))
@router.callback_query(F.data == "my_orders")
async def show_orders(event: Message | CallbackQuery):
    user_id = event.from_user.id
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
        if not user:
            text = "Сначала /start"
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                await event.answer(text)
            return

        orders = await get_user_orders(session, user.id)

    if not orders:
        text = "📦 У вас пока нет заказов.\n\nВыберите услугу в каталоге или оформите индивидуальный заказ."
        kb = back_to_menu_kb()
    else:
        text = "📦 <b>Мои заказы</b>\n\n"
        builder = InlineKeyboardBuilder()
        for order in orders[:15]:
            text += (
                f"• <code>{order.order_number}</code> — {status_label(order.status)}\n"
                f"  {truncate(order.title, 40)}\n"
            )
            builder.row(
                InlineKeyboardButton(
                    text=f"{order.order_number} · {status_label(order.status)}",
                    callback_data=f"order:{order.order_number}",
                )
            )
        builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
        kb = builder.as_markup()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("order:"))
async def show_order_detail(callback: CallbackQuery):
    order_number = callback.data.split(":")[1]
    async with get_session() as session:
        order = await get_order_by_number(session, order_number)
        if not order or order.user.telegram_id != callback.from_user.id:
            await callback.answer("Заказ не найден", show_alert=True)
            return

        price = f"{order.price_stars} ⭐" if order.price_stars else "не назначена"
        text = (
            f"📦 <b>Заказ {order.order_number}</b>\n\n"
            f"Название: {order.title}\n"
            f"Статус: {status_label(order.status)}\n"
            f"Цена: {price}\n"
            f"Создан: {order.created_at.strftime('%d.%m.%Y %H:%M') if order.created_at else '—'}\n"
        )
        if order.description:
            text += f"\nОписание:\n{truncate(order.description, 300)}\n"
        if order.admin_comment:
            text += f"\n💬 Комментарий: {order.admin_comment}\n"

        can_pay = order.status == "pending_payment" and order.price_stars is not None

    await callback.message.edit_text(
        text,
        reply_markup=order_actions_kb(order_number, can_pay=can_pay),
        parse_mode="HTML",
    )
    await callback.answer()
