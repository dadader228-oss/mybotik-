import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from db import get_session
from user_service import get_or_create_user, get_user_by_telegram_id
from main_kb import main_menu_kb
from helpers import is_admin
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()


WELCOME_TEXT = """
🌑 <b>BOT STORE</b>

Добро пожаловать в магазин разработки Telegram-ботов на заказ.

Здесь вы можете:
• Выбрать готовую услугу из каталога
• Оформить индивидуальный заказ
• Оплатить через Telegram Stars
• Отслеживать статус разработки

Выберите раздел в меню ниже.
"""


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    referral_code = None
    if command.args and command.args.startswith("ref_"):
        referral_code = command.args[4:].upper()

    async with get_session() as session:
        user, created = await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            referral_code=referral_code,
        )

    admin = is_admin(message.from_user.id)
    text = WELCOME_TEXT
    if created and referral_code:
        text += "\n\n✅ Вы зарегистрированы по реферальной ссылке!"

    await message.answer(
        text,
        reply_markup=main_menu_kb(is_admin=admin),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    admin = is_admin(callback.from_user.id)
    await callback.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu_kb(is_admin=admin),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    admin = is_admin(callback.from_user.id)
    await callback.message.edit_text(
        "❌ Действие отменено.\n\n" + WELCOME_TEXT,
        reply_markup=main_menu_kb(is_admin=admin),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    admin = is_admin(message.from_user.id)
    await message.answer(
        "❌ Текущее действие отменено.",
        reply_markup=main_menu_kb(is_admin=admin),
    )


@router.message(Command("profile"))
@router.callback_query(F.data == "profile")
async def show_profile(event: Message | CallbackQuery):
    user_id = event.from_user.id
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
        if not user:
            text = "Пользователь не найден. Нажмите /start"
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                await event.answer(text)
            return

        text = (
            f"👤 <b>Профиль</b>\n\n"
            f"ID: <code>{user.telegram_id}</code>\n"
            f"Имя: {user.first_name or '—'}\n"
            f"Username: @{user.username or '—'}\n"
            f"Баланс бонусов: <b>{user.balance:.0f} ₽</b>\n"
            f"Реферальный код: <code>{user.referral_code}</code>\n"
            f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y') if user.created_at else '—'}\n"
        )

    kb = main_menu_kb(is_admin=is_admin(user_id))
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("terms"))
async def cmd_terms(message: Message):
    text = (
        "📜 <b>Условия BOT STORE</b>\n\n"
        "1. Все услуги оплачиваются исключительно Telegram Stars (XTR).\n"
        "2. Бонусный баланс — информационный, не является платёжным средством.\n"
        "3. Сроки разработки указаны ориентировочно и зависят от сложности.\n"
        "4. После оплаты заказ принимается в работу.\n"
        "5. Возврат Stars возможен по решению администратора через refundStarPayment.\n"
        "6. Один пользователь — один отзыв на заказ.\n"
        "7. Администрация оставляет за собой право отказать в обслуживании.\n\n"
        "По вопросам оплаты: /paysupport"
    )
    await message.answer(text, parse_mode="HTML")
