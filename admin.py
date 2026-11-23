import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy import select, func

from db import get_session
from models import User, Order, Payment, Service, Category
from stats_service import get_stats
from order_service import (
    get_order_by_number, update_order_status, set_custom_order_price, status_label,
)
from catalog_service import get_categories, get_all_services, create_service, get_service
from promo_service import create_promo, get_all_promos
from support_service import get_open_tickets, get_ticket_by_number, add_message
from review_service import get_pending_reviews, moderate_review
from user_service import get_user_by_telegram_id, change_balance
from payment_service import get_payment_by_charge_id, mark_refunded
from admin_kb import (
    admin_panel_kb, admin_back_kb, stats_period_kb,
    order_status_kb, confirm_broadcast_kb,
)
from main_kb import cancel_kb, main_menu_kb
from helpers import admin_required, is_admin, truncate
from states import AdminStates
from config import ADMIN_IDS, STARS_CURRENCY

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("admin"))
@router.callback_query(F.data == "admin_panel")
@admin_required
async def admin_panel(event: Message | CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    text = "⚙️ <b>Админ-панель BOT STORE</b>\n\nВыберите раздел:"
    kb = admin_panel_kb()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


# ─── Statistics ───────────────────────────────────────────

@router.callback_query(F.data == "admin:stats")
@admin_required
async def admin_stats_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📊 Выберите период:",
        reply_markup=stats_period_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:stats:"))
@admin_required
async def admin_stats(callback: CallbackQuery):
    period = callback.data.split(":")[-1]
    async with get_session() as session:
        stats = await get_stats(session, period)

    period_labels = {"day": "День", "week": "Неделя", "month": "Месяц", "all": "Всё время"}
    text = (
        f"📊 <b>Статистика ({period_labels.get(period, period)})</b>\n\n"
        f"👥 Пользователей: {stats['total_users']} (новых: {stats['new_users']})\n"
        f"📦 Заказов всего: {stats['total_orders']}\n"
        f"✅ Оплаченных: {stats['paid_orders']}\n"
        f"🎉 Завершённых: {stats['completed_orders']}\n"
        f"🔧 Активных: {stats['active_orders']}\n"
        f"⭐ Выручка: {stats['revenue_stars']} Stars\n"
        f"📈 Средний чек: {stats['avg_check']:.0f} Stars\n"
        f"👥 Рефералов: {stats['total_referrals']}\n"
        f"🆘 Обращений: {stats['tickets']}\n"
    )
    if stats["popular_services"]:
        text += "\n<b>Популярные услуги:</b>\n"
        for name, cnt in stats["popular_services"]:
            text += f"• {name}: {cnt}\n"

    await callback.message.edit_text(text, reply_markup=stats_period_kb(), parse_mode="HTML")
    await callback.answer()


# ─── Orders ───────────────────────────────────────────────

@router.callback_query(F.data == "admin:orders")
@admin_required
async def admin_orders(callback: CallbackQuery):
    async with get_session() as session:
        result = await session.execute(
            select(Order).order_by(Order.created_at.desc()).limit(20)
        )
        orders = result.scalars().all()

    builder = InlineKeyboardBuilder()
    text = "📦 <b>Последние заказы</b>\n\n"
    for o in orders:
        text += f"• <code>{o.order_number}</code> {status_label(o.status)}\n"
        builder.row(
            InlineKeyboardButton(
                text=f"{o.order_number} · {o.status}",
                callback_data=f"admin:order:{o.order_number}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:search_order"))
    builder.row(InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel"))
    await callback.message.edit_text(text[:4000], reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:order:"))
@admin_required
async def admin_order_detail(callback: CallbackQuery):
    number = callback.data.split(":")[-1]
    async with get_session() as session:
        order = await get_order_by_number(session, number)
        if not order:
            await callback.answer("Не найден", show_alert=True)
            return
        user = order.user
        text = (
            f"📦 <b>{order.order_number}</b>\n\n"
            f"Статус: {status_label(order.status)}\n"
            f"Клиент: {user.telegram_id} (@{user.username or '—'})\n"
            f"Название: {order.title}\n"
            f"Цена: {order.price_stars or '—'} ⭐\n"
            f"Кастом: {'да' if order.is_custom else 'нет'}\n"
            f"Создан: {order.created_at.strftime('%d.%m.%Y %H:%M') if order.created_at else '—'}\n"
        )
        if order.description:
            text += f"\nОписание:\n{truncate(order.description, 400)}\n"
        if order.admin_comment:
            text += f"\nКомментарий: {order.admin_comment}\n"

    await callback.message.edit_text(
        text,
        reply_markup=order_status_kb(number),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:set_status:"))
@admin_required
async def admin_set_status(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    number, new_status = parts[2], parts[3]
    async with get_session() as session:
        order = await get_order_by_number(session, number)
        if not order:
            await callback.answer("Не найден", show_alert=True)
            return
        old = order.status
        await update_order_status(session, order, new_status)
        user_tg = order.user.telegram_id

    await callback.answer(f"Статус: {new_status}")
    try:
        await bot.send_message(
            user_tg,
            f"📦 Статус заказа <code>{number}</code> изменён:\n"
            f"{status_label(old)} → {status_label(new_status)}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Offer review if ready
    if new_status == "ready":
        try:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton
            kb = InlineKeyboardBuilder()
            for i in range(1, 6):
                kb.add(InlineKeyboardButton(text=f"{i}⭐", callback_data=f"review:{number}:{i}"))
            kb.adjust(5)
            await bot.send_message(
                user_tg,
                f"🎉 Заказ <code>{number}</code> готов!\nОцените работу:",
                reply_markup=kb.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass

    await admin_order_detail(callback)


@router.callback_query(F.data.startswith("admin:set_price:"))
@admin_required
async def admin_set_price_start(callback: CallbackQuery, state: FSMContext):
    number = callback.data.split(":")[-1]
    await state.set_state(AdminStates.set_price)
    await state.update_data(order_number=number)
    await callback.message.edit_text(
        f"Введите цену в Stars для заказа {number}:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.set_price)
@admin_required
async def admin_set_price_process(message: Message, state: FSMContext, bot: Bot):
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое положительное число.")
        return

    data = await state.get_data()
    number = data.get("order_number")
    await state.clear()

    async with get_session() as session:
        order = await get_order_by_number(session, number)
        if not order:
            await message.answer("Заказ не найден")
            return
        await set_custom_order_price(session, order, price)
        user_tg = order.user.telegram_id

    await message.answer(f"Цена {price} ⭐ назначена для {number}.", reply_markup=admin_panel_kb())
    try:
        from catalog_kb import order_actions_kb
        await bot.send_message(
            user_tg,
            f"💰 Для заказа <code>{number}</code> назначена цена: <b>{price} ⭐</b>\n\n"
            f"Вы можете принять и оплатить.",
            reply_markup=order_actions_kb(number, can_pay=True),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Notify user price: {e}")


@router.callback_query(F.data.startswith("admin:msg_user:"))
@admin_required
async def admin_msg_user_start(callback: CallbackQuery, state: FSMContext):
    number = callback.data.split(":")[-1]
    await state.set_state(AdminStates.message_user)
    await state.update_data(order_number=number)
    await callback.message.edit_text("Введите сообщение клиенту:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(AdminStates.message_user)
@admin_required
async def admin_msg_user_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    number = data.get("order_number")
    await state.clear()
    async with get_session() as session:
        order = await get_order_by_number(session, number)
        if not order:
            await message.answer("Заказ не найден")
            return
        user_tg = order.user.telegram_id
    try:
        await bot.send_message(
            user_tg,
            f"💬 Сообщение по заказу <code>{number}</code>:\n\n{message.text}",
            parse_mode="HTML",
        )
        await message.answer("Отправлено.", reply_markup=admin_panel_kb())
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.callback_query(F.data.startswith("admin:refund:"))
@admin_required
async def admin_refund(callback: CallbackQuery, bot: Bot):
    number = callback.data.split(":")[-1]
    async with get_session() as session:
        order = await get_order_by_number(session, number)
        if not order:
            await callback.answer("Не найден", show_alert=True)
            return
        result = await session.execute(
            select(Payment).where(
                Payment.order_id == order.id,
                Payment.status == "succeeded",
            )
        )
        payment = result.scalar_one_or_none()
        if not payment or not payment.telegram_payment_charge_id:
            await callback.answer("Нет успешного платежа", show_alert=True)
            return

        try:
            await bot.refund_star_payment(
                user_id=payment.user_telegram_id,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
            )
            await mark_refunded(session, payment)
            await callback.answer("Возврат выполнен", show_alert=True)
            try:
                await bot.send_message(
                    payment.user_telegram_id,
                    f"↩️ По заказу {number} выполнен возврат {payment.amount_stars} Stars.",
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Refund error: {e}")
            await callback.answer(f"Ошибка возврата: {e}", show_alert=True)


@router.callback_query(F.data == "admin:search_order")
@admin_required
async def admin_search_order(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.search_order)
    await callback.message.edit_text("Введите номер заказа:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(AdminStates.search_order)
@admin_required
async def admin_search_order_process(message: Message, state: FSMContext):
    number = message.text.strip().upper()
    await state.clear()
    async with get_session() as session:
        order = await get_order_by_number(session, number)
    if not order:
        await message.answer("Не найден.", reply_markup=admin_panel_kb())
        return
    # Reuse detail
    from aiogram.types import CallbackQuery as CQ
    # Just show text
    await message.answer(
        f"Найден: {order.order_number} — {status_label(order.status)}\n"
        f"Используйте кнопки в списке заказов.",
        reply_markup=order_status_kb(order.order_number),
    )


# ─── Catalog admin ────────────────────────────────────────

@router.callback_query(F.data == "admin:catalog")
@admin_required
async def admin_catalog(callback: CallbackQuery):
    async with get_session() as session:
        services = await get_all_services(session)

    builder = InlineKeyboardBuilder()
    text = "🛒 <b>Каталог (админ)</b>\n\n"
    for s in services:
        avail = "✅" if s.is_available else "❌"
        text += f"{avail} {s.name} — {s.price_stars}⭐\n"
        builder.row(
            InlineKeyboardButton(text=f"{'✅' if s.is_available else '❌'} {s.name}", callback_data=f"admin:svc:{s.id}")
        )
    builder.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data="admin:add_service"))
    builder.row(InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel"))
    await callback.message.edit_text(text[:4000], reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:add_service")
@admin_required
async def admin_add_service_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_service_name)
    await callback.message.edit_text("Название услуги:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(AdminStates.add_service_name)
@admin_required
async def admin_add_svc_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip()[:255])
    await state.set_state(AdminStates.add_service_desc)
    await message.answer("Описание:")


@router.message(AdminStates.add_service_desc)
@admin_required
async def admin_add_svc_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip()[:2000])
    await state.set_state(AdminStates.add_service_price)
    await message.answer("Цена в Stars (целое число):")


@router.message(AdminStates.add_service_price)
@admin_required
async def admin_add_svc_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("Число!")
        return
    await state.update_data(price_stars=price)
    await state.set_state(AdminStates.add_service_days)
    await message.answer("Срок разработки (дней):")


@router.message(AdminStates.add_service_days)
@admin_required
async def admin_add_svc_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("Число!")
        return
    await state.update_data(development_days=days)
    await state.set_state(AdminStates.add_service_features)
    await message.answer("Возможности (через ; или с новой строки):")


@router.message(AdminStates.add_service_features)
@admin_required
async def admin_add_svc_features(message: Message, state: FSMContext):
    await state.update_data(features=message.text.strip()[:2000])
    async with get_session() as session:
        cats = await get_categories(session, active_only=False)
    builder = InlineKeyboardBuilder()
    for c in cats:
        builder.row(InlineKeyboardButton(text=c.name, callback_data=f"admin:svc_cat:{c.id}"))
    await state.set_state(AdminStates.add_service_category)
    await message.answer("Выберите категорию:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("admin:svc_cat:"), AdminStates.add_service_category)
@admin_required
async def admin_add_svc_cat(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[-1])
    await state.update_data(category_id=cat_id)
    await state.set_state(AdminStates.add_service_photo)
    await callback.message.edit_text(
        "Отправьте фото услуги (или /skip):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.add_service_photo, F.photo)
@admin_required
async def admin_add_svc_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    await state.clear()
    async with get_session() as session:
        svc = await create_service(
            session,
            category_id=data["category_id"],
            name=data["name"],
            description=data["description"],
            price_stars=data["price_stars"],
            development_days=data["development_days"],
            features=data.get("features"),
            photo_file_id=photo_id,
            is_available=True,
        )
    await message.answer(f"✅ Услуга «{svc.name}» создана (ID {svc.id}).", reply_markup=admin_panel_kb())


@router.message(AdminStates.add_service_photo, F.text == "/skip")
@admin_required
async def admin_add_svc_skip_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    async with get_session() as session:
        svc = await create_service(
            session,
            category_id=data["category_id"],
            name=data["name"],
            description=data["description"],
            price_stars=data["price_stars"],
            development_days=data["development_days"],
            features=data.get("features"),
            is_available=True,
        )
    await message.answer(f"✅ Услуга «{svc.name}» создана (ID {svc.id}).", reply_markup=admin_panel_kb())


@router.callback_query(F.data.startswith("admin:svc:"))
@admin_required
async def admin_svc_detail(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        svc = await get_service(session, svc_id)
        if not svc:
            await callback.answer("Не найдена", show_alert=True)
            return
        # Toggle availability
        svc.is_available = not svc.is_available
        await session.commit()
    await callback.answer(f"Доступность: {svc.is_available}")
    await admin_catalog(callback)


# ─── Promos ───────────────────────────────────────────────

@router.callback_query(F.data == "admin:promos")
@admin_required
async def admin_promos(callback: CallbackQuery):
    async with get_session() as session:
        promos = await get_all_promos(session)
    text = "🎟 <b>Промокоды</b>\n\n"
    for p in promos[:15]:
        status = "✅" if p.is_active else "❌"
        text += f"{status} <code>{p.code}</code> — {p.bonus_amount:.0f}₽ ({p.current_activations}/{p.max_activations})\n"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать", callback_data="admin:add_promo"))
    builder.row(InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:add_promo")
@admin_required
async def admin_add_promo_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_promo_code)
    await callback.message.edit_text("Код промокода:", reply_markup=cancel_kb())
    await callback.answer()


@router.message(AdminStates.add_promo_code)
@admin_required
async def admin_add_promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip().upper())
    await state.set_state(AdminStates.add_promo_amount)
    await message.answer("Размер бонуса (₽):")


@router.message(AdminStates.add_promo_amount)
@admin_required
async def admin_add_promo_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("Число!")
        return
    await state.update_data(bonus_amount=amount)
    await state.set_state(AdminStates.add_promo_max)
    await message.answer("Макс. активаций:")


@router.message(AdminStates.add_promo_max)
@admin_required
async def admin_add_promo_max(message: Message, state: FSMContext):
    try:
        max_a = int(message.text.strip())
    except ValueError:
        await message.answer("Число!")
        return
    data = await state.get_data()
    await state.clear()
    async with get_session() as session:
        promo = await create_promo(
            session,
            code=data["code"],
            bonus_amount=data["bonus_amount"],
            max_activations=max_a,
            max_per_user=1,
            is_active=True,
        )
    await message.answer(f"✅ Промокод {promo.code} создан.", reply_markup=admin_panel_kb())


# ─── Tickets ──────────────────────────────────────────────

@router.callback_query(F.data == "admin:tickets")
@admin_required
async def admin_tickets(callback: CallbackQuery):
    async with get_session() as session:
        tickets = await get_open_tickets(session)
    builder = InlineKeyboardBuilder()
    text = "🆘 <b>Открытые обращения</b>\n\n"
    for t in tickets[:15]:
        text += f"• {t.ticket_number} — {t.status} (user {t.user.telegram_id})\n"
        builder.row(
            InlineKeyboardButton(
                text=f"{t.ticket_number} · {t.status}",
                callback_data=f"admin:ticket:{t.ticket_number}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel"))
    await callback.message.edit_text(text or "Нет открытых.", reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:ticket:"))
@admin_required
async def admin_ticket_detail(callback: CallbackQuery, state: FSMContext):
    number = callback.data.split(":")[-1]
    async with get_session() as session:
        ticket = await get_ticket_by_number(session, number)
        if not ticket:
            await callback.answer("Не найден", show_alert=True)
            return
        text = f"🎫 {ticket.ticket_number} ({ticket.status})\nUser: {ticket.user.telegram_id}\n\n"
        for msg in sorted(ticket.messages, key=lambda m: m.created_at):
            who = "Admin" if msg.is_admin else "User"
            text += f"[{who}] {msg.text or '[media]'}\n"

    await state.set_state(AdminStates.reply_ticket)
    await state.update_data(ticket_number=number)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ К обращениям", callback_data="admin:tickets"))
    await callback.message.edit_text(
        text[:3500] + "\n\nВведите ответ:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.message(AdminStates.reply_ticket)
@admin_required
async def admin_ticket_reply(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    number = data.get("ticket_number")
    await state.clear()
    async with get_session() as session:
        ticket = await get_ticket_by_number(session, number)
        if not ticket:
            await message.answer("Не найден")
            return
        await add_message(
            session, ticket,
            sender_telegram_id=message.from_user.id,
            is_admin=True,
            text=message.text,
        )
        user_tg = ticket.user.telegram_id

    try:
        await bot.send_message(
            user_tg,
            f"💬 Ответ по обращению <code>{number}</code>:\n\n{message.text}",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await message.answer("Ответ отправлен.", reply_markup=admin_panel_kb())


# ─── Reviews ──────────────────────────────────────────────

@router.callback_query(F.data == "admin:reviews")
@admin_required
async def admin_reviews(callback: CallbackQuery):
    async with get_session() as session:
        reviews = await get_pending_reviews(session)
    builder = InlineKeyboardBuilder()
    text = "⭐ <b>Отзывы на модерации</b>\n\n"
    for r in reviews[:10]:
        text += f"• ID {r.id}: {r.rating}⭐ — {truncate(r.comment or '', 50)}\n"
        builder.row(
            InlineKeyboardButton(text=f"✅ {r.id}", callback_data=f"admin:pub_review:{r.id}"),
            InlineKeyboardButton(text=f"❌ {r.id}", callback_data=f"admin:rej_review:{r.id}"),
        )
    builder.row(InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_panel"))
    await callback.message.edit_text(text or "Нет.", reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:pub_review:"))
@admin_required
async def admin_pub_review(callback: CallbackQuery):
    rid = int(callback.data.split(":")[-1])
    async with get_session() as session:
        from models import Review
        r = await session.get(Review, rid)
        if r:
            await moderate_review(session, r, publish=True)
    await callback.answer("Опубликован")
    await admin_reviews(callback)


@router.callback_query(F.data.startswith("admin:rej_review:"))
@admin_required
async def admin_rej_review(callback: CallbackQuery):
    rid = int(callback.data.split(":")[-1])
    async with get_session() as session:
        from models import Review
        r = await session.get(Review, rid)
        if r:
            await moderate_review(session, r, publish=False)
    await callback.answer("Отклонён")
    await admin_reviews(callback)


# ─── Broadcast ────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
@admin_required
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcast_content)
    await callback.message.edit_text(
        "📢 Отправьте сообщение для рассылки (текст/фото/видео/документ):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.broadcast_content)
@admin_required
async def admin_broadcast_preview(message: Message, state: FSMContext):
    await state.update_data(
        broadcast_text=message.text or message.caption,
        broadcast_photo=message.photo[-1].file_id if message.photo else None,
        broadcast_video=message.video.file_id if message.video else None,
        broadcast_doc=message.document.file_id if message.document else None,
    )
    await state.set_state(AdminStates.broadcast_confirm)
    await message.answer(
        "Предпросмотр готов. Отправить всем пользователям?",
        reply_markup=confirm_broadcast_kb(),
    )


@router.callback_query(F.data == "admin:broadcast_confirm", AdminStates.broadcast_confirm)
@admin_required
async def admin_broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text("Рассылка начата...")

    async with get_session() as session:
        result = await session.execute(select(User.telegram_id).where(User.is_blocked == False))
        user_ids = [r[0] for r in result.all()]

    ok, fail = 0, 0
    for uid in user_ids:
        try:
            if data.get("broadcast_photo"):
                await bot.send_photo(uid, data["broadcast_photo"], caption=data.get("broadcast_text"))
            elif data.get("broadcast_video"):
                await bot.send_video(uid, data["broadcast_video"], caption=data.get("broadcast_text"))
            elif data.get("broadcast_doc"):
                await bot.send_document(uid, data["broadcast_doc"], caption=data.get("broadcast_text"))
            else:
                await bot.send_message(uid, data.get("broadcast_text") or "—")
            ok += 1
        except Exception:
            fail += 1

    await callback.message.edit_text(
        f"📢 Рассылка завершена.\nУспешно: {ok}\nОшибок: {fail}",
        reply_markup=admin_panel_kb(),
    )
    await callback.answer()


# ─── Users / Settings / Referrals / Portfolio stubs ───────

@router.callback_query(F.data == "admin:users")
@admin_required
async def admin_users(callback: CallbackQuery):
    async with get_session() as session:
        total = (await session.execute(select(func.count(User.id)))).scalar() or 0
        recent = (await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )).scalars().all()
    text = f"👥 <b>Пользователи</b>\nВсего: {total}\n\nПоследние:\n"
    for u in recent:
        text += f"• {u.telegram_id} @{u.username or '—'} — {u.balance:.0f}₽\n"
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:referrals")
@admin_required
async def admin_referrals(callback: CallbackQuery):
    async with get_session() as session:
        total = (await session.execute(select(func.count()).select_from(
            __import__("database.models", fromlist=["Referral"]).Referral
        ))).scalar() or 0
    text = f"👥 Реферальная система\nВсего рефералов: {total}\nВключена: да"
    await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:portfolio")
@admin_required
async def admin_portfolio(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_portfolio_title)
    await callback.message.edit_text(
        "🖼 Добавление в портфолио.\nВведите название работы (или /cancel):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.add_portfolio_title)
@admin_required
async def admin_pf_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminStates.add_portfolio_desc)
    await message.answer("Описание:")


@router.message(AdminStates.add_portfolio_desc)
@admin_required
async def admin_pf_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminStates.add_portfolio_features)
    await message.answer("Возможности:")


@router.message(AdminStates.add_portfolio_features)
@admin_required
async def admin_pf_features(message: Message, state: FSMContext):
    await state.update_data(features=message.text.strip())
    await state.set_state(AdminStates.add_portfolio_link)
    await message.answer("Ссылка на демо (или —):")


@router.message(AdminStates.add_portfolio_link)
@admin_required
async def admin_pf_link(message: Message, state: FSMContext):
    link = message.text.strip()
    if link == "—":
        link = None
    await state.update_data(demo_link=link)
    await state.set_state(AdminStates.add_portfolio_photo)
    await message.answer("Отправьте фото (или /skip):")


@router.message(AdminStates.add_portfolio_photo, F.photo)
@admin_required
async def admin_pf_photo(message: Message, state: FSMContext):
    import json
    data = await state.get_data()
    await state.clear()
    from portfolio_service import create_portfolio_item
    async with get_session() as session:
        item = await create_portfolio_item(
            session,
            title=data["title"],
            description=data["description"],
            features=data.get("features"),
            demo_link=data.get("demo_link"),
            photo_file_ids=json.dumps([message.photo[-1].file_id]),
            is_active=True,
        )
    await message.answer(f"✅ Работа «{item.title}» добавлена.", reply_markup=admin_panel_kb())


@router.message(AdminStates.add_portfolio_photo, F.text == "/skip")
@admin_required
async def admin_pf_skip(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    from portfolio_service import create_portfolio_item
    async with get_session() as session:
        item = await create_portfolio_item(
            session,
            title=data["title"],
            description=data["description"],
            features=data.get("features"),
            demo_link=data.get("demo_link"),
            is_active=True,
        )
    await message.answer(f"✅ Работа «{item.title}» добавлена.", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:settings")
@admin_required
async def admin_settings(callback: CallbackQuery):
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"Admin IDs: {ADMIN_IDS}\n"
        "Реферальная система: включена\n"
        "Валюта оплаты: XTR (Stars)\n\n"
        "Для изменения ADMIN_IDS и токена отредактируйте .env и перезапустите бота."
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await callback.answer()


from aiogram.fsm.state import State, StatesGroup


class ReviewCommentState(StatesGroup):
    waiting = State()


@router.callback_query(F.data.startswith("review:"))
async def review_rating(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    number, rating = parts[1], int(parts[2])
    await state.set_state(ReviewCommentState.waiting)
    await state.update_data(review_order=number, review_rating=rating)
    await callback.message.edit_text(f"Оценка {rating}⭐. Напишите отзыв или «-»:")
    await callback.answer()


@router.message(ReviewCommentState.waiting)
async def review_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    number = data.get("review_order")
    rating = data.get("review_rating", 5)
    comment = message.text.strip() if message.text and message.text.strip() != "-" else None

    async with get_session() as session:
        order = await get_order_by_number(session, number)
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not order or not user:
            await message.answer("Ошибка")
            return
        from review_service import create_review
        review, msg = await create_review(session, order, user.id, rating, comment)

    await message.answer(msg, reply_markup=main_menu_kb(is_admin=is_admin(message.from_user.id)))
