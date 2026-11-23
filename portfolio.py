import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from db import get_session
from portfolio_service import get_portfolio, get_portfolio_item, parse_photos
from review_service import get_published_reviews
from main_kb import back_to_menu_kb
from helpers import truncate

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "portfolio")
async def cb_portfolio(callback: CallbackQuery):
    async with get_session() as session:
        items = await get_portfolio(session)

    if not items:
        await callback.message.edit_text(
            "🖼 Портфолио пока пусто.",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    text = "🖼 <b>Портфолио</b>\n\nВыберите работу:"
    for item in items:
        builder.row(
            InlineKeyboardButton(
                text=item.title,
                callback_data=f"pf:{item.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("pf:"))
async def cb_portfolio_item(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    async with get_session() as session:
        item = await get_portfolio_item(session, item_id)

    if not item:
        await callback.answer("Не найдено", show_alert=True)
        return

    features = item.features or "—"
    text = (
        f"<b>{item.title}</b>\n\n"
        f"{item.description}\n\n"
        f"<b>Возможности:</b>\n{features}\n"
    )
    if item.demo_link:
        text += f"\n🔗 <a href=\"{item.demo_link}\">Демо</a>"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Портфолио", callback_data="portfolio"))
    builder.row(InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"))

    photos = parse_photos(item.photo_file_ids)
    if photos:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photos[0],
                caption=text[:1024],
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
            await callback.answer()
            return
        except Exception as e:
            logger.warning(f"Portfolio photo error: {e}")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "reviews")
async def cb_reviews(callback: CallbackQuery):
    async with get_session() as session:
        reviews = await get_published_reviews(session, limit=15)

    if not reviews:
        text = "⭐ Пока нет опубликованных отзывов."
    else:
        text = "⭐ <b>Отзывы клиентов</b>\n\n"
        for r in reviews:
            stars = "⭐" * r.rating
            text += f"{stars}\n"
            if r.comment:
                text += f"{truncate(r.comment, 150)}\n"
            text += "\n"

    await callback.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")
    await callback.answer()
