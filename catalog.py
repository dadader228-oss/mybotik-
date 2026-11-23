import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext

from db import get_session
from catalog_service import get_categories, get_services_by_category, get_service
from user_service import get_user_by_telegram_id
from order_service import create_order_from_service, get_order_by_number, status_label
from payment_service import create_payment, get_payment_by_payload, process_successful_payment
from catalog_kb import categories_kb, services_kb, service_detail_kb, order_actions_kb
from main_kb import main_menu_kb, back_to_menu_kb
from helpers import is_admin, format_price_stars
from config import STARS_CURRENCY

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "catalog")
async def cb_catalog(callback: CallbackQuery):
    async with get_session() as session:
        categories = await get_categories(session)
    if not categories:
        await callback.message.edit_text(
            "Каталог пока пуст.",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    text = "🛒 <b>Каталог услуг</b>\n\nВыберите категорию:"
    await callback.message.edit_text(
        text,
        reply_markup=categories_kb(categories),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        services = await get_services_by_category(session, cat_id)
        from catalog_service import get_category
        category = await get_category(session, cat_id)

    if not services:
        await callback.answer("В этой категории пока нет услуг", show_alert=True)
        return

    cat_name = category.name if category else "Категория"
    emoji = category.emoji if category else "📁"
    text = f"{emoji} <b>{cat_name}</b>\n\nВыберите услугу:"
    await callback.message.edit_text(
        text,
        reply_markup=services_kb(services, cat_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc:"))
async def cb_service(callback: CallbackQuery):
    svc_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        service = await get_service(session, svc_id)

    if not service or not service.is_available:
        await callback.answer("Услуга недоступна", show_alert=True)
        return

    features = service.features or "—"
    if features and "\n" not in features:
        features = features.replace(";", "\n• ").strip()
        if not features.startswith("•"):
            features = "• " + features

    text = (
        f"<b>{service.name}</b>\n\n"
        f"{service.description}\n\n"
        f"💰 Цена: <b>{format_price_stars(service.price_stars)}</b>\n"
        f"⏱ Срок: ~{service.development_days} дн.\n\n"
        f"<b>Возможности:</b>\n{features}"
    )

    if service.photo_file_id:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=service.photo_file_id,
                caption=text,
                reply_markup=service_detail_kb(service.id, service.category_id),
                parse_mode="HTML",
            )
            await callback.answer()
            return
        except Exception as e:
            logger.warning(f"Failed to send photo: {e}")

    await callback.message.edit_text(
        text,
        reply_markup=service_detail_kb(service.id, service.category_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, bot: Bot):
    svc_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        service = await get_service(session, svc_id)
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not service or not user:
            await callback.answer("Ошибка", show_alert=True)
            return

        order = await create_order_from_service(session, user, service)
        payment = await create_payment(
            session, order, callback.from_user.id, service.price_stars
        )

    # Send invoice
    prices = [LabeledPrice(label=service.name, amount=service.price_stars)]
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=service.name[:32],
            description=(service.description[:255] if service.description else service.name),
            payload=payment.invoice_payload,
            provider_token="",  # Empty for Stars
            currency=STARS_CURRENCY,
            prices=prices,
        )
        await callback.answer("Счёт отправлен")
    except Exception as e:
        logger.error(f"Invoice error: {e}")
        await callback.answer(f"Ошибка создания счёта: {e}", show_alert=True)


@router.callback_query(F.data.startswith("pay_order:"))
async def cb_pay_order(callback: CallbackQuery, bot: Bot):
    order_number = callback.data.split(":")[1]
    async with get_session() as session:
        order = await get_order_by_number(session, order_number)
        if not order or order.user.telegram_id != callback.from_user.id:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        if order.status != "pending_payment" or not order.price_stars:
            await callback.answer("Заказ нельзя оплатить", show_alert=True)
            return

        payment = await create_payment(
            session, order, callback.from_user.id, order.price_stars
        )

    prices = [LabeledPrice(label=order.title[:32], amount=order.price_stars)]
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=order.title[:32],
            description=(order.description or order.title)[:255],
            payload=payment.invoice_payload,
            provider_token="",
            currency=STARS_CURRENCY,
            prices=prices,
        )
        await callback.answer("Счёт отправлен")
    except Exception as e:
        logger.error(f"Invoice error: {e}")
        await callback.answer(f"Ошибка: {e}", show_alert=True)


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout: PreCheckoutQuery, bot: Bot):
    async with get_session() as session:
        payment = await get_payment_by_payload(session, pre_checkout.invoice_payload)
        if not payment:
            await bot.answer_pre_checkout_query(pre_checkout.id, ok=False, error_message="Платёж не найден")
            return
        if payment.amount_stars != pre_checkout.total_amount:
            await bot.answer_pre_checkout_query(pre_checkout.id, ok=False, error_message="Неверная сумма")
            return
        if pre_checkout.currency != STARS_CURRENCY:
            await bot.answer_pre_checkout_query(pre_checkout.id, ok=False, error_message="Неверная валюта")
            return
        if payment.user_telegram_id != pre_checkout.from_user.id:
            await bot.answer_pre_checkout_query(pre_checkout.id, ok=False, error_message="Платёж принадлежит другому пользователю")
            return
        if payment.status == "succeeded":
            await bot.answer_pre_checkout_query(pre_checkout.id, ok=False, error_message="Уже оплачено")
            return

    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment_handler(message: Message, bot: Bot):
    sp = message.successful_payment
    async with get_session() as session:
        payment = await get_payment_by_payload(session, sp.invoice_payload)
        if not payment:
            logger.error(f"Payment not found for payload {sp.invoice_payload}")
            await message.answer("Ошибка обработки платежа. Обратитесь в поддержку /paysupport")
            return

        processed = await process_successful_payment(
            session,
            payment,
            telegram_payment_charge_id=sp.telegram_payment_charge_id,
            provider_payment_charge_id=getattr(sp, "provider_payment_charge_id", None),
        )

        from models import Order
        order = await session.get(Order, payment.order_id)

        if processed:
            text = (
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"Заказ: <code>{order.order_number if order else '—'}</code>\n"
                f"Сумма: {sp.total_amount} ⭐\n"
                f"ID платежа: <code>{sp.telegram_payment_charge_id}</code>\n\n"
                f"Заказ принят. Мы свяжемся с вами."
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=main_menu_kb(is_admin=is_admin(message.from_user.id)),
            )

            from config import ADMIN_IDS
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"💰 Новый оплаченный заказ!\n"
                        f"Номер: {order.order_number if order else '?'}\n"
                        f"Пользователь: {message.from_user.id}\n"
                        f"Сумма: {sp.total_amount} ⭐",
                    )
                except Exception:
                    pass
        else:
            await message.answer("Платёж уже был обработан ранее.")
