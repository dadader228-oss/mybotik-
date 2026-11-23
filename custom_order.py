import json
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from db import get_session
from user_service import get_user_by_telegram_id
from order_service import create_custom_order
from main_kb import cancel_kb, main_menu_kb, confirm_kb
from states import CustomOrderStates
from helpers import is_admin
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "custom_order")
async def start_custom_order(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CustomOrderStates.title)
    await callback.message.edit_text(
        "✍️ <b>Индивидуальный заказ</b>\n\n"
        "Шаг 1/7. Введите название проекта:",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(CustomOrderStates.title)
async def custom_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip()[:500])
    await state.set_state(CustomOrderStates.description)
    await message.answer(
        "Шаг 2/7. Опишите идею проекта:",
        reply_markup=cancel_kb(),
    )


@router.message(CustomOrderStates.description)
async def custom_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip()[:2000])
    await state.set_state(CustomOrderStates.features)
    await message.answer(
        "Шаг 3/7. Перечислите желаемые функции:",
        reply_markup=cancel_kb(),
    )


@router.message(CustomOrderStates.features)
async def custom_features(message: Message, state: FSMContext):
    await state.update_data(features=message.text.strip()[:2000])
    await state.set_state(CustomOrderStates.budget)
    await message.answer(
        "Шаг 4/7. Ориентировочный бюджет (или «не важно»):",
        reply_markup=cancel_kb(),
    )


@router.message(CustomOrderStates.budget)
async def custom_budget(message: Message, state: FSMContext):
    await state.update_data(budget=message.text.strip()[:128])
    await state.set_state(CustomOrderStates.deadline)
    await message.answer(
        "Шаг 5/7. Желаемый срок (например, «2 недели»):",
        reply_markup=cancel_kb(),
    )


@router.message(CustomOrderStates.deadline)
async def custom_deadline(message: Message, state: FSMContext):
    await state.update_data(deadline=message.text.strip()[:128])
    await state.set_state(CustomOrderStates.extra)
    await message.answer(
        "Шаг 6/7. Дополнительная информация (или «нет»):",
        reply_markup=cancel_kb(),
    )


@router.message(CustomOrderStates.extra)
async def custom_extra(message: Message, state: FSMContext):
    await state.update_data(extra=message.text.strip()[:1000])
    await state.set_state(CustomOrderStates.attachments)
    await message.answer(
        "Шаг 7/7. Прикрепите фото, видео или документы (можно несколько).\n"
        "Когда закончите — отправьте /done",
        reply_markup=cancel_kb(),
    )


@router.message(CustomOrderStates.attachments, F.photo | F.video | F.document)
async def custom_attachments(message: Message, state: FSMContext):
    data = await state.get_data()
    attachments = data.get("attachments", [])
    if message.photo:
        attachments.append({"type": "photo", "file_id": message.photo[-1].file_id})
    elif message.video:
        attachments.append({"type": "video", "file_id": message.video.file_id})
    elif message.document:
        attachments.append({"type": "document", "file_id": message.document.file_id})
    await state.update_data(attachments=attachments)
    await message.answer(f"Файл добавлен ({len(attachments)}). Ещё или /done")


@router.message(CustomOrderStates.attachments, F.text == "/done")
async def custom_done(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(CustomOrderStates.confirm)
    text = (
        f"<b>Проверьте заявку:</b>\n\n"
        f"Название: {data.get('title')}\n"
        f"Описание: {data.get('description')[:200]}...\n"
        f"Функции: {data.get('features')[:150]}...\n"
        f"Бюджет: {data.get('budget')}\n"
        f"Срок: {data.get('deadline')}\n"
        f"Доп.: {data.get('extra')}\n"
        f"Вложений: {len(data.get('attachments', []))}\n\n"
        f"Отправить заявку?"
    )
    await message.answer(text, reply_markup=confirm_kb("custom_confirm"), parse_mode="HTML")


@router.callback_query(F.data == "custom_confirm", CustomOrderStates.confirm)
async def custom_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()

    async with get_session() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("Ошибка", show_alert=True)
            return

        attachments_json = json.dumps(data.get("attachments", []), ensure_ascii=False)
        order = await create_custom_order(
            session,
            user=user,
            title=data.get("title", "Без названия"),
            description=data.get("description"),
            features=data.get("features"),
            budget=data.get("budget"),
            desired_deadline=data.get("deadline"),
            extra_info=data.get("extra"),
            attachments=attachments_json,
        )

    await callback.message.edit_text(
        f"✅ Заявка <code>{order.order_number}</code> создана!\n\n"
        f"Администратор рассмотрит её и предложит стоимость в Stars.",
        reply_markup=main_menu_kb(is_admin=is_admin(callback.from_user.id)),
        parse_mode="HTML",
    )
    await callback.answer()

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📝 Новая индивидуальная заявка!\n"
                f"Номер: <code>{order.order_number}</code>\n"
                f"От: {callback.from_user.id} (@{callback.from_user.username or '—'})\n"
                f"Название: {order.title}\n\n"
                f"Откройте /admin → Заказы",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Notify admin failed: {e}")
