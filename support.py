import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from db import get_session
from user_service import get_user_by_telegram_id
from support_service import (
    create_ticket, get_user_tickets, get_ticket_by_number,
    add_message, close_ticket,
)
from main_kb import cancel_kb, back_to_menu_kb, main_menu_kb
from states import SupportStates
from helpers import is_admin, truncate
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("support"))
@router.callback_query(F.data == "support")
async def support_menu(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✍️ Новое обращение", callback_data="support_new"))
    builder.row(InlineKeyboardButton(text="📋 Мои обращения", callback_data="support_list"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    text = (
        "🆘 <b>Поддержка</b>\n\n"
        "Создайте обращение или просмотрите историю.\n"
        "По вопросам оплаты и возвратов Stars: /paysupport"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(Command("paysupport"))
async def paysupport(message: Message, state: FSMContext):
    await state.set_state(SupportStates.waiting_text)
    await state.update_data(is_pay=True)
    await message.answer(
        "💳 <b>Вопросы по оплате и возвратам Stars</b>\n\n"
        "Опишите проблему (укажите номер заказа и ID платежа, если есть):",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "support_new")
async def support_new(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_text)
    await state.update_data(is_pay=False)
    await callback.message.edit_text(
        "✍️ Опишите ваш вопрос или проблему.\n"
        "Можно прикрепить фото/видео/документ.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(SupportStates.waiting_text)
async def support_text(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    is_pay = data.get("is_pay", False)
    text = message.text or message.caption or ""
    media_type = None
    media_file_id = None
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id

    if not text and not media_file_id:
        await message.answer("Отправьте текст или медиа.")
        return

    async with get_session() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("Сначала /start")
            await state.clear()
            return

        subject = "Оплата / Возврат Stars" if is_pay else "Обращение"
        ticket = await create_ticket(
            session,
            user=user,
            text=text or "[медиа]",
            subject=subject,
            media_type=media_type,
            media_file_id=media_file_id,
        )

    await state.clear()
    await message.answer(
        f"✅ Обращение <code>{ticket.ticket_number}</code> создано.\n"
        f"Мы ответим как можно скорее.",
        reply_markup=main_menu_kb(is_admin=is_admin(message.from_user.id)),
        parse_mode="HTML",
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🆘 Новое обращение {ticket.ticket_number}\n"
                f"От: {message.from_user.id}\n"
                f"Тема: {subject}\n"
                f"{truncate(text, 200)}",
            )
        except Exception:
            pass


@router.callback_query(F.data == "support_list")
async def support_list(callback: CallbackQuery):
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("Сначала /start", show_alert=True)
            return
        tickets = await get_user_tickets(session, user.id)

    if not tickets:
        await callback.message.edit_text(
            "У вас нет обращений.",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    text = "📋 <b>Мои обращения</b>\n\n"
    for t in tickets[:10]:
        status_emoji = {"open": "🟡", "answered": "🟢", "closed": "⚪"}.get(t.status, "•")
        text += f"{status_emoji} <code>{t.ticket_number}</code> — {t.status}\n"
        builder.row(
            InlineKeyboardButton(
                text=f"{t.ticket_number} · {t.status}",
                callback_data=f"ticket:{t.ticket_number}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="support"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ticket:"))
async def show_ticket(callback: CallbackQuery):
    number = callback.data.split(":")[1]
    async with get_session() as session:
        ticket = await get_ticket_by_number(session, number)
        if not ticket or ticket.user.telegram_id != callback.from_user.id:
            await callback.answer("Не найдено", show_alert=True)
            return

        text = f"🎫 <b>{ticket.ticket_number}</b> ({ticket.status})\n\n"
        for msg in sorted(ticket.messages, key=lambda m: m.created_at):
            who = "👤 Вы" if not msg.is_admin else "🛠 Поддержка"
            text += f"<b>{who}</b> ({msg.created_at.strftime('%d.%m %H:%M')}):\n"
            if msg.text:
                text += f"{msg.text}\n"
            if msg.media_type:
                text += f"[{msg.media_type}]\n"
            text += "\n"

    builder = InlineKeyboardBuilder()
    if ticket.status != "closed":
        builder.row(InlineKeyboardButton(text="💬 Ответить", callback_data=f"ticket_reply:{number}"))
        builder.row(InlineKeyboardButton(text="🔒 Закрыть", callback_data=f"ticket_close:{number}"))
    builder.row(InlineKeyboardButton(text="◀️ К списку", callback_data="support_list"))
    await callback.message.edit_text(text[:4000], reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ticket_reply:"))
async def ticket_reply_start(callback: CallbackQuery, state: FSMContext):
    number = callback.data.split(":")[1]
    await state.set_state(SupportStates.reply)
    await state.update_data(ticket_number=number)
    await callback.message.edit_text("Введите ответ:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(SupportStates.reply)
async def ticket_reply_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    number = data.get("ticket_number")
    await state.clear()

    async with get_session() as session:
        ticket = await get_ticket_by_number(session, number)
        if not ticket:
            await message.answer("Тикет не найден")
            return
        await add_message(
            session,
            ticket,
            sender_telegram_id=message.from_user.id,
            is_admin=False,
            text=message.text,
        )

    await message.answer(
        "Ответ отправлен.",
        reply_markup=main_menu_kb(is_admin=is_admin(message.from_user.id)),
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"💬 Ответ в тикете {number} от {message.from_user.id}")
        except Exception:
            pass


@router.callback_query(F.data.startswith("ticket_close:"))
async def ticket_close(callback: CallbackQuery):
    number = callback.data.split(":")[1]
    async with get_session() as session:
        ticket = await get_ticket_by_number(session, number)
        if ticket and ticket.user.telegram_id == callback.from_user.id:
            await close_ticket(session, ticket)
    await callback.answer("Закрыто")
    await support_menu(callback, None)
