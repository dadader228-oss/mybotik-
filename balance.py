import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from db import get_session
from user_service import get_user_by_telegram_id, get_transactions, get_referral_stats
from promo_service import activate_promo
from main_kb import back_to_menu_kb, main_menu_kb
from helpers import is_admin, format_balance
from states import PromoStates
from config import REFERRAL_ENABLED

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "balance")
async def cb_balance(callback: CallbackQuery):
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("Сначала /start", show_alert=True)
            return
        txs = await get_transactions(session, user.id, limit=10)

    text = (
        f"💰 <b>Мой баланс</b>\n\n"
        f"Бонусный баланс: <b>{format_balance(user.balance)}</b>\n\n"
        f"<i>Бонусный баланс информационный и не используется для оплаты услуг. "
        f"Все услуги оплачиваются исключительно Telegram Stars.</i>\n\n"
    )
    if txs:
        text += "<b>Последние операции:</b>\n"
        for tx in txs:
            sign = "+" if tx.amount > 0 else ""
            text += f"• {sign}{tx.amount:.0f} ₽ — {tx.description}\n"
    else:
        text += "История операций пуста."

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="promo"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "promo")
async def cb_promo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PromoStates.waiting_code)
    await callback.message.edit_text(
        "🎟 <b>Промокод</b>\n\nВведите код промокода:",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(PromoStates.waiting_code)
async def process_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("Сначала /start")
            await state.clear()
            return
        ok, msg = await activate_promo(session, user, code)

    await state.clear()
    await message.answer(
        msg,
        reply_markup=main_menu_kb(is_admin=is_admin(message.from_user.id)),
    )


@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery, bot):
    if not REFERRAL_ENABLED:
        await callback.answer("Реферальная система отключена", show_alert=True)
        return

    async with get_session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("Сначала /start", show_alert=True)
            return
        stats = await get_referral_stats(session, user.telegram_id)

    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{user.referral_code}"

    text = (
        f"👥 <b>Пригласить друга</b>\n\n"
        f"Ваша ссылка:\n<code>{link}</code>\n\n"
        f"Приглашено: <b>{stats['total']}</b>\n"
        f"Бонус начислен: <b>{stats['paid']}</b>\n"
        f"Ожидают первого заказа: <b>{stats['pending']}</b>\n"
        f"Всего бонусов: <b>{stats['total_bonus']:.0f} ₽</b>\n\n"
        f"Бонус начисляется после первого оплаченного заказа приглашённого."
    )
    await callback.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    await callback.answer()
